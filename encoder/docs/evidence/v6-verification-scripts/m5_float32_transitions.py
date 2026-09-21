"""v6 verification of D22 (output rounded to a multiple of 8 LSB) against the M5's float32 path.

Model, step by step in float32: M5/src/RSNexus.cpp:85, M5/include/AngleProcessor.h:52-54 (invert), :57-66 (init
against the jig offset), :68-72 (incremental unwrap). Uses the real ker_compensate() (libref.so).

Questions the author's author_s3_check.py does not answer (it is stationary, 3 cells, 1 coefficient set, no invert,
no mapping change):
  Q1  moving joints, the 0/360 seam, the _invert path, several coefficient sets, a full sensor x joint grid
  Q2  compensation suspended/resumed (spec 6.2): the stream switches between the upstream mapping (not a multiple
      of 8) and the rounded calibrated mapping. Rare, and pathological flapping every 16 reads.
  Q3  jig offset that was stored from an UNCALIBRATED reading (not a multiple of 45*2^-15 deg)
  Q4  is 8 really the smallest step? (spec 7.1 says so) -> steps 1, 2, 4, 8

    gcc -O2 -shared -fPIC -o $O/libref.so ../v3-reference/ref_comp.c ../v3-reference/batch.c
    ../../../.venv/bin/python m5_float32_transitions.py $O/libref.so [hours]
"""
import pathlib, sys
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "v3-reference"))
import station_fit as sf  # noqa: E402

f32 = np.float32
LSB = 360.0 / 2 ** 21


def upstream(raw15):
    r = raw15.astype(np.uint32)
    return (r << 6) | (r >> 9)


def m5(u, joint_deg, invert=False, jig_from_upstream_raw15=None):
    """float32 model of the M5. Returns accumulated-minus-exact error at the end, degrees."""
    deg = (u.astype(f32) / f32(1 << 21)) * f32(360.0)                       # RSNexus.cpp:85
    if invert:
        deg = (f32(360.0) - np.fmod(deg, f32(360.0))).astype(f32)           # AngleProcessor.h:52-54
    if jig_from_upstream_raw15 is None:
        # a jig offset on the same grid as the stream: the reading at zeroing, shifted by a whole number of 8-LSB steps
        steps = int(round(joint_deg / (8 * LSB)))
        u_jig = (int(u[0]) - (-steps if invert else steps) * 8) % (1 << 21)
    else:
        u_jig = int(upstream(np.array([jig_from_upstream_raw15], dtype=np.uint16))[0])
    jig = (f32(u_jig) / f32(1 << 21)) * f32(360.0)
    if invert:
        jig = f32(360.0) - np.fmod(jig, f32(360.0))                          # main.cpp:239-240
    delta = f32(deg[0] - jig)                                                # :59-61
    if delta > f32(180):
        delta = f32(delta - f32(360))
    if delta <= f32(-180):
        delta = f32(delta + f32(360))
    diff = (deg[1:] - deg[:-1]).astype(f32)                                  # :68-70
    diff = np.where(diff > f32(180), diff - f32(360), diff).astype(f32)
    diff = np.where(diff < f32(-180), diff + f32(360), diff).astype(f32)
    acc = np.add.accumulate(np.concatenate([[delta], diff]).astype(f32), dtype=f32)   # :71
    ui = u.astype(np.int64)
    d = (np.diff(ui) + (1 << 20)) % (1 << 21) - (1 << 20)
    d0 = ((int(u[0]) - u_jig) + (1 << 20)) % (1 << 21) - (1 << 20)
    sgn = -1 if invert else 1
    exact0 = sgn * d0 * LSB
    if invert and d0 == -(1 << 20):
        exact0 = -exact0
    exact = exact0 + sgn * float(d.sum()) * LSB
    return float(acc[-1]) - exact, float(np.abs(acc).max())


def stream(lib, cal, rng, sensor_deg, n, motion_deg, mapping, suspend=None):
    t = np.arange(n) / 1000.0
    ang = sensor_deg + motion_deg * np.sin(2 * np.pi * 0.2 * t) + rng.normal(0, 0.05, n)
    raw15 = (np.floor((ang % 360) / sf.Q).astype(np.int64) % 32768).astype(np.uint16)
    if mapping == "upstream":
        return upstream(raw15), raw15
    u = sf.compensate(lib, raw15, cal)
    if mapping.startswith("q"):                      # re-round the routine's output to a coarser/finer grid is not possible;
        q = int(mapping[1:])                         # so q1/q2/q4 are built from the routine's 8-LSB output plus a dither-free
        if q != 8:                                   # sub-step: emulate a finer rounding by adding the exact correction back
            th = raw15.astype(np.float64) * 2 * np.pi / 32768
            dlt = sum(cal.amp[k] * np.sin((k + 1) * th + cal.phase[k] * 2 * np.pi / 65536) for k in range(cal.n))
            u = ((raw15.astype(np.int64) << 6) + (np.round(dlt / q) * q).astype(np.int64)) % (1 << 21)
            u = u.astype(np.uint32)
    if suspend is not None:
        u = np.where(suspend, upstream(raw15), u).astype(np.uint32)
    return u, raw15


def random_cal(rng):
    amps = rng.uniform(0.2, 2.5) * np.array([1, rng.uniform(.2, .6), rng.uniform(.05, .3), rng.uniform(0, .15),
                                             rng.uniform(0, .1), rng.uniform(0, .08)])
    ph = rng.uniform(0, 2 * np.pi, 6)
    return sf.to_cal(amps * np.cos(ph), amps * np.sin(ph))


if __name__ == "__main__":
    lib = sf.load(sys.argv[1])
    hours = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    n = int(hours * 3600 * 1000)
    SENS = [3, 20, 50, 100, 150, 200, 260, 300, 359.99]
    JOINT = [-170, -135, -90, -40, 30, 75, 110, 129, 170]
    rng = np.random.default_rng(2026)
    cals = [random_cal(rng) for _ in range(5)]
    assert all((sf.compensate(lib, np.arange(32768, dtype=np.uint16), c) % 8 == 0).all() for c in cals), "output not a multiple of 8"
    print(f"ker_compensate() output is a multiple of 8 for all 32768 codes x {len(cals)} coefficient sets")
    print(f"{hours} h at 1 kHz per cell; grid {len(SENS)} sensor angles x {len(JOINT)} joint angles; error = float32 accumulator minus exact, degrees")

    def grid(label, mapping, motion, invert=False, suspend_fn=None, jig_up=False):
        worst, nz, cells = 0.0, 0, 0
        for i, s in enumerate(SENS):
            for j, jd in enumerate(JOINT):
                cal = cals[(i + j) % len(cals)]
                sus = suspend_fn(n) if suspend_fn else None
                u, raw15 = stream(lib, cal, rng, s, n, motion, mapping, sus)
                e, _ = m5(u, jd, invert, jig_from_upstream_raw15=(int(raw15[0]) - int(jd / sf.Q)) % 32768 if jig_up else None)
                worst = max(worst, abs(e)); nz += abs(e) > 1e-9; cells += 1
        print(f"{label:78s} max |err| {worst:.6f}   cells with err != 0: {nz}/{cells}")

    print("--- Q1/Q4: mapping x motion")
    for mapping in ("upstream", "q1", "q2", "q4", "q8"):
        for motion in (0, 60):
            grid(f"{mapping:9s} motion +-{motion:2d} deg", mapping, motion)
    grid("q8        motion +-60 deg, _invert path", "q8", 60, invert=True)
    grid("upstream  motion +-60 deg, _invert path", "upstream", 60, invert=True)
    print("--- Q2: compensation suspended / resumed (spec 6.2)")
    rare = lambda n: (np.arange(n) % 60000) < 5000                     # 5 s suspended in every minute
    flap = lambda n: ((np.arange(n) // 16) % 2).astype(bool)             # pathological: toggles every 16 reads
    grid("q8 <-> upstream, 5 s suspended per minute, stationary", "q8", 0, suspend_fn=rare)
    grid("q8 <-> upstream, 5 s suspended per minute, moving +-60", "q8", 60, suspend_fn=rare)
    grid("q8 <-> upstream, flapping every 16 reads, stationary", "q8", 0, suspend_fn=flap)
    grid("q8 <-> upstream, flapping every 16 reads, moving +-60", "q8", 60, suspend_fn=flap)
    print("--- Q3: jig offset stored from an uncalibrated (upstream-mapped) reading, stream calibrated")
    grid("q8, jig offset on the upstream grid, stationary", "q8", 0, jig_up=True)
    grid("q8, jig offset on the upstream grid, moving +-60", "q8", 60, jig_up=True)
