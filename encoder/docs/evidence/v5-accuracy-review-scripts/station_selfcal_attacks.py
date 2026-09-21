"""Attack on spec §7.7 (reference self-calibration by remounting) — extended copy of
evidence/v3-reference/ref_selfcal.py. Review script, 2026-09-20 (station-metrology reviewer).

The author's model:   psi - theta_s = c_j + R(psi) - M(theta_s),  R fixed to the encoder's own angle.
This copy generalises the measurement chain so that the assumptions can be broken one at a time:

  theta            true angle of the magnet shaft (what theta_true is supposed to be)
  kappa = theta + beta_j                 coupling body angle (beta_j != 0 only for a stage-side remount)
  phi   = kappa + gamma_j + S(kappa) + C_j(kappa)      encoder shaft angle
            S    coupling kinematic transfer error, lab-fixed misalignment x coupling asymmetry:
                 tied to the COUPLING BODY, identical at every encoder-side remount
            C_j  the part of the transfer error that changes with each re-clamping
  psi   = phi + R(phi) + E_j(phi) + noise              reference reading
            E_j  encoder-angle-synchronous error that changes per remount (kit / hollow-shaft
                 reference: clamping eccentricity)
  theta_s = theta + 37 + (1 + drift*t/T) * M(theta) + noise     module, M drifting with time t

Production is assumed to run on ONE final mounting P (nominal 22.5 deg, the spec's step-5 mounting),
which has its own C_P, E_P. Reported for that mounting:
  err      half-range of  theta_true_est - theta  with theta_true_est = psi - R_hat(psi)   [truth]
  s5_raw   step-5 statistic, raw: half-range of the corrected residual at the 256 positions
  s5_harm  step-5 statistic, harmonic: half-range of an H1..H20 (without 8, 16) fit to that residual
  err_T    truth error if H1..H3 of mounting P's residual are folded back into the correction ("transfer")

    python station_selfcal_attacks.py [trials]
"""
import sys
import numpy as np

AS = 1 / 3600.0
N_MOUNT, N_POS, K_FIT = 8, 256, 20
SIGMA_MOD = 0.05 / np.sqrt(1024)
SIGMA_REF = 1.5 * AS
MOUNT_JITTER = 3.0
GRID = np.linspace(0, 360, 4096, endpoint=False)


def series(x_deg, coef, k0=1):
    r = np.deg2rad(x_deg)
    out = np.zeros_like(r, dtype=float)
    for i, (a, b) in enumerate(coef):
        out = out + a * np.sin((i + k0) * r) + b * np.cos((i + k0) * r)
    return out


def hr(e):
    return (e.max() - e.min()) / 2


def cols(x_deg, ks):
    r = np.deg2rad(x_deg)
    return [f(k * r) for k in ks for f in (np.sin, np.cos)]


# ---- reference error models (callables of the encoder's own angle, degrees) ------------------
def ref_author(rng, peak=50.0):
    k = np.arange(1, 21)
    amp = np.where(k == 1, 1.0, np.where(k == 2, 0.4, 0.15 / k ** 0.7)) * rng.uniform(0.5, 1.0, 20)
    ph = rng.uniform(0, 2 * np.pi, 20)
    coef = np.column_stack([amp * np.cos(ph), amp * np.sin(ph)])
    coef *= peak * AS / np.abs(series(GRID, coef)).max()
    return lambda x: series(x, coef)


def ref_lines(rng, low=40.0, period_per_rev=2048, sde=8.0):
    """Optical-like: H1/H2 dominated low-order error + sub-divisional error at the line frequency."""
    base = ref_author(rng, low)
    p1, p2 = rng.uniform(0, 2 * np.pi, 2)
    return lambda x: (base(x) + sde * AS * np.sin(period_per_rev * np.deg2rad(x) + p1)
                      + 0.5 * sde * AS * np.sin(2 * period_per_rev * np.deg2rad(x) + p2))


def ref_pow2(rng, peak=50.0):
    """xMR-like spectrum: energy at H1, H2, H4, H8, H16 (the last two are blind at 8 mountings)."""
    ks = [1, 2, 4, 8, 16]
    amp = np.array([1.0, 0.5, 0.5, 0.3, 0.15]) * rng.uniform(0.5, 1.0, 5)
    ph = rng.uniform(0, 2 * np.pi, 5)
    f0 = lambda x: sum(a * np.sin(k * np.deg2rad(x) + p) for k, a, p in zip(ks, amp, ph))
    s = peak * AS / np.abs(f0(GRID)).max()
    return lambda x: s * f0(x)


def h12(rng, a1, a2):
    """Random-phase H1 + H2 error, amplitudes in arcsec."""
    p1, p2 = rng.uniform(0, 2 * np.pi, 2)
    return lambda x: (a1 * np.sin(np.deg2rad(x) + p1) + a2 * np.sin(2 * np.deg2rad(x) + p2)) * AS


ZERO = lambda x: np.zeros_like(np.asarray(x, dtype=float))


def random_module(rng):
    k = np.arange(1, 13)
    amp = rng.uniform(0.2, 1.0) * np.where(k <= 6, 1.0 / k, 0.02 / k) * rng.uniform(0.3, 1.0, 12)
    ph = rng.uniform(0, 2 * np.pi, 12)
    coef = np.column_stack([amp * np.cos(ph), amp * np.sin(ph)])
    return lambda x: series(x, coef)


# ---- the joint fit, returning both R_hat and M_hat -------------------------------------------
def self_calibrate(psi, theta_s, mount, n_mount, ks):
    d = (psi - theta_s + 180) % 360 - 180
    A = [(mount == j).astype(float) for j in range(n_mount)]
    A += cols(psi, ks) + [-c for c in cols(theta_s, ks)]
    A = np.column_stack(A)
    coef, *_ = np.linalg.lstsq(A, d, rcond=None)
    n = 2 * len(ks)
    r, m = coef[n_mount:n_mount + n], coef[n_mount + n:]
    ev = lambda x, c: sum(c[2 * i] * np.sin(k * np.deg2rad(x)) + c[2 * i + 1] * np.cos(k * np.deg2rad(x))
                          for i, k in enumerate(ks))
    return (lambda x: ev(x, r)), (lambda x: ev(x, m)), A


def measure(rng, th, gamma, beta, R, M, S, C, E, drift_factor, noise=True):
    kappa = th + beta
    phi = kappa + gamma + S(kappa) + C(kappa)
    psi = phi + R(phi) + E(phi) + (rng.normal(0, SIGMA_REF, th.size) if noise else 0)
    ts = th + 37.0 + drift_factor * M(th) + (rng.normal(0, SIGMA_MOD, th.size) if noise else 0)
    return psi % 360, ts % 360


def trial(rng, ref_gen=ref_author, S_amp=(0, 0), C_amp=(0, 0), E_amp=(0, 0), drift=0.0,
          stage_side=False, order=None, ks=None, n_mount=N_MOUNT, palindrome=False, include_P=False):
    ks = ks or [k for k in range(1, K_FIT + 1) if k % n_mount]
    R, M = ref_gen(rng), random_module(rng)
    S = h12(rng, *S_amp) if any(S_amp) else ZERO
    theta = np.arange(N_POS) * 360.0 / N_POS
    seq = list(order if order is not None else range(n_mount))
    if palindrome:
        seq = seq + seq[::-1]
    T = len(seq)                                   # time index of the production mounting = T
    psi, ts, mount = [], [], []
    nominal = {j: j * 360.0 / n_mount + rng.uniform(-MOUNT_JITTER, MOUNT_JITTER) for j in range(n_mount)}
    Cj = {j: (h12(rng, *C_amp) if any(C_amp) else ZERO) for j in range(n_mount)}
    Ej = {j: (h12(rng, *E_amp) if any(E_amp) else ZERO) for j in range(n_mount)}
    for t, j in enumerate(seq):
        th = theta + rng.uniform(0, 360.0 / N_POS)
        g, b = (0.0, nominal[j]) if stage_side else (nominal[j], 0.0)
        if palindrome and t >= n_mount:            # a second visit is a NEW clamping: new C_j, E_j
            Cj[j] = h12(rng, *C_amp) if any(C_amp) else ZERO
            Ej[j] = h12(rng, *E_amp) if any(E_amp) else ZERO
        p, s = measure(rng, th, g, b, R, M, S, Cj[j], Ej[j], 1 + drift * t / T)
        psi.append(p); ts.append(s); mount.append(np.full(N_POS, j))
    # production mounting P, nominal 22.5 deg, its own clamp errors, measured last
    gP = 22.5 + rng.uniform(-MOUNT_JITTER, MOUNT_JITTER)
    CP = h12(rng, *C_amp) if any(C_amp) else ZERO
    EP = h12(rng, *E_amp) if any(E_amp) else ZERO
    g, b = (0.0, gP) if stage_side else (gP, 0.0)
    th = theta + rng.uniform(0, 360.0 / N_POS)
    pP, sP = measure(rng, th, g, b, R, M, S, CP, EP, 1 + drift)
    if include_P:                                  # use mounting P in the fit (then step 5 is not independent)
        psi.append(pP); ts.append(sP); mount.append(np.full(N_POS, n_mount))
    Rh, Mh, A = self_calibrate(np.concatenate(psi), np.concatenate(ts), np.concatenate(mount),
                               n_mount + (1 if include_P else 0), ks)
    rho = (pP - Rh(pP) - sP + Mh(sP) + 180) % 360 - 180
    rho = rho - rho.mean()
    s5_raw = hr(rho)
    allk = [k for k in range(1, K_FIT + 1) if k % 8]   # H8/H16 of the residual are the MODULE's, not a fault
    c5, *_ = np.linalg.lstsq(np.column_stack([np.ones(N_POS)] + cols(pP, allk)), rho, rcond=None)
    fit5 = lambda x, kk=allk, c=c5: sum(c[1 + 2 * i] * np.sin(k * np.deg2rad(x)) + c[2 + 2 * i] * np.cos(k * np.deg2rad(x))
                                        for i, k in enumerate(kk))
    s5_harm = hr(fit5(GRID))
    # truth on a dense noise-free grid at mounting P
    pG, _ = measure(rng, GRID, g, b, R, M, S, CP, EP, 1 + drift, noise=False)
    e0 = (pG - GRID + 180) % 360 - 180
    before = hr(e0 - e0.mean())
    e1 = (pG - Rh(pG) - GRID + 180) % 360 - 180
    err = hr(e1)
    kT = [1, 2, 3]                                  # clamp-specific error is low order
    cT, *_ = np.linalg.lstsq(np.column_stack([np.ones(N_POS)] + cols(pP, kT)), rho, rcond=None)
    fitT = sum(cT[1 + 2 * i] * np.sin(k * np.deg2rad(pG)) + cT[2 + 2 * i] * np.cos(k * np.deg2rad(pG))
               for i, k in enumerate(kT))
    e2 = (pG - Rh(pG) - fitT - GRID + 180) % 360 - 180
    return before / AS, err / AS, s5_raw / AS, s5_harm / AS, hr(e2) / AS, A


def run(label, n, seed=7, **kw):
    rng = np.random.default_rng(seed)
    res = np.array([trial(rng, **kw)[:5] for _ in range(n)])
    q = lambda c: f"{np.median(res[:, c]):6.1f}/{res[:, c].max():6.1f}"
    print(f"{label:<58} {q(0)}  {q(1)}  {q(2)}  {q(3)}  {q(4)}")
    return res


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    print(f"{n} trials each; all figures arcsec half-range, median/max.  err = true error of theta_true on the")
    print("production mounting after R_hat;  s5 = step-5 statistic (raw / harmonic);  err_T = after folding")
    print("the production-mounting residual back in.\n")
    print(f"{'scenario':<58} {'before':>13}  {'err':>13}  {'s5_raw':>13}  {'s5_harm':>13}  {'err_T':>13}")

    print("-- 0. author's model"); run("baseline (ref_selfcal.py assumptions)", n)
    rng = np.random.default_rng(1); A = trial(rng)[5]
    An = A / np.linalg.norm(A, axis=0)
    sv = np.linalg.svd(An, compute_uv=False)
    print(f"   design matrix {A.shape}, column-normalised condition number {sv[0] / sv[-1]:.2f}")
    ks_all = list(range(1, K_FIT + 1))
    A2 = trial(rng, ks=ks_all)[5]; A2n = A2 / np.linalg.norm(A2, axis=0)
    sv2 = np.linalg.svd(A2n, compute_uv=False)
    print(f"   with H8 and H16 included (observable only through the +-3 deg jitter): cond {sv2[0] / sv2[-1]:.1f}")
    run("   H8,H16 included in the fit", n, ks=ks_all)
    run("   noise only (R tail off: H1,H2 reference)", n, ref_gen=lambda r: h12(r, 40, 15))

    print("-- 1. reference spectrum the fit cannot represent")
    run("optical-like: 40\" low order + 8\" SDE at 2048/rev", n, ref_gen=ref_lines)
    run("nonius-like: 40\" low order + 20\" at 32/rev", n, ref_gen=lambda r: ref_lines(r, 40, 32, 20))
    run("xMR-like: H1,2,4,8,16 (50\" peak)", n, ref_gen=ref_pow2)
    run("   same, mounting P (22.5 deg) in the fit, H8 fitted", n, ref_gen=ref_pow2, include_P=True,
        ks=[k for k in range(1, K_FIT + 1) if k != 16])
    run("author spectrum, 200\" peak (magnetic, mis-rated)", n, ref_gen=lambda r: ref_author(r, 200))

    print("-- 2. coupling transfer error tied to the coupling body (invariant under encoder-side remount)")
    for a in (6, 13, 40):
        run(f"S = {a}\" H1 + {a/2:.0f}\" H2, remount at ENCODER side (spec)", n, S_amp=(a, a / 2))
    run("S = 40\" H1 + 20\" H2, remount at STAGE side", n, S_amp=(40, 20), stage_side=True)

    print("-- 3. error that changes with every re-clamping")
    for a in (3, 10, 30):
        run(f"C_j = {a}\" H1 + {a/2:.0f}\" H2 per remount (coupling)", n, C_amp=(a, a / 2))
    for a in (10, 70):
        run(f"E_j = {a}\" H1 per remount (kit / hollow-shaft reference)", n, E_amp=(a, 0))

    print("-- 4. module error drifting during the session (fraction of M over the whole session)")
    for d in (0.003, 0.01, 0.03):
        run(f"drift {100*d:.1f} %, mount order 0..7", n, drift=d)
    run("drift 1.0 %, order 0,4,2,6,1,5,3,7", n, drift=0.01, order=[0, 4, 2, 6, 1, 5, 3, 7])
    run("drift 1.0 %, palindrome 0..7,7..0 (16 turns)", n, drift=0.01, palindrome=True)
    run("drift 3.0 %, palindrome 0..7,7..0 (16 turns)", n, drift=0.03, palindrome=True)

    print("-- 5. combined, plausible low-cost station")
    run("S 20/10, C_j 5/2.5, drift 1 %, optical-like ref", n, ref_gen=ref_lines, S_amp=(20, 10),
        C_amp=(5, 2.5), drift=0.01)
    run("same, STAGE-side remount + palindrome", n, ref_gen=ref_lines, S_amp=(20, 10),
        C_amp=(5, 2.5), drift=0.01, stage_side=True, palindrome=True)
