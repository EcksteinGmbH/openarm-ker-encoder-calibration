# Through-bore reference: what it costs the commissioning

`reclamp_sweep.py` → `reclamp_sweep.txt`. Run it with the project venv:

```bash
cd encoder
OPENBLAS_NUM_THREADS=1 .venv/bin/python docs/evidence/v7-throughbore/reclamp_sweep.py 200
```

## The question

The station was redesigned around **two through-bore grating encoders clamped on one precision
shaft**, because the through-bore parts available at this price are about an order of magnitude
better on paper than the solid-shaft ones. `protocol-spec.md` §7.7 warns against exactly that — *"a
hollow-shaft or kit encoder breaks the method for H1"* — and the warning is about **repeatability,
not accuracy**: a clamped-on encoder's rotor-to-stator eccentricity is set by each clamping, and
**set A of the commissioning re-clamps the reference ten times**.

Eccentricity `e` at grating radius `r` is an H1 error of about `e/r`. At `r` = 25 mm, **1 µm is
8.25″** — so a clamp repeatable to a couple of micrometres already costs tens of arcseconds.

## The answer, measured

200 simulated stations per row, on top of the `GOOD` station of §7.7 (C1 40″+20″, C2 6″+3″, artefact
drift 1 %, sub-divisional error 8″, C2 varying 30 % per fixturing). Criteria as §7.7: reproducibility
≤ 8″, check ≤ 12″.

**v6 procedure** — set A re-clamps the reference ten times, out and back, then set B:

| re-clamp error | ≈ eccentricity | θ_true after, med/max | of which H1–H6 | passes both |
|---|---|---|---|---|
| 0″ | 0 µm | 14.3″ / 18.8″ | 4.8″ / 8.5″ | 100 % |
| 3″+2″ | 0.4 µm | 14.4″ / 18.3″ | 4.7″ / 9.2″ | 100 % |
| 8″+4″ | 1.0 µm | 14.6″ / 20.3″ | 5.1″ / 11.2″ | **93.5 %** |
| 16″+8″ | 1.9 µm | 16.0″ / 23.6″ | 7.0″ / 14.5″ | **2.5 %** |
| 25″+12″ | 3.0 µm | 18.4″ / 27.2″ | 9.5″ / 18.2″ | **0 %** |
| 40″+20″ and worse | ≥ 4.8 µm | 23.1″ → 39.2″ | 14.4″ → 31.2″ | 0 % |

**B-only** — the reference is clamped **once** and never touched; only the horn is re-clocked:

| re-clamp error | θ_true after, med/max | of which H1–H6 | repro | check | passes both |
|---|---|---|---|---|---|
| 0″ through 90″+45″ | **13.4″ / 17.2″**, unchanged at every level | **3.4″ / 6.5″** | 3.3″ | 2.5″ | 100 % |

Flat. The clamping error simply becomes part of the fixed reference curve and is fitted out with
everything else, because it never changes. Twelve horn clockings instead of eight improve it a
little further: 12.9″ / 16.7″, H1–H6 3.3″ / 5.8″.

B-only is also **slightly better than v6 at zero clamp error** — 3.4″ against 4.8″ in H1–H6 — because
v6's twenty-one extra set-A turns each carry a fresh clamping error into the fit.

## What B-only gives up, and who covers it

B-only cannot separate `R′` from `S2`; both sit in the ψ frame at one fixed γ. Production never needs
them separately, because it always runs on that one mounting — which is exactly why it works, and
exactly what it risks. **If the reference's mounting shifts after commissioning, nothing in the
commissioning can see it**: the criteria were computed before it happened.

B-only at clamp 25″+12″, with the mounting disturbed afterwards:

| shift | θ_true after, med/max | of which H1–H6 | repro | check | passes both |
|---|---|---|---|---|---|
| none | 13.4″ / 17.2″ | 3.4″ / 6.5″ | 3.3″ | 2.5″ | 100 % |
| 0.4 µm | 15.1″ / 19.5″ | 5.5″ / 9.9″ | 3.3″ | 2.5″ | 100 % |
| 1.0 µm | 20.1″ / 23.6″ | **10.7″** / 15.9″ | 3.3″ | 2.5″ | 100 % |
| 1.9 µm | 29.3″ / 33.6″ | **20.1″** / 26.2″ | 3.3″ | 2.5″ | 100 % |
| 3.0 µm | 39.4″ / 44.8″ | 30.7″ / 37.5″ | 3.3″ | 2.5″ | 100 % |
| 4.8 µm | 57.6″ / 64.6″ | 49.5″ / 57.4″ | 3.3″ | 2.5″ | 100 % |

**A one-micrometre shift triples the error that can reach a module, and every criterion still reads
green.** The reproducibility and check columns do not move at all, because they are properties of
the commissioning run, not of the station afterwards.

This is what the **second encoder** is for, and it turns it from a recommendation into a
requirement: two encoders on one rigid shaft see the same mechanical angle, so their difference is
the only thing in the station that can notice one of them moving. Clock them 90° apart, or their
sub-divisional errors may cancel in exactly the comparison that is supposed to catch this.

## Status

Not yet independently verified, and not yet folded into §7.7 as normative. It is recorded here, and
§7.7 carries a pointer.
