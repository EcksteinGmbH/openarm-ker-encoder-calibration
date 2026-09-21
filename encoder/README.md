# OpenArm KER Encoder — calibrated fork

ATtiny1616 firmware. Reads a TLE5012B magnetic angle sensor over SSC and streams it over RS485 (chainable, multi-device).

> **This is a fork**, maintained by Eckstein GmbH, of
> [enactic/openarm_ker_firmware](https://github.com/enactic/openarm_ker_firmware) (Apache-2.0).
> It adds a per-unit harmonic calibration stored in the MCU's USERROW, a locked sensor
> configuration, health monitoring and a bench-only diagnostic sub-protocol — **without changing the
> wire format, the reply semantics or the chain timing** the M5 controller depends on. A module with
> no calibration written is bit-exact with upstream on CMD=1 and CMD=2. `M5/` is untouched.
>
> | | |
> |---|---|
> | **Start here** | [`docs/development.md`](docs/development.md) — setup, layout, and what to do next |
> | What it does and why | [`docs/protocol-spec.md`](docs/protocol-spec.md) |
> | What was built, what it costs | [`CHANGELOG.md`](CHANGELOG.md) |
> | How it cannot break an M5 | [`docs/compatibility-checklist.md`](docs/compatibility-checklist.md) |
> | Host tool for provisioning and calibration | [`tools/kercal/`](tools/kercal/) |
> | Verification you can run yourself | [`test/run_tests.sh`](test/run_tests.sh) |
>
> **No part of this fork has run on hardware yet.** Everything claimed is either measured off-target
> (the arithmetic, the resource usage, the simulations) or reasoned from datasheets. The bench work is
> [`docs/timing-measurements.md`](docs/timing-measurements.md), and the first item to check is in
> `docs/protocol-spec.md` section 12.2, O2.

## Hardware

- **MCU**: ATtiny1616 (20MHz, 2KB RAM / 16KB Flash)
- **Sensor**: TLE5012B (15-bit angle, SSC)
- **Bus**: RS485 @ 2Mbps, 4-byte packets, up to 21-bit angle output
- **Device ID**: 1–30, stored in the USERROW; 31 = unprovisioned (see *Flashing*)

## Writer

A USB-serial UPDI programmer (Adafruit UPDI Friend, serialUPDI). It appears as e.g. `/dev/ttyUSB0` (CH340E).

- **Standard** — [Switch Science #9535](https://www.switch-science.com/products/9535) / [Adafruit 5879](https://www.adafruit.com/product/5879)
- **High-Voltage** — [DigiKey 5893](https://www.digikey.jp/ja/products/detail/adafruit-industries-llc/5893/22596412) / [Adafruit 5893](https://www.adafruit.com/product/5893). Adds a 12V pulse for chips whose UPDI pin is fused as reset/GPIO, and for unbricking.

The standard version is enough for normal use; the HV version is handy if you ever need to recover a bricked chip.

## Flashing

Set up PlatformIO in a uv venv (first time only):

```bash
uv venv
source .venv/bin/activate
uv pip install platformio
```

Build and upload:

```bash
platformio run -t upload --upload-port /dev/ttyUSB0
```

**The device ID is no longer a build flag in this fork.** One image is flashed to every module; it
boots as ID 31 (unprovisioned) and takes its real ID, 1–30, from the calibration page in the USERROW,
which `kercal` writes. USERROW survives a UPDI chip erase on an unlocked device, so re-flashing does
not lose a calibration. See `docs/protocol-spec.md` sections 5.3 and 5.4.

Overriding `-DDEVICE_ID=n` still works and still builds an upstream-compatible uncalibrated module,
but a module built that way answers at *n* regardless of what is stored, which is not what a
provisioned arm expects. Use it only to reproduce upstream behaviour.

## Hardware design

They are distributed from [enactic/openarm_hardware](https://github.com/enactic/openarm_hardware).

## Licence

Apache-2.0, as upstream. Files that came from upstream keep their `Copyright 2026 Enactic, Inc.`
notice and carry a modification notice; files written for this fork are
`Copyright 2026 Eckstein GmbH`. `src/ker_ssc.h` keeps the upstream notice because its contents were
moved out of `src/main.cpp` unchanged.
