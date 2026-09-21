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
// Modified from upstream OpenArm (enactic/openarm_ker_firmware @ ffd2aa2) by
// Eckstein GmbH, 2026, for the calibrated-encoder fork. The SSC pins, fast-I/O
// wrappers and bit-bang primitives were moved unchanged to ker_ssc.h; the
// AVAL-only read was replaced by ker_sensor.cpp's block transaction; the
// build-default ID became 31; and ker_init / ker_read_due / ker_read_angle /
// ker_on_frame were added. Each edit is marked "fork" below. The CMD=1 and
// CMD=2 reply paths are untouched. See docs/protocol-spec.md section 11.1 and
// CHANGELOG.md.
// ---------------------------------------------------------------------------

#include <Arduino.h>
#include <math.h>

// --- calibrated-encoder fork ---------------------------------------------
// The SSC primitives below were moved to ker_ssc.h unchanged; everything else
// the fork adds lives behind ker_init / ker_read_due / ker_read_angle /
// ker_on_frame. See docs/protocol-spec.md section 11.1 and CHANGELOG.md.
#include "ker_ssc.h"
#include "ker_cmd3.h"

// #define DEVICE_ID 1// Device ID (set in range 0-31)

// ================================
// pin assign
// ================================
// CLK, DATA_PIN and CS moved to ker_ssc.h (fork)
#define LED 9

#define TX 7
#define RX 6
#define EN 5

#define SERIAL_BAUD 2000000UL
#define SSC_INTERVAL_MS 20UL      // Max SSC read interval [ms]
#define CHAIN_MAX_ID 16             // Last ID in chain (wraps back to ID=1 after this)

#ifndef DEVICE_ID
#define DEVICE_ID 31 // Default value (fork: 31 = unprovisioned, spec section 5.4)
#endif

// ================================
// fast I/O wrapper moved to ker_ssc.h (fork)
// ================================

// ================================
// TLE5012B SSC command
// The fork reads STAT, ACSTAT, AVAL and the safety word in one transaction
// instead of AVAL alone; the command word lives in ker_sensor.cpp.
// ================================



// RS485 transmit buffer
static uint8_t tx_data[4];

// Packet receive state
static uint8_t r_id = 0, r_cmd = 0;
static uint32_t r_data = 0;

// Device configuration
static uint8_t device_id = DEVICE_ID;

// Latest sensor data (value sent via RS485)
static uint32_t latest_angle_21bit = 0;

// SSC read timing
static uint32_t last_ssc_time = 0;
static bool do_ssc_read = true;  // Read immediately on first iteration

// ================================
// CRC-8 0x07 calculation
// ================================
uint8_t crc8_0x07(const uint8_t *data, size_t len) {
  const uint8_t polynomial = 0x07;
  uint8_t crc = 0x00;
  for (size_t i = 0; i < len; ++i) {
    crc ^= data[i];
    for (uint8_t bit = 0; bit < 8; ++bit) {
      if (crc & 0x80) {
        crc = (uint8_t)(crc << 1) ^ polynomial;
      } else {
        crc = (uint8_t)(crc << 1);
      }
    }
  }
  return crc;
}

// ================================
// Optimized to reduce floating-point operations
// ================================

// ================================
// 4-byte packet builder
// ID   : 0-31
// CMD  : 0-3
// data : 0-2^21-1
// ================================
void makePacket21(uint8_t ID, uint8_t CMD, uint32_t data) {
  // Clamp to valid range
  ID   &= 0x1F;          // 5bit
  CMD  &= 0x03;          // 2bit
  uint32_t data21 = data & 0x1FFFFF;  // 21bit

  // Lower 7 bits of header = ID(5bit) + CMD(2bit)
  uint8_t header7 = (ID << 2) | CMD;  // 7bit
  uint8_t header  = 0x80 | header7;   // Set MSB=1

  // Split data into 3 bytes of 7 bits each (MSB always 0)
  uint8_t d0 =  data21        & 0x7F;    // bits [6:0]
  uint8_t d1 = (data21 >> 7)  & 0x7F;    // bits [13:7]
  uint8_t d2 = (data21 >> 14) & 0x7F;    // bits [20:14]

  tx_data[0] = header; // MSB=1
  tx_data[1] = d0;     // MSB=0
  tx_data[2] = d1;     // MSB=0
  tx_data[3] = d2;     // MSB=0
}

// ================================
// RS485 transmit
// ================================
void send485() {
  digitalWrite(LED, HIGH);
  digitalWrite(EN, HIGH);

  // Send payload
  Serial.write(tx_data[0]);
  Serial.write(tx_data[1]);
  Serial.write(tx_data[2]);
  Serial.write(tx_data[3]);

  // Push all bytes to the UART hardware
  Serial.flush();

  // Disable RS-485 driver and turn off LED
  digitalWrite(LED, LOW);
  digitalWrite(EN, LOW);
}

// ================================
// 4-byte packet receiver (non-blocking)
// Returns true on success
// Packet format: [H:1xxxxxxx] [d0:0xxxxxxx] [d1:0xxxxxxx] [d2:0xxxxxxx]
// Lower 7 bits of H = (ID<<2) | CMD
// ================================
bool receivePacket21(uint8_t &ID, uint8_t &CMD, uint32_t &data) {
  enum { WAIT_HEADER, GET_D0, GET_D1, GET_D2 };
  static uint8_t state = WAIT_HEADER;
  static uint8_t header = 0;
  static uint8_t d0 = 0, d1 = 0;

  while (Serial.available() > 0) {
    uint8_t b = (uint8_t)Serial.read();
    switch (state) {
      case WAIT_HEADER:
        if (b & 0x80) {
          header = b;
          state = GET_D0;
        }
        break;
      case GET_D0:
        if ((b & 0x80) == 0) {
          d0 = b;
          state = GET_D1;
        } else {
          state = WAIT_HEADER;
        }
        break;
      case GET_D1:
        if ((b & 0x80) == 0) {
          d1 = b;
          state = GET_D2;
        } else {
          state = WAIT_HEADER;
        }
        break;
      case GET_D2:
        if ((b & 0x80) == 0) {
          uint8_t d2 = b;
          uint8_t header7 = header & 0x7F;
          ID = header7 >> 2;
          CMD = header7 & 0x03;
          data = (uint32_t)d0 | ((uint32_t)d1 << 7) | ((uint32_t)d2 << 14);
          state = WAIT_HEADER;
          return true;
        } else {
          state = WAIT_HEADER;
        }
        break;
    }
  }

  return false;
}

// ================================
// TLE5012B SSC read functions moved to ker_ssc.h (fork); the AVAL-only
// transaction they served is replaced by ker_sensor.cpp's block read.
// ================================

// Treat as 15-bit signed value
static inline int16_t signExtend15(uint16_t raw) {
  uint16_t v15 = raw & 0x7FFF;
  if (v15 & 0x4000) {
    return (int16_t)(v15 | 0x8000);
  }
  return (int16_t)v15;
}

// For debugging (unused)
// static inline float rawToDeg(uint16_t raw) {
//   int16_t aval = signExtend15(raw);
//   return (float)aval * 360.0f / 32768.0f;
// }

void setup() {
  // GPIO init
  pinModeFast(CS, OUTPUT);
  pinModeFast(CLK, OUTPUT);
  pinModeFast(DATA_PIN, INPUT);

  pinMode(LED, OUTPUT);
  digitalWrite(LED, LOW);

  pinMode(EN, OUTPUT);
  digitalWrite(EN, LOW);  // EN = LOW -> receive mode

  // Serial init (RS485 TX/RX)
  Serial.begin(SERIAL_BAUD);

  // TLE5012B SSC init
  csHigh();
  clkLow();

  // Fork: USERROW identity and calibration, sensor configuration lock, first
  // valid reading. Nothing is answered until this returns (spec section 6.2).
  // device_id is passed by address: a later COMMIT_CAL or SET_ID changes the
  // module's ID without a reset, and the dispatch above must follow it.
  ker_init(&device_id, DEVICE_ID);
}

void loop() {
  // ========================================
  // 1. RS485 receive check (highest priority, non-blocking)
  // ========================================
  if (receivePacket21(r_id, r_cmd, r_data)) {
    // 1-1. Command addressed to this device
    if (r_id == device_id) {
      uint8_t cmd_only = r_cmd & 0x03;

      if (cmd_only == 1) {
        // CMD=1: send cached data (reply with cmd=1)
        makePacket21(device_id, r_cmd, latest_angle_21bit);
        send485();
        do_ssc_read = true;  // Trigger SSC read immediately after send
      }
      // cmd=0, cmd=2, cmd=3: do nothing
    }
    // 1-2. Chain read (prev device -> this device -> next device)
    else {
      uint8_t prev_id = (device_id - 1) & 0x1F;
      // If this device is the last ID in chain, SSC trigger comes from ID=1 (wrap-around)
      // uint8_t fowd_id = (device_id >= CHAIN_MAX_ID) ? 1 : (device_id + 1);

      if (r_id == prev_id && (r_cmd & 0x03) == 2) {
        // Received CMD=2 from previous device -> reply immediately (cmd=2)
        makePacket21(device_id, r_cmd, latest_angle_21bit);
        send485();
        do_ssc_read = true;  // Trigger SSC read immediately after send
      }

      // if (r_id == fowd_id && (r_cmd & 0x03) == 2) {
      //   // Next device (or wrap-around ID=1) sent CMD=2 -> trigger SSC read
      //   // Run SSC between our own output and next turn to avoid collision with send loop
      //   do_ssc_read = true;
      // }
    }

    // Fork: one hook for every received frame, after the reply is already on the
    // wire. Owns the read gate, arm_seen, factory mode and all of CMD=3.
    ker_on_frame(r_id, r_cmd, r_data);
  }

  // ========================================
  // 2. TLE5012B SSC read
  //    Condition a: SSC_INTERVAL_MS elapsed since last read
  //    Condition b: immediately after RS485 send (do_ssc_read flag)
  // ========================================
  //    Condition c (fork): the averaged-sampling engine wants its next reading
  if (do_ssc_read || ker_read_due() || (millis() - last_ssc_time >= SSC_INTERVAL_MS)) {
    // Fork: block transaction, health evaluation and compensation. An
    // uncalibrated module returns exactly upstream's bit-replicated mapping.
    latest_angle_21bit = ker_read_angle();
    last_ssc_time = millis();
    do_ssc_read = false;
  }
}
