/* Host-only helper for station simulations: runs the real ker_compensate() over an array.
 * Build: gcc -O2 -shared -fPIC -o libref.so ref_comp.c batch.c */
#include "ref_comp.h"
void ker_compensate_batch(const uint16_t *raw15, uint32_t n, const ker_cal_t *c, uint32_t *out) {
  for (uint32_t i = 0; i < n; i++) out[i] = ker_compensate(raw15[i], c);
}
