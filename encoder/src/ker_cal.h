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
// fork: USERROW calibration page (protocol-spec.md section 5), its CRC-16 and
// validation, USERROW programming and the supply check that guards it.
// ---------------------------------------------------------------------------

#ifndef KER_CAL_H
#define KER_CAL_H

#include <stdint.h>
#include "ker_comp.h"

#ifdef __cplusplus
extern "C" {
#endif

#define KER_PAGE_BYTES     32
#define KER_PAGE_WORDS     16
#define KER_PAGE_MAGIC     0x4B   /* 'K' */
#define KER_LAYOUT_VER     1
#define KER_ID_MIN         1
#define KER_ID_MAX         30
#define KER_ID_UNPROVISIONED 31

/* Supply floor for programming, spec section 5.5 (D19): the ATtiny1616's own
 * minimum for 20 MHz operation. */
#define KER_VDD_MIN_PROG_MV 4500u

/* Why a page was rejected. The order is the check order of spec section 5.2;
 * only KER_PAGE_ERR_CRC maps to NAK CRC_FAIL, every other failure to BAD_PAGE. */
typedef enum {
  KER_PAGE_OK = 0,
  KER_PAGE_ERR_CRC,
  KER_PAGE_ERR_MAGIC,
  KER_PAGE_ERR_VER,
  KER_PAGE_ERR_ID,
  KER_PAGE_ERR_NHARM,
  KER_PAGE_ERR_SLOT
} ker_page_err_t;

typedef struct {
  ker_page_err_t err;        /* KER_PAGE_OK if every check passed */
  uint8_t  crc_ok;
  uint8_t  magic_ok;
  uint8_t  ver_ok;
  uint8_t  fields_ok;        /* checks 4-6 of section 5.2 */
  uint8_t  virgin;           /* all 32 bytes 0xFF */
  uint8_t  layout_ver;       /* as stored, whatever it is */
  uint8_t  device_id;        /* as stored */
  uint8_t  station_id;
  uint16_t cal_day;
  uint8_t  n_harm;
} ker_page_info_t;

/* CRC-16/CCITT-FALSE: poly 0x1021, init 0xFFFF, no reflection, no final XOR. */
uint16_t ker_crc16(const uint8_t *data, uint8_t len);

/* Little-endian word accessors; the page is a byte array everywhere so that the
 * wire format, the USERROW and the staging buffer are all the same object. */
uint16_t ker_page_word(const uint8_t *page, uint8_t i);
void     ker_page_set_word(uint8_t *page, uint8_t i, uint16_t v);

/* Full validation, spec section 5.2. Never dereferences past 32 bytes. */
void ker_page_inspect(const uint8_t *page, ker_page_info_t *info);

/* Coefficients of a page that passed inspection. Zeroes cal for an invalid page. */
void ker_page_to_cal(const uint8_t *page, const ker_page_info_t *info, ker_cal_t *cal);

/* Recompute and store word 15. */
void ker_page_seal(uint8_t *page);

/* Identity page: magic, version, id, STATION_ID 0, N_HARM 0, CAL_DAY 0, no
 * coefficients, sealed. Spec section 4.9, SET_ID over a virgin page. */
void ker_page_build_identity(uint8_t *page, uint8_t device_id);

/* Read the 32 USERROW bytes. */
void ker_userrow_read(uint8_t *page);

/* Program the USERROW and verify it by reading back. Returns 1 on success.
 * Does not check VDD; the caller does that, so that a low supply and a failed
 * program are distinguishable in the log. */
uint8_t ker_userrow_program(const uint8_t *page);

/* Supply in millivolts, internal 1.1 V reference measured against VDD.
 *
 * ker_vdd_mv() blocks for roughly 0.15 ms and is used where that is free: at
 * start-up and before a COMMIT_CAL. The read step of section 8.3 has no room
 * for it, so the housekeeping transaction of section 6.3 uses the split pair
 * instead: ker_vdd_start() kicks a conversion that runs while the SSC bits are
 * clocked, and the next housekeeping transaction collects it with
 * ker_vdd_ready(). The reported value is then at most one housekeeping slot
 * older than D_MAG and FSYNC, which section 6.3 already bounds at 32 reads. */
uint16_t ker_vdd_mv(void);
void     ker_vdd_start(void);
uint8_t  ker_vdd_ready(uint16_t *mv);   /* 1 if a result was collected */

#ifndef __AVR__
/* Host test hooks; no effect on the firmware build. */
extern uint8_t  ker_test_userrow[KER_PAGE_BYTES];
extern uint8_t  ker_test_program_fail;   /* 1 = next program fails outright */
extern uint8_t  ker_test_verify_corrupt; /* 1 = next program flips a byte after writing */
extern uint16_t ker_test_vdd_mv;
#endif

#ifdef __cplusplus
}
#endif
#endif /* KER_CAL_H */
