"""Station dynamics: module averages 1024 readings over 204.8 ms, the reference is polled over Modbus.
How large is (reference reading - module average) caused by motion alone?  Review script 2026-09-20.

Shaft after 'in position' at t = 0:  x(t) = A0 exp(-t/tau) cos(2 pi f t + p)   (ring-down of an
open-loop stepper with an inertial load), optionally plus one step of size D at a random instant
(hold-current reduction, stick-slip). Reference read strategies:
  single-before : one Modbus read just before SAMPLE_START        (what §7.2 step 1 permits)
  single-after  : one read after GET_SAMPLE
  bracket-mean  : mean of reads spread over the window (as many as the poll period allows)
Reported: worst |error| over the ring phase p (and step instant), arcsec.

    python station_dynamics.py
"""
import numpy as np

AS = 3600.0
T_WIN, N = 0.2048, 1024
tm = np.arange(N) * 200e-6


def modbus_poll_ms(baud, bits=11, req=8, rsp=9, turnaround_ms=2.0, usb_ms=2.0):
    char = bits / baud * 1e3
    return (req + rsp) * char + 2 * 3.5 * char + turnaround_ms + usb_ms


def worst(A0, f, tau, wait, poll_s, D=0.0):
    out = {"single-before": 0.0, "single-after": 0.0, "bracket-mean": 0.0, "bracket-spread": 0.0}
    for p in np.linspace(0, 2 * np.pi, 48, endpoint=False):
        for te in (np.linspace(0, T_WIN, 9) if D else [None]):
            x = lambda t: (A0 * np.exp(-(t + wait) / tau) * np.cos(2 * np.pi * f * (t + wait) + p)
                           + (D * (np.asarray(t) >= te) if D else 0.0))
            mod = np.mean(x(tm))
            polls = np.arange(-poll_s, T_WIN + poll_s + 1e-9, poll_s)
            xr = x(polls)
            out["single-before"] = max(out["single-before"], abs(xr[0] - mod))
            out["single-after"] = max(out["single-after"], abs(xr[-1] - mod))
            out["bracket-mean"] = max(out["bracket-mean"], abs(xr.mean() - mod))
            out["bracket-spread"] = max(out["bracket-spread"], xr.max() - xr.min())
    return {k: v * AS for k, v in out.items()}


if __name__ == "__main__":
    for baud in (9600, 19200, 115200):
        print(f"Modbus-RTU 03h, 2 registers, 8E1, {baud} bps: {modbus_poll_ms(baud):5.1f} ms per poll "
              f"(+ up to 16 ms if an FTDI adapter is left at its default latency timer)")
    poll = modbus_poll_ms(9600) / 1e3
    print(f"\nring-down, poll period {poll*1e3:.0f} ms; worst-case |ref - module average|, arcsec")
    print(f"{'A0 deg':>7} {'f Hz':>5} {'tau ms':>6} {'wait ms':>7} | {'single-before':>13} {'single-after':>12} {'bracket-mean':>12} | {'bracket spread':>14}")
    for A0, f, tau in ((0.05, 100, 30), (0.05, 100, 100), (0.2, 60, 100), (0.02, 700, 25)):
        for wait in (0, 100, 300, 500):
            r = worst(A0, f, tau / 1e3, wait / 1e3, poll)
            print(f"{A0:7.2f} {f:5d} {tau:6d} {wait:7d} | {r['single-before']:13.2f} {r['single-after']:12.2f} {r['bracket-mean']:12.2f} | {r['bracket-spread']:14.2f}")
    print("\none step of D during the window (no ringing): hold-current reduction, stick-slip creep")
    for D in (0.002, 0.01, 0.05):
        r = worst(0.0, 100, 0.03, 0.5, poll, D=D)
        print(f"  D = {D:5.3f} deg ({D*AS:5.1f}\"): single-before {r['single-before']:6.1f}\"  single-after {r['single-after']:6.1f}\""
              f"  bracket-mean {r['bracket-mean']:6.1f}\"  bracket spread {r['bracket-spread']:6.1f}\" (detects it)")
    print("\ntorsional wind-up of the reference coupling under encoder friction torque T: T/C")
    for C in (60, 150, 500, 20):
        for T in (0.001, 0.003, 0.01):
            print(f"  C = {C:4d} N·m/rad, T = {T*1e3:4.0f} mN·m -> {T / C * 206265:6.1f}\"", end="")
        print()
