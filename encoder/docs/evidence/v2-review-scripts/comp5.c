/* Extended verification harness: N harmonics (1..5), OOB detection, adversarial search. */
#include <stdint.h>
#include <stdio.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

#define ANG_BITS 21
#define ANG_FULL (1UL << ANG_BITS)
#define ANG_MASK (ANG_FULL - 1UL)
#define NH 5

static int16_t sinq[66];          /* one guard entry so we can DETECT the OOB safely */
static long oob_hits = 0;
static long guard_poison = 0;

static void build_table(void) {
    for (int i = 0; i <= 64; i++)
        sinq[i] = (int16_t)lround(sin((double)i / 64.0 * M_PI / 2.0) * 32767.0);
    sinq[65] = (int16_t)0x7777;   /* poison: if read AND used, result would be wrong */
}

static int16_t sin_q15(uint16_t a) {
    uint8_t quad = (uint8_t)(a >> 14);
    uint16_t x = a & 0x3FFF;
    if (quad & 1) x = (uint16_t)(0x4000 - x);
    uint8_t  idx  = (uint8_t)(x >> 8);
    uint8_t  frac = (uint8_t)(x & 0xFF);
    if (idx >= 64) { oob_hits++; if (frac) guard_poison++; }   /* idx+1 == 65 -> past end of a 65-entry table */
    int16_t  a0 = sinq[idx], a1 = sinq[idx + 1];
    int16_t  v  = (int16_t)(a0 + (int16_t)(((int32_t)(a1 - a0) * frac) >> 8));
    return (quad & 2) ? (int16_t)(-v) : v;
}

typedef struct { int16_t amp[NH]; uint16_t phase[NH]; int n; } cal_t;

static int32_t last_delta_max = 0, last_delta_min = 0;

uint32_t compensate_fixed(uint32_t u, const cal_t *c) {
    int32_t delta = 0;
    for (uint8_t k = 1; k <= c->n; k++) {
        uint32_t arg = ((uint32_t)k * u) & ANG_MASK;
        uint16_t a16 = (uint16_t)((arg >> (ANG_BITS - 16)) + c->phase[k - 1]);
        delta += ((int32_t)c->amp[k - 1] * sin_q15(a16)) >> 15;
    }
    if (delta > last_delta_max) last_delta_max = delta;
    if (delta < last_delta_min) last_delta_min = delta;
    return (uint32_t)(((int32_t)u - delta) & (int32_t)ANG_MASK);
}

double compensate_double(uint32_t u, const cal_t *c) {
    double th = (double)u / (double)ANG_FULL * 2.0 * M_PI;
    double delta = 0.0;
    for (int k = 1; k <= c->n; k++) {
        double ph = (double)c->phase[k - 1] / 65536.0 * 2.0 * M_PI;
        delta += (double)c->amp[k - 1] * sin((double)k * th + ph);
    }
    double r = fmod((double)u - delta, (double)ANG_FULL);
    if (r < 0) r += (double)ANG_FULL;
    return r;
}

/* sweep_mode: 0 = 32768 reachable codes (as in comp.c), 1 = ALL 2^21 codes */
static double sweep(const cal_t *c, int sweep_mode, uint32_t *worst_u) {
    double worst = 0.0; *worst_u = 0;
    uint32_t n = sweep_mode ? ANG_FULL : 32768;
    for (uint32_t i = 0; i < n; i++) {
        uint32_t u = sweep_mode ? i : ((i << 6) | (i >> 9));
        uint32_t f = compensate_fixed(u, c);
        double   d = compensate_double(u, c);
        double   e = fabs((double)f - d);
        if (e > ANG_FULL / 2.0) e = ANG_FULL - e;
        if (e > worst) { worst = e; *worst_u = u; }
    }
    return worst;
}

static double lsb_deg;

static void report(const char *tag, const cal_t *c, int mode) {
    uint32_t wu; double w = sweep(c, mode, &wu);
    printf("%-46s n=%d %s : %8.3f LSB = %.6f deg %s\n", tag, c->n,
           mode ? "ALL 2^21" : "32768rch", w, w*lsb_deg, w*lsb_deg <= 0.005 ? "PASS" : "**FAIL**");
}

int main(int argc, char **argv) {
    build_table(); lsb_deg = 360.0 / (double)ANG_FULL;

    printf("=== 1. spec 6.4 cases, but swept over ALL 2^21 codes (not just 32768 reachable) ===\n");
    cal_t c0 = {{ 8738,  5243,  1748,0,0}, {     0, 16384, 32768,0,0}, 3};
    cal_t c1 = {{-8738, -5243, -1748,0,0}, { 12345, 54321,  1111,0,0}, 3};
    cal_t c2 = {{32767, 16384,  8192,0,0}, { 65535,     1, 40000,0,0}, 3};
    cal_t c3 = {{  583,   291,    58,0,0}, {  9000, 21000, 60000,0,0}, 3};
    report("case0 1.5/0.9/0.3", &c0, 0); report("case0 1.5/0.9/0.3", &c0, 1);
    report("case1 neg",         &c1, 0); report("case1 neg",         &c1, 1);
    report("case2 5.63/2.81/1.41", &c2, 0); report("case2 5.63/2.81/1.41", &c2, 1);
    report("case3 small",       &c3, 0); report("case3 small",       &c3, 1);

    printf("\n=== 2. N_HARM = 5, spec-shaped coefficient sets ===\n");
    /* realistic geometric decay, scaled up to the layout's declared max on H1 */
    cal_t d0 = {{ 8738,  5243,  1748,  874,  437}, {0,16384,32768,49152,8000}, 5};
    cal_t d1 = {{32767, 16384,  8192, 4096, 2048}, {65535,1,40000,20000,30000}, 5};
    cal_t d2 = {{32767,-32767, 32767,-32767,32767}, {0,0,0,0,0}, 5};
    cal_t d3 = {{-32768,-32768,-32768,-32768,-32768}, {16384,16384,16384,16384,16384}, 5};
    report("5H geometric (1.5 deg H1)", &d0, 0);
    report("5H extreme geometric",      &d1, 0);
    report("5H all-max alternating",    &d2, 0);
    report("5H all INT16_MIN",          &d3, 0);
    report("5H all-max alternating",    &d2, 1);
    report("5H all INT16_MIN",          &d3, 1);
    printf("   delta range observed so far: [%ld .. %ld]  (int32 headroom fine)\n",
           (long)last_delta_min, (long)last_delta_max);

    printf("\n=== 3. table out-of-bounds accounting ===\n");
    printf("   sin_q15 calls with idx==64 (reads sinq[65], one past a 65-entry table): %ld\n", oob_hits);
    printf("   ... of which frac!=0 (would use the OOB value): %ld\n", guard_poison);

    printf("\n=== 4. randomized adversarial search, N_HARM=5 ===\n");
    srand(12345);
    double gw = 0; cal_t gc; int trials = atoi(argc>1?argv[1]:"400");
    for (int t = 0; t < trials; t++) {
        cal_t c; c.n = 5;
        for (int k = 0; k < 5; k++) {
            c.amp[k]   = (int16_t)((rand() % 65536) - 32768);
            c.phase[k] = (uint16_t)(rand() % 65536);
        }
        uint32_t wu; double w = sweep(&c, 0, &wu);
        if (w > gw) { gw = w; gc = c; }
    }
    printf("   worst of %d random 5H sets (full int16 amp range): %.3f LSB = %.6f deg %s\n",
           trials, gw, gw*lsb_deg, gw*lsb_deg <= 0.005 ? "PASS" : "**FAIL**");
    printf("   amps: "); for (int k=0;k<5;k++) printf("%d(%.3fdeg) ", gc.amp[k], gc.amp[k]*lsb_deg);
    printf("\n   phases: "); for (int k=0;k<5;k++) printf("%u ", gc.phase[k]); printf("\n");

    printf("\n=== 5. randomized adversarial search, N_HARM=5, REALISTIC amps (|H1|<=1.5deg, decaying) ===\n");
    srand(999); gw = 0;
    for (int t = 0; t < trials; t++) {
        cal_t c; c.n = 5;
        double base = 8738.0;
        for (int k = 0; k < 5; k++) {
            double s = base / pow(1.7, k);
            c.amp[k]   = (int16_t)lround(((rand()/(double)RAND_MAX)*2.0-1.0) * s);
            c.phase[k] = (uint16_t)(rand() % 65536);
        }
        uint32_t wu; double w = sweep(&c, 0, &wu);
        if (w > gw) { gw = w; gc = c; }
    }
    printf("   worst: %.3f LSB = %.6f deg %s\n", gw, gw*lsb_deg, gw*lsb_deg <= 0.005 ? "PASS" : "**FAIL**");

    printf("\n=== 6. systematic bias of the arithmetic right shift (>>15 rounds toward -inf) ===\n");
    {
        cal_t c = {{32767,32767,32767,32767,32767},{0,13107,26214,39321,52428},5};
        double sum=0; long n=0;
        for (uint32_t i=0;i<32768;i++){ uint32_t u=(i<<6)|(i>>9);
            sum += (double)compensate_fixed(u,&c) - compensate_double(u,&c); n++; }
        printf("   mean(fixed-double) over sweep = %+.4f LSB = %+.6f deg (5 terms, each biased +0.5 LSB by truncation)\n",
               sum/n, sum/n*lsb_deg);
    }
    return 0;
}
