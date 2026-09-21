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
# New file, not present in upstream OpenArm. The RS-485 transport, and the host
# discipline C4 of docs/protocol-spec.md section 3.2, which is normative for
# this tool: a host that talks on a bus with an M5 on it can make a robot move.
# ---------------------------------------------------------------------------
"""Framed RS-485 link with the safety discipline of spec section 3.2 (C4)."""

from __future__ import annotations

import time

from . import protocol as P

BAUD = 2_000_000
LISTEN_BEFORE_TX_S = 0.2      # C4: listen at least this long before the first transmission


class BusUnsafe(RuntimeError):
    """The bus carries cascade traffic. Nothing may be transmitted on it, now or later."""


class Framer:
    """Byte stream to frames. Same state machine as receivePacket21() in main.cpp."""

    def __init__(self):
        self._buf = []

    def feed(self, data: bytes):
        for b in data:
            if b & 0x80:
                self._buf = [b]
            elif self._buf:
                self._buf.append(b)
                if len(self._buf) == 4:
                    frame = bytes(self._buf)
                    self._buf = []
                    yield P.decode_frame(frame)


class Link:
    """One RS-485 port. Refuses to transmit on a bus that shows cascade traffic.

    The rules below are not conveniences. An unmodified M5 parses any frame with
    ID 1..16 as a joint angle (spec sections 1.5, 1.6), so a host request on a
    live arm can move a robot.
    """

    def __init__(self, port: str, baud: int = BAUD, timeout: float = 0.01, serial_module=None):
        if serial_module is None:
            import serial as serial_module     # pyserial; imported late so the codec needs no port
        self._ser = serial_module.Serial(port, baud, timeout=timeout)
        self._framer = Framer()
        self._rx = []
        self._unsafe = None
        self._armed = False
        self.round_trip_s = 0.0

    # -- receiving ---------------------------------------------------------
    def _pump(self):
        data = self._ser.read(256)
        if data:
            for frame in self._framer.feed(data):
                self._note(frame)
                self._rx.append(frame)

    def _note(self, frame):
        """C4, second rule. This tool never sends CMD=1 in a provisioning session,
        so any CMD=1 or CMD=2 frame at all means something else is driving the bus.
        The session is poisoned permanently: the M5 that went quiet for 100 ms can
        come back, and a half-finished write is worse than no write."""
        dev_id, cmd, _ = frame
        if cmd == 2:
            self._unsafe = "a CMD=2 frame (ID %d) is on the bus: a cascade is running" % dev_id
        elif cmd == 1:
            self._unsafe = "an unexpected CMD=1 frame (ID %d) is on the bus" % dev_id

    def listen(self, seconds: float) -> list:
        """Collect every frame seen for `seconds`. Never transmits."""
        seen, end = [], time.monotonic() + seconds
        while time.monotonic() < end:
            self._pump()
            seen.extend(self._rx)
            self._rx.clear()
        return seen

    # -- session -----------------------------------------------------------
    def open_session(self, listen_s: float = LISTEN_BEFORE_TX_S):
        """C4: listen first, and refuse to start if anything is talking."""
        seen = self.listen(listen_s)
        if seen:
            raise BusUnsafe("%d frame(s) seen while listening for %.0f ms; "
                            "this bus is not a bench bus" % (len(seen), listen_s * 1000))
        self._armed = True
        return self

    def _check(self):
        if not self._armed:
            raise BusUnsafe("open_session() has not run: the bus has not been listened to")
        if self._unsafe:
            raise BusUnsafe(self._unsafe + " -- this session will not transmit again")

    # -- request / reply ---------------------------------------------------
    def send_raw(self, frame: bytes):
        self._check()
        self._ser.reset_input_buffer()
        self._ser.write(frame)
        self._ser.flush()

    def request(self, dev_id: int, sub: int, arg: int = 0, timeout: float = None):
        """One request, one reply. Returns the reply DATA, or raises Nak / TimeoutError.

        Rule 8 of section 4.3: after a timeout the caller must stay quiet for a
        further period of the same length, which this enforces before returning.
        """
        timeout = (P.TIMEOUT_REPLY_S if timeout is None else timeout) + self.round_trip_s
        self.send_raw(P.encode_cmd3(dev_id, sub, arg))
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            self._pump()
            while self._rx:
                r_id, r_cmd, data = self._rx.pop(0)
                if r_id != 0 or r_cmd != 3:
                    continue                            # not a reply to us
                r_sub, r_arg = P.decode_cmd3(data)
                if r_sub == P.SUB["NAK"]:
                    raise P.Nak((r_arg >> 8) & 0x1F, r_arg & 0xFF)
                if r_sub == sub:
                    return r_arg
                # A reply echoing another SUB belongs to an earlier request.
        time.sleep(timeout)                             # rule 8's quiet period
        raise TimeoutError("no reply to %s from ID %d" % (P.SUB_NAME.get(sub, sub), dev_id))

    def broadcast(self, sub: int, arg: int = 0):
        """A broadcast never replies (rule 2), so there is nothing to wait for."""
        self.send_raw(P.encode_cmd3(0, sub, arg))

    def measure_round_trip(self, dev_id: int, n: int = 8) -> float:
        """USB-RS-485 adapters add milliseconds. Section 4.3 rule 9 says the host
        adds its own measured latency to every timeout rather than guessing."""
        worst = 0.0
        for _ in range(n):
            t0 = time.monotonic()
            self.request(dev_id, P.SUB["PING"], timeout=0.5)
            worst = max(worst, time.monotonic() - t0)
        self.round_trip_s = worst
        return worst

    def close(self):
        self._ser.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
