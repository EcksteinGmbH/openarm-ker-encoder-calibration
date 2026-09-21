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
# New file, not present in upstream OpenArm. Drives the normative station
# procedure of docs/protocol-spec.md section 7.2 end to end, and records what
# section 9.7 says must be recorded.
# ---------------------------------------------------------------------------
"""The station calibration run: measure, fit, commit, validate, grade."""

from __future__ import annotations

import csv
import datetime
import json
import time
from dataclasses import dataclass, field

import numpy as np

from . import fit as F
from . import protocol as P

EPOCH = datetime.date(2026, 1, 1)      # CAL_DAY is days since this date (section 5.1)


def cal_day(today: datetime.date = None) -> int:
    d = (today or datetime.date.today()) - EPOCH
    if not 0 <= d.days <= 0xFFF:
        raise ValueError("CAL_DAY does not fit in 12 bits; the layout runs out on 2037-03-19")
    return d.days


class Reference:
    """The station's angular reference chain (section 7.7).

    A real station implements this against its rotary stage and its reference
    encoder. Everything above it -- the order of the passes, the settling rule,
    the fit and the grade -- is the same whatever the hardware is.
    """

    def move_to(self, angle_deg: float, direction: int):
        """Approach `angle_deg` from `direction` (+1 clockwise, -1 counter-clockwise).
        The approach must never overshoot, or the hysteresis measurement is void."""
        raise NotImplementedError

    def read(self) -> float:
        """The corrected reference angle theta_true, degrees."""
        raise NotImplementedError

    def wait_stationary(self, tol_deg: float = 0.0005, samples: int = 5, timeout_s: float = 5.0):
        """Section 7.2 step 1: sample only once the reference polls are stationary."""
        end = time.monotonic() + timeout_s
        while time.monotonic() < end:
            vals = [self.read() for _ in range(samples)]
            if max(vals) - min(vals) <= tol_deg:
                return float(np.mean(vals))
            time.sleep(0.05)
        raise TimeoutError("the stage did not settle to %.4f deg" % tol_deg)


@dataclass
class Measurement:
    position_deg: float
    direction: int            # +1 clockwise, -1 counter-clockwise
    phase: str                # "fit" or "val"
    theta_true_deg: float
    theta_s_deg: float
    theta_out_deg: float = float("nan")
    n_pass: int = 0
    n_fail: int = 0
    sigma_reading_deg: float = float("nan")


@dataclass
class StationRun:
    sernum: str = ""
    station_id: int = 0
    device_id: int = P.ID_UNPROVISIONED
    conditions: dict = field(default_factory=dict)
    measurements: list = field(default_factory=list)
    sigma_mean_deg: float = float("nan")

    # -- section 7.2 steps 3-6 -----------------------------------------------
    def _sel(self, phase, direction=None):
        m = [x for x in self.measurements
             if x.phase == phase and (direction is None or x.direction == direction)]
        return m

    def fit(self):
        """Steps 4 and 5 on the POOLED samples of both directions: the mean curve
        of the hysteresis loop, which is what a static page can represent."""
        m = self._sel("fit")
        if len(m) < 2 * F.N_FIT:
            raise ValueError("%d fit samples; section 7.2 needs %d (2 directions x %d positions)"
                             % (len(m), 2 * F.N_FIT, F.N_FIT))
        tt = np.array([x.theta_true_deg for x in m])
        ts = np.array([x.theta_s_deg for x in m])
        return F.fit(tt, ts)

    def page(self, device_id: int = None, day: int = None) -> P.Page:
        a, b, _offset = self.fit()
        return F.page_from_fit(a, b, device_id=device_id or self.device_id,
                               station_id=self.station_id,
                               cal_day=cal_day() if day is None else day)

    # -- section 7.2 steps 7-9 ----------------------------------------------
    def grade(self):
        cw, ccw = self._sel("val", +1), self._sel("val", -1)
        if not cw or len(cw) != len(ccw):
            raise ValueError("validation needs the same positions in both directions")
        cw.sort(key=lambda x: x.position_deg)
        ccw.sort(key=lambda x: x.position_deg)
        if len(cw) < F.N_VAL:
            raise ValueError("%d validation positions; section 7.2 needs %d" % (len(cw), F.N_VAL))
        tt = np.array([x.theta_true_deg for x in cw])
        return F.grade(tt, np.array([x.theta_out_deg for x in cw]),
                       np.array([x.theta_out_deg for x in ccw]), self.sigma_mean_deg)

    def centring(self):
        a, b, _ = self.fit()
        return F.centring(a, b)

    def report(self) -> dict:
        g, stat, hyst = self.grade()
        h2, h2_ok = self.centring()
        return {
            "sernum": self.sernum, "station_id": self.station_id, "device_id": self.device_id,
            "grade": g, "statistic_deg": stat, "hysteresis_half_difference_deg": hyst,
            "h2_deg": h2, "centring_ok": h2_ok,
            "sigma_mean_deg": self.sigma_mean_deg,
            "ships": g in ("A", "B") and h2_ok,
            "limits": {"R_MAX": F.R_MAX, "R_MAX_B": F.R_MAX_B, "guard": F.GUARD,
                       "HYST_MAX": F.HYST_MAX, "H2_MAX": F.H2_MAX,
                       "N_FIT": F.N_FIT, "N_VAL": F.N_VAL, "K": F.K_SAMPLES},
            "conditions": self.conditions,
            "spec": "protocol-spec.md section 7.2 (v6)",
        }

    # -- records (section 9.7) ----------------------------------------------
    def to_csv(self, path):
        with open(path, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["position_deg", "direction", "phase", "theta_true_deg", "theta_s_deg",
                        "theta_out_deg", "n_pass", "n_fail", "sigma_reading_deg"])
            for m in self.measurements:
                w.writerow([m.position_deg, m.direction, m.phase, m.theta_true_deg,
                            m.theta_s_deg, m.theta_out_deg, m.n_pass, m.n_fail,
                            m.sigma_reading_deg])

    @classmethod
    def from_csv(cls, path, **kw):
        run = cls(**kw)
        with open(path, newline="") as fh:
            for row in csv.DictReader(fh):
                run.measurements.append(Measurement(
                    position_deg=float(row["position_deg"]), direction=int(row["direction"]),
                    phase=row["phase"], theta_true_deg=float(row["theta_true_deg"]),
                    theta_s_deg=float(row["theta_s_deg"]),
                    theta_out_deg=float(row.get("theta_out_deg") or "nan"),
                    n_pass=int(row.get("n_pass") or 0), n_fail=int(row.get("n_fail") or 0),
                    sigma_reading_deg=float(row.get("sigma_reading_deg") or "nan")))
        return run


# --- the hardware run ------------------------------------------------------

def _measure(module, reference, position, direction, phase, e):
    reference.move_to(position, direction)
    theta_true = reference.wait_stationary()
    s = module.sample(e=e)
    if s["aborted"] or s["saturated"] or s["n_pass"] < 0.9 * (1 << e):
        raise RuntimeError("sample at %.3f deg discarded: %r" % (position, s))
    return Measurement(position_deg=position, direction=direction, phase=phase,
                       theta_true_deg=theta_true, theta_s_deg=s["theta_s_deg"],
                       theta_out_deg=s["theta_out_deg"], n_pass=s["n_pass"],
                       n_fail=s["n_fail"], sigma_reading_deg=s.get("sigma_reading_deg", float("nan")))


def run_calibration(module, reference, station_id: int, device_id: int,
                    e: int = 10, warmup_s: float = 600.0, log=print) -> StationRun:
    """Section 7.2, steps 1 to 10, on one assembled unit.

    Two passes of everything: the fit is of the mean curve of the hysteresis
    loop, and the grade is of the direction mean. The unit is committed between
    the fit and the validation passes, so validation measures what ships.
    """
    if (1 << e) < F.K_SAMPLES:
        raise ValueError("K = %d is below the minimum %d of section 7.2" % (1 << e, F.K_SAMPLES))

    run = StationRun(sernum=module.sernum().hex(), station_id=station_id, device_id=device_id)

    log("step 1: warm-up and conditions")
    t0 = time.monotonic()
    while time.monotonic() - t0 < warmup_s:
        time.sleep(5.0)
    run.conditions = dict(module.environment(), firmware=module.firmware(),
                          cfg_verify=module.cfg_verify(),
                          started=datetime.datetime.now().isoformat(timespec="seconds"))
    if not run.conditions["cfg_verify"]["passed"]:
        raise RuntimeError("the sensor configuration lock did not pass; the fit would not transfer")

    fit_pos, val_pos = F.positions()

    log("step 2: noise check, %d repeats at one position, always clockwise" % F.N_REPEAT)
    vals = []
    for _ in range(F.N_REPEAT):
        reference.move_to(fit_pos[0] - 5.0, +1)
        m = _measure(module, reference, float(fit_pos[0]), +1, "noise", e)
        vals.append(m.theta_true_deg - m.theta_s_deg)
    run.sigma_mean_deg = F.noise_check(vals)
    log("  sigma_mean = %.5f deg (limit %.5f)" % (run.sigma_mean_deg, F.SIGMA_MEAN_MAX))
    if run.sigma_mean_deg > F.SIGMA_MEAN_MAX:
        raise RuntimeError("insufficient data: fix the station, do not grade the part")

    log("step 3: fit passes, %d positions x 2 directions" % len(fit_pos))
    for direction in (+1, -1):
        for pos in (fit_pos if direction > 0 else fit_pos[::-1]):
            run.measurements.append(_measure(module, reference, float(pos), direction, "fit", e))

    log("step 6: convert and commit")
    page = run.page(device_id=device_id)
    result = module.write_page(page.to_bytes())
    if not result["verified"]:
        raise RuntimeError("the committed page did not read back; do not release this unit")
    log("  committed as ID %d" % result["id"])

    log("step 7: validation passes on the committed unit")
    for direction in (+1, -1):
        for pos in (val_pos if direction > 0 else val_pos[::-1]):
            run.measurements.append(_measure(module, reference, float(pos), direction, "val", e))

    rep = run.report()
    log("step 8: grade %s, statistic %.5f deg, hysteresis %.5f deg, H2 %.4f deg"
        % (rep["grade"], rep["statistic_deg"] or float("nan"),
           rep["hysteresis_half_difference_deg"] or float("nan"), rep["h2_deg"]))
    return run


def write_records(run: StationRun, directory, prefix=None):
    """Section 9.7: the run keyed to SERNUM, so a unit can be traced later."""
    import pathlib
    d = pathlib.Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    stem = prefix or ("%s-%s" % (run.sernum, datetime.date.today().isoformat()))
    run.to_csv(d / (stem + ".csv"))
    (d / (stem + ".json")).write_text(json.dumps(run.report(), indent=2, default=str))
    return d / (stem + ".json")
