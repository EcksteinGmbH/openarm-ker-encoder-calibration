/* Copyright 2026 Eckstein GmbH Apache-2.0; see LICENSE.txt at the repository root.
 * MODIFICATION NOTICE: new file, not present in upstream OpenArm.
 *
 * Host unit tests of src/ker_cal.c (deliverable 5, spec section 11.2 items 1 and 5):
 * the CRC-16, the page validation of section 5.2 with virgin, corrupted,
 * wrong-version and out-of-range pages, and the USERROW commit paths of section
 * 4.9 against the RAM USERROW the host build provides. */
#include <string.h>
#include "ker_assert.h"
#include "../src/ker_cal.h"

static void good_page(uint8_t *p, uint8_t id, uint8_t n) {
  memset(p, 0, KER_PAGE_BYTES);
  p[0] = KER_PAGE_MAGIC;
  p[1] = KER_LAYOUT_VER;
  p[2] = id;
  p[3] = 7;                                     /* STATION_ID */
  ker_page_set_word(p, 2, (uint16_t)(200u | ((uint16_t)n << 12)));   /* CAL_DAY 200 */
  for (uint8_t k = 0; k < n; k++) {
    ker_page_set_word(p, (uint8_t)(2 * k + 3), (uint16_t)(int16_t)(-1000 * (k + 1)));
    ker_page_set_word(p, (uint8_t)(2 * k + 4), (uint16_t)(5000 * (k + 1)));
  }
  ker_page_seal(p);
}

int main(void) {
  uint8_t p[KER_PAGE_BYTES], back[KER_PAGE_BYTES];
  ker_page_info_t in;

  SECTION("CRC-16/CCITT-FALSE against published vectors");
  {
    CHECK(ker_crc16((const uint8_t *)"123456789", 9) == 0x29B1,
          "CRC16(\"123456789\") = 0x%04X, expected 0x29B1", ker_crc16((const uint8_t *)"123456789", 9));
    uint8_t ff[30];
    memset(ff, 0xFF, sizeof ff);
    CHECK(ker_crc16(ff, 30) == 0x5FBD,
          "CRC16(30 x 0xFF) = 0x%04X, spec section 5.2 says 0x5FBD", ker_crc16(ff, 30));
  }

  SECTION("a virgin page is rejected, and reported as virgin");
  {
    memset(p, 0xFF, KER_PAGE_BYTES);
    ker_page_inspect(p, &in);
    CHECK(in.err == KER_PAGE_ERR_CRC, "virgin page err = %d, expected CRC", in.err);
    CHECK(in.virgin == 1, "virgin page not flagged virgin");
    CHECK(in.magic_ok == 0, "virgin page reports a valid magic");
  }

  SECTION("a well-formed page is accepted and decoded");
  {
    good_page(p, 12, 6);
    ker_page_inspect(p, &in);
    CHECK(in.err == KER_PAGE_OK, "good page rejected, err = %d", in.err);
    CHECK(in.device_id == 12 && in.station_id == 7 && in.cal_day == 200 && in.n_harm == 6,
          "fields decoded wrong: id %u station %u day %u n %u",
          in.device_id, in.station_id, in.cal_day, in.n_harm);
    ker_cal_t cal;
    ker_page_to_cal(p, &in, &cal);
    CHECK(cal.n == 6 && cal.amp[0] == -1000 && cal.phase[0] == 5000 &&
          cal.amp[5] == -6000 && cal.phase[5] == 30000, "coefficients decoded wrong");
  }

  SECTION("every check of spec section 5.2, in its order");
  {
    good_page(p, 12, 6); p[17] ^= 0x01;                 /* payload bit flip, CRC now stale */
    ker_page_inspect(p, &in);
    CHECK(in.err == KER_PAGE_ERR_CRC, "bit flip: err %d", in.err);

    good_page(p, 12, 6); p[0] = 0x4C; ker_page_seal(p); /* wrong magic, CRC valid */
    ker_page_inspect(p, &in);
    CHECK(in.err == KER_PAGE_ERR_MAGIC, "wrong magic: err %d", in.err);

    good_page(p, 12, 6); p[1] = 2; ker_page_seal(p);
    ker_page_inspect(p, &in);
    CHECK(in.err == KER_PAGE_ERR_VER, "wrong layout version: err %d", in.err);
    CHECK(in.layout_ver == 2 && in.magic_ok == 1,
          "GET_CAL_STATUS could not report the stored version");

    /* ID 0 is the master, 31 is unprovisioned, and 33 would transmit as wire ID 1
     * and answer the M5's own trigger (spec section 5.2). */
    const uint8_t bad_ids[] = {0, 31, 33, 255};
    for (unsigned i = 0; i < sizeof bad_ids; i++) {
      good_page(p, bad_ids[i], 6); ker_page_seal(p);
      ker_page_inspect(p, &in);
      CHECK(in.err == KER_PAGE_ERR_ID, "ID %u accepted (err %d)", bad_ids[i], in.err);
    }
    for (uint8_t id = KER_ID_MIN; id <= KER_ID_MAX; id++) {
      good_page(p, id, 3);
      ker_page_inspect(p, &in);
      CHECK(in.err == KER_PAGE_OK, "ID %u rejected", id);
    }

    for (uint8_t n = 7; n <= 15; n++) {
      good_page(p, 12, 6);
      ker_page_set_word(p, 2, (uint16_t)(200u | ((uint16_t)n << 12)));
      ker_page_seal(p);
      ker_page_inspect(p, &in);
      CHECK(in.err == KER_PAGE_ERR_NHARM, "N_HARM %u accepted (err %d)", n, in.err);
    }

    /* A slot above N_HARM carrying data would become live on a later version bump. */
    good_page(p, 12, 3);
    ker_page_set_word(p, 10, 1);                        /* H4_AMP while N_HARM = 3 */
    ker_page_seal(p);
    ker_page_inspect(p, &in);
    CHECK(in.err == KER_PAGE_ERR_SLOT, "populated slot above N_HARM accepted (err %d)", in.err);

    good_page(p, 12, 3);
    ker_page_set_word(p, 11, 1);                        /* H4_PHASE only */
    ker_page_seal(p);
    ker_page_inspect(p, &in);
    CHECK(in.err == KER_PAGE_ERR_SLOT, "populated phase slot above N_HARM accepted (err %d)", in.err);
  }

  SECTION("N_HARM = 0 is a valid identity page with no compensation");
  {
    ker_page_build_identity(p, 17);
    ker_page_inspect(p, &in);
    CHECK(in.err == KER_PAGE_OK, "identity page rejected, err %d", in.err);
    CHECK(in.device_id == 17 && in.n_harm == 0 && in.cal_day == 0 && in.station_id == 0,
          "identity page fields wrong");
    ker_cal_t cal;
    ker_page_to_cal(p, &in, &cal);
    CHECK(cal.n == 0, "identity page produced coefficients");
  }

  SECTION("re-identifying a running page keeps its coefficients (SET_ID)");
  {
    good_page(p, 5, 4);
    memcpy(back, p, KER_PAGE_BYTES);
    back[2] = 9;
    ker_page_seal(back);
    ker_page_inspect(back, &in);
    CHECK(in.err == KER_PAGE_OK && in.device_id == 9 && in.n_harm == 4,
          "re-identified page invalid or altered");
    CHECK(memcmp(p + 6, back + 6, 24) == 0, "re-identifying disturbed the coefficients");
  }

  SECTION("USERROW commit, read-back and the failure paths of spec section 4.9");
  {
    good_page(p, 21, 2);
    ker_test_program_fail = 0; ker_test_verify_corrupt = 0;
    CHECK(ker_userrow_program(p) == 1, "program of a good page failed");
    ker_userrow_read(back);
    CHECK(memcmp(p, back, KER_PAGE_BYTES) == 0, "read-back differs from what was written");

    memset(back, 0, sizeof back);
    ker_test_verify_corrupt = 1;
    good_page(p, 22, 2);
    CHECK(ker_userrow_program(p) == 0, "a corrupted read-back was reported as success");
    ker_test_verify_corrupt = 0;

    ker_test_program_fail = 1;
    CHECK(ker_userrow_program(p) == 0, "a failed program was reported as success");
    ker_test_program_fail = 0;

    /* After a failed write the stored page may be anything; what matters is that
     * validation catches it rather than the module booting on rubbish. */
    ker_userrow_read(back);
    ker_page_inspect(back, &in);
    CHECK(in.err != KER_PAGE_OK || in.device_id >= KER_ID_MIN,
          "a page that survived a failed write validated with an illegal ID");

    CHECK(KER_VDD_MIN_PROG_MV == 4500u, "VDD_MIN_PROG is not the 4.5 V of D19");
    ker_test_vdd_mv = 4400;
    CHECK(ker_vdd_mv() < KER_VDD_MIN_PROG_MV, "a 4.4 V supply would be allowed to program");
    ker_test_vdd_mv = 5000;
    CHECK(ker_vdd_mv() >= KER_VDD_MIN_PROG_MV, "a 5.0 V supply would be refused");
  }

  return ker_report("test_cal");
}
