"""Does the calibrated base need to be exact (raw15<<6) rather than upstream's bit replication?

Station fits wrap(theta_true - theta_base) on sin/cos(k*theta_s), k=1..6, where theta_s is the
sensor angle raw15*360/32768 and theta_base is what the firmware adds the correction to.
Residual is reported after removing the mean (the M5's zero offset absorbs any constant).
"""
import numpy as np
rng = np.random.default_rng(7)
N = 32768 * 8
tt = np.arange(N) * 360.0 / N
Q = 360.0 / 32768
def wrap(x): return (x + 180) % 360 - 180
rel = [1, .5, .2, .02, .01, .005]
for label, a1 in (("good", 0.3), ("typical", 1.0)):
    w = {"exact raw15<<6": 0.0, "bit replication": 0.0}
    for _ in range(10):
        ph = rng.uniform(0, 2 * np.pi, 6)
        tm = tt + sum(a1 * r * np.sin((k + 1) * np.deg2rad(tt) + p) for k, (r, p) in enumerate(zip(rel, ph)))
        raw15 = np.floor((tm % 360) / Q).astype(np.int64)
        ts = raw15 * Q
        bases = {"exact raw15<<6": ts,
                 "bit replication": ((raw15 << 6) | (raw15 >> 9)) * 360.0 / 2**21}
        M = np.column_stack([f(k * np.deg2rad(ts)) for k in range(1, 7) for f in (np.sin, np.cos)])
        for name, base in bases.items():
            y = wrap(tt - base)
            c, *_ = np.linalg.lstsq(M, y, rcond=None)
            r = wrap(base + M @ c - tt); r -= r.mean()
            w[name] = max(w[name], np.abs(r).max())
    print(f"{label:8s} 6 harmonics, 15-bit, 10 draws: " + "   ".join(f"{k}: {v:.5f} deg" for k, v in w.items()))
