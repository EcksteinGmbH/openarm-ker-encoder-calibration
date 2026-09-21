#!/usr/bin/env python3
"""system_budget.py -- accuracy review 2026-09-20: end-to-end joint-angle budget, host side.

Everything here is arithmetic on stated assumptions; nothing is measured.  Sources of each
number are in the review text (file:line or spec section).  1-sigma-equivalent terms are
combined by RSS; "95 %" is 2 x RSS.
"""
import numpy as np

R_MAX = 0.02

# ---------------------------------------------------------------- timing model
# encoder/src/main.cpp:342-344 reply from cache, :362-371 read right after the reply
# M5/src/main.cpp:139 timestamp, :141 parse replies of the PREVIOUS trigger, :146 new trigger,
# :255 vTaskDelay(1) -> one loop per 1 ms tick.  Spec 8.1: trigger reaches module 1 / 8 / 16
# at ~20 / 230 / 470 us -> ~30 us per hop.
T_CYCLE = 1000.0            # us
HOP = 30.0                  # us per module
M5_PARSE = 50.0             # us, readPacket + millis before requestPacket (estimate)
TX = 20.0                   # us, 4 bytes at 2 Mbps
SENSOR_DELAY = (80.0, 95.0) # us, spec 2.7 FIR_MD 2, no prediction
T_UPD = 85.3                # us, AVAL register refresh: phase uniform 0..T_UPD


def age_at_m5_timestamp(i):
    """age (us) of module i's angle relative to snapshot.timestamp of the frame that carries it."""
    arrive = M5_PARSE + TX + HOP * (i - 1)      # trigger k reaches module i, after T_k
    sample = arrive + TX + 5.0                   # reply sent, then SSC read starts
    # sampled in cycle k-1, sent in cycle k, parsed and stamped at T_(k+1)
    return 2 * T_CYCLE - sample + np.mean(SENSOR_DELAY) + T_UPD / 2


print("=== 1. Data age relative to the M5 timestamp (us) ===")
for i in (1, 7, 8, 9, 15, 16):
    print("  module %2d : %6.0f us" % (i, age_at_m5_timestamp(i)))
ages = np.array([age_at_m5_timestamp(i) for i in range(1, 17)])
print("  mean %.0f us; spread module 1..16 = %.0f us; within one arm (7 joints) = %.0f us"
      % (ages.mean(), ages.max() - ages.min(), 6 * HOP))
print("  of which caused by reply-from-cache: ~%.0f us; by M5 parse-before-trigger ordering: ~%.0f us"
      % (T_CYCLE - TX - 5, T_CYCLE - (M5_PARSE + TX + HOP * 7.5 + TX)))

SPEEDS = (10.0, 30.0, 60.0, 180.0, 360.0)   # deg/s, assumption (see review)
print("\n=== 2. Angle error = speed x unmodelled time (deg) ===")
print("  %-44s" % "term \\ joint speed (deg/s)" + "".join("%9.0f" % w for w in SPEEDS))
rows = (("total age at M5 timestamp, mean (%.2f ms)" % (ages.mean() / 1000), ages.mean()),
        ("reply-from-cache part only (0.975 ms)", 975.0),
        ("skew, 7 joints of one arm (+-90 us about mean)", 90.0),
        ("skew, module 1 vs 16 (450 us)", 450.0),
        ("sensor delay + AVAL phase (130 us)", 130.0),
        ("residual after host time-alignment (+-50 us)", 50.0))
for name, us in rows:
    print("  %-44s" % name + "".join("%9.4f" % (w * us * 1e-6) for w in SPEEDS))
print("  speed at which the term equals R_MAX = 0.02 deg:")
for name, us in rows:
    print("    %-44s %7.1f deg/s" % (name, R_MAX / (us * 1e-6)))

# ---------------------------------------------------------------- zero noise
print("\n=== 3. Single-reading zero (M5/src/main.cpp:238-241): frozen offset ===")
from math import erf, sqrt
sig = 0.05
for thr in (0.05, 0.10, 0.15):
    p1 = 1 - erf(thr / sig / sqrt(2))
    print("  P(|zero error| > %.2f deg) per joint = %.3f ; at least one of 14 joints = %.3f"
          % (thr, p1, 1 - (1 - p1) ** 14))
rng = np.random.default_rng(1)
z = np.abs(rng.normal(0, sig, (200000, 14))).max(axis=1)
print("  expected worst joint of 14: %.3f deg (median %.3f, 95 %% %.3f)"
      % (z.mean(), np.median(z), np.percentile(z, 95)))

# ---------------------------------------------------------------- budget
def rss(*a):
    return float(np.sqrt(np.sum(np.square(a))))


def sys_rel_zero(half_range, kind):
    """1-sigma-equivalent of a systematic curve seen relative to a single-point zero.
    'sine': one dominant harmonic, RMS = h/sqrt2, x sqrt2 for the zero -> h.
    'resid': broadband residual after the fit, RMS ~ h/2.5, x sqrt2 -> 0.57 h."""
    return half_range if kind == "sine" else half_range * np.sqrt(2) / 2.5


NOISE = 0.05          # spec 2.7, per reading, 1 sigma
ZERO_NOISE = 0.05     # one reading frozen into the jig offset
JIG = 0.10            # ASSUMPTION: mechanical repeatability of the jig pose per joint, 1 sigma
TH = (0.05, 0.20)     # ASSUMPTION: temperature + hysteresis + ageing not removed by a static fit
                      # (spec 2.7 gives no split; upper bound = 1.6 - 0.6 = 1.0 deg)
REF = {"as delivered +-50\"": 0.014, "self-calibrated ~5\"": 0.0014}

print("\n=== 4. Static budget per joint, single received sample, 1-sigma-equivalent (deg) ===")
hdr = "  %-50s %10s %10s" % ("term", "before", "after")
print(hdr)
terms = [
    ("sensor systematic rel. to one-point zero (typ 0.6)", sys_rel_zero(0.6, "sine"), sys_rel_zero(R_MAX, "resid")),
    ("station reference error (as delivered, H1-like)", 0.0, sys_rel_zero(0.014, "sine")),
    ("per-reading noise, unfiltered", NOISE, NOISE),
    ("zero: one noisy reading frozen", ZERO_NOISE, ZERO_NOISE),
    ("zero: jig mechanical (ASSUMED)", JIG, JIG),
    ("temp + hysteresis + ageing (ASSUMED, optimistic)", TH[0], TH[0]),
    ("bit-replication ramp / arithmetic", 0.003, 0.001),
]
for n, b, a in terms:
    print("  %-50s %10.4f %10.4f" % (n, b, a))
b = rss(*[t[1] for t in terms]); a = rss(*[t[2] for t in terms])
print("  %-50s %10.3f %10.3f   ratio %.1fx" % ("RSS", b, a, b / a))
b2 = rss(*[t[1] for t in terms if "jig" not in t[0]]); a2 = rss(*[t[2] for t in terms if "jig" not in t[0]])
print("  %-50s %10.3f %10.3f   ratio %.1fx" % ("RSS without the jig term (relative accuracy)", b2, a2, b2 / a2))
cal_share = (terms[0][2] ** 2) / a ** 2
print("  share of the calibrated residual in the after-variance: %.1f %%" % (100 * cal_share))
print("  datasheet-max part (1.6 deg) before: RSS %.2f deg" % rss(1.6, *[t[1] for t in terms[1:]]))
print("  pessimistic temp/hyst (%.2f): after RSS %.3f deg" % (TH[1], rss(*[t[2] for t in terms[:5]], TH[1])))

print("\n=== 5. Moving: add unmodelled age (mean %.2f ms) ===" % (ages.mean() / 1000))
print("  %-12s %10s %10s %8s" % ("speed deg/s", "before", "after", "ratio"))
for w in SPEEDS:
    e = w * ages.mean() * 1e-6
    print("  %-12.0f %10.3f %10.3f %8.1fx" % (w, rss(b, e), rss(a, e), rss(b, e) / rss(a, e)))

print("\n=== 6. Knee: after-calibration static RSS vs. gate R_MAX ===")
scen = {
    "as designed (noise .05, zero .05, jig .10, T/H .05)": (NOISE, ZERO_NOISE, JIG, TH[0]),
    "zero-trim + host filter 25 Hz (noise .011, zero .002, jig .10, T/H .05)": (0.011, 0.002, JIG, TH[0]),
    "same, perfect jig (relative accuracy only)": (0.011, 0.002, 0.0, TH[0]),
    "same, perfect jig, T/H 0.02": (0.011, 0.002, 0.0, 0.02),
}
gates = (0.01, 0.02, 0.03, 0.05, 0.10, 0.20)
print("  %-74s" % "scenario \\ R_MAX" + "".join("%8.2f" % g for g in gates))
for name, (n, z0, j, th) in scen.items():
    print("  %-74s" % name + "".join("%8.3f" % rss(sys_rel_zero(g, "resid"), n, z0, j, th) for g in gates))

print("\n=== 7. Noise after filtering: sigma x sqrt(B / 500 Hz) at 1 kHz sampling ===")
for B in (500, 100, 50, 25, 10):
    print("  noise bandwidth %4d Hz : %.4f deg" % (B, NOISE * np.sqrt(B / 500.0)))

print("\n=== 8. Tip-position equivalent of one joint's error (ASSUMED lever arm 0.45 m) ===")
for d in (0.02, 0.05, 0.13, 0.6, 1.6):
    print("  %5.2f deg -> %5.2f mm" % (d, 450 * np.deg2rad(d)))
