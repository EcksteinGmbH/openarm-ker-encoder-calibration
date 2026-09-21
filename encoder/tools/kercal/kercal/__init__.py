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
"""kercal -- host library and CLI for the calibrated OpenArm KER encoder.

Deliverable 4. Everything it does is defined by docs/protocol-spec.md; where a
rule here looks like caution rather than function, it is section 3.2's host
discipline C4, and it is normative.
"""

__version__ = "1.0.0"

from .protocol import (Page, ProtocolError, Nak, SUB, MAGIC, crc16,   # noqa: F401
                       encode_frame, decode_frame, encode_cmd3, decode_cmd3,
                       inspect_page, sernum_digest, decode_temperature, decode_sample)
