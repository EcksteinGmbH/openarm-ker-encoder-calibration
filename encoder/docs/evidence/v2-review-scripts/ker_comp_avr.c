#include <stdint.h>
#include <avr/pgmspace.h>
#define ANG_MASK 0x1FFFFFUL
extern const int16_t sinq[65] PROGMEM;
typedef struct { int16_t amp[5]; uint16_t phase[5]; uint8_t n; } cal_t;

static int16_t sin_q15(uint16_t a) {
    uint8_t quad = (uint8_t)(a >> 14);
    uint16_t x = a & 0x3FFF;
    if (quad & 1) x = (uint16_t)(0x4000 - x);
    uint8_t idx = (uint8_t)(x >> 8), frac = (uint8_t)(x & 0xFF);
    int16_t a0 = (int16_t)pgm_read_word(&sinq[idx]);
    int16_t a1 = (int16_t)pgm_read_word(&sinq[idx+1]);
    int16_t v = (int16_t)(a0 + (int16_t)(((int32_t)(a1 - a0) * frac) >> 8));
    return (quad & 2) ? (int16_t)(-v) : v;
}
uint32_t ker_compensate(uint32_t u, const cal_t *c) {
    int32_t delta = 0;
    for (uint8_t k = 1; k <= c->n; k++) {
        uint32_t arg = ((uint32_t)k * u) & ANG_MASK;
        uint16_t a16 = (uint16_t)((arg >> 5) + c->phase[k-1]);
        delta += ((int32_t)c->amp[k-1] * sin_q15(a16)) >> 15;
    }
    return (uint32_t)(((int32_t)u - delta) & (int32_t)ANG_MASK);
}
