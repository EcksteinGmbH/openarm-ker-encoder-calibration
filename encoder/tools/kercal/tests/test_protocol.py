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
# New file, not present in upstream OpenArm.
# ---------------------------------------------------------------------------
"""kercal against the firmware, not against itself.

Where the tool and the firmware both implement a rule -- the page CRC, the page
validation of spec section 5.2, the compensation -- the test compiles the
firmware's own C and compares. A tool that agrees only with its own idea of the
format would write pages a module rejects, or worse, accept ones it should not.

Run:  python -m unittest discover -s tools/kercal/tests   (from encoder/)
"""

import ctypes
import os
import pathlib
import random
import struct
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE.parents[2] / "src"
sys.path.insert(0, str(HERE.parent))

from kercal import protocol as P            # noqa: E402
from kercal.link import Framer              # noqa: E402

_TMP = tempfile.mkdtemp()


def _build_lib():
    lib_path = os.path.join(_TMP, "libkercal_test.so")
    subprocess.run(["gcc", "-O2", "-shared", "-fPIC", "-I", str(SRC), "-o", lib_path,
                    str(SRC / "ker_cal.c"), str(SRC / "ker_comp.c")], check=True)
    lib = ctypes.CDLL(lib_path)
    lib.ker_crc16.restype = ctypes.c_uint16
    lib.ker_crc16.argtypes = [ctypes.c_char_p, ctypes.c_uint8]
    lib.ker_compensate.restype = ctypes.c_uint32
    return lib


class PageInfo(ctypes.Structure):
    _fields_ = [("err", ctypes.c_int), ("crc_ok", ctypes.c_uint8), ("magic_ok", ctypes.c_uint8),
                ("ver_ok", ctypes.c_uint8), ("fields_ok", ctypes.c_uint8), ("virgin", ctypes.c_uint8),
                ("layout_ver", ctypes.c_uint8), ("device_id", ctypes.c_uint8),
                ("station_id", ctypes.c_uint8), ("cal_day", ctypes.c_uint16),
                ("n_harm", ctypes.c_uint8)]


class Cal(ctypes.Structure):
    _fields_ = [("n", ctypes.c_uint8), ("amp", ctypes.c_int16 * 6), ("phase", ctypes.c_uint16 * 6)]


ERR_NAME = {0: None, 1: "CRC", 2: "MAGIC", 3: "VERSION", 4: "FIELDS", 5: "FIELDS", 6: "FIELDS"}


class TestFrames(unittest.TestCase):
    def test_round_trip_and_msb_pattern(self):
        rng = random.Random(4)
        for _ in range(2000):
            dev_id, cmd, data = rng.randrange(32), rng.randrange(4), rng.randrange(1 << 21)
            buf = P.encode_frame(dev_id, cmd, data)
            self.assertTrue(buf[0] & 0x80, "header MSB must be 1")
            self.assertFalse(any(b & 0x80 for b in buf[1:]), "data MSBs must be 0")
            self.assertEqual(P.decode_frame(buf), (dev_id, cmd, data))

    def test_no_legal_cmd3_payload_sets_a_data_msb(self):
        """Spec section 4.1 claims this; a violation would break the framing."""
        for sub in P.SUB.values():
            for arg in (0, 1, 0x7FFF, 0x8000, 0xFFFF, 0xA5E8, 0x5A17, 0xC0DE):
                buf = P.encode_cmd3(1, sub, arg)
                self.assertFalse(any(b & 0x80 for b in buf[1:]),
                                 "SUB 0x%02X ARG 0x%04X sets a data MSB" % (sub, arg))
                self.assertEqual(P.decode_cmd3(P.decode_frame(buf)[2]), (sub, arg))

    def test_framer_resynchronises_after_garbage(self):
        good = P.encode_cmd3(9, P.SUB["PING"])
        stream = b"\x01\x02" + good[:2] + good + b"\x7f" + good
        frames = list(Framer().feed(stream))
        self.assertEqual(frames.count(P.decode_frame(good)), 2)

    def test_frame_rejects_out_of_range(self):
        for bad in (lambda: P.encode_frame(32, 0, 0), lambda: P.encode_frame(0, 4, 0),
                    lambda: P.encode_frame(0, 0, 1 << 21), lambda: P.encode_cmd3(1, 0x20),
                    lambda: P.encode_cmd3(1, 1, 0x10000)):
            self.assertRaises(ValueError, bad)


class TestAgainstFirmware(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = _build_lib()

    def c_inspect(self, raw):
        info = PageInfo()
        self.lib.ker_page_inspect(ctypes.c_char_p(raw), ctypes.byref(info))
        return info

    def test_crc16_matches_the_firmware(self):
        rng = random.Random(11)
        for _ in range(500):
            data = bytes(rng.randrange(256) for _ in range(rng.randrange(1, 31)))
            self.assertEqual(P.crc16(data), self.lib.ker_crc16(data, len(data)))

    def test_page_validation_matches_the_firmware(self):
        """A corpus that hits every check of section 5.2, both ways."""
        rng = random.Random(3)
        pages = [b"\xff" * 32, b"\x00" * 32]
        for dev_id in (0, 1, 15, 30, 31, 33, 255):
            for n in range(0, 9):
                amp = [rng.randrange(-3000, 3000) for _ in range(min(n, 6))]
                ph = [rng.randrange(65536) for _ in range(min(n, 6))]
                words = [P.PAGE_MAGIC | (P.LAYOUT_VER << 8), (dev_id & 0xFF) | (2 << 8),
                         (100 & 0xFFF) | ((n & 0xF) << 12)]
                for k in range(6):
                    words.append(amp[k] & 0xFFFF if k < len(amp) else 0)
                    words.append(ph[k] & 0xFFFF if k < len(ph) else 0)
                body = struct.pack("<15H", *words)
                pages.append(body + struct.pack("<H", P.crc16(body)))
        # mutations: bad CRC, bad magic, bad version, a populated slot above N_HARM
        base = P.Page(device_id=7, station_id=1, cal_day=9, amp=[100, 200], phase=[1, 2]).to_bytes()
        pages.append(base[:17] + bytes([base[17] ^ 1]) + base[18:])
        for patch in ((0, 0x4C), (1, 2), (1, 0)):
            m = bytearray(base); m[patch[0]] = patch[1]
            m[30:32] = struct.pack("<H", P.crc16(bytes(m[:30])))
            pages.append(bytes(m))
        m = bytearray(base); m[12:14] = b"\x01\x00"          # H4_AMP with N_HARM = 2
        m[30:32] = struct.pack("<H", P.crc16(bytes(m[:30])))
        pages.append(bytes(m))

        for raw in pages:
            py = P.inspect_page(raw)
            c = self.c_inspect(raw)
            self.assertEqual(py["valid"], c.err == 0, "validity differs for %s" % raw.hex())
            self.assertEqual(py["error"], ERR_NAME[c.err], "reason differs for %s" % raw.hex())
            for field in ("crc_ok", "magic_ok", "ver_ok", "fields_ok", "virgin"):
                self.assertEqual(bool(py[field]), bool(getattr(c, field)),
                                 "%s differs for %s" % (field, raw.hex()))
            self.assertEqual(py["device_id"], c.device_id)
            self.assertEqual(py["n_harm"], c.n_harm)
            self.assertEqual(py["cal_day"], c.cal_day)

    def test_page_the_tool_writes_is_the_page_the_module_runs(self):
        """Fit a synthetic part, build the page, decode it as the firmware would,
        and run the firmware's own compensation: the residual must be small."""
        import numpy as np
        from kercal import fit as F

        rng = np.random.default_rng(5)
        theta_true = np.arange(0, 360, 360 / 512)
        amps, phases = np.array([1.0, 0.4, 0.15, 0.03, 0.01, 0.004]), rng.uniform(0, 2 * np.pi, 6)
        measured = theta_true + sum(a * np.sin((k + 1) * np.deg2rad(theta_true) + p)
                                    for k, (a, p) in enumerate(zip(amps, phases)))
        raw15 = np.floor((measured % 360) / P.Q_DEG).astype(np.int64)

        a, b, _ = F.fit(theta_true, raw15 * P.Q_DEG)
        page = F.page_from_fit(a, b, device_id=6, station_id=1, cal_day=264)
        raw = page.to_bytes()
        self.assertTrue(P.inspect_page(raw)["valid"])

        back = P.Page.from_bytes(raw)                       # what the module will load
        cal = Cal(); cal.n = back.n_harm
        for k in range(back.n_harm):
            cal.amp[k] = back.amp[k]; cal.phase[k] = back.phase[k]
        out = np.array([self.lib.ker_compensate(ctypes.c_uint16(int(r)), ctypes.byref(cal))
                        for r in raw15]) * P.LSB21_DEG
        e = (out - theta_true + 180) % 360 - 180
        e -= np.median(e)                                   # the constant belongs to the M5
        worst = float(np.abs(e).max())
        self.assertLess(worst, 0.02, "residual %.5f deg through the real firmware routine" % worst)


class TestDecoders(unittest.TestCase):
    def test_temperature_is_signed(self):
        self.assertAlmostEqual(P.decode_temperature(0x1AD), 25.0, delta=0.3)
        self.assertGreater(P.decode_temperature(0x000), 50.0)   # TEMPR 0 is 54.76 C

    def test_sample_record(self):
        rec = [0x0A01, 1000, 24, 12345, 0x0064, 0x0000, 0x0190, 0x0000, 0x9ABC, 0x0001, 0x00C8, 0x0000]
        s = P.decode_sample(rec)
        self.assertTrue(s["done"]) and self.assertFalse(s["aborted"])
        self.assertEqual((s["e"], s["n_pass"], s["n_fail"], s["r0"]), (10, 1000, 24, 12345))
        self.assertEqual(s["sum_d"], 100)
        self.assertAlmostEqual(s["theta_s_deg"], ((12345 + 0.1) % 32768) * P.Q_DEG)
        self.assertIn("sigma_reading_deg", s)

    def test_sample_sum_is_signed(self):
        rec = [1, 10, 0, 0, 0xFFFF, 0xFFFF, 0, 0, 0, 0, 0xFFFF, 0xFFFF]
        self.assertEqual(P.decode_sample(rec)["sum_d"], -1)
        self.assertEqual(P.decode_sample(rec)["sum_c"], -1)

    def test_unlock_arg_is_keyed_to_the_part(self):
        sn_a = bytes(range(10))
        sn_b = bytes(range(1, 11))
        self.assertNotEqual(P.unlock_2_arg(sn_a), P.unlock_2_arg(sn_b))
        self.assertEqual(P.unlock_2_arg(sn_a), P.MAGIC["UNLOCK_2"] ^ P.crc16(sn_a))
        self.assertRaises(ValueError, P.sernum_digest, b"short")


class TestPage(unittest.TestCase):
    def test_round_trip(self):
        p = P.Page(device_id=12, station_id=3, cal_day=4095, amp=[-32768, 32767, 1],
                   phase=[0, 65535, 32768])
        self.assertEqual(P.Page.from_bytes(p.to_bytes()), p)

    def test_refuses_what_a_module_would_reject(self):
        for bad in (P.Page(device_id=0, amp=[], phase=[]),
                    P.Page(device_id=31, amp=[], phase=[]),
                    P.Page(device_id=5, cal_day=4096, amp=[], phase=[]),
                    P.Page(device_id=5, amp=[1] * 7, phase=[1] * 7),
                    P.Page(device_id=5, amp=[70000], phase=[0]),
                    P.Page(device_id=5, amp=[1, 2], phase=[1])):
            self.assertRaises(ValueError, bad.to_bytes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
