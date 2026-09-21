"""Spec author's independent check of review finding S3 (system-budget review, 2026-09-20), and the regression
for spec §11.2 item 7.

Not derived from the reviewer's script. Uses the real ker_compensate() and a different coefficient set, and
follows M5/src/RSNexus.cpp:85 and M5/include/AngleProcessor.h:57-72 step by step in float32. Three mappings:
upstream (uncalibrated), v6 (the real routine, output a multiple of 8 LSB), and the NEGATIVE CONTROL: mutant C,
the same routine rounding to 1 LSB as spec v5 did, which must drift. A wider grid, motion, `_invert` and the
suspend/resume transitions are in ../v6-verification-scripts/m5_float32_transitions.py (independent verifier).

    cd ../v3-reference
    gcc -O2 -shared -fPIC -o /tmp/libref.so ref_comp.c batch.c
    cp ref_comp_mutant_noround.c.txt /tmp/mut_noround.c && gcc -O2 -I. -shared -fPIC -o /tmp/libmut.so /tmp/mut_noround.c batch.c
    ../../../.venv/bin/python ../v5-accuracy-review-scripts/author_s3_check.py /tmp/libref.so /tmp/libmut.so
"""
import pathlib
import sys
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "v3-reference"))
import station_fit as sf  # noqa: E402

f32 = np.float32


def run(lib, cal, mapping, sensor_deg, joint_deg, hours=1.0, seed=0):
    rng = np.random.default_rng(seed)
    n = int(hours * 3600 * 1000)                                   # 1 kHz
    ang = (sensor_deg + rng.normal(0, 0.05, n)) % 360              # stationary joint, 0.05° noise per reading
    raw15 = np.floor(ang / sf.Q).astype(np.uint16) & 0x7FFF
    if mapping == "upstream":
        u = (raw15.astype(np.uint32) << 6) | (raw15.astype(np.uint32) >> 9)
    else:
        u = sf.compensate(lib, raw15, cal)
    deg = (u.astype(f32) / f32(1 << 21)) * f32(360.0)              # RSNexus.cpp:85
    jig = f32((float(deg[0]) - joint_deg) % 360)                   # AngleProcessor.h:57-66
    delta = deg[0] - jig
    if delta > f32(180):
        delta -= f32(360)
    if delta <= f32(-180):
        delta += f32(360)
    diff = deg[1:] - deg[:-1]                                      # :68-70
    diff = np.where(diff > f32(180), diff - f32(360), diff)
    diff = np.where(diff < f32(-180), diff + f32(360), diff).astype(f32)
    acc = np.add.accumulate(np.concatenate([[f32(delta)], diff]), dtype=f32)   # :71, sequential float32 adds
    du = (u.astype(np.int64) - int(u[0]) + (1 << 20)) % (1 << 21) - (1 << 20)
    exact = float(delta) + du * 360.0 / 2 ** 21
    return float(acc[-1]) - exact[-1]


if __name__ == "__main__":
    libs = {"upstream": sf.load(sys.argv[1]), "v6 (8 LSB)": sf.load(sys.argv[1]), "mutant C (1 LSB)": sf.load(sys.argv[2])}
    rng0 = np.random.default_rng(3)
    amps = np.array([1.0, .5, .2, .02, .01, .005])
    ph = rng0.uniform(0, 2 * np.pi, 6)
    cal = sf.to_cal(amps * np.cos(ph), amps * np.sin(ph))
    worst = {}
    for mapping, lib in libs.items():
        for s, j in ((20, 140), (20, 100), (5, 75), (250, -135)):
            r = [run(lib, cal, mapping, s, j, 1.0, seed) for seed in range(3)]
            worst[mapping] = max(worst.get(mapping, 0.0), max(abs(x) for x in r))
            print(f"{mapping:17s} sensor {s:3d} joint {j:4d}  accumulation error after 1 h: " + "  ".join(f"{x:+.6f}" for x in r))
    ok = worst["v6 (8 LSB)"] == 0.0 and worst["upstream"] <= 1e-4 and worst["mutant C (1 LSB)"] > 1e-3
    print(f"v6 exactly zero: {worst['v6 (8 LSB)'] == 0.0}; upstream bounded (<= 1e-4): {worst['upstream'] <= 1e-4}; "
          f"negative control drifts (> 1e-3): {worst['mutant C (1 LSB)'] > 1e-3}  ->  {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)
