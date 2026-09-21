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
"""The station fit and grade of docs/protocol-spec.md section 7.2.

There is deliberately no second implementation here. The spec names
`docs/evidence/v3-reference/station_fit.py` as the golden reference, and every
number in section 7.2 -- the mounting-offset table, the operating characteristic,
the grade boundaries -- was measured on it. This module loads that file and
re-exports it, so the tool that calibrates a part and the artefact the spec was
verified on cannot drift apart. A second copy would be a second thing to keep
right.
"""

from __future__ import annotations

import importlib.util
import pathlib

_REF = (pathlib.Path(__file__).resolve().parents[3]
        / "docs" / "evidence" / "v3-reference" / "station_fit.py")


def _load():
    if not _REF.exists():
        raise RuntimeError(
            "the reference station procedure is missing: %s\n"
            "kercal deliberately has no second copy of the fit (see this module's docstring)." % _REF)
    spec = importlib.util.spec_from_file_location("kercal._station_fit", _REF)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_sf = _load()

# The computational part of every normative step of section 7.2.
Cal = _sf.Cal
positions = _sf.positions
noise_check = _sf.noise_check
fit = _sf.fit
to_cal = _sf.to_cal
grade = _sf.grade
centring = _sf.centring
half_range = _sf.half_range
wrap = _sf.wrap
circular_mean = _sf.circular_mean
sample_angle = _sf.sample_angle
sample_output = _sf.sample_output

# Constants, so that a station cannot quietly run below the minimums the
# operating characteristic was established at.
N_FIT = _sf.N_FIT
N_VAL = _sf.N_VAL
K_SAMPLES = _sf.K_SAMPLES
N_REPEAT = _sf.N_REPEAT
R_MAX = _sf.R_MAX
R_MAX_B = _sf.R_MAX_B
GUARD = _sf.GUARD
SIGMA_MEAN_MAX = _sf.SIGMA_MEAN_MAX
HYST_MAX = _sf.HYST_MAX
H2_MAX = _sf.H2_MAX

reference_path = _REF


def page_from_fit(a, b, device_id, station_id=0, cal_day=0):
    """Step 6 plus the page layout of section 5.1. Returns a protocol.Page."""
    from .protocol import Page
    cal = to_cal(a, b)
    if cal is None:
        raise ValueError("an amplitude exceeds the int16 field (5.625 deg); the part is out of range")
    return Page(device_id=device_id, station_id=station_id, cal_day=cal_day,
                amp=[cal.amp[k] for k in range(cal.n)],
                phase=[cal.phase[k] for k in range(cal.n)])
