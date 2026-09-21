"""What an error in theta_true does to the §7.2 gate and to the coefficients that ship.
Review script, 2026-09-20 (station-metrology reviewer).

Float model of §7.2 (the fixed-point arithmetic, 0.0003 deg realistic, and the noise-dithered 15-bit
quantisation were verified on 2026-09-19 and are not repeated): per position the module returns an
average with sigma = 0.05/sqrt(1024) deg; the station believes theta_ref = theta + X(theta), where X is
the error of theta_true (reference, coupling, ...), IDENTICAL in the fit and validation passes. The part
population is station_sim.py's. 'True' systematic error is the half-range against the real angle theta.

    python station_gate_ref_error.py [parts]
"""
import sys
import numpy as np

AS = 1 / 3600.0
NH, N_FIT, N_VAL = 6, 128, 128
R_MAX = 0.02
R_ACCEPT = 0.95 * R_MAX
SIG = 0.05 / np.sqrt(1024)
GRID = np.arange(4096) * 360.0 / 4096


def wrap(x):
    return (np.asarray(x) + 180.0) % 360.0 - 180.0


def hr(e):
    e = wrap(e - e.flat[0]); return (e.max() - e.min()) / 2


def design(ts, const=True):
    r = np.deg2rad(ts)
    c = [f(k * r) for k in range(1, NH + 1) for f in (np.sin, np.cos)]
    return np.column_stack(([np.ones_like(r)] if const else []) + c)


def harm(x, comps):
    """comps: list of (k, amplitude_arcsec, phase)."""
    r = np.deg2rad(x)
    return sum(a * AS * np.sin(k * r + p) for k, a, p in comps) if comps else np.zeros_like(r)


def population(rng, parts, x_gen):
    fit_pos = np.arange(N_FIT) * 360.0 / N_FIT
    val_pos = (np.arange(N_VAL) + 0.5) * 360.0 / N_VAL
    rows = []
    for _ in range(parts):
        h1 = rng.uniform(0.2, 2.5)
        amps = h1 * np.array([1, rng.uniform(.2, .6), rng.uniform(.05, .3), rng.uniform(0, .15),
                              rng.uniform(0, .10), rng.uniform(0, .08), rng.uniform(0, .03), rng.uniform(0, .02)])
        ph = rng.uniform(0, 2 * np.pi, 8); off = rng.uniform(0, 360)
        sens = lambda t: t + off + sum(a * np.sin((k + 1) * np.deg2rad(t) + p) for k, (a, p) in enumerate(zip(amps, ph)))
        X = x_gen(rng)
        # fit pass
        ts = sens(fit_pos) + rng.normal(0, SIG, N_FIT)
        d = wrap(fit_pos + X(fit_pos) - ts); c = np.rad2deg(np.arctan2(np.sin(np.deg2rad(d)).mean(), np.cos(np.deg2rad(d)).mean()))
        coef, *_ = np.linalg.lstsq(design(ts), wrap(d - c), rcond=None)
        comp = lambda s: s + design(s, const=False) @ coef[1:]
        # validation pass (same X)
        tv = sens(val_pos) + rng.normal(0, SIG, N_VAL)
        stat = hr(val_pos + X(val_pos) - comp(tv))
        true = hr(GRID - comp(sens(GRID)))
        # what the same part would have been with a perfect theta_true (same noise draw)
        d0 = wrap(fit_pos - ts); c0 = np.rad2deg(np.arctan2(np.sin(np.deg2rad(d0)).mean(), np.cos(np.deg2rad(d0)).mean()))
        coef0, *_ = np.linalg.lstsq(design(ts), wrap(d0 - c0), rcond=None)
        true0 = hr(GRID - (sens(GRID) + design(sens(GRID), const=False) @ coef0[1:]))
        rows.append((true, stat, true0, hr(X(GRID))))
    return np.array(rows)


def report(label, r):
    acc = r[:, 1] <= R_ACCEPT
    fa = acc & (r[:, 0] > R_MAX)
    good0 = r[:, 2] < 0.75 * R_MAX                       # parts that a perfect station would surely accept
    print(f"{label:<46} X {np.median(r[:,3])/AS:5.1f}\"  accepted {acc.sum():4d}  false-accept {fa.sum():4d}"
          f"  worst accepted true {r[acc,0].max() if acc.any() else 0:.4f} deg ({(r[acc,0].max() if acc.any() else 0)/AS:5.1f}\")"
          f"  good parts rejected {(good0 & ~acc).sum():4d}/{good0.sum()}"
          f"  median true/ideal of accepted {np.median(r[acc,0]/r[acc,2]) if acc.any() else 0:.2f}")


if __name__ == "__main__":
    parts = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    P = lambda rng: rng.uniform(0, 2 * np.pi)
    cases = [
        ("perfect theta_true", lambda rng: (lambda x: np.zeros_like(x))),
        ("H1 50\" (rated limit, eccentricity-like)", lambda rng: (lambda x, c=[(1, 50, P(rng))]: harm(x, c))),
        ("H1 35\" + H2 15\" (rated limit)", lambda rng: (lambda x, c=[(1, 35, P(rng)), (2, 15, P(rng))]: harm(x, c))),
        ("H2 40\" + H1 20\" (bellows coupling S)", lambda rng: (lambda x, c=[(2, 40, P(rng)), (1, 20, P(rng))]: harm(x, c))),
        ("H1 5\" (after ideal self-calibration)", lambda rng: (lambda x, c=[(1, 5, P(rng))]: harm(x, c))),
        ("H1 15\" + H2 8\" (honest post-selfcal budget)", lambda rng: (lambda x, c=[(1, 15, P(rng)), (2, 8, P(rng))]: harm(x, c))),
        ("H32 20\" only (nonius-like SDE)", lambda rng: (lambda x, c=[(32, 20, P(rng))]: harm(x, c))),
        ("H1 200\" (magnetic reference, mis-rated)", lambda rng: (lambda x, c=[(1, 200, P(rng))]: harm(x, c))),
    ]
    print(f"{parts} parts per case, sigma_mean {SIG:.5f} deg, R_MAX {R_MAX}, R_ACCEPT {R_ACCEPT}")
    for label, gen in cases:
        report(label, population(np.random.default_rng(20260920), parts, gen))
