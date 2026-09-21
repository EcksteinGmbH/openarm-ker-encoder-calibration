"""Uncertainty budget for theta_true and for the absolute systematic error of an accepted module, at
station conditions. Review script 2026-09-20. Every component is a HALF-WIDTH in arcsec of a systematic
(angle-dependent) error; 'lin' is the worst-case linear sum, 'rss' the root-sum-square of the half-widths
(what is likely if the contributions have unrelated phases). Sources are given in the review, §5.

    python station_budget.py
"""
import numpy as np

GATE = 0.02 * 3600          # R_MAX: what the gate bounds, relative to theta_true

budgets = {
    "A. as bought, §7.7 not done, bellows coupling": [
        ("reference intrinsic error (rated, UNVERIFIED)", 50),
        ("coupling kinematic transfer error (bellows, 0.1 mm / 0.09 deg)", 40),
        ("per-clamp / mounting-specific error", 0),          # inside the two lines above
        ("reference repeatability + bearing NRRO", 3),
        ("wind-up variation (friction x compliance)", 4),
        ("settle / timing (no criteria defined)", 10),
        ("reference thermal change of error curve", 5),
    ],
    "B. §7.7 as written (encoder-side remount, 8 turns, order 0..7)": [
        ("reference residual: >H20, H8/H16 (optical-like 8\" SDE)", 9),
        ("coupling kinematic transfer error — NOT seen by §7.7", 40),
        ("per-clamp error of the production mounting", 8),
        ("module drift 1 % during the session", 6),
        ("reference repeatability + bearing NRRO", 3),
        ("wind-up variation", 4),
        ("settle / timing (no criteria defined)", 10),
        ("reference thermal change of error curve", 5),
    ],
    "C. recommended: stage-side remount, palindrome+closure, diaphragm coupling, bracketed reads": [
        ("reference residual: >H20 (SDE measured by fine scan), H16", 9),
        ("coupling transfer error residual (now calibrated with R)", 4),
        ("per-clamp error after fold-back of the production mounting", 5),
        ("module drift (cancelled to first order, closure-checked)", 3),
        ("reference repeatability + bearing NRRO", 3),
        ("wind-up variation", 2),
        ("settle / timing (bracket criterion 2\")", 2),
        ("reference thermal change of error curve", 5),
    ],
}
for name, rows in budgets.items():
    h = np.array([r[1] for r in rows], float)
    lin, rss = h.sum(), np.sqrt((h ** 2).sum())
    print(name)
    for label, v in rows:
        print(f"    {label:<66} {v:5.0f}\"")
    print(f"    theta_true:  lin {lin:5.0f}\" ({lin/3600:.4f} deg)   rss {rss:5.0f}\" ({rss/3600:.4f} deg)")
    print(f"    accepted module, absolute, station conditions: gate {GATE:.0f}\" + theta_true -> "
          f"lin {(GATE+lin)/3600:.4f} deg   rss-based {(GATE+rss)/3600:.4f} deg\n")

print("metrology ratio tolerance : reference uncertainty (rule of thumb >= 4:1, ISO 14253-1 guard band otherwise)")
for u in (50, 64, 44, 13, 5):
    print(f"    U(theta_true) = {u:3d}\"  ->  R_MAX/U = {GATE/u:4.1f} : 1 ;  guard-banded R_ACCEPT = R_MAX - U = {(GATE-u)/3600:.4f} deg")

print("\nlab-fixed magnetic field B_ext in the sensor plane -> H1 error of amplitude B_ext/B_magnet (small-angle)")
for Bm in (30e-3, 50e-3):
    for Be, what in ((20e-6, "Earth, horizontal component (mid-Europe)"), (48e-6, "Earth, total"), (100e-6, "stepper / steel stray, assumed")):
        print(f"    B_magnet {Bm*1e3:.0f} mT, B_ext {Be*1e6:4.0f} uT ({what}): {np.degrees(Be/Bm):.4f} deg = {np.degrees(Be/Bm)*3600:5.1f}\"")

print("\nstep-5 raw residual noise floor: sigma/pos = sqrt(5.6^2+1.5^2) = %.1f\"; E[half-range of 256] ~ %.1f\"" %
      (np.hypot(5.625, 1.5), np.hypot(5.625, 1.5) * 2.83))
print("per-harmonic amplitude sigma from one 256-position turn: %.2f\"" % (np.hypot(5.625, 1.5) * np.sqrt(2 / 256)))
print("kit encoder eccentricity: 5 um at r = 15 mm -> %.0f\" ; 10 um -> %.0f\"" % (5e-6 / 15e-3 * 206265, 10e-6 / 15e-3 * 206265))
print("bearing NRRO 0.3 / 1 / 2 um at r = 15 mm, single read head -> %.1f\" / %.1f\" / %.1f\"" %
      tuple(x * 1e-6 / 15e-3 * 206265 for x in (0.3, 1, 2)))
