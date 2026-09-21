"""v6 verification: attack the v6 two-direction graded gate (spec 7.2) the way the v5 verification attacked the v5
gate. Spec v6 only ASSERTS that those attacks carry over ("the v6 statistic averages two directions and is less
noisy than the one it attacked"); the grade-B limit was never attacked.

Attack population: small H1-H6 content (fitted away), the residual error carried by UNMODELLED H7-H16, amplitudes
drawn so that the true systematic error clusters around R_MAX (0.02) and R_MAX_B (0.05); hysteresis loop with a
SHAPE that differs between parts (H1 and H2 modulation, 0.03-0.09 deg); AR(1) correlated sensor noise (rho 0.5 by
default: the largest correlation that still passes the step-2 noise check most of the time; at rho 0.8 step 2 returns
'insufficient data' for ~80 % of parts, as intended), scaled to the same marginal sigma. Same exact reference as station_sim.py (expectation over sensor noise, direction mean).

    gcc -O2 -shared -fPIC -o $O/libref.so ../v3-reference/ref_comp.c ../v3-reference/batch.c
    ../../../.venv/bin/python gate_attack_v6.py $O/libref.so [parts] [rho]
"""
import pathlib, sys
import numpy as np
from math import erf, sqrt
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "v3-reference"))
import station_fit as sf  # noqa: E402

lib = sf.load(sys.argv[1])
PARTS = int(sys.argv[2]) if len(sys.argv) > 2 else 600
SIGMA, K = 0.05, sf.K_SAMPLES
RHO = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
Q, LSB21 = sf.Q, sf.LSB21
rng = np.random.default_rng(606)
GRID = np.arange(2048) * 360.0 / 2048
_phi = np.vectorize(lambda x: 0.5 * (1 + erf(x / sqrt(2))))


def ar1(shape):
    e = rng.normal(0, 1, shape)
    x = np.empty(shape)
    x[:, 0] = e[:, 0]
    s = sqrt(1 - RHO ** 2)
    for i in range(1, shape[1]):
        x[:, i] = RHO * x[:, i - 1] + s * e[:, i]
    return x * SIGMA


def readings(theta, err_fn, n):
    t = np.asarray(theta)[:, None]
    return np.floor(((t + err_fn(t) + ar1((t.shape[0], n))) % 360.0) / Q).astype(np.int64) % 32768


def get_sample(codes, modulus):
    ref = codes[:, :1]
    d = (codes - ref + modulus // 2) % modulus - modulus // 2
    return ref[:, 0], d.sum(axis=1), codes.shape[1]


def expected_error(err_fn, out_all):
    mean_sens = GRID + err_fn(GRID)
    j0 = np.floor((mean_sens % 360) / Q).astype(np.int64)
    span = int(np.ceil(6 * SIGMA / Q)) + 1
    js = j0[:, None] + np.arange(-span, span + 1)[None, :]
    lo = (js * Q - (mean_sens % 360)[:, None]) / SIGMA
    p = _phi(lo + Q / SIGMA) - _phi(lo)
    p /= p.sum(axis=1, keepdims=True)
    o = out_all[js % 32768]
    ref = o[:, span:span + 1]
    o = ref + sf.wrap(o - ref)
    return sf.wrap(GRID - (p * o).sum(axis=1))


fit_pos, val_pos = sf.positions()
rec = []
for part in range(PARTS):
    lowa = rng.uniform(0.3, 1.5) * np.array([1, .4, .15, .05, .03, .02]) * rng.uniform(.5, 1, 6)
    target = rng.choice([0.02, 0.05]) * rng.uniform(0.8, 1.25)            # cluster around both limits
    ks = rng.choice(np.arange(7, 17), size=rng.integers(1, 4), replace=False)
    ha = rng.uniform(.3, 1, ks.size); ha *= target / ha.sum()
    amps = np.zeros(16); amps[:6] = lowa; amps[ks - 1] = ha
    ph = rng.uniform(0, 2 * np.pi, 16); off = rng.uniform(0, 360)
    err = lambda t, a=amps, p=ph, o=off: o + sum(a[k] * np.sin((k + 1) * np.deg2rad(t) + p[k]) for k in range(16) if a[k])
    h0, m1, m2, p1, p2 = rng.uniform(.03, .09), rng.uniform(0, .4), rng.uniform(0, .3), *rng.uniform(0, 2 * np.pi, 2)
    hy = lambda t: h0 * (1 + m1 * np.sin(np.deg2rad(t) + p1) + m2 * np.sin(2 * np.deg2rad(t) + p2))
    ecw, eccw = (lambda t: err(t) + hy(t)), (lambda t: err(t) - hy(t))
    ts = [sf.sample_angle(*get_sample(readings(fit_pos, e, K), 32768)) for e in (ecw, eccw)]
    a, b, _ = sf.fit(np.concatenate([fit_pos, fit_pos]), np.concatenate(ts))
    cal = sf.to_cal(a, b)
    outs = []
    for e in (ecw, eccw):
        codes = readings(val_pos, e, K)
        comp = sf.compensate(lib, codes.ravel(), cal).reshape(codes.shape).astype(np.int64)
        outs.append(sf.sample_output(*get_sample(comp, 2 ** 21)))
    rep = sf.sample_angle(*get_sample(readings(np.full(sf.N_REPEAT, 0.0), err, K), 32768))
    g, stat, hm = sf.grade(val_pos, outs[0], outs[1], sf.noise_check(rep))
    out_all = sf.compensate(lib, np.arange(32768), cal).astype(np.float64) * LSB21
    dcw, dccw = expected_error(ecw, out_all), expected_error(eccw, out_all)
    rec.append((sf.half_range(dccw + sf.wrap(dcw - dccw) / 2), g, stat))

t = np.array([r[0] for r in rec]); g = np.array([r[1] for r in rec])
print(f"{PARTS} attack parts: error in H7-H16 clustered at 0.02 and 0.05 deg, part-specific hysteresis shape, AR(1) noise rho {RHO}")
print("grades:", dict(zip(*[x.tolist() for x in np.unique(g, return_counts=True)])))
A, B = g == "A", g == "B"
fa, fb = A & (t > sf.R_MAX), (A | B) & (t > sf.R_MAX_B)
print(f"graded A with true error > {sf.R_MAX}: {fa.sum()} of {(t > sf.R_MAX).sum()} such parts (worst {t[fa].max() if fa.any() else 0:.4f})")
print(f"graded A or B with true error > {sf.R_MAX_B}: {fb.sum()} of {(t > sf.R_MAX_B).sum()} such parts (worst {t[fb].max() if fb.any() else 0:.4f})")
print(f"not A with true error < 0.75 x {sf.R_MAX}: {((~A) & (t < .75 * sf.R_MAX) & (g != 'insufficient-data')).sum()};  "
      f"reworked with true error < 0.75 x {sf.R_MAX_B}: {(np.char.startswith(g.astype(str), 'rework') & (t < .75 * sf.R_MAX_B)).sum()}")
for lo, hi in [(0, .015), (.015, .02), (.02, .0225), (.0225, .04), (.04, .05), (.05, .055), (.055, 1)]:
    m = (t >= lo) & (t < hi)
    if m.any():
        print(f"  true {lo:.4f}-{hi:.4f}: {m.sum():4d} parts   A {100*np.mean(g[m]=='A'):5.1f}%  B {100*np.mean(g[m]=='B'):5.1f}%  rework* {100*np.mean(np.char.startswith(g[m].astype(str),'rework')):5.1f}%  insufficient {100*np.mean(g[m]=='insufficient-data'):5.1f}%")
