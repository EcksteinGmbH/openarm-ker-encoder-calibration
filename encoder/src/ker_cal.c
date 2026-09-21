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
// fork. See ker_cal.h.
// ---------------------------------------------------------------------------

#include "ker_cal.h"

#ifdef __AVR__
#include <avr/io.h>
#include <avr/interrupt.h>
#endif

uint16_t ker_crc16(const uint8_t *data, uint8_t len) {
  uint16_t crc = 0xFFFF;
  for (uint8_t i = 0; i < len; i++) {
    crc ^= (uint16_t)data[i] << 8;
    for (uint8_t b = 0; b < 8; b++) {
      crc = (crc & 0x8000u) ? (uint16_t)((crc << 1) ^ 0x1021u) : (uint16_t)(crc << 1);
    }
  }
  return crc;
}

uint16_t ker_page_word(const uint8_t *page, uint8_t i) {
  return (uint16_t)page[2u * i] | ((uint16_t)page[2u * i + 1u] << 8);
}

void ker_page_set_word(uint8_t *page, uint8_t i, uint16_t v) {
  page[2u * i]      = (uint8_t)(v & 0xFF);
  page[2u * i + 1u] = (uint8_t)(v >> 8);
}

void ker_page_inspect(const uint8_t *page, ker_page_info_t *info) {
  uint8_t virgin = 1;
  for (uint8_t i = 0; i < KER_PAGE_BYTES; i++) {
    if (page[i] != 0xFF) { virgin = 0; break; }
  }
  info->virgin     = virgin;
  info->layout_ver = page[1];
  info->device_id  = page[2];
  info->station_id = page[3];
  info->cal_day    = (uint16_t)(ker_page_word(page, 2) & 0x0FFFu);
  info->n_harm     = (uint8_t)(ker_page_word(page, 2) >> 12);
  info->crc_ok     = (ker_crc16(page, KER_PAGE_BYTES - 2) == ker_page_word(page, 15)) ? 1u : 0u;
  info->magic_ok   = (page[0] == KER_PAGE_MAGIC) ? 1u : 0u;
  info->ver_ok     = (info->layout_ver == KER_LAYOUT_VER) ? 1u : 0u;
  /* The four flags are independent so that GET_CAL_STATUS bits 1-4 tell the host
   * what is wrong, not merely that something is. `err` then follows the order of
   * spec section 5.2, which is what decides the NAK. */
  info->fields_ok  = (info->device_id >= KER_ID_MIN && info->device_id <= KER_ID_MAX &&
                      info->n_harm <= KER_NHARM_MAX) ? 1u : 0u;
  if (info->fields_ok) {
    /* Unpopulated slots must be zero in both words, so that a page cannot carry
     * data the running module ignores and a later N_HARM bump would enable. */
    for (uint8_t k = info->n_harm; k < KER_NHARM_MAX; k++) {
      if (ker_page_word(page, (uint8_t)(2u * k + 3u)) != 0u ||
          ker_page_word(page, (uint8_t)(2u * k + 4u)) != 0u) {
        info->fields_ok = 0; break;
      }
    }
  }

  if (!info->crc_ok)   { info->err = KER_PAGE_ERR_CRC;   return; }
  if (!info->magic_ok) { info->err = KER_PAGE_ERR_MAGIC; return; }
  if (!info->ver_ok)   { info->err = KER_PAGE_ERR_VER;   return; }
  if (info->device_id < KER_ID_MIN || info->device_id > KER_ID_MAX) {
    info->err = KER_PAGE_ERR_ID; return;
  }
  if (info->n_harm > KER_NHARM_MAX) { info->err = KER_PAGE_ERR_NHARM; return; }
  if (!info->fields_ok) { info->err = KER_PAGE_ERR_SLOT; return; }
  info->err = KER_PAGE_OK;
}

void ker_page_to_cal(const uint8_t *page, const ker_page_info_t *info, ker_cal_t *cal) {
  for (uint8_t k = 0; k < KER_NHARM_MAX; k++) { cal->amp[k] = 0; cal->phase[k] = 0; }
  if (info->err != KER_PAGE_OK) { cal->n = 0; return; }
  cal->n = info->n_harm;
  for (uint8_t k = 0; k < info->n_harm; k++) {
    cal->amp[k]   = (int16_t)ker_page_word(page, (uint8_t)(2u * k + 3u));
    cal->phase[k] =          ker_page_word(page, (uint8_t)(2u * k + 4u));
  }
}

void ker_page_seal(uint8_t *page) {
  ker_page_set_word(page, 15, ker_crc16(page, KER_PAGE_BYTES - 2));
}

void ker_page_build_identity(uint8_t *page, uint8_t device_id) {
  for (uint8_t i = 0; i < KER_PAGE_BYTES; i++) page[i] = 0;
  page[0] = KER_PAGE_MAGIC;
  page[1] = KER_LAYOUT_VER;
  page[2] = device_id;
  /* STATION_ID 0, CAL_DAY 0 (unknown), N_HARM 0, all coefficients zero. */
  ker_page_seal(page);
}

/* ------------------------------------------------------------------------- */
/* USERROW and supply                                                        */
/* ------------------------------------------------------------------------- */

#ifdef __AVR__

void ker_userrow_read(uint8_t *page) {
  const volatile uint8_t *ur = (const volatile uint8_t *)USER_SIGNATURES_START;
  for (uint8_t i = 0; i < KER_PAGE_BYTES; i++) page[i] = ur[i];
}

uint8_t ker_userrow_program(const uint8_t *page) {
  volatile uint8_t *ur = (volatile uint8_t *)USER_SIGNATURES_START;
  uint8_t sreg;

  /* USERROW is one 32-byte NVM page on this part (USER_SIGNATURES_PAGE_SIZE),
   * so the whole calibration is written by a single erase-write and a power
   * loss can never leave a half-updated page with a valid CRC. Writes to the
   * mapped addresses fill the shared page buffer; the command commits it.
   * Sequence and the cli() window follow megaTinyCore's own EEPROM write. */
  while (NVMCTRL.STATUS & (NVMCTRL_EEBUSY_bm | NVMCTRL_FBUSY_bm)) { }
  sreg = SREG;
  cli();
  for (uint8_t i = 0; i < KER_PAGE_BYTES; i++) ur[i] = page[i];
  _PROTECTED_WRITE_SPM(NVMCTRL.CTRLA, NVMCTRL_CMD_PAGEERASEWRITE_gc);
  SREG = sreg;
  while (NVMCTRL.STATUS & NVMCTRL_EEBUSY_bm) { }

  for (uint8_t i = 0; i < KER_PAGE_BYTES; i++) {
    if (ur[i] != page[i]) return 0;
  }
  return 1;
}

/* ADC0 measures the 1.1 V internal reference against VDD: res = 1024 * 1.1 / VDD.
 * Nothing else on the module uses the ADC, so this owns it outright and leaves
 * it enabled. The reference's own tolerance (a few percent, O2) is not
 * subtracted; spec section 5.5 takes that as failing safe.
 * CLK_PER / 16 = 1.25 MHz is inside the 1.5 MHz limit for 10-bit conversions;
 * SAMPCTRL lengthens sampling because the internal reference is a high-impedance
 * source, and INITDLY lets it settle after the ADC is enabled. */
static uint8_t vdd_pending;

static void vdd_setup(void) {
  /* Unconditionally, every time. megaTinyCore's init() has already enabled ADC0
   * with its own reference and prescaler for analogRead(), so "configure it only
   * if it is disabled" would silently measure the wrong thing. Nothing else on
   * the module uses the ADC, so taking it over outright is safe.
   * Disabling before reconfiguring makes the enable insert INITDLY, which is
   * what lets the reference settle. */
  VREF.CTRLA = (uint8_t)((VREF.CTRLA & (uint8_t)~VREF_ADC0REFSEL_gm) | VREF_ADC0REFSEL_1V1_gc);
  VREF.CTRLB = (uint8_t)(VREF.CTRLB | VREF_ADC0REFEN_bm);    /* force the reference on */
  ADC0.CTRLA    = 0;
  ADC0.CTRLC    = (uint8_t)(ADC_PRESC_DIV16_gc | ADC_REFSEL_VDDREF_gc | ADC_SAMPCAP_bm);
  ADC0.CTRLD    = ADC_INITDLY_DLY64_gc;
  ADC0.SAMPCTRL = 20;
  ADC0.MUXPOS   = ADC_MUXPOS_INTREF_gc;
  ADC0.CTRLA    = (uint8_t)(ADC_ENABLE_bm | ADC_RESSEL_10BIT_gc);
}

static uint16_t vdd_from_res(uint16_t res) {
  if (res == 0) return 0;                  /* no reading; the caller treats it as too low */
  return (uint16_t)((1024UL * 1100UL) / res);
}

uint16_t ker_vdd_mv(void) {
  vdd_setup();
  ADC0.INTFLAGS = ADC_RESRDY_bm;
  ADC0.COMMAND = ADC_STCONV_bm;                       /* first conversion: discarded */
  while (!(ADC0.INTFLAGS & ADC_RESRDY_bm)) { }
  (void)ADC0.RES;
  ADC0.COMMAND = ADC_STCONV_bm;
  while (!(ADC0.INTFLAGS & ADC_RESRDY_bm)) { }
  vdd_pending = 0;                                    /* this result supersedes any background one */
  return vdd_from_res(ADC0.RES);
}

void ker_vdd_start(void) {
  vdd_setup();
  ADC0.INTFLAGS = ADC_RESRDY_bm;
  ADC0.COMMAND  = ADC_STCONV_bm;
  vdd_pending   = 1;
}

uint8_t ker_vdd_ready(uint16_t *mv) {
  if (!vdd_pending || !(ADC0.INTFLAGS & ADC_RESRDY_bm)) return 0;
  *mv = vdd_from_res(ADC0.RES);
  vdd_pending = 0;
  return 1;
}

#else  /* host build: a RAM USERROW, so the commit paths are testable off-target */

uint8_t  ker_test_userrow[KER_PAGE_BYTES] = {
  0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
  0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
  0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF
};
uint8_t  ker_test_program_fail   = 0;
uint8_t  ker_test_verify_corrupt = 0;
uint16_t ker_test_vdd_mv         = 5000;

void ker_userrow_read(uint8_t *page) {
  for (uint8_t i = 0; i < KER_PAGE_BYTES; i++) page[i] = ker_test_userrow[i];
}

uint8_t ker_userrow_program(const uint8_t *page) {
  if (ker_test_program_fail) return 0;
  for (uint8_t i = 0; i < KER_PAGE_BYTES; i++) ker_test_userrow[i] = page[i];
  if (ker_test_verify_corrupt) ker_test_userrow[0] ^= 0x01;
  for (uint8_t i = 0; i < KER_PAGE_BYTES; i++) {
    if (ker_test_userrow[i] != page[i]) return 0;
  }
  return 1;
}

uint16_t ker_vdd_mv(void) { return ker_test_vdd_mv; }
void     ker_vdd_start(void) { }
uint8_t  ker_vdd_ready(uint16_t *mv) { *mv = ker_test_vdd_mv; return 1; }

#endif
