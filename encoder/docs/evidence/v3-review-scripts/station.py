"""Spec §7.2 station procedure, verbatim, on a synthetic sensor; coefficients run through the real
ker_compensate() (ctypes). Residual = wrap(u_out*360/2^21 - theta_true - offset_estimate)."""
import ctypes, numpy as np, sys
lib = ctypes.CDLL("./libref.so")
class Cal(ctypes.Structure):
    _fields_ = [("n", ctypes.c_uint8), ("amp", ctypes.c_int16*6), ("phase", ctypes.c_uint16*6)]
lib.ker_compensate.restype = ctypes.c_uint32
lib.ker_compensate.argtypes = [ctypes.c_uint16, ctypes.POINTER(Cal)]
def wrap(x): return (x + 180) % 360 - 180
Q = 360/32768
def run(a1, rel, ph, offset, npos, const_col, N=6, seed=0):
    # sensor: theta_s_cont = theta_true + offset + e(theta_true); raw15 = floor(...)
    tt = np.arange(npos) * 360.0 / npos
    e = sum(a1*r*np.sin((k+1)*np.deg2rad(tt)+p) for k,(r,p) in enumerate(zip(rel,ph)))
    raw = np.floor(((tt - offset + e) % 360) / Q).astype(np.int64)   # sensor reads true - offset + error
    ts = raw * Q
    y = wrap(tt - ts)                                                   # step 2
    cols = [f(k*np.deg2rad(ts)) for k in range(1,N+1) for f in (np.sin,np.cos)]
    if const_col: cols.append(np.ones_like(ts))
    M = np.column_stack(cols)
    c, *_ = np.linalg.lstsq(M, y, rcond=None)                           # step 3
    cal = Cal(); cal.n = N
    for k in range(N):
        a, b = c[2*k], c[2*k+1]
        A = round(np.hypot(a,b) * 2**21 / 360)
        phi = round(np.degrees(np.arctan2(b, a)) * 65536 / 360) % 65536   # step 4
        if A > 32767: return float("inf")   # step 5: station rejects
        cal.amp[k] = A; cal.phase[k] = phi
    # evaluate on a dense true-angle grid through the real firmware arithmetic
    tv = np.arange(32768*4) * 360.0 / (32768*4)
    ev = sum(a1*r*np.sin((k+1)*np.deg2rad(tv)+p) for k,(r,p) in enumerate(zip(rel,ph)))
    rv = np.floor(((tv - offset + ev) % 360) / Q).astype(np.int64)
    out = np.array([lib.ker_compensate(int(r), ctypes.byref(cal)) for r in range(32768)], dtype=np.float64) * 360 / 2**21
    res = wrap(out[rv] - tv)
    res = wrap(res - np.mean(res))      # M5 zero offset absorbs any constant
    return np.abs(res).max()
rel = [1,.5,.2,.02,.01,.005]
rng = np.random.default_rng(1)
print("typical part (H1 1.0 deg, small H4-6), 15-bit, worst of 5 phase draws, residual after mean removal (deg)")
print(f"{'offset':>7} {'positions':>9} {'spec: no const':>15} {'with const col':>15}")
for npos in (360, 4096):
  for off in (0.0, 1.0, 5.0, 30.0, 100.0, 179.0):
    w0=w1=0
    for d in range(5):
        ph = rng.uniform(0,2*np.pi,6)
        w0=max(w0,run(1.0,rel,ph,off,npos,False)); w1=max(w1,run(1.0,rel,ph,off,npos,True))
    print(f"{off:7.1f} {npos:9d} {w0:15.5f} {w1:15.5f}")
