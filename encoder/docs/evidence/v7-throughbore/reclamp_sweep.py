# Copyright 2026 Eckstein GmbH
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# ---------------------------------------------------------------------------
# MODIFICATION NOTICE
# New file, not present in upstream OpenArm.
# ---------------------------------------------------------------------------
"""Can the commissioning of spec section 7.7 survive a through-bore reference encoder?

The station was redesigned around two through-bore grating encoders clamped on one
precision shaft, because the through-bore parts available at this price are about an
order of magnitude better on paper than the solid-shaft ones. Section 7.7 warns against
exactly that ("a hollow-shaft or kit encoder breaks the method for H1"), and the warning
is about REPEATABILITY, not accuracy: a clamped-on encoder's rotor-to-stator eccentricity
is set by each clamping, and set A of the commissioning re-clamps the reference ten times.
An eccentricity of e at grating radius r is an H1 error of about e/r -- 1 um at r = 25 mm
is 8.25 arcsec, so a re-clamp repeatable to a few micrometres is already tens of arcsec.

This sweeps that. Two procedures:

  v6      set A (reference re-clamped at 10 angles, out and back) + set B (horn re-clocked)
          -- exactly ref_selfcal.py, whose clamp=(h1,h2) IS the per-clamping error

  B-only  the reference is clamped ONCE and never touched again; only the horn is
          re-clocked. R' and S2 can then no longer be separated -- both sit in the psi
          frame at a fixed gamma -- but production never needs them separately, because it
          always runs on that one mounting. The fit absorbs their sum.

Run:  python reclamp_sweep.py [trials] [stations]
"""

import importlib.util
import pathlib
import sys

import numpy as np

_REF = pathlib.Path(__file__).resolve().parents[1] / "v3-reference" / "ref_selfcal.py"
_spec = importlib.util.spec_from_file_location("ref_selfcal", _REF)
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)

AS = R.AS
CHECK_B_ANGLE = 100.0          # a horn clocking not used in the fit, for the B-only check


def trial_b_only(rng, s1, s2, clamp=(0, 0), drift=0.0, sde=0.0, s2_unit=0.0,
                 b_angles=None, post_shift=(0, 0), want_cond=False):
    """The reference is clamped once. Only the horn moves. Same returns as R.trial().

    post_shift is what B-only gives up: the reference mounting shifting AFTER
    commissioning -- a bump, a thermal cycle, a bushing letting go. v6 at least
    measures how repeatable the clamping is across ten of them; B-only never
    re-clamps, so it cannot see a later change. Nothing in the commissioning
    catches this; only the second encoder does."""
    b_angles = R.B_ANGLES if b_angles is None else b_angles
    st = R.Station(rng, s1, s2, clamp, sde, s2_unit, v5=False)
    M = R.random_module(rng)
    delta0 = rng.uniform(0, 360)
    jit = lambda a: a + rng.uniform(-R.JITTER, R.JITTER)

    gamma = rng.uniform(0, 360)                     # the one and only reference mounting
    clamp0 = st.clamp()                             # its one and only clamping error
    seq = [("B", gamma, jit(delta0 + b), clamp0, st.s2_now()) for b in b_angles + b_angles[::-1]]
    seq.insert(len(seq) // 2, ("check", gamma, jit(delta0 + CHECK_B_ANGLE), clamp0, st.s2_now()))

    T = len(seq)
    data = [st.turn(g, d, M, ct, s2t, mscale=1 + drift * i / (T - 1))
            for i, (_, g, d, ct, s2t) in enumerate(seq)]
    fit_idx = [i for i, q in enumerate(seq) if q[0] != "check"]
    chk = next(i for i, q in enumerate(seq) if q[0] == "check")

    # with_s2=False: R' + clamp0 - S2(.-gamma) are one curve in psi, which is all production needs
    turns = [(data[i][0], data[i][1], 0.0) for i in fit_idx]
    c, r, m, s2h, cond = R.fit(turns, with_s2=False, want_cond=want_cond)

    shifted = clamp0 + R.low_order(rng, *post_shift)
    psi, _, th_h = st.turn(gamma, rng.uniform(0, 360), R.random_module(rng), shifted, st.s2_now())
    est = psi - R.series(psi, r)

    repro = np.sqrt(np.mean([R.low_amps(t[0], R.residual(t[0], t[1], t[2], r, m, s2h), 3) ** 2
                             for t in turns]))
    pc, tc, _ = data[chk]
    check = R.low_amps(pc, R.residual(pc, tc, 0.0, r, m, s2h), 7).max()

    e = R.wrap(est - th_h)
    e = R.wrap(e - R.circ_mean(e))
    A = np.column_stack([np.ones_like(th_h)] + R.harm(th_h, range(1, 7)))
    low = A @ np.linalg.lstsq(A, e, rcond=None)[0]
    return (R.half_range(psi - th_h) / AS, R.half_range(est - th_h) / AS, cond,
            repro / AS, check / AS, R.half_range(low) / AS)


BASE = dict(s1=(40, 20), s2=(6, 3), drift=0.01, sde=8, s2_unit=0.3)
CLAMPS = [(0, 0), (3, 2), (8, 4), (16, 8), (25, 12), (40, 20), (60, 30), (90, 45)]
DENSE_B = [0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330]


def scaled(kw):
    """R.scaled() converts s1/s2/clamp/sde from arcsec to degrees but knows nothing
    about post_shift, which is ours. Scaling it here rather than editing ref_selfcal.py,
    which is the artefact section 7.7's published numbers were measured on."""
    out = R.scaled({k: v for k, v in kw.items() if k != "post_shift"})
    if "post_shift" in kw:
        out["post_shift"] = tuple(x * AS for x in kw["post_shift"])
    return out


def run(fn, kw, n, seed):
    rng = np.random.default_rng(seed)
    return np.array([fn(rng, **scaled(kw)) for _ in range(n)])


def row(label, res):
    pr, pk = res[:, 3] <= R.REPRO_MAX, res[:, 4] <= R.CHECK_MAX
    both = pr & pk
    worst = res[both, 1].max() if both.any() else float("nan")
    worst_low = res[both, 5].max() if both.any() else float("nan")
    print(f"{label:30s} {np.median(res[:, 1]):7.1f}/{res[:, 1].max():6.1f} "
          f"{np.median(res[:, 5]):6.1f}/{res[:, 5].max():6.1f} "
          f"{np.median(res[:, 3]):6.1f} {np.median(res[:, 4]):6.1f} "
          f"{100 * both.mean():7.1f}% {worst:8.1f} /{worst_low:6.1f}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    print(__doc__.split("Run:")[0].rstrip())
    print(f"\n{n} stations per row. Errors are the half-range of theta_true at the horn on a")
    print("production turn with a fresh, freshly fixtured unit, in arcsec. C1 40+20, C2 6+3,")
    print(f"artefact drift 1 %, sub-divisional error 8 arcsec, C2 varies 30 % per fixturing.")
    print("criteria: repro <= 8, check <= 12 arcsec.\n")

    print("re-clamp error, as eccentricity at a 25 mm grating radius:")
    for h1, _ in CLAMPS:
        print(f"    {h1:3d} arcsec  =  {h1 / 8.25:5.2f} um", end="" if h1 % 40 else "\n")
    print("\n")

    hdr = (f"{'re-clamp H1+H2 (arcsec)':30s} {'after med/max':>14s} {'H1-6 med/max':>13s} "
           f"{'repro':>6s} {'check':>6s} {'pass both':>8s} {'worst passing':>17s}")

    print("PROCEDURE v6 -- set A re-clamps the reference 10 times, out and back, + set B")
    print(hdr)
    for cl in CLAMPS:
        row(f"clamp {cl[0]}+{cl[1]}", run(R.trial, dict(BASE, clamp=cl), n, 11))

    print(f"\nPROCEDURE B-only -- reference clamped once; {len(R.B_ANGLES)} horn clockings, out and back")
    print(hdr)
    for cl in CLAMPS:
        row(f"clamp {cl[0]}+{cl[1]}", run(trial_b_only, dict(BASE, clamp=cl), n, 11))

    print(f"\nPROCEDURE B-only, denser -- {len(DENSE_B)} horn clockings, out and back")
    print(hdr)
    for cl in CLAMPS:
        row(f"clamp {cl[0]}+{cl[1]}",
            run(trial_b_only, dict(BASE, clamp=cl, b_angles=DENSE_B), n, 11))

    print("\nWhat B-only gives up: the reference mounting shifts AFTER commissioning.")
    print("Nothing in the commissioning can see this -- the criteria are computed before it")
    print("happens. Only the second encoder can, by disagreeing with the first.")
    print(hdr.replace("re-clamp H1+H2 (arcsec)", "post-commissioning shift  "))
    for sh in [(0, 0), (3, 2), (8, 4), (16, 8), (25, 12), (40, 20)]:
        row(f"shift {sh[0]}+{sh[1]}  ({sh[0] / 8.25:.1f} um)",
            run(trial_b_only, dict(BASE, clamp=(25, 12), post_shift=sh), n, 11))
