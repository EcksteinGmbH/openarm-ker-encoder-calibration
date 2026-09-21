// Copyright 2026 Enactic, Inc.
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
// New file, not present in upstream OpenArm. Its contents were MOVED, without
// functional change, out of upstream's encoder/src/main.cpp: the SSC pin
// assignment, the fast-I/O wrappers and the bit-bang primitives
// (clkLow .. sscRead16). They are needed in two translation units now, because
// the safety word has to be clocked inside the same CS-low window as the angle
// (protocol-spec.md section 6.1) and the boot configuration lock (section 6.2)
// drives the same pins. An upstream change to these primitives will conflict
// here rather than in main.cpp.
// ---------------------------------------------------------------------------

#ifndef KER_SSC_H
#define KER_SSC_H

#include <Arduino.h>

// ================================
// pin assign  (moved from main.cpp, unchanged)
// ================================
#define CLK  16
#define DATA_PIN 14
#define CS   13

// ================================
// fast I/O wrapper  (moved from main.cpp, unchanged)
// Assumes digitalWriteFast / digitalReadFast are available in megaTinyCore
// Falls back to standard functions if undefined in the environment
// ================================
#ifndef digitalWriteFast
  #define digitalWriteFast(pin, val) digitalWrite((pin), (val))
#endif

#ifndef digitalReadFast
  #define digitalReadFast(pin) digitalRead((pin))
#endif

#ifndef pinModeFast
  #define pinModeFast(pin, mode) pinMode((pin), (mode))
#endif

// ================================
// TLE5012B SSC read functions  (moved from main.cpp, unchanged)
// ================================

static inline void clkLow()  { digitalWriteFast(CLK, LOW); }
static inline void clkHigh() { digitalWriteFast(CLK, HIGH); }
static inline void csLow()   { digitalWriteFast(CS, LOW); }
static inline void csHigh()  { digitalWriteFast(CS, HIGH); }

static inline void dataOut() { pinModeFast(DATA_PIN, OUTPUT); }
static inline void dataIn()  { pinModeFast(DATA_PIN, INPUT); }

static inline void dataWrite(uint8_t v) {
  digitalWriteFast(DATA_PIN, v ? HIGH : LOW);
}

static inline uint8_t dataRead() {
  return digitalReadFast(DATA_PIN) ? 1 : 0;
}

// SSC:
// Sensor outputs data on rising edge
// Master reads on falling edge
// Optimized: pinMode calls moved outside bit loop

static inline void sscWrite16(uint16_t v) {
  dataOut();  // Set OUTPUT once at the start
  for (int8_t i = 15; i >= 0; --i) {
    dataWrite((v >> i) & 0x01);
    clkHigh();
    clkLow();
  }
}

static inline uint16_t sscRead16() {
  dataIn();  // Set INPUT once at the start
  uint16_t v = 0;
  for (int8_t i = 15; i >= 0; --i) {
    v <<= 1;
    clkHigh();
    clkLow();
    v |= dataRead();
  }
  return v;
}

#endif /* KER_SSC_H */
