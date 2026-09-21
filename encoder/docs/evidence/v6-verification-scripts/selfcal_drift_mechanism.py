"""v6 re-verification: does 'running out and back cancel linear drift of the artefact' (spec 7.7, Order)?

ref_selfcal.py's own second table says no: with exactly linear drift (mscale = 1 + drift*i/(T-1)) the H1-H6 part of the
theta_true error grows 4.7 -> 7.0 -> 9.5 -> 15.1 -> 29.8 arcsec for 1, 2, 3, 5, 10 % drift. This script isolates why.

Out-and-back makes the MEAN artefact scale equal for every mounting WITHIN a set. It does nothing about the difference
between the sets: set A is centred on turn 10 of 36, set B on turn 28.5. Within set A the columns of M (function of
theta + delta0) and of S2 (function of theta) are collinear; only set B separates them. A scale of M that differs between
the sets is therefore partly booked to S2^, which is in H1-H6 and goes into every module.

  mode 'linear'      : as ref_selfcal.py
  mode 'equal_means' : the same linear drift inside each set, but both sets centred on the same mean scale
                       (unphysical; isolates the A-to-B offset)
  mode 'linear+col'  : as ref_selfcal.py, plus ONE extra fitted parameter in the second pass: the scale of M^ in set B
                       relative to set A (column: -[turn in set B] * M^_pass1(theta_s)). A possible fix, not a demand.

trial() is a copy of ref_selfcal.trial() (v6 branch); fit() is a copy of ref_selfcal.fit() with the optional column.

    OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 ../../../.venv/bin/python selfcal_drift_mechanism.py [trials]
"""
import pathlib, sys
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "v3-reference"))
import ref_selfcal as rs  # noqa: E402

AS = rs.AS


def fit(turns, with_s2, extra=None):
    kr, km, ks = range(1, rs.K_R + 1), range(1, rs.K_M + 1), range(1, rs.K_S2 + 1)
    n = len(turns)
    rows, y, c0 = [], [], []
    for i, (psi, ts, ghat) in enumerate(turns):
        d = psi - ts
        centre = rs.circ_mean(d)
        onehot = np.zeros((len(psi), n)); onehot[:, i] = 1.0
        cols = rs.harm(psi, kr) + [-c for c in rs.harm(ts, km)] + ([-c for c in rs.harm(psi - ghat, ks)] if with_s2 else [])
        if extra is not None:
            cols = cols + [extra[i]]
        rows.append(np.hstack([onehot, np.column_stack(cols)]))
        y.append(rs.wrap(d - centre)); c0.append(centre)
    A, y = np.vstack(rows), np.concatenate(y)
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    c = coef[:n] + np.array(c0)
    r = coef[n:n + 2 * rs.K_R].reshape(-1, 2)
    m = coef[n + 2 * rs.K_R:n + 2 * rs.K_R + 2 * rs.K_M].reshape(-1, 2)
    s2 = coef[n + 2 * rs.K_R + 2 * rs.K_M:n + 2 * rs.K_R + 2 * rs.K_M + 2 * rs.K_S2].reshape(-1, 2) if with_s2 else np.zeros((rs.K_S2, 2))
    return c, r, m, s2


def trial(rng, mode, s1, s2, clamp=(0, 0), drift=0.0, sde=0.0, s2_unit=0.0):
    st = rs.Station(rng, s1, s2, clamp, sde, s2_unit, False)
    M = rs.random_module(rng)
    delta0 = rng.uniform(0, 360)
    s2_art = st.s2_now()
    jit = lambda a: a + rng.uniform(-rs.JITTER, rs.JITTER)
    seq = [("A", jit(a), delta0, st.clamp(), s2_art) for a in rs.A_ANGLES]
    seq.append(("check", jit(rs.CHECK_ANGLE), delta0, st.clamp(), s2_art))
    seq += [("A", jit(a), delta0, st.clamp(), s2_art) for a in rs.A_ANGLES[::-1]]
    g_last, c_last = seq[-1][1], seq[-1][3]
    for b in rs.B_ANGLES + rs.B_ANGLES[::-1]:
        seq.append(("B", g_last, jit(delta0 + b), c_last, st.s2_now()))
    T = len(seq)
    idx = np.arange(T, dtype=float)
    if mode == "equal_means":
        isb = np.array([q[0] == "B" for q in seq])
        idx[isb] -= idx[isb].mean() - idx[~isb].mean()
    data = [st.turn(g, d, M, ct, s2t, mscale=1 + drift * idx[i] / (T - 1)) for i, (_, g, d, ct, s2t) in enumerate(seq)]
    fit_idx = [i for i, q in enumerate(seq) if q[0] != "check"]
    turns = [(data[i][0], data[i][1], 0.0) for i in fit_idx]
    c, r, m, s2h = fit(turns, with_s2=False)
    last_a = max(j for j, i in enumerate(fit_idx) if seq[i][0] == "A")
    ghat = np.array([(c[j] - c[0]) if seq[i][0] == "A" else (c[last_a] - c[0]) for j, i in enumerate(fit_idx)])
    turns = [(p, t, g) for (p, t, _), g in zip(turns, ghat)]
    extra = None
    if mode == "linear+col":
        extra = [-(1.0 if seq[i][0] == "B" else 0.0) * rs.series(data[i][1], m) for i in fit_idx]
    c, r, m, s2h = fit(turns, with_s2=True, extra=extra)
    psi, _, th_h = st.turn(g_last, rng.uniform(0, 360), rs.random_module(rng), c_last, st.s2_now())
    est = psi - rs.series(psi, r) + rs.series(psi - ghat[last_a], s2h)
    e = rs.wrap(est - th_h); e = rs.wrap(e - rs.circ_mean(e))
    A = np.column_stack([np.ones_like(th_h)] + rs.harm(th_h, range(1, 7)))
    low = A @ np.linalg.lstsq(A, e, rcond=None)[0]
    return rs.half_range(est - th_h) / AS, rs.half_range(low) / AS


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    G = {k: (tuple(x * AS for x in v) if k in ("s1", "s2", "clamp") else v * AS if k == "sde" else v) for k, v in rs.GOOD.items()}
    print(f"GOOD station of ref_selfcal.py, exactly linear artefact drift; theta_true error, arcsec, median/max of {n}: all | H1-H6 part")
    for drift in (0.0, 0.01, 0.02, 0.05, 0.10):
        row = []
        for mode in ("linear", "equal_means", "linear+col"):
            res = np.array([trial(np.random.default_rng(100 + k), mode, **dict(G, drift=drift)) for k in range(n)])
            row.append(f"{mode:12s} {np.median(res[:,0]):5.1f}/{res[:,0].max():5.1f} | {np.median(res[:,1]):5.1f}/{res[:,1].max():5.1f}")
        print(f"drift {100*drift:4.0f} %   " + "     ".join(row), flush=True)
