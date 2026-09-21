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
// New file, not present in upstream OpenArm. See ker_cmd3.h.
// ---------------------------------------------------------------------------

#include <Arduino.h>
#include <avr/io.h>
#include <string.h>

#include "ker_cmd3.h"
#include "ker_cal.h"
#include "ker_comp.h"
#include "ker_health.h"
#include "ker_sensor.h"
#include "ker_version.h"

// Defined in main.cpp. Declared here rather than moved, so that the reply path
// of protocol-spec.md section 8.2 stays literally upstream's.
void makePacket21(uint8_t ID, uint8_t CMD, uint32_t data);
void send485();

// ================================
// Sub-protocol constants (spec sections 4.5, 4.6, 4.9)
// ================================
enum {
  SUB_NAK = 0x00, SUB_PING, SUB_GET_FW_VER, SUB_GET_PROTO_VER, SUB_GET_DEVICE_ID,
  SUB_GET_HEALTH, SUB_GET_STAT, SUB_GET_DMAG, SUB_GET_ENV, SUB_GET_SAFETY,
  SUB_GET_ANGLE_RAW, SUB_GET_ANGLE_COMP, SUB_GET_LATCHED, SUB_GET_ERRCNT,
  SUB_CLR_ERRCNT, SUB_GET_CAL_WORD, SUB_GET_CAL_STATUS, SUB_GET_SERNUM,
  SUB_GET_CFG_VERIFY, SUB_GET_TRIM, SUB_LATCH_SYNC, SUB_GET_RUN_WORD,
  SUB_SAMPLE_START, SUB_GET_SAMPLE, SUB_UNLOCK_1, SUB_UNLOCK_2, SUB_STAGE_ADDR,
  SUB_STAGE_DATA, SUB_COMMIT_CAL, SUB_SET_ID, SUB_LOCK, SUB_RESET
};

enum {
  NAK_NOT_UNLOCKED = 0x02, NAK_BAD_ARG = 0x03, NAK_BAD_INDEX = 0x04,
  NAK_CRC_FAIL = 0x05, NAK_WRITE_FAIL = 0x06, NAK_UNSUPPORTED = 0x07,
  NAK_BAD_ADDRESSING = 0x09, NAK_SEQUENCE = 0x0A, NAK_NOT_ELIGIBLE = 0x0B,
  NAK_BAD_PAGE = 0x0C, NAK_STAGING_BUSY = 0x0D
};

#define MAGIC_CLR_ERRCNT   0xC1EAu
#define MAGIC_LATCH_SYNC   0x1A7Cu
#define MAGIC_UNLOCK_1     0x5A17u
#define MAGIC_UNLOCK_2     0xA5E8u          // XOR SERNUM_DIGEST
#define MAGIC_COMMIT_CAL   0xC0DEu
#define MAGIC_LOCK         0x10CCu
#define MAGIC_RESET        0x8EE7u
#define TAG_STAGE_ADDR     0xA5u            // high byte
#define TAG_SET_ID         0x5Eu
#define TAG_SAMPLE_START   0x5Au

#define T_IDLE_MS          100UL            // read gate (C2)
#define T_ARM_WAIT_MS      3000UL           // write eligibility (C3)
#define T_FACTORY_MS       5000UL           // factory-mode inactivity timeout
#define T_UNLOCK_MS        1000UL           // UNLOCK_1 .. UNLOCK_2 window
#define SAMPLE_SPACING_US  200UL

// ================================
// State
// ================================
// main.cpp keeps its own `device_id`, which its CMD=1 and CMD=2 dispatch reads
// every frame. A successful COMMIT_CAL or SET_ID changes the ID without a reset
// (section 4.9), so the two must move together: a module answering the cascade
// at its old ID and CMD=3 at its new one would be a very quiet fault.
static uint8_t   device_id = KER_ID_UNPROVISIONED;
static uint8_t  *device_id_slot;
static uint8_t   build_default_id = KER_ID_UNPROVISIONED;
static uint8_t   id_from_page;

static void set_device_id(uint8_t v) {
  device_id = v;
  if (device_id_slot) *device_id_slot = v;
}
static uint8_t   running_page[KER_PAGE_BYTES];
static ker_cal_t running_cal;
static uint16_t  sernum_digest;

static uint8_t   staging[KER_PAGE_BYTES];
static uint8_t   staging_dirty;
static uint8_t   staging_index;

static uint8_t   factory_mode;
static uint32_t  factory_last_accept;
static uint8_t   unlock_armed;
static uint32_t  unlock_armed_at;

static uint32_t  last_arm_frame;            // last CMD=1 or CMD=2 frame, any ID
static uint8_t   arm_seen;
static uint8_t   run_100ms, run_3s;

// Latch holding register (section 4.8)
static uint32_t  latched_angle;
static uint16_t  latched_raw15;
static uint8_t   latch_count, latch_valid, latch_any;

// Records (section 4.3 rule 6). `*_ok` is rule 6's "index 0 has been read".
static uint16_t  rec_raw[5];   static uint8_t rec_raw_ok;
static uint16_t  rec_comp[2];  static uint8_t rec_comp_ok;
static uint16_t  rec_latch[4]; static uint8_t rec_latch_ok;
static uint16_t  rec_err[8];   static uint8_t rec_err_ok;
static uint16_t  rec_smp[12];  static uint8_t rec_smp_ok;

// Averaged sampling (section 4.10)
static uint8_t   smp_active, smp_e, smp_status, smp_have_ref;
static uint16_t  smp_left, smp_pass, smp_fail, smp_r0;
static uint32_t  smp_c0;
static int32_t   smp_sum_d, smp_sum_c;
static uint32_t  smp_sum_d2;
static uint32_t  smp_last_us;

// ================================
// Replies
// ================================
static void reply(uint8_t sub, uint16_t data) {
  makePacket21(0, 3, ((uint32_t)sub << 16) | (uint32_t)data);
  send485();
}

static void nak(uint8_t sub, uint8_t reason) {
  ker_cnt_bump(&ker_cnt.naks);
  makePacket21(0, 3, ((uint32_t)SUB_NAK << 16) | ((uint32_t)sub << 8) | (uint32_t)reason);
  send485();
}

// ================================
// Calibration and identity
// ================================
static void adopt_page(const uint8_t *page, const ker_page_info_t *info) {
  if (info->err == KER_PAGE_OK) {
    memcpy(running_page, page, KER_PAGE_BYTES);
    set_device_id(info->device_id);
    id_from_page = 1;
    ker_page_to_cal(page, info, &running_cal);
    ker_h_clear(KER_H_CAL_INVALID | KER_H_CAL_VER_UNSUP);
  } else {
    memset(running_page, 0xFF, KER_PAGE_BYTES);    // GET_RUN_WORD reads as virgin
    set_device_id(build_default_id);
    id_from_page = 0;
    running_cal.n = 0;
    ker_h_set(KER_H_CAL_INVALID);
    ker_h_put(KER_H_CAL_VER_UNSUP, (uint8_t)(info->magic_ok && !info->ver_ok));
  }
  ker_sensor_set_cal(&running_cal);
}

static void end_factory_mode(void) {
  factory_mode  = 0;
  unlock_armed  = 0;
  staging_dirty = 0;
  staging_index = 0;
  ker_h_clear(KER_H_FACTORY_MODE);
}

// Program `page`, verify it, and adopt it. Returns 0 on success, else the NAK.
static uint8_t commit_page(const uint8_t *page) {
  if (ker_vdd_mv() < KER_VDD_MIN_PROG_MV || !ker_userrow_program(page)) {
    ker_h_set(KER_H_USERROW_WRITE_FAIL);
    ker_cnt_bump(&ker_cnt.wr_fail);
    return NAK_WRITE_FAIL;                 // running state and buffer untouched
  }
  uint8_t back[KER_PAGE_BYTES];
  ker_page_info_t info;
  ker_userrow_read(back);
  ker_page_inspect(back, &info);
  adopt_page(back, &info);
  return 0;
}

// ================================
// Averaged sampling (section 4.10)
// ================================
static void sample_abort(void) {
  if (smp_active) { smp_active = 0; smp_status |= 0x02u; }
}

static void sample_start(uint8_t e) {
  smp_e = e; smp_left = (uint16_t)(1u << e);
  smp_status = 0; smp_have_ref = 0;
  smp_pass = 0; smp_fail = 0; smp_r0 = 0; smp_c0 = 0;
  smp_sum_d = 0; smp_sum_c = 0; smp_sum_d2 = 0;
  smp_active = 1;
  smp_last_us = micros();
}

static void sample_consume(void) {
  uint8_t flags = ker_sensor_last_flags();
  smp_last_us = micros();

  if (flags & 0x01u) {                       // only readings that passed section 6.2
    uint16_t raw15 = ker_sensor_raw15();
    if (!smp_have_ref) { smp_r0 = raw15; smp_c0 = ker_sensor_angle(); smp_have_ref = 1; }
    int16_t d = (int16_t)((uint16_t)(raw15 - smp_r0) & 0x7FFFu);
    if (d >= 0x4000) d = (int16_t)(d - 0x8000);
    smp_sum_d += d;
    uint32_t dd = (uint32_t)((int32_t)d * (int32_t)d);
    if (smp_sum_d2 > 0xFFFFFFFFUL - dd) { smp_sum_d2 = 0xFFFFFFFFUL; smp_status |= 0x04u; }
    else                                  smp_sum_d2 += dd;
    int32_t dc = (int32_t)((ker_sensor_angle() - smp_c0) & 0x1FFFFFUL);
    if (dc >= 0x100000L) dc -= 0x200000L;
    smp_sum_c += dc;
    smp_pass++;
  } else {
    smp_fail++;
  }

  if (--smp_left == 0) { smp_active = 0; smp_status |= 0x01u; }
}

uint8_t ker_read_due(void) {
  return (uint8_t)(smp_active && (micros() - smp_last_us) >= SAMPLE_SPACING_US);
}

uint32_t ker_read_angle(void) {
  uint32_t v = ker_sensor_read_angle();
  if (smp_active) sample_consume();
  if (!run_100ms && millis() >= T_IDLE_MS)    run_100ms = 1;
  if (!run_3s    && millis() >= T_ARM_WAIT_MS) run_3s = 1;
  return v;
}

// ================================
// Init
// ================================
void ker_init(uint8_t *device_id_out, uint8_t build_default) {
  uint8_t page[KER_PAGE_BYTES];
  ker_page_info_t info;

  device_id_slot   = device_id_out;
  build_default_id = build_default;
  set_device_id(build_default);

  ker_userrow_read(page);
  ker_page_inspect(page, &info);
  adopt_page(page, &info);

  {
    uint8_t sn[10];
    const volatile uint8_t *p = &SIGROW_SERNUM0;
    for (uint8_t i = 0; i < 10; i++) sn[i] = p[i];
    sernum_digest = ker_crc16(sn, 10);
  }

  ker_sensor_start();
}

// ================================
// Records
// ================================
static void capture_raw(void) {
  // The raw15 of the transaction the sequence number and flags describe, which
  // is not the published one when that transaction failed. Section 4.7 says the
  // record is captured "together from one sensor transaction"; bit 0 of field 4
  // is what tells the host whether that transaction passed.
  uint16_t raw15 = ker_sensor_raw15_attempted();
  uint32_t up = ((uint32_t)raw15 << 6) | (uint16_t)(raw15 >> 9);
  rec_raw[0] = (uint16_t)up;
  rec_raw[1] = (uint16_t)(up >> 16);
  rec_raw[2] = raw15;
  rec_raw[3] = ker_sensor_seq();
  rec_raw[4] = ker_sensor_last_flags();
  rec_raw_ok = 1;
}

static void capture_comp(void) {
  uint32_t a = ker_sensor_angle();
  rec_comp[0] = (uint16_t)a;
  rec_comp[1] = (uint16_t)(a >> 16);
  rec_comp_ok = 1;
}

static void capture_latch(void) {
  rec_latch[0] = (uint16_t)latched_angle;
  rec_latch[1] = (uint16_t)(latched_angle >> 16);
  rec_latch[2] = latched_raw15;
  rec_latch[3] = (uint16_t)(latch_count |
                            (latch_valid ? 0x0100u : 0u) |
                            (latch_any   ? 0x0200u : 0u));
  rec_latch_ok = 1;
}

static void capture_err(void) {
  rec_err[0] = (uint16_t)ker_cnt.total;
  rec_err[1] = (uint16_t)(ker_cnt.total >> 16);
  rec_err[2] = ker_cnt.crc_err;
  rec_err[3] = ker_cnt.stat_err;
  rec_err[4] = ker_cnt.no_resp;
  rec_err[5] = ker_cnt.gated;
  rec_err[6] = ker_cnt.naks;
  rec_err[7] = ker_cnt.wr_fail;
  rec_err_ok = 1;
}

static void capture_sample(void) {
  rec_smp[0]  = (uint16_t)(smp_status | ((uint16_t)smp_e << 8));
  rec_smp[1]  = smp_pass;
  rec_smp[2]  = smp_fail;
  rec_smp[3]  = smp_r0;
  rec_smp[4]  = (uint16_t)smp_sum_d;
  rec_smp[5]  = (uint16_t)((uint32_t)smp_sum_d >> 16);
  rec_smp[6]  = (uint16_t)smp_sum_d2;
  rec_smp[7]  = (uint16_t)(smp_sum_d2 >> 16);
  rec_smp[8]  = (uint16_t)smp_c0;
  rec_smp[9]  = (uint16_t)(smp_c0 >> 16);
  rec_smp[10] = (uint16_t)smp_sum_c;
  rec_smp[11] = (uint16_t)((uint32_t)smp_sum_c >> 16);
  rec_smp_ok  = 1;
}

// 1 = the field is in *out; 0 = BAD_INDEX; 2 = SEQUENCE.
// `idx` is the whole 16-bit ARG, not a truncated byte: section 4.5 says BAD_INDEX
// covers an "index or value outside its range", so ARG 0x0100 must be rejected
// and not read as index 0 -- which would silently re-capture the record under a
// host that cannot see the substitution, because replies echo SUB and not the
// index (rule 9). The sequence check comes first: rule 11 orders SEQUENCE before
// index range.
static uint8_t record_read(uint16_t idx, uint8_t last, uint16_t *buf, uint8_t *ok,
                           void (*capture)(void), uint16_t *out) {
  if (idx != 0 && !*ok) return 2;                 // SEQUENCE
  if (idx > last)       return 0;                 // BAD_INDEX
  if (idx == 0) capture();
  *out = buf[idx];
  return 1;
}

// ================================
// Health, calibration status
// ================================
static uint8_t write_eligible(void) { return (uint8_t)(!arm_seen && run_3s); }

static uint16_t health_word(void) {
  ker_h_put(KER_H_FACTORY_MODE,   factory_mode);
  ker_h_put(KER_H_ARM_SEEN,       arm_seen);
  ker_h_put(KER_H_WRITE_ELIGIBLE, write_eligible());
  return ker_health;
}

static uint16_t cal_status(void) {
  uint8_t stored[KER_PAGE_BYTES];
  ker_page_info_t info;
  ker_userrow_read(stored);
  ker_page_inspect(stored, &info);

  uint16_t v = (uint16_t)((uint16_t)info.layout_ver << 8);
  if (info.magic_ok)  v |= 0x0002u;
  if (info.ver_ok)    v |= 0x0004u;
  if (info.crc_ok)    v |= 0x0008u;
  if (info.fields_ok) v |= 0x0010u;
  if ((v & 0x001Eu) == 0x001Eu) v |= 0x0001u;
  if (ker_sensor_comp_active()) v |= 0x0020u;
  if (info.virgin)    v |= 0x0040u;
  if (memcmp(stored, running_page, KER_PAGE_BYTES) != 0) v |= 0x0080u;
  return v;
}

// ================================
// SET_ID (section 4.9)
// ================================
static uint8_t do_set_id(uint8_t new_id) {
  uint8_t page[KER_PAGE_BYTES];

  if (staging_dirty) return NAK_STAGING_BUSY;

  if (id_from_page) {
    memcpy(page, running_page, KER_PAGE_BYTES);   // the running page, re-identified
    page[2] = new_id;
    ker_page_seal(page);
  } else {
    uint8_t stored[KER_PAGE_BYTES];
    ker_page_info_t info;
    ker_userrow_read(stored);
    ker_page_inspect(stored, &info);
    // A page that is invalid but not virgin may hold recoverable data; replacing
    // it takes a deliberate STAGE_* / COMMIT_CAL.
    if (!info.virgin) return NAK_BAD_PAGE;
    ker_page_build_identity(page, new_id);
  }
  return commit_page(page);
}

// ================================
// CMD=3 dispatch
// ================================
static void do_latch(void) {
  latched_angle = ker_sensor_angle();
  latched_raw15 = ker_sensor_raw15();
  latched_angle &= 0x1FFFFFUL;
  latch_valid = (uint8_t)!(ker_health & (KER_H_ANGLE_STALE | KER_H_ANGLE_DEGRADED |
                                         KER_H_NO_VALID_ANGLE));
  latch_count++;
  latch_any = 1;
}

// Returns 1 if the request was accepted (section 4.3 rule 7).
static uint8_t dispatch(uint8_t sub, uint16_t arg) {
  uint16_t v = 0;
  uint8_t  r = 0;

  // --- gates W and F, in the precedence order of rule 11 ------------------
  // Gate R is already open or we would not be here. LOCK is gate R, although it
  // sits among the write subcommands, so that a module can always be locked.
  if (sub >= SUB_UNLOCK_1 && sub != SUB_LOCK) {
    if (!write_eligible()) { nak(sub, NAK_NOT_ELIGIBLE); return 0; }
    if (sub >= SUB_STAGE_ADDR && !factory_mode) { nak(sub, NAK_NOT_UNLOCKED); return 0; }
  }

  switch (sub) {
    case SUB_PING:          reply(sub, 0xA5A5u); return 1;

    case SUB_GET_FW_VER:
      if (arg > 3) { nak(sub, NAK_BAD_INDEX); return 0; }
      switch (arg) {
        case 0: v = (uint16_t)((KER_FW_MAJOR << 8) | KER_FW_MINOR); break;
        case 1: v = (uint16_t)KER_FW_PATCH;                         break;
        case 2: v = (uint16_t)KER_GIT_HASH;                         break;
        default: v = KER_GIT_DIRTY ? 1u : 0u;                       break;
      }
      reply(sub, v); return 1;

    case SUB_GET_PROTO_VER: reply(sub, KER_PROTO_VER); return 1;

    case SUB_GET_DEVICE_ID:
      reply(sub, (uint16_t)(device_id | (id_from_page ? 0x0100u : 0u))); return 1;

    case SUB_GET_HEALTH:    reply(sub, health_word());            return 1;
    case SUB_GET_STAT:      reply(sub, ker_sensor_stat());        return 1;
    case SUB_GET_DMAG:      reply(sub, ker_sensor_dmag());        return 1;
    case SUB_GET_SAFETY:    reply(sub, ker_sensor_safety());      return 1;
    case SUB_GET_CFG_VERIFY:reply(sub, ker_sensor_cfg_verify());  return 1;
    case SUB_GET_CAL_STATUS:reply(sub, cal_status());             return 1;

    case SUB_GET_ENV:
      if (arg > 1) { nak(sub, NAK_BAD_INDEX); return 0; }
      reply(sub, arg ? ker_sensor_vdd() : ker_sensor_fsync()); return 1;

    case SUB_GET_TRIM:
      if (arg > 4) { nak(sub, NAK_BAD_INDEX); return 0; }
      reply(sub, ker_sensor_trim((uint8_t)arg)); return 1;

    case SUB_GET_SERNUM: {
      if (arg > 4) { nak(sub, NAK_BAD_INDEX); return 0; }
      const volatile uint8_t *p = &SIGROW_SERNUM0;
      reply(sub, (uint16_t)(p[2 * arg] | ((uint16_t)p[2 * arg + 1] << 8))); return 1;
    }

    case SUB_GET_CAL_WORD:
    case SUB_GET_RUN_WORD: {
      if (arg > 15) { nak(sub, NAK_BAD_INDEX); return 0; }
      if (sub == SUB_GET_RUN_WORD) {
        reply(sub, ker_page_word(running_page, (uint8_t)arg));
      } else {
        uint8_t stored[KER_PAGE_BYTES];
        ker_userrow_read(stored);
        reply(sub, ker_page_word(stored, (uint8_t)arg));
      }
      return 1;
    }

    case SUB_GET_ANGLE_RAW:
      r = record_read(arg, 4, rec_raw, &rec_raw_ok, capture_raw, &v); break;
    case SUB_GET_ANGLE_COMP:
      r = record_read(arg, 1, rec_comp, &rec_comp_ok, capture_comp, &v); break;
    case SUB_GET_LATCHED:
      r = record_read(arg, 3, rec_latch, &rec_latch_ok, capture_latch, &v); break;
    case SUB_GET_ERRCNT:
      r = record_read(arg, 7, rec_err, &rec_err_ok, capture_err, &v); break;
    case SUB_GET_SAMPLE:
      r = record_read(arg, 11, rec_smp, &rec_smp_ok, capture_sample, &v); break;

    case SUB_CLR_ERRCNT:
      if (arg != MAGIC_CLR_ERRCNT) { nak(sub, NAK_BAD_ARG); return 0; }
      ker_health_clear_counters();
      reply(sub, 0); return 1;

    case SUB_SAMPLE_START:
      if ((arg >> 8) != TAG_SAMPLE_START) { nak(sub, NAK_BAD_ARG); return 0; }
      if ((arg & 0xFFu) > 10u)            { nak(sub, NAK_BAD_INDEX); return 0; }
      sample_start((uint8_t)(arg & 0xFFu));
      reply(sub, 0); return 1;

    case SUB_UNLOCK_1:
      if (factory_mode)               { nak(sub, NAK_SEQUENCE); return 0; }
      if (arg != MAGIC_UNLOCK_1)      { nak(sub, NAK_BAD_ARG);  return 0; }
      unlock_armed = 1; unlock_armed_at = millis();
      reply(sub, 0); return 1;

    case SUB_UNLOCK_2:
      if (!factory_mode && !unlock_armed) { nak(sub, NAK_SEQUENCE); return 0; }
      if (arg != (uint16_t)(MAGIC_UNLOCK_2 ^ sernum_digest)) {
        unlock_armed = 0;                       // a wrong ARG disarms (section 4.9)
        nak(sub, NAK_BAD_ARG); return 0;        // factory mode, if active, continues
      }
      if (!factory_mode) {
        factory_mode = 1;
        memset(staging, 0xFF, KER_PAGE_BYTES);
        staging_index = 0; staging_dirty = 0;
        ker_h_set(KER_H_FACTORY_MODE);
      }
      unlock_armed = 0;
      reply(sub, 0); return 1;

    case SUB_STAGE_ADDR:
      if ((arg >> 8) != TAG_STAGE_ADDR) { nak(sub, NAK_BAD_ARG); return 0; }
      if ((arg & 0xFFu) > 15u)          { nak(sub, NAK_BAD_INDEX); return 0; }
      staging_index = (uint8_t)(arg & 0xFFu);
      reply(sub, staging_index); return 1;

    case SUB_STAGE_DATA:
      if (staging_index > 15u) { nak(sub, NAK_BAD_INDEX); return 0; }   // nothing written
      ker_page_set_word(staging, staging_index, arg);
      staging_index++;
      staging_dirty = 1;
      reply(sub, staging_index); return 1;

    case SUB_COMMIT_CAL: {
      if (arg != MAGIC_COMMIT_CAL) { nak(sub, NAK_BAD_ARG); return 0; }
      ker_page_info_t info;
      ker_page_inspect(staging, &info);
      if (info.err == KER_PAGE_ERR_CRC) { nak(sub, NAK_CRC_FAIL); return 0; }
      if (info.err != KER_PAGE_OK)      { nak(sub, NAK_BAD_PAGE); return 0; }
      uint8_t e = commit_page(staging);
      if (e) { nak(sub, e); return 0; }         // stays unlocked, buffer intact
      end_factory_mode();
      reply(sub, device_id); return 1;
    }

    case SUB_SET_ID: {
      if ((arg >> 8) != TAG_SET_ID)                    { nak(sub, NAK_BAD_ARG); return 0; }
      uint8_t new_id = (uint8_t)(arg & 0xFFu);
      if (new_id < KER_ID_MIN || new_id > KER_ID_MAX)  { nak(sub, NAK_BAD_INDEX); return 0; }
      uint8_t e = do_set_id(new_id);
      if (e) { nak(sub, e); return 0; }
      end_factory_mode();
      reply(sub, device_id); return 1;
    }

    case SUB_LOCK:
      if (arg != MAGIC_LOCK) { nak(sub, NAK_BAD_ARG); return 0; }
      end_factory_mode();
      reply(sub, 0); return 1;                  // idempotent

    case SUB_RESET:
      if (arg != MAGIC_RESET) { nak(sub, NAK_BAD_ARG); return 0; }
      _PROTECTED_WRITE(RSTCTRL.SWRR, RSTCTRL_SWRE_bm);
      for (;;) { }                              // not reached

    default:
      nak(sub, NAK_UNSUPPORTED); return 0;      // SUB 0x00 as a request
  }

  // The indexed-record subcommands land here.
  if (r == 0) { nak(sub, NAK_BAD_INDEX); return 0; }
  if (r == 2) { nak(sub, NAK_SEQUENCE);  return 0; }
  reply(sub, v);
  return 1;
}

// ================================
// Frame hook
// ================================
void ker_on_frame(uint8_t id, uint8_t cmd, uint32_t data) {
  uint32_t now = millis();
  if (!run_100ms && now >= T_IDLE_MS)     run_100ms = 1;
  if (!run_3s    && now >= T_ARM_WAIT_MS) run_3s = 1;

  cmd &= 0x03u;

  if (cmd == 1u || cmd == 2u) {
    // C2, C3 and section 4.9: cascade traffic closes the read gate, ends factory
    // mode, disarms an unlock and aborts a sample run; CMD=2 also latches
    // `arm_seen`, which nothing but a power cycle clears.
    last_arm_frame = now;
    if (cmd == 2u) arm_seen = 1;
    if (factory_mode || unlock_armed) end_factory_mode();
    sample_abort();
    return;
  }
  if (cmd != 3u) return;                        // CMD=0 is unused and inert

  uint8_t bcast = (uint8_t)(id == 0u);
  if (!bcast && id != device_id) return;        // not ours

  uint8_t  sub = (uint8_t)((data >> 16) & 0x1Fu);
  uint16_t arg = (uint16_t)(data & 0xFFFFu);

  // Gate R (C2). Closed means silence, not a NAK. Counter 5 counts only what
  // this module would otherwise have acted on.
  if (!run_100ms || (now - last_arm_frame) < T_IDLE_MS) {
    if (!bcast || sub == SUB_LATCH_SYNC) ker_cnt_bump(&ker_cnt.gated);
    return;
  }

  if (factory_mode && (now - factory_last_accept) >= T_FACTORY_MS) end_factory_mode();
  if (unlock_armed && (now - unlock_armed_at)     >= T_UNLOCK_MS)   unlock_armed = 0;

  if (bcast) {
    // Broadcasts never reply, not even a NAK; only LATCH_SYNC acts.
    // Section 4.9 times factory mode out after 5 s "without an accepted request
    // TO THIS MODULE". A broadcast is addressed to no one, so it does not restart
    // the timer, even though rule 7 counts it as accepted.
    if (sub == SUB_LATCH_SYNC && arg == MAGIC_LATCH_SYNC) do_latch();
    return;
  }

  uint8_t accepted = 0;
  if (sub == SUB_NAK)             nak(sub, NAK_UNSUPPORTED);      // rule 11: SUB first
  else if (sub == SUB_LATCH_SYNC) nak(sub, NAK_BAD_ADDRESSING);   // then addressing
  else                            accepted = dispatch(sub, arg);

  // Section 4.9: the window survives only an accepted UNLOCK_1, which has just
  // re-armed it. Every OTHER addressed request disarms -- including a wrong ARG,
  // the UNLOCK_2 that consumed it, and the two NAK'd cases above. Letting those
  // two through would break the "next request" rule that makes a mis-decoded
  // frame (T6) fail safe.
  if (!(sub == SUB_UNLOCK_1 && accepted)) unlock_armed = 0;
  if (accepted) factory_last_accept = now;
}
