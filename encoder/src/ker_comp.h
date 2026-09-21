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
// fork to implement the harmonic compensation of protocol-spec.md section 7.
// ---------------------------------------------------------------------------

/* Harmonic compensation, spec v6 section 7. Integer only; builds for AVR and host. */
#ifndef KER_COMP_H
#define KER_COMP_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define KER_NHARM_MAX 6

typedef struct {
  uint8_t  n;                     /* harmonics populated, 0..6 */
  int16_t  amp[KER_NHARM_MAX];    /* 21-bit LSB */
  uint16_t phase[KER_NHARM_MAX];  /* BAM16: 65536 == 360 deg */
} ker_cal_t;

/* Q15 sine of a 16-bit binary angle (65536 == 360 deg). Exported for tests. */
int16_t  ker_sin_q15(uint16_t a);

/* 15-bit sensor code -> 21-bit payload. See spec section 7.1. */
uint32_t ker_compensate(uint16_t raw15, const ker_cal_t *c);

#ifdef __cplusplus
}
#endif
#endif /* KER_COMP_H */
