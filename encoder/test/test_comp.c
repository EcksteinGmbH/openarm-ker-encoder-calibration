/* Copyright 2026 Eckstein GmbH Apache-2.0; see LICENSE.txt at the repository root.
 * MODIFICATION NOTICE: new file, not present in upstream OpenArm.
 *
 * Host unit tests of src/ker_comp.c (deliverable 5, spec section 11.2 item 1).
 * Everything here is checked against an independent double-precision model of
 * the same equation, never against ker_comp.c's own intermediate values.
 *
 * Host tests alone are NOT sufficient: on this host `int` is 32 bits and on the
 * ATtiny1616 it is 16, so a missing cast passes here and fails on the target.
 * That is what the AVR differential test and its mutants exist for (run_tests.sh). */
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include "ker_assert.h"
#include "../src/ker_comp.h"

#define LSB_DEG (360.0 / 2097152.0)
#define BUDGET_DEG 0.005          /* the brief's fixed-point error budget */

/* Independent double model of spec section 7.1, argument defined from raw15. */
static double ref_out(uint16_t r, const ker_cal_t *c) {
  double u = c->n ? (double)((uint32_t)r << 6)
                  : (double)(((uint32_t)r << 6) | (r >> 9));
  double th = r * 2.0 * M_PI / 32768.0, d = 0.0;
  for (int k = 0; k < c->n; k++)
    d += c->amp[k] * sin((k + 1) * th + c->phase[k] * 2.0 * M_PI / 65536.0);
  double o = fmod(u + d, 2097152.0);
  return o < 0 ? o + 2097152.0 : o;
}

static double max_err_lsb(const ker_cal_t *c) {
  double w = 0;
  for (uint32_t r = 0; r < 32768; r++) {
    double e = fabs((double)ker_compensate((uint16_t)r, c) - ref_out((uint16_t)r, c));
    if (e > 1048576.0) e = 2097152.0 - e;     /* the short way round the seam */
    if (e > w) w = e;
  }
  return w;
}

/* The constructed worst cases of spec section 7.5, recorded as regression
 * vectors so that the test does not have to repeat the 2^31 search that found
 * them (docs/evidence/v3-reference/results/accuracy_constructed_worst.txt). */
static const struct { uint8_t n; int16_t a[6]; uint16_t p[6]; double lsb; } worst[] = {
  {1, {-32495}, {47157}, 6.419},
  {2, {-32609, 32654}, {51147, 18379}, 8.859},
  {3, {32677, -32763, -32591}, {14389, 51147, 47157}, 11.300},
  {4, {32710, 32642, -32749, 32755}, {14389, 14389, 47157, 18379}, 13.701},
  {5, {32462, 32362, -32565, -32542, -32707}, {18379, 18379, 47157, 51147, 47157}, 16.122},
  {6, {-32739, 32545, 32760, -32597, 32670, -32366},
      {51147, 18379, 18379, 51142, 14394, 51147}, 18.561},
};

int main(void) {
  ker_cal_t c;
  memset(&c, 0, sizeof c);

  SECTION("uncalibrated path is upstream's mapping, bit for bit, all 32768 codes");
  {
    unsigned bad = 0;
    c.n = 0;
    for (uint32_t r = 0; r < 32768; r++) {
      uint32_t up = ((uint32_t)r << 6) | (r >> 9);      /* upstream main.cpp:367-368 */
      if (ker_compensate((uint16_t)r, &c) != up) bad++;
    }
    CHECK(bad == 0, "n=0: %u codes differ from upstream", bad);
  }

  SECTION("n out of range is treated as uncalibrated, not as an overrun");
  {
    unsigned bad = 0;
    for (uint8_t n = 7; n < 255; n++) {
      c.n = n;
      for (uint8_t k = 0; k < 6; k++) { c.amp[k] = 12345; c.phase[k] = 4321; }
      for (uint32_t r = 0; r < 32768; r += 337) {
        uint32_t up = ((uint32_t)r << 6) | (r >> 9);
        if (ker_compensate((uint16_t)r, &c) != up) bad++;
      }
    }
    CHECK(bad == 0, "n>6: %u codes are not the uncalibrated mapping", bad);
  }

  SECTION("every calibrated output is a multiple of 8 LSB (D22)");
  {
    unsigned bad = 0;
    srand(7);
    for (int t = 0; t < 200; t++) {
      c.n = (uint8_t)(1 + rand() % 6);
      for (uint8_t k = 0; k < 6; k++) {
        c.amp[k] = (int16_t)(rand() & 0xFFFF);
        c.phase[k] = (uint16_t)(rand() & 0xFFFF);
      }
      for (uint32_t r = 0; r < 32768; r += 97)
        if (ker_compensate((uint16_t)r, &c) % 8u) bad++;
    }
    CHECK(bad == 0, "%u calibrated outputs are not on the 8-LSB grid", bad);
  }

  SECTION("output always inside 21 bits, including across the seam");
  {
    unsigned bad = 0, below = 0, above = 0;
    c.n = 6;
    for (uint8_t k = 0; k < 6; k++) { c.amp[k] = -32768; c.phase[k] = (uint16_t)(k * 7777u); }
    for (uint32_t r = 0; r < 32768; r++) {
      uint32_t o = ker_compensate((uint16_t)r, &c);
      if (o > 0x1FFFFFu) bad++;
      if ((int32_t)((uint32_t)r << 6) + (int32_t)(o - ((uint32_t)r << 6)) < 0) below++;
    }
    for (uint8_t k = 0; k < 6; k++) c.amp[k] = 32767;
    for (uint32_t r = 0; r < 32768; r++)
      if (ker_compensate((uint16_t)r, &c) > 0x1FFFFFu) bad++;
    (void)above;
    CHECK(bad == 0, "%u outputs outside 21 bits", bad);
  }

  SECTION("sine table against double, whole 16-bit angle range");
  {
    double w = 0;
    for (uint32_t a = 0; a < 65536; a++) {
      double e = fabs((double)ker_sin_q15((uint16_t)a) - 32767.0 * sin(2 * M_PI * a / 65536.0));
      if (e > w) w = e;
    }
    printf("  worst sine error: %.3f of 32767 (%.2e of full scale)\n", w, w / 32767.0);
    CHECK(w < 4.0, "sine table error %.3f counts is larger than expected", w);
  }

  SECTION("constructed worst cases of spec section 7.5");
  {
    for (unsigned i = 0; i < sizeof worst / sizeof worst[0]; i++) {
      memset(&c, 0, sizeof c);
      c.n = worst[i].n;
      for (uint8_t k = 0; k < worst[i].n; k++) { c.amp[k] = worst[i].a[k]; c.phase[k] = worst[i].p[k]; }
      double e = max_err_lsb(&c);
      printf("  N=%u: %6.3f LSB = %.6f deg (recorded %.3f)\n",
             c.n, e, e * LSB_DEG, worst[i].lsb);
      CHECK(fabs(e - worst[i].lsb) < 0.002,
            "N=%u worst case moved: %.3f LSB, recorded %.3f", c.n, e, worst[i].lsb);
      CHECK(e * LSB_DEG <= BUDGET_DEG,
            "N=%u worst case %.6f deg exceeds the %.3f deg budget", c.n, e * LSB_DEG, BUDGET_DEG);
    }
  }

  SECTION("realistic coefficient sets stay far inside the budget");
  {
    double w = 0;
    srand(1);
    for (int t = 0; t < 60; t++) {
      double a = (double)(rand() % 8738);          /* H1 up to 1.5 deg */
      memset(&c, 0, sizeof c);
      c.n = 6;
      for (int k = 0; k < 6; k++) {
        c.amp[k] = (int16_t)((rand() & 1 ? 1 : -1) * a);
        a /= 1.7;
        c.phase[k] = (uint16_t)(rand() & 0xFFFF);
      }
      double e = max_err_lsb(&c);
      if (e > w) w = e;
    }
    printf("  realistic worst of 60 sets: %.3f LSB = %.6f deg\n", w, w * LSB_DEG);
    CHECK(w * LSB_DEG <= BUDGET_DEG, "realistic worst %.6f deg exceeds budget", w * LSB_DEG);
  }

  return ker_report("test_comp");
}
