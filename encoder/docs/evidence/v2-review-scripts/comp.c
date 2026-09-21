/* Feasibility prototype: fixed-point 3-harmonic compensation in 21-bit angle space.
   Goal: verify max |fixed - double| <= 0.005 deg over the full circle. */
#include <stdint.h>
#include <stdio.h>
#include <math.h>
#include <stdlib.h>

#define ANG_BITS 21
#define ANG_FULL (1UL << ANG_BITS)      /* 2097152 */
#define ANG_MASK (ANG_FULL - 1UL)

/* Quarter-wave sine table, Q15, 65 entries: sin(i/64 * pi/2) * 32767 */
static int16_t sinq[65];

static void build_table(void) {
    for (int i = 0; i <= 64; i++)
        sinq[i] = (int16_t)lround(sin((double)i / 64.0 * M_PI / 2.0) * 32767.0);
}

/* sin of a 16-bit binary angle (0..65535 == 0..360deg), returns Q15 */
static int16_t sin_q15(uint16_t a) {
    uint8_t quad = (uint8_t)(a >> 14);          /* 0..3 */
    uint16_t x = a & 0x3FFF;                     /* 0..16383 within quadrant */
    if (quad & 1) x = (uint16_t)(0x4000 - x);    /* mirror in quadrants 1,3 */
    uint8_t  idx  = (uint8_t)(x >> 8);           /* 0..63 */
    uint8_t  frac = (uint8_t)(x & 0xFF);
    int16_t  a0 = sinq[idx], a1 = sinq[idx + 1];
    int16_t  v  = (int16_t)(a0 + (int16_t)(((int32_t)(a1 - a0) * frac) >> 8));
    return (quad & 2) ? (int16_t)(-v) : v;
}

typedef struct { int16_t amp[3]; uint16_t phase[3]; } cal_t;

/* Fixed-point compensation. u: 21-bit angle. amp in 21-bit LSB, phase in 16-bit BAM. */
uint32_t compensate_fixed(uint32_t u, const cal_t *c) {
    int32_t delta = 0;
    for (uint8_t k = 1; k <= 3; k++) {
        uint32_t arg = ((uint32_t)k * u) & ANG_MASK;         /* k*theta, 21-bit */
        uint16_t a16 = (uint16_t)((arg >> (ANG_BITS - 16)) + c->phase[k - 1]);
        delta += ((int32_t)c->amp[k - 1] * sin_q15(a16)) >> 15;
    }
    return (uint32_t)(((int32_t)u - delta) & (int32_t)ANG_MASK);
}

/* Double reference of the SAME formula. */
double compensate_double(uint32_t u, const cal_t *c) {
    double th = (double)u / (double)ANG_FULL * 2.0 * M_PI;
    double delta = 0.0;
    for (int k = 1; k <= 3; k++) {
        double ph = (double)c->phase[k - 1] / 65536.0 * 2.0 * M_PI;
        delta += (double)c->amp[k - 1] * sin((double)k * th + ph);
    }
    double r = fmod((double)u - delta, (double)ANG_FULL);
    if (r < 0) r += (double)ANG_FULL;
    return r;
}

int main(void) {
    build_table();
    /* Worst-case-ish calibration: large harmonic amplitudes (~1.5 deg on H1). */
    cal_t cases[] = {
        {{ 8738,  5243,  1748}, {     0, 16384, 32768}},  /* 1.5, 0.9, 0.3 deg */
        {{-8738, -5243, -1748}, { 12345, 54321,  1111}},
        {{32767, 16384,  8192}, { 65535,     1, 40000}},  /* 5.6 deg, extreme */
        {{  583,   291,    58}, {  9000, 21000, 60000}},  /* 0.1, 0.05, 0.01 deg */
    };
    double lsb_deg = 360.0 / (double)ANG_FULL;
    for (unsigned ci = 0; ci < sizeof(cases)/sizeof(cases[0]); ci++) {
        double worst = 0.0; uint32_t worst_u = 0;
        /* Sweep every one of the 32768 reachable 15-bit sensor codes, mapped to 21-bit. */
        for (uint32_t raw15 = 0; raw15 < 32768; raw15++) {
            uint32_t u = (raw15 << 6) | (raw15 >> 9);
            uint32_t f = compensate_fixed(u, &cases[ci]);
            double   d = compensate_double(u, &cases[ci]);
            double   e = fabs((double)f - d);
            if (e > ANG_FULL / 2.0) e = ANG_FULL - e;   /* wrap-aware */
            if (e > worst) { worst = e; worst_u = u; }
        }
        printf("case %u: max err = %8.3f LSB = %.6f deg  (at u=%lu)  %s\n",
               ci, worst, worst * lsb_deg, (unsigned long)worst_u,
               worst * lsb_deg <= 0.005 ? "PASS" : "FAIL");
    }
    printf("\n21-bit LSB = %.6f deg ; 15-bit sensor LSB = %.6f deg\n",
           lsb_deg, 360.0 / 32768.0);
    printf("sine table = %zu bytes flash\n", sizeof(sinq));
    return 0;
}
