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
// New file, not present in upstream OpenArm. Added by the calibrated-encoder
// fork: the CMD=3 sub-protocol of protocol-spec.md section 4 -- read and write
// gates, factory mode, the staging buffer, the records and the averaged
// sampling engine -- plus the four entry points main.cpp calls.
// ---------------------------------------------------------------------------

#ifndef KER_CMD3_H
#define KER_CMD3_H

#include <stdint.h>

/* --- the whole interface main.cpp uses ----------------------------------- */

/* Start-up of protocol-spec.md sections 5.3 and 6.2: load and validate the
 * USERROW page, publish the calibration, wait t_pon, lock the sensor
 * configuration and read until one transaction passes.
 *
 * `device_id_out` is main.cpp's own `device_id`, which its CMD=1/CMD=2 dispatch
 * reads every frame. ker_init writes the effective ID into it -- from the page
 * if the page is valid, otherwise `build_default` -- and writes it AGAIN
 * whenever a COMMIT_CAL or SET_ID changes the ID, which section 4.9 allows
 * without a reset. Passing the address rather than returning the value is what
 * keeps the two copies from diverging. */
void     ker_init(uint8_t *device_id_out, uint8_t build_default);

/* True when the averaged-sampling engine (section 4.10) wants another reading
 * before upstream's own SSC_INTERVAL_MS would come round. */
uint8_t  ker_read_due(void);

/* One angle transaction; returns the 21-bit value CMD=1/CMD=2 must send. */
uint32_t ker_read_angle(void);

/* Called once for every received frame, after main.cpp's own dispatch. Owns the
 * read gate, `arm_seen`, the factory-mode timers and all of CMD=3. */
void     ker_on_frame(uint8_t id, uint8_t cmd, uint32_t data);

#endif /* KER_CMD3_H */
