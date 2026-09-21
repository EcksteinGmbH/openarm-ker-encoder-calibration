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
"""kercal command line.  python -m kercal --help

Every command that transmits refuses to run until the port has been listened to
and found silent (spec section 3.2, C4). Never connect this tool to a bus with
an M5 on it: an unmodified M5 parses a host request addressed to ID 1..16 as a
joint angle (sections 1.5, 1.6).
"""

from __future__ import annotations

import argparse
import json
import sys

from . import fit as F
from . import protocol as P
from . import station as S
from .link import BusUnsafe, Link
from .module import Module, scan


def _out(obj):
    print(json.dumps(obj, indent=2, default=str))


def _link(args):
    link = Link(args.port, baud=args.baud)
    link.open_session(args.listen)
    return link


def cmd_listen(args):
    """Passive: report what is on the bus. The only command safe on an arm."""
    link = Link(args.port, baud=args.baud)
    seen = link.listen(args.seconds)
    kinds = {}
    for dev_id, cmd, _ in seen:
        kinds["ID %d CMD %d" % (dev_id, cmd)] = kinds.get("ID %d CMD %d" % (dev_id, cmd), 0) + 1
    _out({"seconds": args.seconds, "frames": len(seen), "by_kind": kinds,
          "verdict": "quiet -- a bench bus" if not seen
                     else "TRAFFIC PRESENT -- do not transmit on this bus"})


def cmd_scan(args):
    with _link(args) as link:
        found = sorted(scan(link).keys())
        _out({"responding_ids": found,
              "note": "section 3.4 requires exactly one module during provisioning"
                      if len(found) > 1 else None})


def cmd_info(args):
    with _link(args) as link:
        m = Module(link, args.id)
        link.measure_round_trip(args.id)
        _out({"round_trip_s": round(link.round_trip_s, 6),
              "firmware": m.firmware(), "device_id": m.device_id(),
              "health": m.health(), "cal_status": m.cal_status(),
              "cfg_verify": m.cfg_verify(), "environment": m.environment(),
              "trim": m.trim(), "counters": m.counters(),
              "sernum": m.sernum().hex(), "angle": m.angle(), "angle_raw": m.angle_raw()})


def cmd_page(args):
    with _link(args) as link:
        m = Module(link, args.id)
        raw = m.running_page() if args.running else m.stored_page()
        info = P.inspect_page(raw)
        page = P.Page.from_bytes(raw)
        amps, phases = page.degrees()
        _out({"source": "running" if args.running else "userrow", "hex": raw.hex(),
              "inspect": info,
              "harmonics": [{"k": k + 1, "amp_deg": round(a, 6), "phase_deg": round(p, 3)}
                            for k, (a, p) in enumerate(zip(amps, phases))]})


def cmd_sample(args):
    with _link(args) as link:
        _out(Module(link, args.id).sample(e=args.e))


def cmd_set_id(args):
    with _link(args) as link:
        m = Module(link, args.id)
        m.unlock()
        new = m.set_id(args.new_id)
        m.id = new
        _out({"new_id": new, "device_id": m.device_id(), "cal_status": m.cal_status()})


def cmd_write_page(args):
    page = bytes.fromhex(open(args.page).read().strip()) if args.page.endswith(".hex") \
        else P.Page(**json.load(open(args.page))).to_bytes()
    with _link(args) as link:
        result = Module(link, args.id).write_page(page)
        result["stored"] = result["stored"].hex()
        _out(result)
        if not result["verified"]:
            sys.exit("read-back does not match: do not release this unit")


def cmd_clear(args):
    with _link(args) as link:
        m = Module(link, args.id)
        m.clear_counters()
        _out(m.counters())


def cmd_fit(args):
    """Offline: fit, grade and page from a recorded run. Needs no hardware."""
    run = S.StationRun.from_csv(args.csv, station_id=args.station_id, device_id=args.id)
    run.sigma_mean_deg = args.sigma_mean
    report = run.report()
    if args.write_page:
        page = run.page(device_id=args.id)
        open(args.write_page, "w").write(page.to_bytes().hex() + "\n")
        report["page_written"] = args.write_page
    _out(report)
    if not report["ships"]:
        sys.exit("grade %s: this unit does not ship (section 7.2 step 8)" % report["grade"])


def cmd_limits(args):
    _out({"reference_implementation": str(F.reference_path),
          "N_FIT": F.N_FIT, "N_VAL": F.N_VAL, "K": F.K_SAMPLES, "N_REPEAT": F.N_REPEAT,
          "R_MAX": F.R_MAX, "R_MAX_B": F.R_MAX_B, "guard": F.GUARD,
          "sigma_mean_max": F.SIGMA_MEAN_MAX, "HYST_MAX": F.HYST_MAX, "H2_MAX": F.H2_MAX,
          "note": "these are minimums and limits, not defaults (section 7.2)"})


def main(argv=None):
    ap = argparse.ArgumentParser(prog="kercal", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("--baud", type=int, default=2_000_000)
    ap.add_argument("--listen", type=float, default=0.2,
                    help="seconds to listen before the first transmission (C4)")
    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("listen", help="passive: report bus traffic, transmit nothing")
    p.add_argument("--seconds", type=float, default=1.0)
    p.set_defaults(func=cmd_listen)

    sp.add_parser("scan", help="PING every ID").set_defaults(func=cmd_scan)
    sp.add_parser("limits", help="print the station constants of section 7.2").set_defaults(func=cmd_limits)

    p = sp.add_parser("info", help="everything readable about one module")
    p.add_argument("--id", type=int, required=True); p.set_defaults(func=cmd_info)

    p = sp.add_parser("page", help="read the calibration page")
    p.add_argument("--id", type=int, required=True)
    p.add_argument("--running", action="store_true", help="the page in use, not the stored one")
    p.set_defaults(func=cmd_page)

    p = sp.add_parser("sample", help="averaged reading (SAMPLE_START / GET_SAMPLE)")
    p.add_argument("--id", type=int, required=True)
    p.add_argument("-e", type=int, default=10, help="K = 2**e readings")
    p.set_defaults(func=cmd_sample)

    p = sp.add_parser("set-id", help="assign an ID, leaving any calibration intact")
    p.add_argument("--id", type=int, required=True)
    p.add_argument("--new-id", type=int, required=True)
    p.set_defaults(func=cmd_set_id)

    p = sp.add_parser("write-page", help="stage, commit and verify a calibration page")
    p.add_argument("--id", type=int, required=True)
    p.add_argument("--page", required=True, help="a .hex of 32 bytes, or a .json Page")
    p.set_defaults(func=cmd_write_page)

    p = sp.add_parser("clear-counters", help="CLR_ERRCNT")
    p.add_argument("--id", type=int, required=True); p.set_defaults(func=cmd_clear)

    p = sp.add_parser("fit", help="offline: fit, grade and page from a recorded run")
    p.add_argument("csv")
    p.add_argument("--id", type=int, required=True)
    p.add_argument("--station-id", type=int, default=0)
    p.add_argument("--sigma-mean", type=float, required=True,
                   help="step 2's sigma_mean for this run, degrees")
    p.add_argument("--write-page", help="write the resulting page here as hex")
    p.set_defaults(func=cmd_fit)

    args = ap.parse_args(argv)
    try:
        args.func(args)
    except BusUnsafe as e:
        sys.exit("refusing to transmit: %s" % e)
    except P.Nak as e:
        sys.exit("module rejected the request: %s" % e)


if __name__ == "__main__":
    main()
