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
// fork: the health bits of protocol-spec.md section 4.7 (GET_HEALTH) and the
// counters of GET_ERRCNT.
// ---------------------------------------------------------------------------

#ifndef KER_HEALTH_H
#define KER_HEALTH_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* GET_HEALTH, spec section 4.7. "live" bits describe the present state and are
 * recomputed by their owner; "sticky" bits latch until CLR_ERRCNT. */
#define KER_H_CAL_INVALID        (1u << 0)   /* live   */
#define KER_H_CAL_VER_UNSUP      (1u << 1)   /* live   */
#define KER_H_SENSOR_CFG_FAIL    (1u << 2)   /* live   */
#define KER_H_SAFETY_CRC_ERR     (1u << 3)   /* sticky */
#define KER_H_SENSOR_STAT_ERR    (1u << 4)   /* sticky */
#define KER_H_SENSOR_NO_RESPONSE (1u << 5)   /* sticky */
/*      bit 6 reserved, always 0 */
#define KER_H_ANGLE_STALE        (1u << 7)   /* live   */
#define KER_H_FACTORY_MODE       (1u << 8)   /* live   */
#define KER_H_USERROW_WRITE_FAIL (1u << 9)   /* sticky */
#define KER_H_ARM_SEEN           (1u << 10)  /* live   */
#define KER_H_WRITE_ELIGIBLE     (1u << 11)  /* live   */
#define KER_H_NO_VALID_ANGLE     (1u << 12)  /* live   */
#define KER_H_ANGLE_DEGRADED     (1u << 13)  /* live   */

#define KER_H_STICKY_MASK (KER_H_SAFETY_CRC_ERR | KER_H_SENSOR_STAT_ERR | \
                           KER_H_SENSOR_NO_RESPONSE | KER_H_USERROW_WRITE_FAIL)

/* GET_ERRCNT, spec section 4.7. Index 0/1 are the halves of `total`; 2..7 are
 * uint16_t and saturate rather than wrap, so a reading can never understate. */
typedef struct {
  uint32_t total;      /* 0,1: angle transactions        */
  uint16_t crc_err;    /* 2: safety-word CRC failures    */
  uint16_t stat_err;   /* 3: reads with a status fault   */
  uint16_t no_resp;    /* 4: no-response reads           */
  uint16_t gated;      /* 5: CMD=3 requests dropped by the read gate */
  uint16_t naks;       /* 6: CMD=3 requests NAK'd        */
  uint16_t wr_fail;    /* 7: USERROW program failures    */
} ker_counters_t;

extern uint16_t       ker_health;
extern ker_counters_t ker_cnt;

static inline void ker_h_set(uint16_t bits)   { ker_health = (uint16_t)(ker_health | bits); }
static inline void ker_h_clear(uint16_t bits) { ker_health = (uint16_t)(ker_health & (uint16_t)~bits); }
static inline void ker_h_put(uint16_t bits, uint8_t on) {
  if (on) ker_h_set(bits); else ker_h_clear(bits);
}

static inline void ker_cnt_bump(uint16_t *c) { if (*c != 0xFFFFu) (*c)++; }

/* CLR_ERRCNT: counters to zero, sticky health bits cleared. */
void ker_health_clear_counters(void);

#ifdef __cplusplus
}
#endif
#endif /* KER_HEALTH_H */
