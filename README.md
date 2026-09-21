# OpenArm KER firmware — calibrated encoder fork

> **This is a fork** of [enactic/openarm_ker_firmware](https://github.com/enactic/openarm_ker_firmware),
> maintained by Eckstein GmbH. It adds a **per-unit angle calibration** to the encoder: a harmonic
> correction fitted at a calibration station, stored in the ATtiny1616's USERROW and applied on the
> module, together with a locked sensor configuration, health monitoring and a bench-only diagnostic
> sub-protocol.
>
> **It changes nothing an M5 can see.** The wire format, the reply semantics and the chain timing are
> untouched, `M5/` is byte-identical to upstream, and a module with no calibration written is
> bit-exact with upstream on CMD=1 and CMD=2 over all 32768 sensor codes. Only `encoder/` differs —
> three upstream files modified, the rest added.
>
> **Nothing in the fork has run on hardware yet.** Every figure it quotes is either measured
> off-target (the arithmetic, the resource usage, the simulations) or reasoned from datasheets.
>
> **Start at [`encoder/docs/development.md`](encoder/docs/development.md)** — setup, repository map,
> where the work stands and what to do next. The design is
> [`encoder/docs/protocol-spec.md`](encoder/docs/protocol-spec.md); what was built and what it costs
> is [`encoder/CHANGELOG.md`](encoder/CHANGELOG.md); how to build the bench and the calibration
> station is [`encoder/docs/bench-and-station.md`](encoder/docs/bench-and-station.md).
>
> Questions about **this fork** belong in its own issue tracker, not in the upstream channels below.

OpenArm KER has 2 firmware:

* [Encoder](encoder/) that collects sensor data and streams them to M5 — **modified by this fork**
* [M5](M5/) that receives streamed sensor data and streams them to PC — untouched

## Why this fork exists

The KER encoder reads a TLE5012B through a Ø3 mm diametric magnet. Most of its angle error is not
noise and not the die — it is a **repeatable function of the module's own angle**, dominated by how
that small magnet ended up sitting relative to the sensor:

| Contribution | Size | Source |
|---|---|---|
| die alone, autocalibration off | 0.6° typical, 1.6° maximum | data sheet, `§2.7` |
| magnet assembly error, Ø3 mm | 0.15–1.5° in simulation, mostly H1 and H2 | `§2.8` |
| raw error of an assembled unit | 2–3° plausible | `§2.8` — **to be measured, `O1`** |

Error shaped like that is exactly what a stored per-unit correction can remove. This fork fits six
harmonics per unit at a calibration station, stores them in the MCU's USERROW, and applies them on
the module in integer arithmetic. What is left is what no static curve can remove: per-reading
noise, direction hysteresis, stray fields from the world, and temperature.

## What it costs to adopt: nothing on the M5 side

| | |
|---|---|
| M5 firmware changes | **none.** `M5/` is byte-identical to upstream |
| protocol changes | **none.** CMD=0/1/2 wire format, reply semantics and chain timing unchanged |
| wiring or hardware changes | **none** |
| mixed arms | supported — calibrated and uncalibrated modules on the same chain |
| an uncalibrated module | **bit-exact with upstream** over all 32768 sensor codes |
| cost on the MCU | +7.7 kB flash, +280 B RAM; 62.5 % of flash and 22.4 % of RAM used in total |

Compatibility is not a claim here, it is a constraint the design was built under, and
[`encoder/docs/compatibility-checklist.md`](encoder/docs/compatibility-checklist.md) is 40 numbered
statements of it, each marked either *desk* or *measured*.

## Useful even if you never calibrate anything

Several changes have nothing to do with calibration and apply to any module:

- **The sensor configuration is written and read back at boot.** Upstream writes no sensor register
  at all, so a module runs whatever the part powers up with — on the E1000, autocalibration mode 1,
  prediction on, FIR_MD 1. Autocalibration silently adapts the curve; this fork turns it off,
  turns prediction off, sets FIR_MD 2 for 0.05° instead of 0.08° of noise per reading, and verifies
  it took.
- **Every read is checked.** Upstream reads `AVAL` alone and never clocks in the safety word the
  sensor already sends. This fork reads `STAT`, `ACSTAT`, `AVAL` and the safety word in one
  transaction, checks the CRC and the status bits, and holds or flags a bad reading (`§6.2`).
- **Identity comes from the chip, not the build.** One image is flashed to every module and takes
  its ID from the USERROW. Upstream's build-flag fallback is ID 1 — the ID that answers the M5's own
  trigger, so a board flashed without the flag impersonates joint 1 rather than staying silent.
- **You can ask a module what is wrong with it.** Health flags, error counters, the sensor's
  temperature and supply, the configuration read-back and its serial number, over a bench-only
  sub-protocol whose every reply is addressed to ID 0 — which an M5 discards unconditionally.

## What this fork does not claim

Stated plainly, because the difference matters:

- **Nothing has run on hardware yet.** Every figure is measured off-target — the arithmetic, the
  resource usage, the simulations — or reasoned from datasheets. The bench work is
  [`encoder/docs/timing-measurements.md`](encoder/docs/timing-measurements.md) and the open
  questions are `§12.2`.
- **0.02° is a station gate, not an accuracy.** It is measured relative to the station's own
  reference, at station conditions, and the station is self-consistent but **not traceable**.
- **In use on an assembled arm, the reviews estimate 0.1–0.4°**, dominated by stray fields from
  neighbouring joints, hysteresis and temperature. Only a measurement on a real arm settles it
  (`§9.6`). This fork improves the systematic, repeatable part of the error; it does not make a
  0.02° robot.

Thirteen review passes — protocol, numerics, sensor physics, station metrology, system budget, four
specification verifications and the firmware itself — are in
[`encoder/docs/reviews/`](encoder/docs/reviews/) with their seven responses. They are kept because
most of what the design now says was learned by being wrong first.

## Related links

- 📚 Read the [documentation](https://docs.openarm.dev/hardware/openarm-ker/general)
- 💬 Join the community on [Discord](https://discord.gg/FsZaZ4z3We)
- 📬 Contact us through <openarm@enactic.ai>

## License

Licensed under the Apache License 2.0. See [LICENSE.txt](LICENSE.txt) for details.

Copyright 2026 Enactic, Inc.

Files added by this fork are Copyright 2026 Eckstein GmbH, under the same licence. Files that came
from upstream keep Enactic's notice and carry a modification notice saying what changed;
`encoder/src/ker_ssc.h` keeps the upstream notice although it is a new file, because its contents
were moved out of `encoder/src/main.cpp` unchanged.

## Code of Conduct

All participation in the OpenArm project is governed by our [Code of Conduct](CODE_OF_CONDUCT.md).
