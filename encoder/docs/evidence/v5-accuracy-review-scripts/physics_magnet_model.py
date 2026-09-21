"""Accuracy review 2026-09-20 (sensor physics): field of the KER encoder magnet, the angle error caused by
sensor/magnet misalignment, and the error left after a station calibration when that geometry CHANGES.

Magnet: diametrically magnetised NdFeB cylinder.
  * published BOM (OpenArm KER BOM.xlsx, ENC_UNIT item 6): N35, D3 x 2.5 mm
  * user update 2026-09-20: "3 x 3 mm, air gap unchanged" -> taken as D3 x 3 mm (grade unknown -> N35 assumed)
Model: uniformly magnetised cylinder == surface "magnetic charge" sigma = M cos(phi) on the curved surface;
B = mu0/(4 pi) * integral sigma (r - r')/|r - r'|^3 dA.  NOT modelled: the steel 6700ZZ bearing that
surrounds the magnet (it shunts flux, so the real field is LOWER than computed here), the finite size of
the GMR bridges (point sensor), GMR hysteresis/anisotropy.  Sensor: reports the direction of the field
component in its own die plane.  Lengths in mm, angles in degrees.  "gap" = magnet top face -> sensitive plane.

Usage: python physics_magnet_model.py            (numpy only; ~1 min)
"""
import numpy as np

R_MAX = 0.02


class Magnet:
    def __init__(self, d, l, br=1.20, nphi=144, nz=48):
        self.r, self.l, self.br = d / 2.0, l, br
        phi = (np.arange(nphi) + 0.5) * 2 * np.pi / nphi
        z = (np.arange(nz) + 0.5) * l / nz - l / 2
        p, zz = np.meshgrid(phi, z, indexing="ij")
        self.src = np.stack([self.r * np.cos(p), self.r * np.sin(p), zz], -1).reshape(-1, 3)
        self.q = (br * np.cos(p) * (self.r * 2 * np.pi / nphi) * (l / nz)).reshape(-1) / (4 * np.pi)

    def b(self, pt):
        """B (tesla) at one point given in the magnet frame (origin = centre, z = axis, M along +x)."""
        d = pt[None, :] - self.src
        r3 = np.linalg.norm(d, axis=1) ** 3
        return (d * (self.q / r3)[:, None]).sum(0)

    def b_axis(self, gap):
        return float(np.linalg.norm(self.b(np.array([0.0, 0.0, self.l / 2 + gap]))))

    def gap_for(self, b_target):
        lo, hi = 0.2, 30.0
        for _ in range(50):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if self.b_axis(mid) > b_target else (lo, mid)
        return (lo + hi) / 2


def rot(axis, deg):
    a = np.deg2rad(deg); c, s = np.cos(a), np.sin(a)
    return {"x": np.array([[1, 0, 0], [0, c, -s], [0, s, c]]),
            "y": np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]]),
            "z": np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])}[axis]


def wrap(x):
    return (x + 180) % 360 - 180


def error_curve(mag, gap, sens_xy=(0, 0), sens_tilt=(0, 0), mag_xy=(0, 0), mag_tilt=(0, 0), n=72, b_ext=(0, 0, 0)):
    """Angle error (deg, mean removed) over one turn, and the mean in-plane field (T).
    sens_xy   sensor displacement from the rotation axis (stator frame)
    sens_tilt sensor die tilt about stator x, y
    mag_xy    magnet centre displacement from the rotation axis (rotor frame)
    mag_tilt  magnet axis / magnetisation tilt about rotor x, y
    b_ext     external field, stator frame, tesla"""
    th = np.arange(n) * 360.0 / n
    ps = np.array([sens_xy[0], sens_xy[1], mag.l / 2 + gap])
    rs = rot("x", sens_tilt[0]) @ rot("y", sens_tilt[1])
    rm = rot("x", mag_tilt[0]) @ rot("y", mag_tilt[1])
    out, m = [], []
    for t in th:
        rz = rot("z", t)
        p_mag = rm.T @ (rz.T @ ps - np.array([mag_xy[0], mag_xy[1], 0.0]))
        b = rz @ (rm @ mag.b(p_mag)) + np.asarray(b_ext)
        bs = rs.T @ b
        out.append(np.degrees(np.arctan2(bs[1], bs[0]))); m.append(np.hypot(bs[0], bs[1]))
    d = np.array(out) - th                                           # on the axis B is antiparallel to M, so the
    c = np.degrees(np.angle(np.mean(np.exp(1j * np.radians(d)))))    # constant is ~180 deg: remove the circular
    e = wrap(d - c)                                                  # mean BEFORE wrapping
    return e - e.mean(), float(np.mean(m))


def harmonics(e, kmax=6):
    return np.abs(np.fft.rfft(e) / len(e) * 2)[1:kmax + 1]


def hr(e):
    return (e.max() - e.min()) / 2


def change(mag, gap, base, moved, dgap=0.0):
    e0, _ = error_curve(mag, gap, **base)
    e1, _ = error_curve(mag, gap + dgap, **{**base, **moved})
    d = wrap(e1 - e0)
    return hr(d - d.mean())


LOOSE = dict(sens_xy=(0.30, 0), mag_xy=(0.07, 0.07), mag_tilt=(0, 3), sens_tilt=(3, 0))
TIGHT = dict(sens_xy=(0.10, 0), mag_xy=(0.03, 0.03), mag_tilt=(0, 1), sens_tilt=(1, 0))
# LOOSE: sensor 0.3 mm off the rotation axis (die-in-package +-0.2 mm per datasheet Table 30, plus placement,
#        M2 clearance holes and a printed nylon spacer), magnetisation tilt 3 deg (the BOM's sorting limit),
#        die tilt 3 deg (datasheet Table 30).  TIGHT: a carefully built unit.

if __name__ == "__main__":
    m25, m30 = Magnet(3, 2.5), Magnet(3, 3.0)

    print("# A. field on the axis vs gap, N35 (Br 1.20 T), no bearing steel.  TLE5012B: 30-50 mT specified,")
    print("#    25-30 mT +0.1 deg, 20-25 mT +0.2 deg (Infineon 'GMR Accuracy Extension'), < 20 mT not characterised")
    print("   gap mm   D3x2.5   D3x3.0   D3x3.0 if N52 (Br 1.45)")
    for g in (1.0, 1.5, 2.0, 2.25, 2.5, 2.75, 3.0, 3.25, 3.5, 4.0):
        b25, b30 = 1e3 * m25.b_axis(g), 1e3 * m30.b_axis(g)
        print("   %5.2f   %6.1f   %6.1f   %6.1f   mT" % (g, b25, b30, b30 * 1.45 / 1.20))
    for name, mg in (("D3x2.5", m25), ("D3x3.0", m30)):
        print("   %s N35: 50 mT at gap %.2f, 30 mT at %.2f, 25 mT at %.2f, 20 mT at %.2f mm"
              % (name, mg.gap_for(0.050), mg.gap_for(0.030), mg.gap_for(0.025), mg.gap_for(0.020)))

    print("   closed form check (on-axis, transversely magnetised cylinder): B = Br/4 [ (g+L)/sqrt(R^2+(g+L)^2) - g/sqrt(R^2+g^2) ]")
    for g in (2.0, 2.5, 3.0):
        cf = 1.20 / 4 * ((g + 3.0) / np.hypot(1.5, g + 3.0) - g / np.hypot(1.5, g))
        print("      gap %.1f: closed form %.2f mT, numerical %.2f mT" % (g, 1e3 * cf, 1e3 * m30.b_axis(g)))
    print("   D3x3.0, window of gap (magnet face -> sensitive plane) per grade, and slope:")
    print("   grade (Br)      50 mT at   30 mT at   25 mT at   20 mT at   in-spec window   dB/B per +0.1 mm at the 30 mT point")
    for grade, br in (("N35 (1.20 T)", 1.20), ("N42 (1.30 T)", 1.30), ("N52 (1.45 T)", 1.45)):
        mg = Magnet(3, 3.0, br=br)
        g50, g30, g25, g20 = (mg.gap_for(b) for b in (0.050, 0.030, 0.025, 0.020))
        slope = (mg.b_axis(g30 + 0.1) / mg.b_axis(g30) - 1) * 100
        print("   %-14s %7.2f    %7.2f    %7.2f    %7.2f    %5.2f mm wide      %+.1f %%" % (grade, g50, g30, g25, g20, g30 - g50, slope))

    print("\n# B. D3x3.0: static assembly error the station fit must absorb (deg): half-range, H1..H6")
    for gap in (1.5, 2.0, 2.5, 3.0):
        for bn, base in (("loose", LOOSE), ("tight", TIGHT)):
            e, b0 = error_curve(m30, gap, **base)
            print("   gap %.1f  %-5s  B0 %5.1f mT   %7.4f   " % (gap, bn, 1e3 * b0, hr(e)) + " ".join("%7.4f" % h for h in harmonics(e)))
    print("   single contributions at gap 2.5: sensor off-axis e -> pure H2")
    for e_mm in (0.05, 0.1, 0.2, 0.3, 0.5):
        e, _ = error_curve(m30, 2.5, sens_xy=(e_mm, 0))
        print("      e = %.2f mm : %.4f deg" % (e_mm, hr(e)))
    print("   magnet off-axis alone / magnet tilt alone with the sensor ON the axis: %.5f / %.5f deg (no error: the"
          % (hr(error_curve(m30, 2.5, mag_xy=(0.1, 0))[0]), hr(error_curve(m30, 2.5, mag_tilt=(0, 3))[0])))
    print("   field at a point on the axis is fixed in the rotor frame); they act only TOGETHER with sensor eccentricity -> H1")

    print("\n# C. D3x3.0: error left in use after a PERFECT station fit, when the geometry moves afterwards (deg)")
    print("   %-46s" % "change after calibration" + "".join("  gap%.1f/%s" % (g, b[0]) for g in (2.0, 2.5, 3.0) for b in ("loose", "tight")))
    moves = [("rotor radial shift 5 um (bearing clearance)", lambda b: dict(sens_xy=(b["sens_xy"][0] + 0.005, 0)), 0),
             ("rotor radial shift 10 um", lambda b: dict(sens_xy=(b["sens_xy"][0] + 0.010, 0)), 0),
             ("rotor radial shift 20 um (clearance + seat fits)", lambda b: dict(sens_xy=(b["sens_xy"][0] + 0.020, 0)), 0),
             ("rotor tilt 0.1 deg (single-bearing moment play)", lambda b: dict(sens_tilt=(b["sens_tilt"][0], 0.1)), 0),
             ("rotor tilt 0.2 deg", lambda b: dict(sens_tilt=(b["sens_tilt"][0], 0.2)), 0),
             ("axial +0.05 mm", lambda b: {}, 0.05),
             ("axial +0.20 mm (spacer creep / re-torque)", lambda b: {}, 0.20),
             ("PCB or spacer re-seated 0.10 mm", lambda b: dict(sens_xy=(b["sens_xy"][0], 0.10)), 0),
             ("PCB or spacer re-seated 0.20 mm", lambda b: dict(sens_xy=(b["sens_xy"][0], 0.20)), 0)]
    for name, mv, dg in moves:
        row = [change(m30, g, base, mv(base), dg) for g in (2.0, 2.5, 3.0) for base in (LOOSE, TIGHT)]
        print("   %-46s" % name + "".join("  %9.4f" % v for v in row))
    print("   radial shift that uses up R_MAX = 0.02 deg (linearised from the 10 um row), um:")
    print("   %-46s" % "" + "".join("  %9.1f" % (10 * R_MAX / change(m30, g, base, dict(sens_xy=(base["sens_xy"][0] + 0.010, 0))))
                                     for g in (2.0, 2.5, 3.0) for base in (LOOSE, TIGHT)))

    print("\n# D. scaling with magnet diameter (L = D/2 ... 3 mm as listed), gap chosen so that B0 = 40 mT, loose build")
    print("   magnet      gap mm   static half-range   H2 for e=0.2mm   residual per 10 um shift   shift for 0.02 deg (um)")
    for d, l in ((3, 2.5), (3, 3.0), (4, 3.0), (5, 3.0), (6, 3.0), (8, 3.0), (10, 3.0)):
        mg = Magnet(d, l); g = mg.gap_for(0.040)
        e, _ = error_curve(mg, g, **LOOSE); e2, _ = error_curve(mg, g, sens_xy=(0.2, 0))
        c10 = change(mg, g, LOOSE, dict(sens_xy=(0.31, 0)))
        print("   D%-2dx%.1f    %6.2f   %12.4f   %15.4f   %20.4f   %18.1f" % (d, l, g, hr(e), hr(e2), c10, 10 * R_MAX / c10))

    print("\n# E. does the station need the module's OWN magnet?  D3x3.0, gap 2.5, fit made on magnet A, used with magnet B")
    a = LOOSE
    ea, _ = error_curve(m30, 2.5, **a)
    cases = [("same type, another individual: magnetisation tilt 3 deg at 180 deg azimuth", m30, {**a, "mag_tilt": (0, -3)}),
             ("same type, another individual: tilt 3 deg at 90 deg azimuth", m30, {**a, "mag_tilt": (3, 0)}),
             ("same type, tilt 1 deg instead of 3 deg", m30, {**a, "mag_tilt": (0, 1)}),
             ("same individual orientation, magnet seated 0.07 mm elsewhere in its pocket", m30, {**a, "mag_xy": (-0.07, -0.07)}),
             ("station master magnet D3x2.5 instead of D3x3.0 (same gap)", m25, a),
             ("station master magnet D6x3, perfectly centred, no tilt", Magnet(6, 3.0), {**a, "mag_xy": (0, 0), "mag_tilt": (0, 0)})]
    print("   uncalibrated error of this unit: %.3f deg half-range" % hr(ea))
    for name, mg, kw in cases:
        eb, _ = error_curve(mg, 2.5, **kw)
        d = wrap(ea - eb)
        print("   %-82s residual %.3f deg" % (name, hr(d - d.mean())))

    print("\n# F. stray in-plane field Bs: adds an H1 term of amplitude atan(Bs/B0) that is fixed in the STATOR/world, not in the module")
    print("   B0 mT :" + "".join("%8.0f" % b for b in (15, 20, 25, 30, 40, 50)))
    for bs in (20, 50, 75, 150):
        print("   %3d uT :" % bs + "".join("%8.3f" % np.degrees(np.arctan(bs * 1e-6 / (b * 1e-3))) for b in (15, 20, 25, 30, 40, 50)) + "  deg")
    print("   stray field that uses up 0.02 deg:" + "".join("  %.0f uT @ %d mT" % (1e6 * np.tan(np.radians(R_MAX)) * b * 1e-3, b) for b in (20, 30, 50)))
