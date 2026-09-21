"""Operating characteristic of the §7.2 (v6) two-direction, graded acceptance, with sensor noise and hysteresis.

For many simulated parts: run the full station procedure from station_fit.py — averaged fit samples
approaching clockwise and counter-clockwise, pooled fit, round, commit (the real ker_compensate() via
libref.so), averaged validation samples of the compensated output in both directions, grade — and compare
the grade with the part's TRUE systematic error. Each part has a hysteresis loop: the two directions read
+-h(theta) about the mean curve, h = HYST x (1 + 0.3 sin(theta + phase)).

True systematic error = half the peak-to-peak over a dense grid of the direction-mean of
E[θ_out | θ_true] − θ_true (the max error about the minimax constant, the same statistic the gate uses), where the
expectation over sensor noise is computed exactly: each sensor code's probability under Gaussian noise
times that code's compensated output. No sampling error in the reference.

Usage: python station_sim.py libref.so [sigma_deg] [K] [parts] [N_FIT=N_VAL, 0 = default] [drift_deg] [hyst_deg]
"""
import sys
import numpy as np
from math import erf, sqrt
import station_fit as sf

lib = sf.load(sys.argv[1])
SIGMA = float(sys.argv[2]) if len(sys.argv) > 2 else 0.05        # TLE5012B, FIR_MD 2 (datasheet)
K = int(sys.argv[3]) if len(sys.argv) > 3 else sf.K_SAMPLES
PARTS = int(sys.argv[4]) if len(sys.argv) > 4 else 400
if len(sys.argv) > 5 and int(sys.argv[5]) > 0:   # override N_FIT = N_VAL, to show the minimum matters
    sf.N_FIT = sf.N_VAL = int(sys.argv[5])
DRIFT = float(sys.argv[6]) if len(sys.argv) > 6 else 0.0   # offset shift between fit and validation passes
HYST = float(sys.argv[7]) if len(sys.argv) > 7 else 0.05   # hysteresis half-difference between directions, degrees
rng = np.random.default_rng(20260919)
Q, LSB21 = sf.Q, sf.LSB21

def sensor_readings(theta_true, err_fn, n):
    """n noisy 15-bit readings at each true angle. Returns int codes, shape (len, n)."""
    t = np.asarray(theta_true)[:, None]
    th = t + err_fn(t) + rng.normal(0.0, SIGMA, (t.shape[0], n))
    return np.floor((th % 360.0) / Q).astype(np.int64) % 32768

def get_sample(codes, modulus):
    """What GET_SAMPLE yields per position: reference (first reading), sum of wrapped differences, n."""
    ref = codes[:, :1]
    d = (codes - ref + modulus // 2) % modulus - modulus // 2
    return ref[:, 0], d.sum(axis=1), codes.shape[1]

GRID = np.arange(2048) * 360.0 / 2048
_phi = np.vectorize(lambda x: 0.5 * (1 + erf(x / sqrt(2))))

def true_systematic(err_cw, err_ccw, cal):
    out_all = sf.compensate(lib, np.arange(32768), cal).astype(np.float64) * LSB21   # every code
    d_cw, d_ccw = (_expected_error(e, out_all) for e in (err_cw, err_ccw))
    return sf.half_range(d_ccw + sf.wrap(d_cw - d_ccw) / 2)   # direction mean, about the minimax constant


def _expected_error(err_fn, out_all):
    mean_sens = GRID + err_fn(GRID)                          # noise-free sensor angle at each grid point
    j0 = np.floor((mean_sens % 360) / Q).astype(np.int64)
    span = int(np.ceil(6 * SIGMA / Q)) + 1
    js = j0[:, None] + np.arange(-span, span + 1)[None, :]  # candidate codes (unwrapped)
    lo = (js * Q - (mean_sens % 360)[:, None]) / SIGMA
    p = _phi(lo + Q / SIGMA) - _phi(lo)                     # P(code) under Gaussian noise
    p /= p.sum(axis=1, keepdims=True)
    o = out_all[js % 32768]
    ref = o[:, span:span + 1]                               # unwrap around the central code's output,
    o = ref + sf.wrap(o - ref)                              # never around the grid angle (offset ≈ ±180°)
    e_out = (p * o).sum(axis=1)
    return sf.wrap(GRID - e_out)

fit_pos, val_pos = sf.positions()
records = []
for part in range(PARTS):
    # parts deliberately spread past the datasheet (≤ 1.6°) and with unmodelled H7/H8, so that true
    # errors span both sides of R_MAX and the gate's discrimination can be measured
    h1 = rng.uniform(0.2, 2.5)
    amps = h1 * np.array([1, rng.uniform(.2, .6), rng.uniform(.05, .3),
                          rng.uniform(0, .15), rng.uniform(0, .10), rng.uniform(0, .08),
                          rng.uniform(0, .03), rng.uniform(0, .02)])
    ph = rng.uniform(0, 2 * np.pi, 8)
    off = rng.uniform(0, 360)
    err_fn = lambda t, a=amps, p=ph, o=off: o + sum(ak * np.sin((k + 1) * np.deg2rad(t) + pk)
                                                   for k, (ak, pk) in enumerate(zip(a, p)))
    ph_h = rng.uniform(0, 2 * np.pi)
    hyst = lambda t, p=ph_h: HYST * (1 + 0.3 * np.sin(np.deg2rad(t) + p))
    err_cw = lambda t: err_fn(t) + hyst(t)
    err_ccw = lambda t: err_fn(t) - hyst(t)
    # fit passes, both directions: averaged raw samples at the fit positions, pooled
    ts = [sf.sample_angle(*get_sample(sensor_readings(fit_pos, e, K), 32768)) for e in (err_cw, err_ccw)]
    a, b, _ = sf.fit(np.concatenate([fit_pos, fit_pos]), np.concatenate(ts))
    cal = sf.to_cal(a, b)
    if cal is None:
        continue
    # validation passes, after COMMIT_CAL: averaged compensated output, both directions
    outs = []
    for e in (err_cw, err_ccw):
        codes = sensor_readings(val_pos, lambda t, e=e: e(t) + DRIFT, K)
        comp = sf.compensate(lib, codes.ravel(), cal).reshape(codes.shape).astype(np.int64)
        outs.append(sf.sample_output(*get_sample(comp, 2**21)))
    # station step 2: σ_mean from 8 repeated averaged samples at one position (empirical, so it
    # also captures any correlation between consecutive readings)
    rep = sf.sample_angle(*get_sample(sensor_readings(np.full(sf.N_REPEAT, 0.0), err_fn, K), 32768))
    verdict, stat, hyst_meas = sf.grade(val_pos, outs[0], outs[1], sf.noise_check(rep))
    records.append((true_systematic(err_cw, err_ccw, cal), verdict, stat, hyst_meas))

ts_ = np.array([r[0] for r in records]); g = np.array([r[1] for r in records])
hm = np.array([r[3] for r in records if r[3] is not None])
print(f"sigma per reading {SIGMA}°, K = {K} (σ_mean {SIGMA/np.sqrt(K):.4f}°), grade A ≤ {sf.R_MAX}°, grade B ≤ {sf.R_MAX_B}°, "
      f"{sf.N_FIT} fit + {sf.N_VAL} validation positions × 2 directions, drift {DRIFT}°, hysteresis ±{HYST}°, {len(records)} parts")
print(f"grades: {dict(zip(*[x.tolist() for x in np.unique(g, return_counts=True)]))}")
if hm.size:
    print(f"measured hysteresis half-difference: median {np.median(hm):.4f}°, max {hm.max():.4f}°  (true max {1.3 * HYST:.4f}°)")
print(f"{'true systematic error':>24} {'parts':>6} {'A':>7} {'B':>7} {'rework':>7}")
edges = [0, .005, .010, .015, .020, .025, .030, .040, .050, .060, 1]
for lo, hi in zip(edges[:-1], edges[1:]):
    m = (ts_ >= lo) & (ts_ < hi)
    if m.any():
        row = [100 * np.mean(g[m] == x) for x in ("A", "B", "rework")]
        print(f"{f'{lo:.3f}–{hi:.3f}°':>24} {m.sum():>6} " + " ".join(f"{x:>6.1f}%" for x in row))
A, B = g == "A", g == "B"
fa = A & (ts_ > sf.R_MAX); fb = (A | B) & (ts_ > sf.R_MAX_B)
print(f"graded A with true error > {sf.R_MAX}°: {fa.sum()}  (worst {ts_[fa].max() if fa.any() else 0:.4f}°)")
print(f"graded A or B with true error > {sf.R_MAX_B}°: {fb.sum()}  (worst {ts_[fb].max() if fb.any() else 0:.4f}°)")
print(f"not graded A with true error < 0.75 × {sf.R_MAX}°: {(~A & (ts_ < 0.75 * sf.R_MAX) & (g != 'insufficient-data')).sum()}")
print(f"reworked with true error < 0.75 × {sf.R_MAX_B}°: {((g == 'rework') & (ts_ < 0.75 * sf.R_MAX_B)).sum()}")
