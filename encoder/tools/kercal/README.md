# kercal

Deliverable 4: the host library and CLI for the calibrated OpenArm KER encoder. It provisions
modules, calibrates them against a station reference, and reads everything a module can report.

```bash
cd encoder
.venv/bin/python -m kercal --help          # with tools/kercal on PYTHONPATH, or from tools/kercal/
```

Needs Python 3.9+, `numpy`, and `pyserial` for anything that touches a port. The offline
commands (`fit`, `limits`) need neither a port nor pyserial.

## Read this before connecting it to anything

An unmodified M5 parses **any** frame with ID 1–16 as a joint angle. A request this tool sends
to a module on a live arm bus is, to the M5, a joint that has moved. During zeroing it is
worse (spec §1.6).

So: **never connect this tool to a bus with an M5 on it.** The tool enforces what it can —
it listens for 200 ms before its first transmission and refuses to start if anything is
talking, and any CMD=2 frame it ever sees poisons the session permanently (§3.2, C4) — but
those are backstops, not permission. `kercal listen` transmits nothing and is the only command
that is safe on an arm.

During provisioning and calibration, exactly one module is on the bus (§3.4).

## Commands

| | |
|---|---|
| `listen` | passive; reports what is on the bus and whether it is a bench bus |
| `scan` | PING every ID |
| `info --id N` | firmware, health, calibration status, configuration lock, environment, counters, trim, serial number |
| `page --id N [--running]` | the calibration page, decoded to degrees; `--running` reads what the module is using rather than what is stored |
| `sample --id N -e 10` | K = 2ᵉ averaged readings on the module (§4.10) |
| `set-id --id N --new-id M` | assign an ID, leaving any calibration intact |
| `write-page --id N --page f` | unlock, stage, commit, read back — and fail loudly if the read-back differs |
| `clear-counters --id N` | CLR_ERRCNT |
| `fit run.csv --id N --sigma-mean σ` | offline: fit, grade and page from a recorded run. No hardware |
| `limits` | the station constants of §7.2, and which file they come from |

## Layout

| | |
|---|---|
| `kercal/protocol.py` | frames, subcommands, the USERROW page, CRC-16, payload decoding. Pure functions; no I/O |
| `kercal/link.py` | the serial transport and the host discipline C4 |
| `kercal/module.py` | one module: every subcommand, with the ordering rules of §4.3 and the unlock sequence of §4.9 |
| `kercal/fit.py` | **loads** `docs/evidence/v3-reference/station_fit.py` and re-exports it |
| `kercal/station.py` | the calibration run of §7.2 end to end, and the records of §9.7 |
| `kercal/cli.py` | the command line |
| `tests/` | run with `python -m unittest discover -s tools/kercal/tests` |

`fit.py` deliberately contains no second implementation of the fit. The spec names
`station_fit.py` as the golden reference, and every number in §7.2 — the mounting-offset
table, the operating characteristic, the grade boundaries — was measured on it. A copy here
would be a second thing to keep right.

## Calibrating a unit

`station.run_calibration()` drives §7.2 steps 1–10, but it needs a `Reference`: the station's
own rotary stage and reference encoder, behind three methods (`move_to`, `read`,
`wait_stationary`). That part is hardware-specific and is not supplied. `docs/protocol-spec.md`
§7.7 and `docs/station-reference-encoder.md` specify the chain it must implement, including
why there are two couplings and why the approach must never overshoot.

Everything above the reference — the pass order, the pooled two-direction fit, the commit, the
out-of-sample validation, the grade and the centring gate — is here and is tested.

## Tested against the firmware, not against itself

`tests/test_protocol.py` compiles `src/ker_cal.c` and `src/ker_comp.c` and compares:
the CRC-16 over random data; page validation over a corpus that hits every check of §5.2 in
both directions; and a full round trip — fit a synthetic part, build the page, decode it as the
module will, and run the module's own `ker_compensate()` on it. A tool that agreed only with
its own idea of the format would write pages a module rejects, or accept ones it should not.
