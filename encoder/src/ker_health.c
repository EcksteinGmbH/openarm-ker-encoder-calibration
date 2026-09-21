// Copyright 2026 Eckstein GmbH
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//
// ---------------------------------------------------------------------------
// MODIFICATION NOTICE
// New file, not present in upstream OpenArm. See ker_health.h.
// ---------------------------------------------------------------------------

#include "ker_health.h"

/* NO_VALID_ANGLE is set from reset: nothing has been read yet (spec section 6.2). */
uint16_t       ker_health = KER_H_NO_VALID_ANGLE;
ker_counters_t ker_cnt;

void ker_health_clear_counters(void) {
  ker_cnt.total   = 0;
  ker_cnt.crc_err = 0;
  ker_cnt.stat_err = 0;
  ker_cnt.no_resp = 0;
  ker_cnt.gated   = 0;
  ker_cnt.naks    = 0;
  ker_cnt.wr_fail = 0;
  ker_h_clear(KER_H_STICKY_MASK);
}
