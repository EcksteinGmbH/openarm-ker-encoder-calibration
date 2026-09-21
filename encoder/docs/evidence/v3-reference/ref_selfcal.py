"""Station commissioning: self-calibration of the reference chain by remounting (spec v6 §7.7), in simulation.

Station topology (spec §7.7):   reference encoder == coupling C1 -- stage shaft (dual-shaft stepper) -- coupling C2 -- unit's horn

    psi     = theta + gamma_m + R'(theta + gamma_m) + clamp_m(theta + gamma_m) + noise      reference reading
    theta_h = theta + delta_m + S2_m(theta)                                                 horn angle
    theta_s = theta_h + const + M(theta_h) + noise                                          module, K = 1024 average

R' = reference error + C1's transfer error. The reference and C1 stay clamped together for good and are remounted
as one body on the STAGE-side hub (set A, angle gamma), so both rotate with psi (review F1). C2 stays on the stage
shaft, so its transfer error S2 is a function of theta; it is separated from the module error M by re-clocking the
HORN in C2 (set B, angle delta) with the unit's housing fixed.

Executable order (verification V1): set A out (0, 45 ... 315, 22.5, 11.25) -> CHECK mounting at 100 deg, not used in
the fit -> set A back (11.25, 22.5, 315 ... 0); the last clamping is the PRODUCTION mounting and is never touched
again -> set B out and back on it. Out-and-back cancels linear drift of the artefact (review F5); 22.5 and 11.25
make H8 and H16 of R' observable (review F2/F6). Joint least squares, two passes (the second knows each turn's
gamma from the first).

In production theta_true(horn) = psi - R'^(psi) + S2^(psi - gamma_production), evaluated here on a production turn
with a FRESH unit whose C2 error differs from the artefact's (it changes with every fixturing). That part cannot be
calibrated; it is a budget line and the reason C2 must be an encoder-grade coupling.

Honesty of the model (verification V2): stage positions scatter by STAGE_SCATTER about the nominal grid, so the
reference's sub-divisional error is NOT sampled at one phase; the reference has content above the fitted H20.

    OPENBLAS_NUM_THREADS=1 python ref_selfcal.py [trials] [criteria_trials]
"""
import sys
import numpy as np

AS = 1 / 3600.0
N_POS = 256
K_R, K_M, K_S2 = 20, 20, 6
SIGMA_MOD = 0.05 / np.sqrt(1024)
SIGMA_REF = 1.5 * AS
STAGE_SCATTER = 0.03                          # rms position error of the stage about the nominal grid, degrees
JITTER = 3.0                                  # remount angles are only roughly nominal, degrees
A_ANGLES = [0, 45, 90, 135, 180, 225, 270, 315, 22.5, 11.25]
B_ANGLES = [0, 45, 90, 135, 180, 225, 270, 315]
CHECK_ANGLE = 100.0                           # set-A mounting at the turning point, not used in the fit
REPRO_MAX = 8.0                               # criteria, arcsec (spec §7.7)
CHECK_MAX = 12.0


def harm(x_deg, ks):
    r = np.deg2rad(x_deg)
    return [f(k * r) for k in ks for f in (np.sin, np.cos)]


def series(x_deg, coef):
    r = np.deg2rad(x_deg)
    return sum(a * np.sin((k + 1) * r) + b * np.cos((k + 1) * r) for k, (a, b) in enumerate(coef))


def low_order(rng, h1, h2):
    """H1 + H2 term with the given amplitudes (degrees), random phase."""
    ph = rng.uniform(0, 2 * np.pi, 2)
    return np.array([[h1 * np.cos(ph[0]), h1 * np.sin(ph[0])], [h2 * np.cos(ph[1]), h2 * np.sin(ph[1])]])


def random_reference(rng, peak=50 * AS):
    """H1 dominant, H2, and a decaying tail to H40: H21-H40 lie above the fitted model."""
    k = np.arange(1, 41)
    amp = np.where(k == 1, 1.0, np.where(k == 2, 0.4, 0.15 / k ** 0.7)) * rng.uniform(0.5, 1.0, 40)
    ph = rng.uniform(0, 2 * np.pi, 40)
    coef = np.column_stack([amp * np.cos(ph), amp * np.sin(ph)])
    pk = np.abs(series(np.linspace(0, 360, 4096, endpoint=False), coef)).max()
    return coef * (peak / pk)


def random_module(rng):
    k = np.arange(1, 13)
    amp = rng.uniform(0.2, 1.0) * np.where(k <= 6, 1.0 / k, 0.02 / k) * rng.uniform(0.3, 1.0, 12)
    ph = rng.uniform(0, 2 * np.pi, 12)
    return np.column_stack([amp * np.cos(ph), amp * np.sin(ph)])


def wrap(x):
    return (np.asarray(x) + 180) % 360 - 180


def circ_mean(d):
    r = np.deg2rad(d)
    return np.rad2deg(np.arctan2(np.mean(np.sin(r)), np.mean(np.cos(r))))


def half_range(e):
    e = wrap(e)
    e = wrap(e - circ_mean(e))
    return (e.max() - e.min()) / 2


class Station:
    def __init__(self, rng, s1, s2, clamp, sde, s2_unit, v5):
        self.rng, self.v5, self.s2_unit = rng, v5, s2_unit
        self.R = random_reference(rng)
        self.S1 = low_order(rng, *s1)
        self.S2 = low_order(rng, *s2)
        self.clamp_amp, self.sde = clamp, sde
        self.sde_phase = rng.uniform(0, 2 * np.pi)

    def clamp(self):
        return low_order(self.rng, *self.clamp_amp)

    def s2_now(self):
        """C2's transfer error as it is after one more fixturing / horn clamping."""
        u = self.s2_unit
        return self.S2 * (1 + self.rng.uniform(-u, u)) + low_order(self.rng, u * np.hypot(*self.S2[0]), 0)

    def turn(self, gamma, delta, M, clampterm, s2, mscale=1.0):
        rng = self.rng
        th = np.arange(N_POS) * 360.0 / N_POS + rng.uniform(0, 360.0 / N_POS) + rng.normal(0, STAGE_SCATTER, N_POS)
        enc = th + gamma
        err = series(enc, self.R) + series(enc, clampterm) + self.sde * np.sin(np.deg2rad(2048 * enc) + self.sde_phase)
        err = err + (series(th, self.S1) if self.v5 else series(enc, self.S1))   # v5: C1 stays on the stage shaft
        psi = (enc + err + rng.normal(0, SIGMA_REF, N_POS)) % 360
        th_h = th + delta + series(th, s2)
        ts = (th_h + 37.0 + mscale * series(th_h, M) + rng.normal(0, SIGMA_MOD, N_POS)) % 360
        return psi, ts, th_h


def fit(turns, with_s2, want_cond=False):
    """turns: list of (psi, ts, ghat). Returns per-turn constants, R', M and S2 coefficients, condition number."""
    kr, km, ks = range(1, K_R + 1), range(1, K_M + 1), range(1, K_S2 + 1)
    n = len(turns)
    rows, y, c0 = [], [], []
    for i, (psi, ts, ghat) in enumerate(turns):
        d = psi - ts
        centre = circ_mean(d)                                   # keep each turn off the +-180 seam
        onehot = np.zeros((len(psi), n))
        onehot[:, i] = 1.0
        blk = np.column_stack(harm(psi, kr) + [-c for c in harm(ts, km)]
                              + ([-c for c in harm(psi - ghat, ks)] if with_s2 else []))
        rows.append(np.hstack([onehot, blk]))
        y.append(wrap(d - centre))
        c0.append(centre)
    A, y = np.vstack(rows), np.concatenate(y)
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    cond = np.linalg.cond(A / np.linalg.norm(A, axis=0)) if want_cond else np.nan
    c = coef[:n] + np.array(c0)
    r = coef[n:n + 2 * K_R].reshape(-1, 2)
    m = coef[n + 2 * K_R:n + 2 * K_R + 2 * K_M].reshape(-1, 2)
    s2 = coef[n + 2 * K_R + 2 * K_M:].reshape(-1, 2) if with_s2 else np.zeros((K_S2, 2))
    return c, r, m, s2, cond


def low_amps(x_deg, resid, kmax):
    """Amplitudes of harmonics 1..kmax of a residual, least squares, degrees."""
    A = np.column_stack([np.ones_like(x_deg)] + harm(x_deg, range(1, kmax + 1)))
    c, *_ = np.linalg.lstsq(A, resid, rcond=None)
    return np.hypot(c[1::2], c[2::2])


def residual(psi, ts, ghat, r, m, s2h):
    rho = wrap(psi - ts) - series(psi, r) + series(psi - ghat, s2h) + series(ts, m)
    return wrap(rho - circ_mean(rho))


def trial(rng, s1, s2, clamp=(0, 0), drift=0.0, sde=0.0, s2_unit=0.0, v5=False, want_cond=False):
    st = Station(rng, s1, s2, clamp, sde, s2_unit, v5)
    M = random_module(rng)
    delta0 = rng.uniform(0, 360)
    s2_art = st.s2_now()                                        # the artefact's fixturing
    seq = []                                                    # (kind, gamma, delta, clamp term, S2)
    jit = lambda a: a + rng.uniform(-JITTER, JITTER)
    if v5:
        seq += [("A", jit(a), delta0, st.clamp(), s2_art) for a in A_ANGLES[:8]]
        seq.append(("check", jit(CHECK_ANGLE), delta0, st.clamp(), s2_art))     # v5: check last
    else:
        seq += [("A", jit(a), delta0, st.clamp(), s2_art) for a in A_ANGLES]
        seq.append(("check", jit(CHECK_ANGLE), delta0, st.clamp(), s2_art))     # turning point of set A
        seq += [("A", jit(a), delta0, st.clamp(), s2_art) for a in A_ANGLES[::-1]]
        g_last, c_last = seq[-1][1], seq[-1][3]                                 # production mounting
        for b in B_ANGLES + B_ANGLES[::-1]:                                     # every horn clamping perturbs C2
            seq.append(("B", g_last, jit(delta0 + b), c_last, st.s2_now()))
    T = len(seq)
    data = [st.turn(g, d, M, ct, s2t, mscale=1 + drift * i / (T - 1)) for i, (_, g, d, ct, s2t) in enumerate(seq)]
    fit_idx = [i for i, q in enumerate(seq) if q[0] != "check"]
    chk = next(i for i, q in enumerate(seq) if q[0] == "check")
    turns = [(data[i][0], data[i][1], 0.0) for i in fit_idx]
    c, r, m, s2h, cond = fit(turns, with_s2=False, want_cond=want_cond and v5)
    ghat = np.zeros(len(fit_idx))
    if not v5:
        last_a = max(j for j, i in enumerate(fit_idx) if seq[i][0] == "A")
        ghat = np.array([(c[j] - c[0]) if seq[i][0] == "A" else (c[last_a] - c[0]) for j, i in enumerate(fit_idx)])
        turns = [(p, t, g) for (p, t, _), g in zip(turns, ghat)]
        c, r, m, s2h, cond = fit(turns, with_s2=True, want_cond=want_cond)
    # production: a fresh unit, freshly fixtured, on the production mounting of the reference
    g_prod, c_prod = (seq[fit_idx[-1]][1], seq[fit_idx[-1]][3]) if v5 else (g_last, c_last)
    psi, _, th_h = st.turn(g_prod, rng.uniform(0, 360), random_module(rng), c_prod, st.s2_now())
    est = psi - series(psi, r) + (0 if v5 else series(psi - ghat[last_a], s2h))
    # criteria (spec §7.7)
    repro = np.sqrt(np.mean([low_amps(t[0], residual(t[0], t[1], t[2], r, m, s2h), 3) ** 2 for t in turns]))
    pc, tc, _ = data[chk]
    g_chk = 0.0 if v5 else circ_mean(pc - tc) - c[0]           # gamma of the check turn from its own constant
    check = low_amps(pc, residual(pc, tc, g_chk, r, m, s2h), 7).max()
    # the part of the theta_true error that can enter a module's six harmonics
    e = wrap(est - th_h)
    e = wrap(e - circ_mean(e))
    A = np.column_stack([np.ones_like(th_h)] + harm(th_h, range(1, 7)))
    low = A @ np.linalg.lstsq(A, e, rcond=None)[0]
    return half_range(psi - th_h) / AS, half_range(est - th_h) / AS, cond, repro / AS, check / AS, half_range(low) / AS


def scaled(kw):
    return {k: (tuple(x * AS for x in v) if k in ("s1", "s2", "clamp") else v * AS if k == "sde" else v) for k, v in kw.items()}


GOOD = dict(s1=(40, 20), s2=(6, 3), clamp=(3, 2), drift=0.01, sde=8, s2_unit=0.3)
CASES = [
    ("v5 procedure; C1 40+20, C2 10+5 (both unmodelled in v5)", dict(s1=(40, 20), s2=(10, 5), v5=True)),
    ("v6 procedure; same couplings; nothing else", dict(s1=(40, 20), s2=(10, 5))),
    ("v6; + clamp 3+2, artefact drift 1 %", dict(s1=(40, 20), s2=(10, 5), clamp=(3, 2), drift=0.01)),
    ("v6; + sub-divisional error 8", dict(s1=(40, 20), s2=(10, 5), clamp=(3, 2), drift=0.01, sde=8)),
    ("v6; + C2 differs 30 % per fixturing", dict(s1=(40, 20), s2=(10, 5), clamp=(3, 2), drift=0.01, sde=8, s2_unit=0.3)),
    ("v6; as above, but C2 a bellows 40+20", dict(GOOD, s2=(40, 20))),
    ("v6; as above, C2 a diaphragm 6+3  (= the GOOD station)", GOOD),
]
FAULTS = [("clamp", (6, 4)), ("clamp", (10, 5)), ("clamp", (20, 10)), ("clamp", (30, 15)),
          ("drift", 0.02), ("drift", 0.03), ("drift", 0.05), ("drift", 0.10)]

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    nc = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    print(f"error of theta_true at the horn, production turn, fresh unit; half-range, arcsec; {n} trials per case")
    print("couplings given as H1+H2 amplitudes in arcsec; reference error 50 arcsec peak before correction, content to H40;")
    print(f"stage position scatter {STAGE_SCATTER} deg rms")
    print("repro = rms of per-turn residual H1-H3 amplitudes; check = largest H1-H7 amplitude on the 100 deg mounting, not in the fit")
    print("H1-6 = the part of the 'after' error that lies in harmonics 1-6, i.e. that can enter a module's coefficients")
    print(f"{'case':58s} {'before med/max':>15s} {'after med/max':>15s} {'H1-6 med/max':>14s} {'cond':>5s} {'repro med/max':>14s} {'check med/max':>14s}")
    for name, kw in CASES:
        rng = np.random.default_rng(7)
        res = np.array([trial(rng, want_cond=(i == 0), **scaled(kw)) for i in range(n)])
        print(f"{name:58s} {np.median(res[:, 0]):8.1f}/{res[:, 0].max():6.1f} {np.median(res[:, 1]):8.1f}/{res[:, 1].max():6.1f} "
              f"{np.median(res[:, 5]):7.1f}/{res[:, 5].max():6.1f} "
              f"{np.nanmax(res[:, 2]):5.1f} {np.median(res[:, 3]):7.1f}/{res[:, 3].max():6.1f} {np.median(res[:, 4]):7.1f}/{res[:, 4].max():6.1f}")
    print()
    print(f"criteria: repro <= {REPRO_MAX} and check <= {CHECK_MAX} arcsec; GOOD station with one fault at a time; {nc} stations per row")
    print(f"{'station':26s} {'after med/max':>15s} {'H1-6 med/max':>14s} {'pass repro':>11s} {'pass check':>11s} {'pass both':>10s} {'worst after / H1-6 among passing':>33s}")
    worst_all = worst_low_all = 0.0
    for label, kw in [("GOOD", {})] + [(f"{k} {v}", {k: v}) for k, v in FAULTS]:
        rng = np.random.default_rng(11)
        res = np.array([trial(rng, **scaled(dict(GOOD, **kw))) for _ in range(nc)])
        pr, pk = res[:, 3] <= REPRO_MAX, res[:, 4] <= CHECK_MAX
        both = pr & pk
        worst = res[both, 1].max() if both.any() else float("nan")
        worst_low = res[both, 5].max() if both.any() else float("nan")
        if both.any():
            worst_all, worst_low_all = max(worst_all, worst), max(worst_low_all, worst_low)
        print(f"{label:26s} {np.median(res[:, 1]):8.1f}/{res[:, 1].max():6.1f} {np.median(res[:, 5]):7.1f}/{res[:, 5].max():6.1f} "
              f"{100 * pr.mean():10.1f}% {100 * pk.mean():10.1f}% {100 * both.mean():9.1f}% {worst:22.1f} / {worst_low:5.1f}")
    print(f"worst theta_true error of any station that passed both criteria: {worst_all:.1f} arcsec, of which in H1-6: {worst_low_all:.1f} arcsec")
