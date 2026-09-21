# CLAUDE.md

Fork of `enactic/openarm_ker_firmware` (Apache-2.0) that adds a per-unit harmonic calibration to the
OpenArm KER encoder module. Published at `EcksteinGmbH/openarm-ker-encoder-calibration`.

**Read `encoder/docs/development.md` first.** It is the handover document: setup, repository map,
where the project stands, and what to do next. `encoder/docs/protocol-spec.md` is the reference —
§12 holds the decision log (D1–D28) and the open questions (O1–O6). This file is only the rules.

## Hard rules

- **Never modify `M5/`.** It must stay byte-identical to upstream. It cannot be deleted either: the
  compatibility argument cites `M5/include/AngleProcessor.h:68-72` and `M5/src/main.cpp:425`.
  All work happens under `encoder/`. The only files this fork adds outside it are `CLAUDE.md` and
  `.gitignore`, which are tooling, not source.
- **Never commit `.venv/`, `.pio/` or `.omc/`.** `encoder/.venv` alone is 114 MB of
  machine-specific files. The repository is under 2.5 MB and already carries the whole project;
  there is no local state worth migrating between machines.
- **`encoder/src/ker_comp.c` must stay byte-for-byte identical** to
  `encoder/docs/evidence/v3-reference/ref_comp.c` apart from the include names. Every accuracy
  figure in spec §7.5 was measured on that file, and `encoder/test/run_tests.sh` fails if they
  drift. Change one, change both, then re-run `encoder/docs/evidence/v3-reference/regen_results.sh`.
- **Mark every claim.** *measured* means a command in the repository reproduces it; anything else
  says so explicitly. A number that is neither is a defect, not a style problem.
- **Nothing has ever run on hardware.** Do not write "verified", "confirmed" or "working" about
  anything touching a TLE5012B, an RS-485 bus or an M5. Say what was actually done.
- **Licence headers.** Files from upstream keep `Copyright 2026 Enactic, Inc.` plus a modification
  notice; new files are `Copyright 2026 Eckstein GmbH`. `encoder/src/ker_ssc.h` keeps the upstream
  notice because its contents were moved out of `main.cpp` unchanged.
- **Commit only when asked.**

## Git

Work on `calibration`, the default branch. **`main` is kept equal to upstream** so that "Sync fork"
keeps working and a small upstream PR can be cut from a clean base — the fork relationship is
deliberate (spec §12 and the README explain why). Do not merge work into `main`.

**On GitHub, a new PR defaults its base to `enactic/openarm_ker_firmware`.** Check the base before
opening one, or an internal review lands on the upstream project.

## Commands

```bash
cd encoder
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt   # first time
.venv/bin/pio run                    # build: expect 10237 B flash, 459 B RAM from a clean checkout
cd test && ./run_tests.sh            # 16 checks, ~3 min; needs simavr and gcc
.venv/bin/python -m unittest discover -s tools/kercal/tests
```

A missing tool is reported as SKIP, never PASS. If the build size differs, the toolchain moved —
say so rather than editing the number in the docs.

## Traps specific to this codebase

- **`int` is 16 bits on the ATtiny1616 and 32 on the host.** A missing `int32_t` cast passes every
  host test and is wrong on the target. That is what the AVR differential test and its three
  generated mutants exist for; they are not decoration.
- **The compensated output must stay a multiple of 8 LSB** (D22, spec §7.1). The M5 integrates
  float32 differences and never re-references, so finer steps make the joint angle drift for hours.
  Any change to `ker_compensate()`'s rounding must keep `test/run_tests.sh` section 5 passing.
- **`DEVICE_ID` is no longer a build flag.** One image is flashed to every module; it boots as 31
  and takes its real ID from the USERROW page. `-DDEVICE_ID=n` still builds an upstream-compatible
  module, but such a module answers at *n* regardless of what is stored.
- **`main.cpp` stays as close to upstream as possible.** New behaviour goes in new `ker_*` files
  behind the four entry points it already calls. Each existing edit is marked `fork`.
- **CMD=3 is bench-only and can move a robot if misused.** Every reply is addressed to ID 0, which
  the M5 discards; a host *request* with ID 1–16 on a live arm bus is parsed as a joint angle.
  `encoder/tools/kercal/` enforces the host discipline — do not work around it.

## Ignore rules

Repository-wide rules live in the root `.gitignore`. `M5/.gitignore` and `encoder/.gitignore` are
upstream's and are left exactly as upstream wrote them — anything this fork needs to ignore goes in
the root file, so the diff against upstream stays as small as possible. Note that
`encoder/firmware/*.hex` is tracked upstream, so no blanket build-output rule may be added.
