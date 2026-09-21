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
// fork: the block sensor transaction, its safety-word and status evaluation,
// the boot configuration lock and the housekeeping reads
// (protocol-spec.md sections 2 and 6).
// ---------------------------------------------------------------------------

#ifndef KER_SENSOR_H
#define KER_SENSOR_H

#include <stdint.h>
#include "ker_comp.h"

#ifdef __cplusplus
extern "C" {
#endif

/* STAT bits that mean a fault, spec section 2.3. SRST (bit 0) is informational;
 * reset detection uses the safety word's S_RST. */
#define KER_STAT_FAULT 0x1EFEu

/* Outcome of one angle transaction, in the evaluation order of section 6.2. */
typedef enum {
  KER_RD_OK = 0,
  KER_RD_NO_RESPONSE,
  KER_RD_CRC,
  KER_RD_RESET,     /* S_RST low: the sensor lost its configuration */
  KER_RD_STATUS
} ker_rd_t;

/* Consecutive failures after which a status-only failure is passed through (D18). */
#define KER_PERSIST_FAIL 20

/* Start-up of section 6.2: t_pon wait, configuration lock, then read until one
 * transaction passes, up to 10 attempts. Call after the calibration is loaded,
 * since a passing read already publishes a compensated angle. */
void ker_sensor_start(void);

/* One angle transaction. Updates the cached angle, the sequence number, the
 * health bits and the counters, and returns the 21-bit value to send. Also owns
 * the every-16th-read housekeeping transaction and the configuration-lock retry. */
uint32_t ker_sensor_read_angle(void);

/* The value CMD=1/CMD=2 would send now. */
uint32_t ker_sensor_angle(void);

/* Accessors for the CMD=3 reads of section 4.6. */
uint16_t ker_sensor_stat(void);
uint16_t ker_sensor_safety(void);
uint16_t ker_sensor_dmag(void);
uint16_t ker_sensor_fsync(void);
uint16_t ker_sensor_vdd(void);
uint16_t ker_sensor_cfg_verify(void);
uint16_t ker_sensor_trim(uint8_t i);      /* 0 MOD_3, 1 OFFX, 2 OFFY, 3 SYNCH, 4 IFAB */
uint16_t ker_sensor_seq(void);
uint16_t ker_sensor_raw15(void);          /* raw15 behind the angle being sent */
uint16_t ker_sensor_raw15_attempted(void);/* raw15 of the last transaction, pass or fail */
uint8_t  ker_sensor_last_flags(void);     /* bit 0 last transaction passed, bit 1 compensation active */
uint8_t  ker_sensor_comp_active(void);

/* Set by ker_cmd3 when the running calibration changes. A null or n == 0 slot is
 * the uncalibrated upstream mapping. */
void ker_sensor_set_cal(const ker_cal_t *cal);

#ifdef __cplusplus
}
#endif
#endif /* KER_SENSOR_H */
