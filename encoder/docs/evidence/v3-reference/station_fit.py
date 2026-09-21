"""Reference implementation of the station procedure, spec §7.2 (v6).

This module is the golden reference for the kercal station code (deliverable 4). It provides the
computational part of every normative step: positions (step 1 layout), GET_SAMPLE record to angle
(steps 3, 7), the noise check (step 2), offset removal and the fit with a discarded constant (4, 5),
coefficient conversion and rounding (6), the out-of-sample, two-direction statistic and its grade (7, 8),
and the centring gate (9). The
parts that need hardware — stage motion, settling, reference polling, frame I/O and the step 1 discard
rules — are the station's.

v6: every position is measured approaching clockwise and counter-clockwise. fit() takes the pooled samples
of both passes, so it fits the mean curve of the hysteresis loop; grade() judges the direction-mean error
and reports the hysteresis half-difference separately.

Run as a script it reproduces the §7.2 mounting-offset table (noise-free, fit points only), using the
REAL firmware routine ker_compensate() loaded from a shared library:

    gcc -O2 -shared -fPIC -o libref.so ref_comp.c batch.c
    python station_fit.py libref.so
"""
import ctypes
import sys
import numpy as np

NH = 6
Q = 360.0 / 32768           # one sensor code, degrees
LSB21 = 360.0 / 2**21       # one output LSB, degrees


class Cal(ctypes.Structure):
    _fields_ = [("n", ctypes.c_uint8), ("amp", ctypes.c_int16 * NH), ("phase", ctypes.c_uint16 * NH)]


def load(path):
    lib = ctypes.CDLL(path)
    lib.ker_compensate.restype = ctypes.c_uint32
    lib.ker_compensate.argtypes = [ctypes.c_uint16, ctypes.POINTER(Cal)]
    lib.ker_compensate_batch.restype = None
    lib.ker_compensate_batch.argtypes = [ctypes.POINTER(ctypes.c_uint16), ctypes.c_uint32,
                                         ctypes.POINTER(Cal), ctypes.POINTER(ctypes.c_uint32)]
    return lib


def compensate(lib, raw15, cal):
    """ker_compensate() over an array of sensor codes, via the C batch helper."""
    raw = np.ascontiguousarray(raw15, dtype=np.uint16)
    out = np.empty(raw.shape, dtype=np.uint32)
    lib.ker_compensate_batch(raw.ctypes.data_as(ctypes.POINTER(ctypes.c_uint16)), raw.size,
                             ctypes.byref(cal), out.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32)))
    return out


def wrap(x):
    """Wrap degrees into [-180, 180)."""
    return (np.asarray(x) + 180.0) % 360.0 - 180.0


def circular_mean(d):
    r = np.deg2rad(d)
    return np.rad2deg(np.arctan2(np.mean(np.sin(r)), np.mean(np.cos(r))))


# ---- GET_SAMPLE record to angles (§4.7, §7.2 steps 3 and 7) --------------------------------

def sample_angle(r0, sum_d, n):
    """Mean sensor angle, degrees, from GET_SAMPLE indices 3, 4-5, 1."""
    return ((r0 + sum_d / n) % 32768) * Q


def sample_output(c0, sum_d, n):
    """Mean compensated output, degrees, from GET_SAMPLE indices 8-9, 10-11, 1."""
    return ((c0 + sum_d / n) % 2**21) * LSB21


# ---- §7.2 steps 4-6 -------------------------------------------------------------------------

def fit(theta_true, theta_s, nh=NH):
    """Fit (θ_true − θ_s) against θ_s. Returns (a, b, offset) with offset = c + a_0, the constant that
    the M5 owns and that is NOT stored. theta_s may be fractional (averaged samples)."""
    d = np.asarray(theta_true) - np.asarray(theta_s)
    c = circular_mean(d)                                     # step 4: remove the mounting offset
    y = wrap(d - c)
    r = np.deg2rad(theta_s)
    M = np.column_stack([np.ones_like(r)] + [f(k * r) for k in range(1, nh + 1) for f in (np.sin, np.cos)])
    coef, *_ = np.linalg.lstsq(M, y, rcond=None)             # step 5: constant column included ...
    a0, ab = coef[0], coef[1:]                               # ... and discarded
    return ab[0::2], ab[1::2], c + a0


def to_cal(a, b):
    """Step 6: convert to USERROW coefficients. Returns None if any amplitude does not fit int16."""
    cal = Cal()
    cal.n = len(a)
    for k, (ak, bk) in enumerate(zip(a, b)):
        A = int(round(np.hypot(ak, bk) / LSB21))
        if A > 32767:
            return None
        cal.amp[k] = A
        cal.phase[k] = int(round(np.rad2deg(np.arctan2(bk, ak)) * 65536 / 360.0)) % 65536
    return cal


# ---- §7.2 steps 1, 2, 7: positions, noise check, acceptance ---------------------------------

# Minimums, not defaults: the operating characteristic of §7.2 is only established at these values or more.
N_FIT = 128          # fit positions, uniform
N_VAL = 128          # validation positions, interleaved half-way between fit positions
K_SAMPLES = 1024     # readings averaged on the module per position (SAMPLE_START e = 10)
N_REPEAT = 8         # step 2: repeated samples at one position
R_MAX = 0.02         # grade A: limit on the systematic error (half-range, relative to the station reference)
R_MAX_B = 0.05       # grade B: still shipped with its calibration; above this the unit is reworked
GUARD = 0.95         # measured statistic is compared with GUARD x limit: 5 % guard band for noise
R_ACCEPT = GUARD * R_MAX
SIGMA_MEAN_MAX = R_MAX / 6   # per-position averaged noise must be at most this, else "insufficient data"
HYST_MAX = 0.10      # PROVISIONAL limit on the hysteresis half-difference, degrees; to be set from bench data (O1)
H2_MAX = 0.2         # PROVISIONAL centring gate (step 9): fitted H2 amplitude, degrees; H2 ≈ 5.0° × e² at a 2.5 mm gap


def positions():
    fit_pos = np.arange(N_FIT) * 360.0 / N_FIT
    val_pos = (np.arange(N_VAL) + 0.5) * 360.0 / N_VAL
    return fit_pos, val_pos


def noise_check(repeat_angles):
    """Step 2: circular standard deviation of N_REPEAT values of theta_true - theta_s, from re-approaching one
    position always clockwise (well defined across the 0°/360° seam). Returns sigma_mean in degrees."""
    a = np.asarray(repeat_angles)
    return float(np.std(wrap(a - circular_mean(a)), ddof=1))


def half_range(err):
    """Half the peak-to-peak of a set of small angular errors: the max error about the best (minimax)
    constant. Invariant to any constant added to err, so no offset estimate is needed."""
    e = wrap(np.asarray(err) - circular_mean(err))
    return float((e.max() - e.min()) / 2)


def grade(theta_true_val, out_cw, out_ccw, sigma_mean):
    """Steps 7 and 8 (v6). out_cw / out_ccw: the committed module's averaged compensated output at the validation
    positions, approached clockwise and counter-clockwise. The graded statistic is the half-range of the
    direction-MEAN error, i.e. of what the stored static curve can be held responsible for. The hysteresis
    half-difference is reported and limited separately: no static curve can remove it, and in use the reading
    lies within +- that value of the mean curve. Returns (grade, statistic, hysteresis half-difference)."""
    if sigma_mean > SIGMA_MEAN_MAX:
        return "insufficient-data", None, None
    t = np.asarray(theta_true_val)
    e_cw, e_ccw = wrap(t - np.asarray(out_cw)), wrap(t - np.asarray(out_ccw))
    hyst = float(np.max(np.abs(wrap(e_cw - e_ccw))) / 2)
    stat = half_range(e_ccw + wrap(e_cw - e_ccw) / 2)
    if hyst > HYST_MAX:
        return "rework-hysteresis", stat, hyst
    if stat <= GUARD * R_MAX:
        return "A", stat, hyst
    if stat <= GUARD * R_MAX_B:
        return "B", stat, hyst
    return "rework", stat, hyst


def centring(a, b):
    """Step 9. Fitted H2 amplitude in degrees and whether it is within the centring gate. a, b from fit()."""
    h2 = float(np.hypot(a[1], b[1]))
    return h2, h2 <= H2_MAX


# ---- demo: the §7.2 mounting-offset table ---------------------------------------------------

def _offset_table(lib):
    def fit_v3(theta_true, raw15):                       # v3's procedure, for comparison
        ts = raw15 * Q
        y = wrap(theta_true - ts)
        r = np.deg2rad(ts)
        M = np.column_stack([f(k * r) for k in range(1, NH + 1) for f in (np.sin, np.cos)])
        c, *_ = np.linalg.lstsq(M, y, rcond=None)
        return to_cal(c[0::2], c[1::2])

    rng = np.random.default_rng(11)
    tt = np.arange(0, 360, 360 / 4096)
    amps = np.array([1.0, .5, .2, .02, .01, .005])
    ph = rng.uniform(0, 2 * np.pi, 6)
    print(f"{'mounting offset':>16} {'v3 procedure':>14} {'v4-v6 procedure':>16}")
    for off in (0, 1, 5, 30, 100, 170, 179, 180, 181, 270):
        tm = tt + off + sum(a * np.sin((k + 1) * np.deg2rad(tt) + p) for k, (a, p) in enumerate(zip(amps, ph)))
        raw15 = np.floor((tm % 360) / Q).astype(np.int64)
        row = []
        for proc in ("v3", "v5"):
            if proc == "v3":
                cal = fit_v3(tt, raw15)
            else:
                a, b, _ = fit(tt, raw15 * Q)
                cal = to_cal(a, b)
            if cal is None:
                row.append("rejected")
                continue
            out = compensate(lib, raw15, cal) * LSB21
            e = wrap(out - tt)
            e = wrap(e - circular_mean(e))
            row.append(f"{np.abs(e).max():.5f}")
        print(f"{off:>15}° {row[0]:>14} {row[1]:>16}")


if __name__ == "__main__":
    _offset_table(load(sys.argv[1]))
