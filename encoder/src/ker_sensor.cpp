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
// New file, not present in upstream OpenArm. See ker_sensor.h.
// ---------------------------------------------------------------------------

#include <Arduino.h>
#include "ker_ssc.h"
#include "ker_sensor.h"
#include "ker_cal.h"
#include "ker_health.h"

// ================================
// TLE5012B command words (spec section 2.1)
//   bit 15 RW (1 = read) | bits 14:11 LOCK | bit 10 UPD | bits 9:4 ADDR | bits 3:0 ND
// ================================
static const uint16_t CMD_READ_ANGLE_BLOCK = 0x8003;  // read STAT, ACSTAT, AVAL   (+ safety)
static const uint16_t CMD_READ_CFG_BLOCK   = 0x806A;  // read MOD_1 .. TCO_Y, 10 words
static const uint16_t CMD_READ_STAT        = 0x8001;
static const uint16_t CMD_READ_FSYNC       = 0x8051;
static const uint16_t CMD_READ_DMAG        = 0x8141;
static const uint16_t CMD_WRITE_MOD_1      = 0x5061;  // LOCK = 1010: write configuration
static const uint16_t CMD_WRITE_MOD_2      = 0x5081;
static const uint16_t CMD_WRITE_TCO_Y      = 0x50F1;

// Index of a register in the CMD_READ_CFG_BLOCK result (ADDR 0x06 .. 0x0F).
enum { CB_MOD_1 = 0, CB_SIL, CB_MOD_2, CB_MOD_3, CB_OFFX, CB_OFFY,
       CB_SYNCH, CB_IFAB, CB_MOD_4, CB_TCO_Y, CB_N };

// Safety word bits (spec section 2.2); 0 means the fault.
#define SW_RST  0x8000u
#define SW_ERR  0x4000u
#define SW_ACC  0x2000u
#define SW_ANG  0x1000u

#define STAT_SFUSE 0x0008u

// Values written by the configuration lock (spec section 2.4) and the masks the
// read-back is compared under. Bits outside a mask are the part's own and kept.
#define MOD_1_FIRMD_MASK 0xC000u
#define MOD_1_FIRMD_2    0x8000u            // FIRMD = 2
#define MOD_2_MASK       0x7FFFu            // AUTOCAL, PREDICT, ANGDIR, ANGRANGE
#define MOD_2_VALUE      0x0800u            // all zero except ANGRANGE = 0x080 (unity)
#define TCO_Y_CRC_MASK   0x00FFu

static const uint8_t crc8_tab[256] = {
#include "ker_crc8.inc"
};

static const ker_cal_t cal_uncalibrated = { 0, {0,0,0,0,0,0}, {0,0,0,0,0,0} };
static const ker_cal_t *g_cal = &cal_uncalibrated;

static uint32_t angle_out;
static uint16_t last_raw15;          // raw15 behind angle_out (published)
static uint16_t attempted_raw15;     // raw15 of the last transaction, pass or fail
static uint16_t seq_no;
static uint16_t stat_last, safety_last;
static uint16_t dmag_cache, fsync_cache, vdd_cache;
static uint16_t cfg_verify;
static uint16_t trim_cache[5];
static uint8_t  consec_fail;
static uint8_t  read_tick;
static uint8_t  last_pass;
static uint8_t  cfg_safety_ok;       // every safety word of the current lock was clean

static inline uint8_t crc8_feed(uint8_t crc, uint8_t b) {
  return crc8_tab[(uint8_t)(crc ^ b)];
}

// CRC-8 of the command word followed by `n` 16-bit words, each big-endian; the
// final value is inverted (spec section 2.2).
static uint8_t crc8_frame(uint16_t cmd, const uint16_t *w, uint8_t n) {
  uint8_t crc = 0xFF;
  crc = crc8_feed(crc, (uint8_t)(cmd >> 8));
  crc = crc8_feed(crc, (uint8_t)cmd);
  for (uint8_t i = 0; i < n; i++) {
    crc = crc8_feed(crc, (uint8_t)(w[i] >> 8));
    crc = crc8_feed(crc, (uint8_t)w[i]);
  }
  return (uint8_t)~crc;
}

// ================================
// Raw SSC transactions. One CS-low window each; interrupts stay enabled, as
// upstream leaves them, so the UART keeps receiving during the window.
// ================================

static uint16_t ssc_read_n(uint16_t cmd, uint16_t *w, uint8_t n) {
  csLow();
  sscWrite16(cmd);
  dataIn();                       // release the line before the sensor drives it
  for (uint8_t i = 0; i < n; i++) w[i] = sscRead16();
  uint16_t safety = sscRead16();
  csHigh();
  return safety;
}

static uint16_t ssc_write_1(uint16_t cmd, uint16_t data) {
  csLow();
  sscWrite16(cmd);
  sscWrite16(data);
  dataIn();
  uint16_t safety = sscRead16();
  csHigh();
  return safety;
}

// A safety word is acceptable during the configuration lock when its CRC is
// valid and S_ERR and S_ACC are set. S_RST is expected there and ignored
// (spec section 6.2).
static uint8_t safety_clean(uint16_t safety, uint16_t cmd, const uint16_t *w, uint8_t n) {
  if ((uint8_t)safety != crc8_frame(cmd, w, n)) return 0;
  if ((safety & (SW_ERR | SW_ACC)) != (SW_ERR | SW_ACC)) return 0;
  return 1;
}

// ================================
// Configuration lock (spec sections 2.4, 2.5, 6.2)
// ================================

static void config_lock(void) {
  uint16_t cb[CB_N], safety, v;
  uint16_t result = 0;
  uint8_t  attempts = (uint8_t)(cfg_verify >> 8);

  cfg_safety_ok = 1;
  if (attempts != 255) attempts++;

  safety = ssc_read_n(CMD_READ_CFG_BLOCK, cb, CB_N);
  if (!safety_clean(safety, CMD_READ_CFG_BLOCK, cb, CB_N)) cfg_safety_ok = 0;

  v = (uint16_t)((cb[CB_MOD_1] & (uint16_t)~MOD_1_FIRMD_MASK) | MOD_1_FIRMD_2);
  safety = ssc_write_1(CMD_WRITE_MOD_1, v);
  if (!safety_clean(safety, CMD_WRITE_MOD_1, &v, 1)) cfg_safety_ok = 0;

  v = (uint16_t)((cb[CB_MOD_2] & (uint16_t)~MOD_2_MASK) | MOD_2_VALUE);
  safety = ssc_write_1(CMD_WRITE_MOD_2, v);
  if (!safety_clean(safety, CMD_WRITE_MOD_2, &v, 1)) cfg_safety_ok = 0;
  cb[CB_MOD_2] = v;

  // CRCPAR (spec section 2.5): CRC-8 over the first 15 bytes of registers
  // 0x08..0x0F, i.e. everything in that block except the CRC byte itself, with
  // the value of MOD_2 we have just written. The full byte is used; Infineon's
  // bitfield table masks it as 0x7F while their write path does not (O2).
  {
    uint8_t crc = 0xFF;
    for (uint8_t i = CB_MOD_2; i <= CB_TCO_Y; i++) {
      crc = crc8_feed(crc, (uint8_t)(cb[i] >> 8));
      if (i != CB_TCO_Y) crc = crc8_feed(crc, (uint8_t)cb[i]);   // 15 bytes, not 16
    }
    v = (uint16_t)((cb[CB_TCO_Y] & (uint16_t)~TCO_Y_CRC_MASK) | (uint8_t)~crc);
  }
  safety = ssc_write_1(CMD_WRITE_TCO_Y, v);
  if (!safety_clean(safety, CMD_WRITE_TCO_Y, &v, 1)) cfg_safety_ok = 0;
  uint16_t tco_y_written = v;

  // Read back and compare under mask.
  uint16_t rb[CB_N];
  safety = ssc_read_n(CMD_READ_CFG_BLOCK, rb, CB_N);
  if (!safety_clean(safety, CMD_READ_CFG_BLOCK, rb, CB_N)) cfg_safety_ok = 0;

  if ((rb[CB_MOD_1] & MOD_1_FIRMD_MASK) == MOD_1_FIRMD_2)          result |= 0x0001u;
  if ((rb[CB_MOD_2] & MOD_2_MASK)       == MOD_2_VALUE)            result |= 0x0002u;
  if ((rb[CB_TCO_Y] & TCO_Y_CRC_MASK)   == (tco_y_written & TCO_Y_CRC_MASK)) result |= 0x0004u;

  // The parameter CRC is checked by the sensor itself: a wrong CRCPAR leaves
  // SFUSE set, which the per-read status check would then fail for ever.
  uint16_t st;
  safety = ssc_read_n(CMD_READ_STAT, &st, 1);
  if (!safety_clean(safety, CMD_READ_STAT, &st, 1)) cfg_safety_ok = 0;
  stat_last = st;
  if (!(st & STAT_SFUSE)) result |= 0x0008u;
  if (cfg_safety_ok)      result |= 0x0010u;

  trim_cache[0] = rb[CB_MOD_3];
  trim_cache[1] = rb[CB_OFFX];
  trim_cache[2] = rb[CB_OFFY];
  trim_cache[3] = rb[CB_SYNCH];
  trim_cache[4] = rb[CB_IFAB];

  cfg_verify = (uint16_t)(result | ((uint16_t)attempts << 8));
  ker_h_put(KER_H_SENSOR_CFG_FAIL, (result & 0x001Fu) != 0x001Fu);
}

// ================================
// Angle transaction (spec sections 6.1, 6.2)
// ================================

static ker_rd_t angle_txn(uint16_t *raw15_out) {
  uint16_t w[3];
  uint16_t safety = ssc_read_n(CMD_READ_ANGLE_BLOCK, w, 3);

  stat_last       = w[0];
  safety_last     = safety;
  attempted_raw15 = (uint16_t)(w[2] & 0x7FFFu);
  *raw15_out      = attempted_raw15;

  if ((w[0] == 0x0000u && w[1] == 0x0000u && w[2] == 0x0000u && safety == 0x0000u) ||
      (w[0] == 0xFFFFu && w[1] == 0xFFFFu && w[2] == 0xFFFFu && safety == 0xFFFFu)) {
    return KER_RD_NO_RESPONSE;
  }
  if ((uint8_t)safety != crc8_frame(CMD_READ_ANGLE_BLOCK, w, 3)) return KER_RD_CRC;
  if (!(safety & SW_RST))                                        return KER_RD_RESET;
  if ((safety & (SW_ERR | SW_ACC | SW_ANG)) != (SW_ERR | SW_ACC | SW_ANG) ||
      (w[0] & KER_STAT_FAULT) != 0u) {
    return KER_RD_STATUS;
  }
  return KER_RD_OK;
}

uint8_t ker_sensor_comp_active(void) {
  return (g_cal->n >= 1u && !(ker_health & KER_H_SENSOR_CFG_FAIL)) ? 1u : 0u;
}

static void publish(uint16_t raw15) {
  last_raw15 = raw15;
  angle_out  = ker_compensate(raw15, ker_sensor_comp_active() ? g_cal : &cal_uncalibrated);
}

// The every-16th-read extras of section 6.3: one housekeeping transaction, or a
// configuration-lock retry in its place while the lock is failing (section 6.2).
static void housekeeping(void) {
  // The supply is measured whatever else happens here: a station diagnosing a
  // module whose configuration lock is failing is exactly when it wants to see
  // VDD, and the conversion runs in the background either way.
  uint16_t mv;
  if (ker_vdd_ready(&mv)) vdd_cache = mv;
  ker_vdd_start();

  if (ker_health & KER_H_SENSOR_CFG_FAIL) { config_lock(); return; }

  uint16_t w, safety, cmd;
  cmd = (read_tick & 0x10u) ? CMD_READ_DMAG : CMD_READ_FSYNC;
  safety = ssc_read_n(cmd, &w, 1);
  if ((uint8_t)safety == crc8_frame(cmd, &w, 1)) {
    if (cmd == CMD_READ_DMAG) dmag_cache = (uint16_t)(w & 0x03FFu);
    else                      fsync_cache = w;
  }
}

uint32_t ker_sensor_read_angle(void) {
  uint16_t raw15;
  ker_rd_t r = angle_txn(&raw15);

  seq_no++;
  ker_cnt.total++;            // 32-bit and wrapping, as section 4.7 specifies

  if (r == KER_RD_OK) {
    consec_fail = 0;
    last_pass = 1;
    publish(raw15);
    ker_h_clear(KER_H_ANGLE_STALE | KER_H_NO_VALID_ANGLE | KER_H_ANGLE_DEGRADED);
  } else {
    last_pass = 0;
    if (consec_fail != 0xFFu) consec_fail++;

    switch (r) {
      case KER_RD_NO_RESPONSE:
        ker_cnt_bump(&ker_cnt.no_resp);  ker_h_set(KER_H_SENSOR_NO_RESPONSE); break;
      case KER_RD_CRC:
        ker_cnt_bump(&ker_cnt.crc_err);  ker_h_set(KER_H_SAFETY_CRC_ERR);     break;
      case KER_RD_RESET:
        // The sensor has reset and lost its volatile configuration; this read
        // fails and the lock is re-run at once, not at the next 16th read.
        // Section 4.7 gives counters for CRC, status and no-response only, and
        // section 6.2 makes S_RST a fourth outcome with no counter of its own.
        // It is booked to the status counter; nothing in the spec assigns it.
        ker_cnt_bump(&ker_cnt.stat_err); ker_h_set(KER_H_SENSOR_STAT_ERR);
        config_lock();
        break;
      default:
        ker_cnt_bump(&ker_cnt.stat_err); ker_h_set(KER_H_SENSOR_STAT_ERR);    break;
    }

    // Persistent-fault rule (D18): after KER_PERSIST_FAIL consecutive failures a
    // status-only failure is passed through, flagged, so that the M5 sees a live
    // angle it can apply its own jump detection to instead of a frozen one.
    // No-response, CRC and S_RST failures are never passed through.
    if (r == KER_RD_STATUS && consec_fail >= KER_PERSIST_FAIL) {
      publish(raw15);
      ker_h_set(KER_H_ANGLE_DEGRADED);
      ker_h_clear(KER_H_ANGLE_STALE | KER_H_NO_VALID_ANGLE);
    } else {
      ker_h_set(KER_H_ANGLE_STALE);
    }
  }

  read_tick++;
  if ((read_tick & 0x0Fu) == 0u) housekeeping();
  return angle_out;
}

// ================================
// Start-up and accessors
// ================================

void ker_sensor_start(void) {
  vdd_cache = ker_vdd_mv();
  delay(7);                       // t_pon: no write access before it (spec section 2.7)
  config_lock();
  for (uint8_t i = 0; i < 10; i++) {
    ker_sensor_read_angle();
    if (last_pass) break;
    delayMicroseconds(200);       // two sensor update periods at FIR_MD 2
  }
}

void ker_sensor_set_cal(const ker_cal_t *cal) {
  g_cal = (cal != 0) ? cal : &cal_uncalibrated;
  // Re-express the angle we are already holding under the new calibration, so
  // that a COMMIT_CAL takes effect without waiting for the next transaction.
  if (!(ker_health & KER_H_NO_VALID_ANGLE)) publish(last_raw15);
}

uint32_t ker_sensor_angle(void)      { return angle_out; }
uint16_t ker_sensor_stat(void)       { return stat_last; }
uint16_t ker_sensor_safety(void)     { return safety_last; }
uint16_t ker_sensor_dmag(void)       { return dmag_cache; }
uint16_t ker_sensor_fsync(void)      { return fsync_cache; }
uint16_t ker_sensor_vdd(void)        { return vdd_cache; }
uint16_t ker_sensor_cfg_verify(void) { return cfg_verify; }
uint16_t ker_sensor_trim(uint8_t i)  { return (i < 5u) ? trim_cache[i] : 0u; }
uint16_t ker_sensor_seq(void)        { return seq_no; }
uint16_t ker_sensor_raw15(void)           { return last_raw15; }
uint16_t ker_sensor_raw15_attempted(void) { return attempted_raw15; }
uint8_t  ker_sensor_last_flags(void) {
  return (uint8_t)((last_pass ? 1u : 0u) | (ker_sensor_comp_active() ? 2u : 0u));
}
