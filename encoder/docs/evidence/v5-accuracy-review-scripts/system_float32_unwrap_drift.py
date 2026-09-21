#!/usr/bin/env python3
"""system_float32_unwrap_drift.py -- accuracy review 2026-09-20 (system budget).

Question: does the unmodified M5's float32 handling preserve the module's 21-bit output?

Bit-faithful float32 model of the M5 angle path:
  RSNexus.cpp:85          raw_deg = (raw / (float)(1<<21)) * 360.0f
  AngleProcessor.h:53     invert: 360 - fmod(raw_deg, 360)
  AngleProcessor.h:59-64  first call: _unwrapped = wrap(raw_deg - jig_offset)
  AngleProcessor.h:68-72  every later call: diff = raw_deg - _last_raw ; wrap ; _unwrapped += diff
  main.cpp:238-241        jig_offset is itself one float32 raw_deg reading
`_unwrapped` is never re-referenced to the absolute reading, so any rounding in `+=` stays.
Reference = the SAME float32 inputs accumulated exactly (float64), so the reported error is the
accumulation error alone, not sensor noise.

Input: 0.05 deg 1-sigma Gaussian noise per reading, 15-bit sensor code, 1 kHz.
Module output mappings:
  'upstream'       (raw15<<6)|(raw15>>9)        spec 1.7, uncalibrated modules
  'calibrated'     (raw15<<6)+Delta             spec 7.1; Delta = 0.6 deg H1 + 0.2 deg H2
  'calibrated_q8'  the same, rounded to a multiple of 8 LSB21 (0.00137 deg) -- proposed fix:
                   raw21*360/2^21 = (raw21/8)*45*2^-15 is then exact in float32 and every
                   value is a multiple of 2^-15 deg, so every add is exact while |angle| < 512
np.cumsum(float32) is a strictly sequential float32 sum (asserted against a Python loop), and the
drift of the worst stationary case was reproduced with an independent scalar loop (review text).
"""
import numpy as np

F = np.float32
RATE = 1000
HOUR = 3600 * RATE
LSB = 2**21 / 360.0


def module_output(raw15, mapping):
    if mapping == "upstream":
        return ((raw15 << 6) | (raw15 >> 9)).astype(np.uint32)
    th = raw15 * (2 * np.pi / 32768.0)
    delta = np.rint(0.6 * LSB * np.sin(th + 0.7) + 0.2 * LSB * np.sin(2 * th + 2.1)).astype(np.int64)
    out = (raw15 << 6) + delta
    if mapping == "calibrated_q8":
        out = ((out + 4) >> 3) << 3
    return (out % (1 << 21)).astype(np.uint32)


def raw_deg32(raw21, invert):
    r = (raw21.astype(F) / F(1 << 21)) * F(360.0)
    if invert:
        r = F(360.0) - np.fmod(r, F(360.0))
    return r


def check_cumsum_is_sequential():
    rng = np.random.default_rng(1)
    d = rng.normal(0, 0.07, 20000).astype(F)
    acc = F(100.0)
    out = np.empty_like(d)
    for i, x in enumerate(d):
        acc = F(acc + x)
        out[i] = acc
    cs = np.cumsum(np.concatenate(([F(100.0)], d)), dtype=F)[1:]
    assert np.array_equal(out, cs), "cumsum is not sequential float32"


def motion_profile(rng, amp):
    f = rng.uniform(0.05, 1.0, 3)
    ph = rng.uniform(0, 2 * np.pi, 3)
    w = np.array([0.6, 0.3, 0.1]) * amp
    return lambda t: sum(w[i] * np.sin(2 * np.pi * f[i] * t + ph[i]) for i in range(3))


def run(sensor_deg, joint_deg, hours, rng, mapping, invert=False, amp=0.0):
    """sensor_deg: magnet angle at the sensor; joint_deg: angle relative to the jig zero."""
    sign = -1.0 if invert else 1.0
    prof = motion_profile(rng, amp)
    jr15 = np.array([int(np.floor(((sensor_deg - sign * joint_deg) % 360.0) / 360.0 * 32768.0))])
    jig = raw_deg32(module_output(jr15, mapping), invert)[0]
    state = last = base = None
    turns = 0.0
    out = {}
    for h in range(hours):
        t = (np.arange(HOUR) + h * HOUR) / RATE
        noisy = sensor_deg + sign * prof(t) + rng.normal(0.0, 0.05, HOUR)
        raw15 = np.floor(noisy / 360.0 * 32768.0).astype(np.int64) % 32768
        r32 = raw_deg32(module_output(raw15, mapping), invert)
        r64 = r32.astype(np.float64)
        if state is None:
            d0 = F(r32[0] - jig)
            if d0 > F(180.0):
                d0 = F(d0 - F(360.0))
            if d0 <= F(-180.0):
                d0 = F(d0 + F(360.0))
            state, last = d0, r32[0]
            base = float(d0) - float(r64[0])
            r32, r64 = r32[1:], r64[1:]
        diffs = np.diff(np.concatenate(([last], r32))).astype(F)
        # AngleProcessor.h:69-70, in float32
        diffs = np.where(diffs > F(180.0), diffs - F(360.0), diffs).astype(F)
        diffs = np.where(diffs < F(-180.0), diffs + F(360.0), diffs).astype(F)
        acc = np.cumsum(np.concatenate(([state], diffs)), dtype=F)[1:]
        # exact reference: same inputs, exact differences, exact +-360 bookkeeping
        d64 = np.diff(np.concatenate(([float(last)], r64)))
        turns += np.cumsum(np.where(d64 > 180.0, -360.0, np.where(d64 < -180.0, 360.0, 0.0)))[-1]
        out[h + 1] = float(acc[-1]) - (float(r64[-1]) + base + turns)
        state, last = acc[-1], r32[-1]
    return out


def main():
    check_cumsum_is_sequential()
    rng = np.random.default_rng(20260920)

    print("A. 8-hour runs, accumulation error of _unwrapped (deg), 3 trials each")
    print("%-16s %-46s %10s %10s %10s" % ("mapping", "case", "1 h", "4 h", "8 h"))
    cases = [("sensor  20, joint 140, stationary", 20.0, 140.0, False, 0.0),
             ("sensor  20, joint 100, stationary", 20.0, 100.0, False, 0.0),
             ("sensor  40, joint  80, moving +-60 deg", 40.0, 80.0, False, 60.0),
             ("sensor 250, joint -135 (ch4 at 0 deg), inverted", 250.0, -135.0, True, 0.0),
             ("sensor   0 (on the 0/360 seam), joint 60", 0.0, 60.0, False, 0.0)]
    for mp in ("upstream", "calibrated", "calibrated_q8"):
        for name, s, j, inv, amp in cases:
            for _ in range(3):
                r = run(s, j, 8, rng, mp, inv, amp)
                print("%-16s %-46s %+10.5f %+10.5f %+10.5f" % (mp, name, r[1], r[4], r[8]))

    print("\nB. 1-hour sweep: sensor angle x joint angle grid (8 x 8), |error| after 1 h (deg)")
    sens = [5.0, 20.0, 50.0, 100.0, 150.0, 200.0, 260.0, 330.0]
    joints = [-150.0, -135.0, -90.0, -40.0, 30.0, 75.0, 110.0, 150.0]
    print("%-16s %-12s %9s %9s %9s %9s %9s" % ("mapping", "motion", "median", "p90", "max",
                                                 ">0.005", ">0.02"))
    for mp in ("upstream", "calibrated", "calibrated_q8"):
        for amp, label in ((0.0, "stationary"), (25.0, "+-25 deg")):
            e = np.array([abs(run(s, j, 1, rng, mp, False, amp)[1]) for s in sens for j in joints])
            print("%-16s %-12s %9.5f %9.5f %9.5f %8d/64 %6d/64" % (
                mp, label, np.median(e), np.percentile(e, 90), e.max(),
                int((e > 0.005).sum()), int((e > 0.02).sum())))

    print("\nfor scale: R_MAX = 0.02 deg; one 21-bit LSB = %.6f deg; q8 rounding <= %.6f deg"
          % (360 / 2**21, 4 * 360 / 2**21))


if __name__ == "__main__":
    main()
