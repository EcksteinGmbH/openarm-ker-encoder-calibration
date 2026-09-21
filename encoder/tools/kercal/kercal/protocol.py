# Copyright 2026 Eckstein GmbH
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# ---------------------------------------------------------------------------
# MODIFICATION NOTICE
# New file, not present in upstream OpenArm. Wire format and CMD=3 sub-protocol
# of docs/protocol-spec.md sections 1.1, 4 and 5. Pure functions only: no I/O,
# so every line here is testable without a module (tests/test_protocol.py).
# ---------------------------------------------------------------------------
"""Frames, subcommands and payload decoding for the calibrated KER encoder."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

PROTO_VER = 5
LAYOUT_VER = 1
PAGE_MAGIC = 0x4B
PAGE_BYTES = 32
ID_MIN, ID_MAX = 1, 30
ID_UNPROVISIONED = 31
LSB21_DEG = 360.0 / 2 ** 21
Q_DEG = 360.0 / 32768

# --- subcommands (spec section 4.6) ---------------------------------------
SUB = {
    "NAK": 0x00, "PING": 0x01, "GET_FW_VER": 0x02, "GET_PROTO_VER": 0x03,
    "GET_DEVICE_ID": 0x04, "GET_HEALTH": 0x05, "GET_STAT": 0x06, "GET_DMAG": 0x07,
    "GET_ENV": 0x08, "GET_SAFETY": 0x09, "GET_ANGLE_RAW": 0x0A, "GET_ANGLE_COMP": 0x0B,
    "GET_LATCHED": 0x0C, "GET_ERRCNT": 0x0D, "CLR_ERRCNT": 0x0E, "GET_CAL_WORD": 0x0F,
    "GET_CAL_STATUS": 0x10, "GET_SERNUM": 0x11, "GET_CFG_VERIFY": 0x12, "GET_TRIM": 0x13,
    "LATCH_SYNC": 0x14, "GET_RUN_WORD": 0x15, "SAMPLE_START": 0x16, "GET_SAMPLE": 0x17,
    "UNLOCK_1": 0x18, "UNLOCK_2": 0x19, "STAGE_ADDR": 0x1A, "STAGE_DATA": 0x1B,
    "COMMIT_CAL": 0x1C, "SET_ID": 0x1D, "LOCK": 0x1E, "RESET": 0x1F,
}
SUB_NAME = {v: k for k, v in SUB.items()}

MAGIC = {
    "CLR_ERRCNT": 0xC1EA, "LATCH_SYNC": 0x1A7C, "UNLOCK_1": 0x5A17,
    "UNLOCK_2": 0xA5E8, "COMMIT_CAL": 0xC0DE, "LOCK": 0x10CC, "RESET": 0x8EE7,
}
TAG_STAGE_ADDR, TAG_SET_ID, TAG_SAMPLE_START = 0xA5, 0x5E, 0x5A

NAK_REASON = {
    0x02: "NOT_UNLOCKED", 0x03: "BAD_ARG", 0x04: "BAD_INDEX", 0x05: "CRC_FAIL",
    0x06: "WRITE_FAIL", 0x07: "UNSUPPORTED", 0x08: "SENSOR_FAIL", 0x09: "BAD_ADDRESSING",
    0x0A: "SEQUENCE", 0x0B: "NOT_ELIGIBLE", 0x0C: "BAD_PAGE", 0x0D: "STAGING_BUSY",
}

HEALTH_BITS = {
    0: "CAL_INVALID", 1: "CAL_VER_UNSUPPORTED", 2: "SENSOR_CFG_FAIL", 3: "SAFETY_CRC_ERR",
    4: "SENSOR_STAT_ERR", 5: "SENSOR_NO_RESPONSE", 7: "ANGLE_STALE", 8: "FACTORY_MODE",
    9: "USERROW_WRITE_FAIL", 10: "ARM_SEEN", 11: "WRITE_ELIGIBLE", 12: "NO_VALID_ANGLE",
    13: "ANGLE_DEGRADED",
}
CAL_STATUS_BITS = {
    0: "valid", 1: "magic_ok", 2: "version_supported", 3: "crc_ok", 4: "fields_ok",
    5: "compensation_active", 6: "stored_virgin", 7: "running_differs_from_stored",
}
CFG_VERIFY_BITS = {
    0: "MOD_1", 1: "MOD_2", 2: "CRCPAR", 3: "SFUSE_clear", 4: "safety_words_clean",
}
CFG_VERIFY_PASS = 0x001F

TIMEOUT_REPLY_S = 0.002       # spec section 4.3 rule 9, plus the host's own round trip
TIMEOUT_PROG_S = 0.100


class ProtocolError(Exception):
    pass


class Nak(ProtocolError):
    def __init__(self, sub: int, reason: int):
        self.sub, self.reason = sub, reason
        super().__init__("%s rejected: %s" % (SUB_NAME.get(sub, "0x%02X" % sub),
                                              NAK_REASON.get(reason, "0x%02X" % reason)))


# --- wire format (spec section 1.1) ---------------------------------------

def encode_frame(dev_id: int, cmd: int, data: int) -> bytes:
    """One 4-byte frame. Mirrors makePacket21() in encoder/src/main.cpp."""
    if not 0 <= dev_id <= 31:
        raise ValueError("ID out of range: %r" % dev_id)
    if not 0 <= cmd <= 3:
        raise ValueError("CMD out of range: %r" % cmd)
    if not 0 <= data < 1 << 21:
        raise ValueError("payload does not fit in 21 bits: %r" % data)
    return bytes((0x80 | (dev_id << 2) | cmd, data & 0x7F, (data >> 7) & 0x7F, (data >> 14) & 0x7F))


def decode_frame(buf: bytes):
    """(id, cmd, data) from four bytes. Raises if the MSB pattern is not a frame."""
    if len(buf) != 4:
        raise ProtocolError("a frame is 4 bytes, got %d" % len(buf))
    if not buf[0] & 0x80 or any(b & 0x80 for b in buf[1:]):
        raise ProtocolError("MSB pattern is not 1,0,0,0: %s" % buf.hex())
    header = buf[0] & 0x7F
    return header >> 2, header & 0x03, buf[1] | (buf[2] << 7) | (buf[3] << 14)


def encode_cmd3(dev_id: int, sub: int, arg: int = 0) -> bytes:
    if not 0 <= sub <= 0x1F:
        raise ValueError("SUB out of range: %r" % sub)
    if not 0 <= arg <= 0xFFFF:
        raise ValueError("ARG out of range: %r" % arg)
    return encode_frame(dev_id, 3, (sub << 16) | arg)


def decode_cmd3(data: int):
    return (data >> 16) & 0x1F, data & 0xFFFF


# --- CRC-16/CCITT-FALSE, the page CRC and SERNUM_DIGEST (sections 5.1, 4.9)

def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def sernum_digest(sernum: bytes) -> int:
    """CRC-16 over SIGROW.SERNUM0..9, as GET_SERNUM returns them."""
    if len(sernum) != 10:
        raise ValueError("SERNUM is 10 bytes, got %d" % len(sernum))
    return crc16(sernum)


def unlock_2_arg(sernum: bytes) -> int:
    return MAGIC["UNLOCK_2"] ^ sernum_digest(sernum)


# --- the USERROW page (spec section 5) ------------------------------------

@dataclass
class Page:
    device_id: int = ID_UNPROVISIONED
    station_id: int = 0
    cal_day: int = 0
    amp: list = field(default_factory=list)      # int16, 21-bit LSB
    phase: list = field(default_factory=list)    # uint16, 65536 == 360 deg

    @property
    def n_harm(self) -> int:
        return len(self.amp)

    def to_bytes(self) -> bytes:
        if not ID_MIN <= self.device_id <= ID_MAX:
            raise ValueError("DEVICE_ID must be %d..%d, got %r" % (ID_MIN, ID_MAX, self.device_id))
        if self.n_harm > 6:
            raise ValueError("at most 6 harmonics, got %d" % self.n_harm)
        if len(self.phase) != self.n_harm:
            raise ValueError("amp and phase must be the same length")
        if not 0 <= self.cal_day <= 0xFFF:
            raise ValueError("CAL_DAY does not fit in 12 bits: %r" % self.cal_day)
        if any(not -32768 <= a <= 32767 for a in self.amp):
            raise ValueError("an amplitude does not fit in int16")
        words = [PAGE_MAGIC | (LAYOUT_VER << 8),
                 self.device_id | (self.station_id << 8),
                 (self.cal_day & 0xFFF) | (self.n_harm << 12)]
        for k in range(6):
            words.append(self.amp[k] & 0xFFFF if k < self.n_harm else 0)
            words.append(self.phase[k] & 0xFFFF if k < self.n_harm else 0)
        body = struct.pack("<15H", *words)
        return body + struct.pack("<H", crc16(body))

    @classmethod
    def from_bytes(cls, raw: bytes) -> "Page":
        if len(raw) != PAGE_BYTES:
            raise ValueError("a page is %d bytes, got %d" % (PAGE_BYTES, len(raw)))
        words = struct.unpack("<16H", raw)
        n = words[2] >> 12
        return cls(device_id=words[1] & 0xFF, station_id=words[1] >> 8,
                   cal_day=words[2] & 0xFFF,
                   amp=[_i16(words[2 * k + 3]) for k in range(min(n, 6))],
                   phase=[words[2 * k + 4] for k in range(min(n, 6))])

    def degrees(self):
        """Amplitudes in degrees and phases in degrees, for reports."""
        return ([a * LSB21_DEG for a in self.amp],
                [p * 360.0 / 65536 for p in self.phase])


def _i16(v: int) -> int:
    return v - 0x10000 if v & 0x8000 else v


def inspect_page(raw: bytes) -> dict:
    """The validation of spec section 5.2, in its order. Mirrors ker_page_inspect()."""
    words = struct.unpack("<16H", raw)
    out = {
        "virgin": all(b == 0xFF for b in raw),
        "layout_ver": raw[1], "device_id": raw[2], "station_id": raw[3],
        "cal_day": words[2] & 0xFFF, "n_harm": words[2] >> 12,
        "crc_ok": crc16(raw[:30]) == words[15],
        "magic_ok": raw[0] == PAGE_MAGIC,
    }
    out["ver_ok"] = out["layout_ver"] == LAYOUT_VER
    out["fields_ok"] = (ID_MIN <= out["device_id"] <= ID_MAX and out["n_harm"] <= 6 and
                        all(words[2 * k + 3] == 0 and words[2 * k + 4] == 0
                            for k in range(out["n_harm"], 6)))
    for key, err in (("crc_ok", "CRC"), ("magic_ok", "MAGIC"), ("ver_ok", "VERSION")):
        if not out[key]:
            out["error"] = err
            break
    else:
        out["error"] = None if out["fields_ok"] else "FIELDS"
    out["valid"] = out["error"] is None
    return out


# --- payload decoding -----------------------------------------------------

def decode_bits(value: int, names: dict) -> list:
    return [name for bit, name in sorted(names.items()) if value >> bit & 1]


def decode_temperature(fsync: int) -> float:
    """TEMPR is signed 9-bit; reading it unsigned gives 209 C at room temperature."""
    tempr = fsync & 0x1FF
    if tempr & 0x100:
        tempr -= 0x200
    return (tempr + 152.0) / 2.776


def angle21(lo: int, hi: int) -> int:
    return (lo | (hi << 16)) & 0x1FFFFF


def signed32(lo: int, hi: int) -> int:
    v = lo | (hi << 16)
    return v - (1 << 32) if v & 0x80000000 else v


def decode_sample(rec) -> dict:
    """GET_SAMPLE indices 0..11 (spec section 4.7) to usable quantities."""
    if len(rec) != 12:
        raise ValueError("GET_SAMPLE has 12 fields, got %d" % len(rec))
    n = rec[1]
    out = {
        "done": bool(rec[0] & 1), "aborted": bool(rec[0] & 2), "saturated": bool(rec[0] & 4),
        "e": (rec[0] >> 8) & 0xF, "n_pass": n, "n_fail": rec[2],
        "r0": rec[3], "sum_d": signed32(rec[4], rec[5]),
        "sum_d2": rec[6] | (rec[7] << 16), "c0": angle21(rec[8], rec[9]),
        "sum_c": signed32(rec[10], rec[11]),
    }
    if n:
        out["theta_s_deg"] = ((out["r0"] + out["sum_d"] / n) % 32768) * Q_DEG
        out["theta_out_deg"] = ((out["c0"] + out["sum_c"] / n) % 2 ** 21) * LSB21_DEG
        if n > 1:
            var = (out["sum_d2"] - out["sum_d"] ** 2 / n) / (n - 1)
            out["sigma_reading_deg"] = (max(var, 0.0) ** 0.5) * Q_DEG
    return out
