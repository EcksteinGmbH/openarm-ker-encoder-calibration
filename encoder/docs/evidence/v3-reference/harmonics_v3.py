"""Harmonic-count and fit-domain analysis for spec v3 (replaces v2 nharm.py / domain.py).

Differences from v2, per the 2026-09-19 numerics review:
  * the sensor's intrinsic error may carry harmonics above the 3rd (C.4),
  * the sensor output is quantised to 15 bits before anything sees it (C.5),
  * the fit-domain comparison includes a properly iterated true-domain inversion (B.3),
  * phases are randomised over many draws instead of four hand-picked cases (B.2).
All numbers are residual vs. the true angle, in degrees, max over one revolution.
"""
import numpy as np
rng = np.random.default_rng(20260919)
N = 32768 * 4
tt = np.arange(N) * 360.0 / N                           # true shaft angle, uniform (rotary stage)
ttr = np.deg2rad(tt)
Q = 360.0 / 32768                                       # 15-bit sensor step

def sensor(amps, phs):
    e = sum(a * np.sin((k + 1) * ttr + p) for k, (a, p) in enumerate(zip(amps, phs)))
    return tt + e

def wrap(x): return (x + 180) % 360 - 180

def fit_measured(tm, nh):
    """station: regress (theta_true - theta_meas) on theta_meas; firmware applies it at theta_meas"""
    r = np.deg2rad(tm)
    M = np.column_stack([f(k * r) for k in range(1, nh + 1) for f in (np.sin, np.cos)])
    c, *_ = np.linalg.lstsq(M, wrap(tt - tm), rcond=None)
    return np.abs(wrap(tm + M @ c - tt)).max()

def fit_true_iterated(tm, nh, iters=3):
    """station: regress (theta_meas - theta_true) on theta_true; firmware inverts by fixed-point iteration"""
    M = np.column_stack([f(k * ttr) for k in range(1, nh + 1) for f in (np.sin, np.cos)])
    c, *_ = np.linalg.lstsq(M, wrap(tm - tt), rcond=None)
    g = tm.copy()
    for _ in range(iters):
        gr = np.deg2rad(g)
        Mg = np.column_stack([f(k * gr) for k in range(1, nh + 1) for f in (np.sin, np.cos)])
        g = tm - Mg @ c
    return np.abs(wrap(g - tt)).max()

def quant(tm): return np.floor(tm / Q) * Q + Q / 2    # 15-bit sensor code, reported at bin centre

H1 = {"good": 0.3, "typical": 1.0, "large": 1.5, "worst": 2.5}
profiles = {                                          # intrinsic amplitude of H1..H6 relative to H1
    "H1-3 only":        [1, .5, .2, 0, 0, 0],
    "H4-6 small (2/1/.5%)": [1, .5, .2, .02, .01, .005],
    "H4-6 moderate (5/3/2%)": [1, .5, .2, .05, .03, .02],
}
print("measured-domain fit, max residual (deg), 20 random phase draws each, worst draw reported")
print(f"{'part':<9}{'intrinsic profile':<26}{'quant':<7}" + "".join(f"{'H1-'+str(n):>9}" for n in (3, 4, 5, 6)))
for pname, rel in profiles.items():
    for part, a1 in H1.items():
        for q in (False, True):
            worst = np.zeros(4)
            for _ in range(20):
                ph = rng.uniform(0, 2 * np.pi, 6)
                tm = sensor([a1 * r for r in rel], ph)
                if q: tm = quant(tm)
                worst = np.maximum(worst, [fit_measured(tm, n) for n in (3, 4, 5, 6)])
            print(f"{part:<9}{pname:<26}{'15-bit' if q else 'none':<7}" + "".join(f"{w:9.5f}" for w in worst))
    print()

print("quantisation floor alone (perfect model): max |quant(theta) - theta| =",
      f"{np.abs(quant(tt) - tt).max():.5f} deg")
print()
print("fit domain, 'typical' part, H4-6 small, 15-bit quantised, 20 draws: worst residual (deg)")
print(f"{'harmonics':<10}{'measured-domain 1 pass':>24}{'true-domain 3 iterations':>27}{'firmware evals':>16}")
for nh in (3, 6):
    wm = wt = 0
    for _ in range(20):
        ph = rng.uniform(0, 2 * np.pi, 6)
        tm = quant(sensor([1.0 * r for r in profiles["H4-6 small (2/1/.5%)"]], ph))
        wm = max(wm, fit_measured(tm, nh)); wt = max(wt, fit_true_iterated(tm, nh))
    print(f"{nh:<10}{wm:>24.5f}{wt:>27.5f}{f'{nh} vs {3*nh}':>16}")
