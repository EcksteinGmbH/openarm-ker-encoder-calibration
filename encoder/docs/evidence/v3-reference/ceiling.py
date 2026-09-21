"""Analytic ceiling of the arithmetic error (spec §7.5) from worstterm.c's output on stdin:
N terms of the largest per-term error, plus 4 LSB for the final rounding to a multiple of 8 LSB (v6)."""
import re, sys
line = sys.stdin.read().strip().splitlines()[-1]
print(line)
worst = max(abs(float(x)) for x in re.findall(r"([+-]?\d+\.\d+) LSB", line))
lsb = 360.0 / 2**21
for n in range(1, 7):
    c = n * worst + 4.0
    print(f"ceiling N={n}: {n} x {worst:.4f} + 4.0 = {c:.2f} LSB = {c * lsb:.6f} deg")
