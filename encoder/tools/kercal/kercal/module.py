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
# New file, not present in upstream OpenArm. One module on the bus, addressed by
# ID: every subcommand of docs/protocol-spec.md section 4.6, with the ordering
# rules of section 4.3 and the unlock sequence of section 4.9 built in.
# ---------------------------------------------------------------------------
"""A single calibrated KER encoder module, over a Link."""

from __future__ import annotations

import time

from . import protocol as P


class Module:
    def __init__(self, link, dev_id: int):
        self.link = link
        self.id = dev_id

    def _rq(self, name: str, arg: int = 0, timeout: float = None) -> int:
        return self.link.request(self.id, P.SUB[name], arg, timeout)

    # -- identity and state -------------------------------------------------
    def ping(self) -> bool:
        return self._rq("PING") == 0xA5A5

    def firmware(self) -> dict:
        ver = self._rq("GET_FW_VER", 0)
        return {"version": "%d.%d.%d" % (ver >> 8, ver & 0xFF, self._rq("GET_FW_VER", 1)),
                "commit": "%04x" % self._rq("GET_FW_VER", 2),
                "dirty": bool(self._rq("GET_FW_VER", 3) & 1),
                "protocol": self._rq("GET_PROTO_VER")}

    def device_id(self) -> dict:
        v = self._rq("GET_DEVICE_ID")
        return {"id": v & 0xFF, "from_userrow": bool(v & 0x100)}

    def health(self) -> dict:
        v = self._rq("GET_HEALTH")
        return {"raw": v, "flags": P.decode_bits(v, P.HEALTH_BITS)}

    def cal_status(self) -> dict:
        v = self._rq("GET_CAL_STATUS")
        return {"raw": v, "flags": P.decode_bits(v, P.CAL_STATUS_BITS), "layout_ver": v >> 8}

    def cfg_verify(self) -> dict:
        v = self._rq("GET_CFG_VERIFY")
        return {"raw": v, "passed": (v & 0x1F) == P.CFG_VERIFY_PASS,
                "checks": P.decode_bits(v, P.CFG_VERIFY_BITS), "attempts": v >> 8}

    def sernum(self) -> bytes:
        return b"".join(self._rq("GET_SERNUM", i).to_bytes(2, "little") for i in range(5))

    def environment(self) -> dict:
        fsync = self._rq("GET_ENV", 0)
        return {"fsync_raw": fsync, "temperature_c": P.decode_temperature(fsync),
                "vdd_mv": self._rq("GET_ENV", 1), "d_mag": self._rq("GET_DMAG"),
                "stat": self._rq("GET_STAT"), "safety": self._rq("GET_SAFETY")}

    def trim(self) -> dict:
        names = ("MOD_3", "OFFX", "OFFY", "SYNCH", "IFAB")
        return {n: self._rq("GET_TRIM", i) for i, n in enumerate(names)}

    # -- records (section 4.3 rule 6: index 0 first, always) ---------------
    def _record(self, name: str, count: int) -> list:
        return [self._rq(name, i) for i in range(count)]

    def angle_raw(self) -> dict:
        r = self._record("GET_ANGLE_RAW", 5)
        return {"upstream_21bit": P.angle21(r[0], r[1]), "raw15": r[2], "sequence": r[3],
                "passed": bool(r[4] & 1), "compensation_active": bool(r[4] & 2),
                "degrees": r[2] * P.Q_DEG}

    def angle(self) -> dict:
        r = self._record("GET_ANGLE_COMP", 2)
        v = P.angle21(r[0], r[1])
        return {"raw21": v, "degrees": v * P.LSB21_DEG}

    def counters(self) -> dict:
        r = self._record("GET_ERRCNT", 8)
        return {"transactions": r[0] | (r[1] << 16), "safety_crc": r[2], "status_fault": r[3],
                "no_response": r[4], "gated": r[5], "naks": r[6], "userrow_write_fail": r[7]}

    def clear_counters(self):
        self._rq("CLR_ERRCNT", P.MAGIC["CLR_ERRCNT"])

    def latched(self) -> dict:
        r = self._record("GET_LATCHED", 4)
        return {"raw21": P.angle21(r[0], r[1]), "degrees": P.angle21(r[0], r[1]) * P.LSB21_DEG,
                "raw15": r[2], "count": r[3] & 0xFF, "valid": bool(r[3] & 0x100),
                "ever_latched": bool(r[3] & 0x200)}

    # -- averaged sampling (section 4.10) ----------------------------------
    def sample(self, e: int = 10, poll_s: float = 0.02) -> dict:
        """SAMPLE_START then poll GET_SAMPLE until done. K = 2**e readings."""
        if not 0 <= e <= 10:
            raise ValueError("e must be 0..10")
        self._rq("SAMPLE_START", (P.TAG_SAMPLE_START << 8) | e)
        deadline = time.monotonic() + (1 << e) * 0.0002 * 3 + 0.5
        while time.monotonic() < deadline:
            time.sleep(poll_s)
            rec = self._record("GET_SAMPLE", 12)
            out = P.decode_sample(rec)
            if out["done"] or out["aborted"]:
                return out
        raise TimeoutError("sample did not finish")

    # -- calibration pages --------------------------------------------------
    def stored_page(self) -> bytes:
        return b"".join(self._rq("GET_CAL_WORD", i).to_bytes(2, "little") for i in range(16))

    def running_page(self) -> bytes:
        return b"".join(self._rq("GET_RUN_WORD", i).to_bytes(2, "little") for i in range(16))

    # -- factory mode (section 4.9) ----------------------------------------
    def unlock(self):
        """UNLOCK_1 then UNLOCK_2 keyed to this part's serial number.

        The digest is read first, so UNLOCK_2 is the next request this module
        sees; reading it after UNLOCK_1 would itself disarm the window.
        """
        digest_arg = P.unlock_2_arg(self.sernum())
        self._rq("UNLOCK_1", P.MAGIC["UNLOCK_1"])
        self._rq("UNLOCK_2", digest_arg)

    def lock(self):
        self._rq("LOCK", P.MAGIC["LOCK"])

    def stage(self, page: bytes):
        """Fill the staging buffer. STAGE_DATA is not idempotent (rule 10), so a
        timeout is recovered by re-issuing STAGE_ADDR, which this does per word."""
        if len(page) != P.PAGE_BYTES:
            raise ValueError("a page is %d bytes" % P.PAGE_BYTES)
        for i in range(16):
            self._rq("STAGE_ADDR", (P.TAG_STAGE_ADDR << 8) | i)
            self._rq("STAGE_DATA", int.from_bytes(page[2 * i:2 * i + 2], "little"))

    def commit(self) -> int:
        """COMMIT_CAL. Returns the module's new effective ID."""
        return self._rq("COMMIT_CAL", P.MAGIC["COMMIT_CAL"], timeout=P.TIMEOUT_PROG_S)

    def set_id(self, new_id: int) -> int:
        if not P.ID_MIN <= new_id <= P.ID_MAX:
            raise ValueError("ID must be %d..%d" % (P.ID_MIN, P.ID_MAX))
        return self._rq("SET_ID", (P.TAG_SET_ID << 8) | new_id, timeout=P.TIMEOUT_PROG_S)

    def reset(self):
        """RESET never replies. The module is unreachable for 3.2 s afterwards."""
        self.link.send_raw(P.encode_cmd3(self.id, P.SUB["RESET"], P.MAGIC["RESET"]))

    # -- the whole write, with the read-back section 4.9 requires ----------
    def write_page(self, page: bytes) -> dict:
        """Unlock, stage, commit and verify. The station must not release a part
        until this has returned a matching read-back (section 4.9)."""
        expect = P.inspect_page(page)
        if not expect["valid"]:
            raise ValueError("refusing to write an invalid page: %s" % expect["error"])
        self.unlock()
        self.stage(page)
        new_id = self.commit()
        self.id = new_id
        back = self.stored_page()
        return {"id": new_id, "verified": back == page, "stored": back,
                "status": self.cal_status()}


def scan(link, ids=range(1, 32), timeout: float = 0.02) -> dict:
    """PING every ID. One module per bus is the rule during provisioning
    (section 3.4); more than one answering here is a finding, not a feature."""
    found = {}
    for dev_id in ids:
        try:
            if Module(link, dev_id).ping():
                found[dev_id] = Module(link, dev_id)
        except (TimeoutError, P.ProtocolError):
            pass
    return found
