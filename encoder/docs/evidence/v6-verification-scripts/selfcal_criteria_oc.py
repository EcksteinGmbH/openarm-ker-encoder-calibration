"""v6 verification: operating characteristic of the two §7.7 commissioning criteria, and the
'production clamp is absorbed by S2' argument. Uses ref_selfcal.py unmodified (imports it); trial() is
re-implemented here only to add three switches:
  prod_clamp : amplitude (H1, H2 arcsec) of the clamp term of the LAST set-A mounting only (others use `clamp`)
  reclamp    : production runs on a FRESH clamp (what happens if the 100 deg check mounting is physically
               taken after set B, as ref_selfcal.py simulates it, and the reference is then put back)
  setb_fresh : (unphysical control) set B turns use fresh clamps, so S2 cannot absorb the production clamp

    OPENBLAS_NUM_THREADS=1 ../../../.venv/bin/python selfcal_criteria_oc.py [trials]
"""
import pathlib, sys
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "v3-reference"))
import ref_selfcal as rs  # noqa: E402

AS = rs.AS
REPRO_MAX, CHECK_MAX = 8.0, 25.0


def trial(rng, s1, s2, clamp=(0, 0), drift=0.0, sde=0.0, s2_unit=0.0, prod_clamp=None, reclamp=False, setb_fresh=False):
    st = rs.Station(rng, s1, s2, clamp, sde, False)
    M = rs.random_module(rng)
    a_seq = rs.A_ANGLES + rs.A_ANGLES[::-1]
    delta0 = rng.uniform(0, 360)
    seq = [("A", a + rng.uniform(-rs.JITTER, rs.JITTER), delta0, st.clamp()) for a in a_seq]
    if prod_clamp is not None:
        seq[-1] = (seq[-1][0], seq[-1][1], seq[-1][2], rs.low_order(rng, *prod_clamp))
    g_last, c_last = seq[-1][1], seq[-1][3]
    for b in rs.B_ANGLES + rs.B_ANGLES[::-1]:
        seq.append(("B", g_last, delta0 + b + rng.uniform(-rs.JITTER, rs.JITTER), st.clamp() if setb_fresh else c_last))
    T = len(seq)
    data = [st.turn(g, d, M, ct, mscale=1 + drift * i / (T - 1)) for i, (_, g, d, ct) in enumerate(seq)]
    turns = [(p, t, s[0], 0.0) for (p, t, _), s in zip(data, seq)]
    c, r, m, s2h, _ = rs.fit(turns, with_s2=False)
    n_a = len(a_seq)
    ghat = [(c[i] - c[0]) if seq[i][0] == "A" else (c[n_a - 1] - c[0]) for i in range(T)]
    turns = [(p, t, s, g) for (p, t, s, _), g in zip(turns, ghat)]
    c, r, m, s2h, _ = rs.fit(turns, with_s2=True)
    g_prod = ghat[n_a - 1]
    s2_prod = st.S2 * (1 + rng.uniform(-s2_unit, s2_unit)) + rs.low_order(rng, s2_unit * np.hypot(*st.S2[0]), 0)
    c_prod = st.clamp() if reclamp else c_last
    psi, _, th_h = st.turn(g_last, rng.uniform(0, 360), rs.random_module(rng), c_prod, s2=s2_prod)
    est = psi - rs.series(psi, r) + rs.series(psi - g_prod, s2h)
    # low-order (H1-H6) part of the theta_true error: what is actually written into a module
    lo = rs.low_amps(psi, rs.half_range.__globals__["np"].asarray((est - th_h + 180) % 360 - 180), 6)
    repro = np.sqrt(np.mean([rs.low_amps(t[0], rs.residual(t[0], t[1], t[3], r, m, s2h), 3) ** 2 for t in turns]))
    g_chk = rs.CHECK_ANGLE + rng.uniform(-rs.JITTER, rs.JITTER)
    pc, tc, _ = st.turn(g_chk, delta0, M, st.clamp(), mscale=1 + drift)
    dc = np.deg2rad(pc - tc)
    c_chk = np.rad2deg(np.arctan2(np.mean(np.sin(dc)), np.mean(np.cos(dc))))
    check = rs.low_amps(pc, rs.residual(pc, tc, c_chk - c[0], r, m, s2h), 7).max()
    return rs.half_range(est - th_h) / AS, np.sqrt(np.sum(lo ** 2)) / AS, repro / AS, check / AS


def run(name, n, **kw):
    rng = np.random.default_rng(11)
    kw = {k: (tuple(x * AS for x in v) if k in ("s1", "s2", "clamp", "prod_clamp") and v is not None else v * AS if k == "sde" else v)
          for k, v in kw.items()}
    res = np.array([trial(rng, **kw) for _ in range(n)])
    after, lo, repro, check = res.T
    p1, p2 = repro <= REPRO_MAX, check <= CHECK_MAX
    both = p1 & p2
    worst_pass = after[both].max() if both.any() else float("nan")
    print(f"{name:58s} after med/max {np.median(after):5.1f}/{after.max():5.1f}  H1-6 rss med/max {np.median(lo):5.1f}/{lo.max():5.1f}  "
          f"repro min/med/max {repro.min():5.1f}/{np.median(repro):5.1f}/{repro.max():5.1f}  check min/med/max {check.min():5.1f}/{np.median(check):5.1f}/{check.max():5.1f}  "
          f"pass repro {100*p1.mean():5.1f}%  pass check {100*p2.mean():5.1f}%  pass both {100*both.mean():5.1f}%  worst 'after' among passing {worst_pass:5.1f}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    base = dict(s1=(40, 20), s2=(6, 3), sde=8, s2_unit=0.3)
    print(f"criteria: repro <= {REPRO_MAX} arcsec rms, check <= {CHECK_MAX} arcsec; {n} trials per case; all arcsec")
    print("--- E1: good stations, the two spec faults, and intermediate faults")
    run("good: clamp 3+2, drift 1 %", n, clamp=(3, 2), drift=0.01, **base)
    run("clamp 6+4, drift 1 %", n, clamp=(6, 4), drift=0.01, **base)
    run("clamp 10+5, drift 1 %", n, clamp=(10, 5), drift=0.01, **base)
    run("clamp 15+8, drift 1 %", n, clamp=(15, 8), drift=0.01, **base)
    run("clamp 20+10, drift 1 %", n, clamp=(20, 10), drift=0.01, **base)
    run("SPEC FAULT: clamp 30+15, drift 1 %", n, clamp=(30, 15), drift=0.01, **base)
    run("clamp 3+2, drift 2 %", n, clamp=(3, 2), drift=0.02, **base)
    run("clamp 3+2, drift 3 %", n, clamp=(3, 2), drift=0.03, **base)
    run("clamp 3+2, drift 5 %", n, clamp=(3, 2), drift=0.05, **base)
    run("SPEC FAULT: clamp 3+2, drift 10 %", n, clamp=(3, 2), drift=0.10, **base)
    print("--- E2: is the production mounting's own clamp deviation absorbed by S2?  (all other clamps perfect, no drift, no SDE, C2 identical per unit)")
    e2 = dict(s1=(40, 20), s2=(6, 3))
    run("reference: no clamp error anywhere", n, **e2)
    run("production clamp 30+15 only, set B on it (spec)", n, prod_clamp=(30, 15), **e2)
    run("production clamp 30+15 only, set B on fresh clamps (control)", n, prod_clamp=(30, 15), setb_fresh=True, **e2)
    print("--- E3: production runs on a re-clamped mounting (check mounting physically taken last, reference then put back)")
    run("good station, production on c_last (as simulated)", n, clamp=(3, 2), drift=0.01, **base)
    run("good station, production re-clamped", n, clamp=(3, 2), drift=0.01, reclamp=True, **base)
    run("clamp 10+5, production re-clamped", n, clamp=(10, 5), drift=0.01, reclamp=True, **base)
