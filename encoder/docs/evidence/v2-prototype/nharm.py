import numpy as np

def fit_measured_domain(tt, tm, nh):
    """Least-squares fit of (theta_true - theta_meas) vs theta_meas, nh harmonics, no DC."""
    tmr = np.deg2rad(tm)
    y = (tt - tm + 180) % 360 - 180
    cols = []
    for k in range(1, nh+1):
        cols += [np.sin(k*tmr), np.cos(k*tmr)]
    M = np.vstack(cols).T
    coef, *_ = np.linalg.lstsq(M, y, rcond=None)
    resid = (tm + M@coef - tt + 180) % 360 - 180
    resid = resid - np.mean(resid)
    return np.abs(resid).max(), coef

cases = [
    ("typical  1.0/0.5/0.2", [1.0, 0.5, 0.2],  [30, 100, 200]),
    ("large    1.5/0.9/0.3", [1.5, 0.9, 0.3],  [0, 90, 180]),
    ("good     0.3/0.15/0.05",[0.3,0.15,0.05], [45, 135, 250]),
    ("worst    2.5/1.2/0.6", [2.5, 1.2, 0.6],  [10, 70, 300]),
]

tt = np.linspace(0, 360, 200001, endpoint=False)
ttr = np.deg2rad(tt)

print(f"{'case':<24} {'raw':>8} " + " ".join(f"{'H1-'+str(n):>9}" for n in (3,4,5,6)))
print("-"*78)
for label, A, phi in cases:
    A = np.array(A, float); ph = np.deg2rad(phi)
    e = sum(A[k]*np.sin((k+1)*ttr + ph[k]) for k in range(3))
    tm = tt + e
    row = [f"{np.abs(e).max():8.4f}"]
    for nh in (3,4,5,6):
        m, _ = fit_measured_domain(tt, tm, nh)
        row.append(f"{m:9.5f}")
    print(f"{label:<24} " + " ".join(row))

print("\nAll values in degrees. Budget for the arithmetic itself is 0.005 deg;")
print("these are MODEL residuals, a separate and larger error term.")

# How big are the higher-harmonic coefficients relative to H1..H3?
print("\nFitted amplitude per harmonic, 'large' case (deg):")
A = np.array([1.5,0.9,0.3]); ph = np.deg2rad([0,90,180])
e = sum(A[k]*np.sin((k+1)*ttr + ph[k]) for k in range(3))
tm = tt + e
_, coef = fit_measured_domain(tt, tm, 6)
for k in range(6):
    amp = np.hypot(coef[2*k], coef[2*k+1])
    print(f"  H{k+1}: {amp:8.5f}   ({amp/0.000172:7.1f} LSB of 21-bit)")
