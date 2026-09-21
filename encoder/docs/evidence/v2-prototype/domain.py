import numpy as np

# True sensor error model: theta_m = theta_t + e(theta_t)
#   e(theta_t) = sum_k A_k * sin(k*theta_t + phi_k)
def run(A_deg, phi_deg, label):
    A   = np.array(A_deg, float)
    phi = np.deg2rad(phi_deg)

    # Dense sweep of TRUE shaft angle
    tt = np.linspace(0, 360, 200001, endpoint=False)
    ttr = np.deg2rad(tt)
    e  = sum(A[k]*np.sin((k+1)*ttr + phi[k]) for k in range(3))
    tm = tt + e                       # what the sensor reports

    # ---- Approach A: station fits e(theta_TRUE); firmware applies it at theta_MEASURED
    tmr = np.deg2rad(tm)
    corrA = -sum(A[k]*np.sin((k+1)*tmr + phi[k]) for k in range(3))
    errA  = tm + corrA - tt
    errA  = (errA + 180) % 360 - 180

    # ---- Approach B: station fits (theta_TRUE - theta_MEASURED) against theta_MEASURED,
    #      3 harmonics, least squares, DC term dropped (zero-mean constraint)
    y = (tt - tm + 180) % 360 - 180
    cols = [np.ones_like(tmr)]
    for k in range(1, 4):
        cols += [np.sin(k*tmr), np.cos(k*tmr)]
    M = np.vstack(cols).T
    coef, *_ = np.linalg.lstsq(M, y, rcond=None)
    corrB_dc    = M @ coef                       # with DC
    coef0 = coef.copy(); coef0[0] = 0.0
    corrB_nodc  = M @ coef0                      # DC forced to zero
    errB    = (tm + corrB_dc   - tt + 180) % 360 - 180
    errBn   = (tm + corrB_nodc - tt + 180) % 360 - 180
    errBn  -= np.mean(errBn)                     # zero-point is re-set on the robot anyway

    print(f"{label}")
    print(f"  raw sensor error              max |e|   = {np.abs(e).max():.4f} deg")
    print(f"  A: true-domain fit, applied at measured = {np.abs(errA).max():.4f} deg")
    print(f"  B: measured-domain fit (with DC)        = {np.abs(errB).max():.4f} deg")
    print(f"  B: measured-domain fit (DC dropped)     = {np.abs(errBn).max():.4f} deg")
    print(f"  --> B/A improvement factor              = {np.abs(errA).max()/np.abs(errB).max():.1f}x")
    print(f"  fitted DC term                          = {coef[0]:.4f} deg")
    print()

run([1.0, 0.5, 0.2], [30, 100, 200], "case 1: typical (1.0/0.5/0.2 deg)")
run([1.5, 0.9, 0.3], [0, 90, 180],   "case 2: large   (1.5/0.9/0.3 deg)")
run([0.3, 0.15, 0.05], [45, 135, 250], "case 3: good part (0.3/0.15/0.05 deg)")
run([2.5, 1.2, 0.6], [10, 70, 300],  "case 4: worst   (2.5/1.2/0.6 deg)")
