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
> is [`encoder/CHANGELOG.md`](encoder/CHANGELOG.md).
>
> Questions about **this fork** belong in its own issue tracker, not in the upstream channels below.

OpenArm KER has 2 firmware:

* [Encoder](encoder/) that collects sensor data and streams them to M5 — **modified by this fork**
* [M5](M5/) that receives streamed sensor data and streams them to PC — untouched

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
