/* Reference harmonic compensation, spec v3. Integer only; compiles for AVR and host. */
#ifndef REF_COMP_H
#define REF_COMP_H
#include <stdint.h>
#define KER_NHARM_MAX 6
typedef struct {
  uint8_t  n;                     /* harmonics populated, 0..6 */
  int16_t  amp[KER_NHARM_MAX];    /* 21-bit LSB */
  uint16_t phase[KER_NHARM_MAX];  /* BAM16: 65536 == 360 deg */
} ker_cal_t;
int16_t  ker_sin_q15(uint16_t a);
uint32_t ker_compensate(uint16_t raw15, const ker_cal_t *c);
#endif
