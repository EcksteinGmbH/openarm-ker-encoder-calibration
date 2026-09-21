"""v6 re-verification of the rewritten ref_selfcal.py (fixes to V1, V2, V5). Imports it unmodified.

trial() below is a copy of ref_selfcal.trial() (v6 branch only) with four switches and nothing else changed:
  prod_clamp : clamp amplitude (H1, H2) of the PRODUCTION mounting only (the last set-A clamping)
  setb_fresh : (unphysical control) set B runs on fresh clamps, so S2^ cannot absorb the production clamp
  ref_kmax   : truncate the reference's spectrum to H1..ref_kmax (20 = exactly the fitted model)
  scatter    : stage position scatter, degrees rms (ref_selfcal.STAGE_SCATTER is patched per run)

    OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 ../../../.venv/bin/python selfcal_recheck.py [trials]

R1  is the SDE / above-H20 content effective, and how sensitive is it to the assumed stage scatter?
R2  the bolded claim of spec 7.7 ("no station that passed both criteria had an error above 23.9 / 14.9 arcsec"):
    other seed, COMBINED faults, and faults outside the table (SDE 20, bellows C2, C2 variation 60 %)
R3  "about 70 % absorbed" re-derived on the new model
"""
import pathlib, sys
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "v3-reference"))
import ref_selfcal as rs  # noqa: E402

AS = rs.AS


def trial(rng, s1, s2, clamp=(0, 0), drift=0.0, sde=0.0, s2_unit=0.0, prod_clamp=None, setb_fresh=False, ref_kmax=40):
    st = rs.Station(rng, s1, s2, clamp, sde, s2_unit, False)
    if ref_kmax < 40:
        st.R = st.R.copy(); st.R[ref_kmax:] = 0.0
    M = rs.random_module(rng)
    delta0 = rng.uniform(0, 360)
    s2_art = st.s2_now()
    jit = lambda a: a + rng.uniform(-rs.JITTER, rs.JITTER)
    seq = [("A", jit(a), delta0, st.clamp(), s2_art) for a in rs.A_ANGLES]
    seq.append(("check", jit(rs.CHECK_ANGLE), delta0, st.clamp(), s2_art))
    seq += [("A", jit(a), delta0, st.clamp(), s2_art) for a in rs.A_ANGLES[::-1]]
    if prod_clamp is not None:
        q = seq[-1]; seq[-1] = (q[0], q[1], q[2], rs.low_order(rng, *prod_clamp), q[4])
    g_last, c_last = seq[-1][1], seq[-1][3]
    for b in rs.B_ANGLES + rs.B_ANGLES[::-1]:
        seq.append(("B", g_last, jit(delta0 + b), st.clamp() if setb_fresh else c_last, st.s2_now()))
    T = len(seq)
    data = [st.turn(g, d, M, ct, s2t, mscale=1 + drift * i / (T - 1)) for i, (_, g, d, ct, s2t) in enumerate(seq)]
    fit_idx = [i for i, q in enumerate(seq) if q[0] != "check"]
    chk = next(i for i, q in enumerate(seq) if q[0] == "check")
    turns = [(data[i][0], data[i][1], 0.0) for i in fit_idx]
    c, r, m, s2h, _ = rs.fit(turns, with_s2=False)
    last_a = max(j for j, i in enumerate(fit_idx) if seq[i][0] == "A")
    ghat = np.array([(c[j] - c[0]) if seq[i][0] == "A" else (c[last_a] - c[0]) for j, i in enumerate(fit_idx)])
    turns = [(p, t, g) for (p, t, _), g in zip(turns, ghat)]
    c, r, m, s2h, _ = rs.fit(turns, with_s2=True)
    psi, _, th_h = st.turn(g_last, rng.uniform(0, 360), rs.random_module(rng), c_last, st.s2_now())
    est = psi - rs.series(psi, r) + rs.series(psi - ghat[last_a], s2h)
    repro = np.sqrt(np.mean([rs.low_amps(t[0], rs.residual(t[0], t[1], t[2], r, m, s2h), 3) ** 2 for t in turns]))
    pc, tc, _ = data[chk]
    check = rs.low_amps(pc, rs.residual(pc, tc, rs.circ_mean(pc - tc) - c[0], r, m, s2h), 7).max()
    e = rs.wrap(est - th_h); e = rs.wrap(e - rs.circ_mean(e))
    A = np.column_stack([np.ones_like(th_h)] + rs.harm(th_h, range(1, 7)))
    low = A @ np.linalg.lstsq(A, e, rcond=None)[0]
    return rs.half_range(est - th_h) / AS, rs.half_range(low) / AS, repro / AS, check / AS


def run(name, n, seed, scatter=0.03, **kw):
    rs.STAGE_SCATTER = scatter
    rng = np.random.default_rng(seed)
    kw = {k: (tuple(x * AS for x in v) if k in ("s1", "s2", "clamp", "prod_clamp") and v is not None else v * AS if k == "sde" else v)
          for k, v in kw.items()}
    res = np.array([trial(rng, **kw) for _ in range(n)])
    after, low, repro, check = res.T
    both = (repro <= rs.REPRO_MAX) & (check <= rs.CHECK_MAX)
    wa = after[both].max() if both.any() else float("nan")
    wl = low[both].max() if both.any() else float("nan")
    print(f"{name:62s} after {np.median(after):5.1f}/{after.max():5.1f}  H1-6 {np.median(low):5.1f}/{low.max():5.1f}  repro {np.median(repro):4.1f}/{repro.max():4.1f}  "
          f"check {np.median(check):4.1f}/{check.max():4.1f}  pass both {100*both.mean():5.1f}%  worst passing {wa:5.1f} / {wl:5.1f}", flush=True)
    return wa, wl


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    G = dict(rs.GOOD)
    print(f"all arcsec, med/max; {n} stations per row; criteria repro <= {rs.REPRO_MAX}, check <= {rs.CHECK_MAX}")
    print("--- R1: is the SDE and the above-H20 content effective? (GOOD station, seed 7)")
    run("GOOD as in ref_selfcal.py (SDE 8, ref to H40, scatter 0.03)", n, 7, **G)
    run("SDE 0", n, 7, **dict(G, sde=0))
    run("SDE 8, reference truncated to H20 (= the fitted model)", n, 7, ref_kmax=20, **G)
    run("SDE 8, stage scatter 0 (the old inert case)", n, 7, scatter=0.0, **G)
    run("SDE 8, stage scatter 0.10 (SDE phase fully randomised)", n, 7, scatter=0.10, **G)
    print("--- R2: the 23.9 / 14.9 claim: other seed, combined faults, faults outside the spec's table")
    w = []
    w.append(run("seed 2026: drift 2 %", n, 2026, **dict(G, drift=0.02)))
    w.append(run("seed 2026: drift 5 %", n, 2026, **dict(G, drift=0.05)))
    w.append(run("seed 2026: clamp 10+5", n, 2026, **dict(G, clamp=(10, 5))))
    w.append(run("COMBINED clamp 6+4 and drift 2 %", n, 5, **dict(G, clamp=(6, 4), drift=0.02)))
    w.append(run("COMBINED clamp 10+5 and drift 3 %", n, 5, **dict(G, clamp=(10, 5), drift=0.03)))
    print(f"   -> worst among passing over these five rows: {np.nanmax([x[0] for x in w]):.1f} / {np.nanmax([x[1] for x in w]):.1f}   (spec: 23.9 / 14.9)")
    run("outside the table: SDE 20 (pole-pitch class), else GOOD", n, 5, **dict(G, sde=20))
    run("outside the table: C2 bellows 40+20, else GOOD", n, 5, **dict(G, s2=(40, 20)))
    run("outside the table: C2 bellows 40+20 and drift 2 %", n, 5, **dict(G, s2=(40, 20), drift=0.02))
    run("outside the table: C2 diaphragm, varies 60 % per fixturing", n, 5, **dict(G, s2_unit=0.6))
    print("--- R3: 'about 70 % of the production clamping's deviation is absorbed into S2^' (H1-6 column is the measure)")
    e3 = dict(s1=(40, 20), s2=(6, 3))
    run("no clamp error anywhere, no drift/SDE/C2 variation", n, 3, **e3)
    run("production clamp 30+15 only, set B on it (spec)", n, 3, prod_clamp=(30, 15), **e3)
    run("production clamp 30+15 only, set B on fresh clamps (control)", n, 3, prod_clamp=(30, 15), setb_fresh=True, **e3)
