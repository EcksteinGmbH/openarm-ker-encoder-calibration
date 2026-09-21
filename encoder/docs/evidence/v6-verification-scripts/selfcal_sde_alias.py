"""v6 verification: is the 'sub-divisional error 8 arcsec' in ref_selfcal.py rows 3-8 actually exercised?

ref_selfcal.py models SDE as sde*sin(2048*enc + phase) and samples 256 positions at EXACT multiples of 360/256 deg
(plus one offset per turn). 2048 * 360/256 = 2880 deg = 8 full periods, so every position of a turn sees the SAME
SDE phase: the term is a per-turn constant, absorbed by c_turn and removed by half_range(). It is numerically inert.
A real stepper stage does not land on exact multiples (+-3 arcmin typical = a large fraction of the 633 arcsec line
period), so on hardware the SDE appears in full as position-to-position scatter of theta_true.

This script re-runs spec row 4 (good station) three ways: as simulated; with sde = 0; with sde = 8 arcsec and a stage
position error of 0.03 deg rms (so the SDE phase is no longer frozen). Station.turn is re-implemented to add the jitter.

    OPENBLAS_NUM_THREADS=1 ../../../.venv/bin/python selfcal_sde_alias.py [trials]
"""
import pathlib, sys
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "v3-reference"))
import ref_selfcal as rs  # noqa: E402

AS = rs.AS
STAGE_JITTER = 0.0


def turn(self, gamma, delta, M, clampterm, s2=None, mscale=1.0):
    rng = self.rng
    th = np.arange(rs.N_POS) * 360.0 / rs.N_POS + rng.uniform(0, 360.0 / rs.N_POS)
    if STAGE_JITTER:
        th = th + rng.normal(0, STAGE_JITTER, rs.N_POS)
    enc = th + gamma
    err = rs.series(enc, self.R) + rs.series(enc, clampterm) + self.sde * np.sin(np.deg2rad(2048 * enc) + self.sde_phase)
    err = err + (rs.series(th, self.S1) if self.v5 else rs.series(enc, self.S1))
    psi = (enc + err + rng.normal(0, rs.SIGMA_REF, rs.N_POS)) % 360
    th_h = th + delta + rs.series(th, self.S2 if s2 is None else s2)
    ts = (th_h + 37.0 + mscale * rs.series(th_h, M) + rng.normal(0, rs.SIGMA_MOD, rs.N_POS)) % 360
    return psi, ts, th_h


rs.Station.turn = turn


def run(name, n, jitter, **kw):
    global STAGE_JITTER
    STAGE_JITTER = jitter
    rng = np.random.default_rng(7)
    kw = {k: (tuple(x * AS for x in v) if k in ("s1", "s2", "clamp") else v * AS if k == "sde" else v) for k, v in kw.items()}
    res = np.array([rs.trial(rng, **kw) for _ in range(n)])
    print(f"{name:64s} after med/max {np.median(res[:,1]):5.1f}/{res[:,1].max():5.1f}   repro med/max {np.median(res[:,3]):5.1f}/{res[:,3].max():5.1f}"
          f"   check med/max {np.median(res[:,4]):5.1f}/{res[:,4].max():5.1f}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    base = dict(s1=(40, 20), s2=(10, 5), clamp=(3, 2), drift=0.01, s2_unit=0.3)
    print(f"spec row 4 (v6; clamp 3+2, drift 1 %, C2 10+5 differing 30 % per unit); {n} trials; arcsec")
    run("as in ref_selfcal.py: SDE 8, exact 360/256 grid", n, 0.0, sde=8, **base)
    run("SDE 0, exact grid", n, 0.0, sde=0, **base)
    run("SDE 80 (absurd), exact grid  -> still no effect = inert", n, 0.0, sde=80, **base)
    run("SDE 8, stage position error 0.03 deg rms", n, 0.03, sde=8, **base)
    run("SDE 0, stage position error 0.03 deg rms (control)", n, 0.03, sde=0, **base)
