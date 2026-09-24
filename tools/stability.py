"""Reports the tipping speed, the hold-down force and the ballast mass, in two poses: flat and on
the legs.

mass.json holds the component masses and centroids, and it has to sit beside this file.

Run with: freecadcmd stability.py
"""

# ruff: noqa: F821, E402  (names and FreeCAD modules come from the macro exec'd below)
import os
import json
import math

os.environ["SMN_NO_EXPORT"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
exec(
    open(os.path.join(HERE, "..", "freecad", "SolarMeshtasticNodeMini_Enclosure.FCMacro"), encoding="utf-8").read(),
    globals(),
)
d = json.load(open(os.path.join(HERE, "mass.json")))
RHO = 1.01e-3
RHO_A = 1.25
G = 9.81
th = math.radians(LEG_ANGLE)


def W(y, z):
    return (y * math.cos(th) - z * math.sin(th), y * math.sin(th) + z * math.cos(th))


items = []
for n in ("base", "lid", "plate"):
    c = d[n]["c"]
    # z comes from the cavity frame, where the floor sits at -FLOOR
    items.append((d[n]["vol"] * 1000 * RHO, c[1], c[2]))
items += [
    (40.0, d["battery"]["c"][1], d["battery"]["c"][2]),
    (14.0, d["pcb"]["c"][1], d["pcb"]["c"][2]),
    (75.0, W_IN / 2, panel_z0 + PANEL_T / 2),
    (12.0, SMA_Y, SMA_Z),
]
legs = [(leg.Volume / 1000 * RHO * 1000 * 2, leg.Solids[0].CenterOfMass.y, leg.Solids[0].CenterOfMass.z)]
# The same expression as make_leg in the macro, so the two cannot drift.
y_piv = -WALL - (EAR_L if EARS else 0.0) - LEG_HEEL
zb = -FLOOR
# The heel rides in the tunnel envelope, so its underside sits at the tunnel floor and it meets the
# ground line forward of the pivot.
y_heel = y_piv + TIE_SKIN / math.tan(th)
z_heel = zb + TIE_SKIN + 0.3  # The heel rides 0.3 mm off the tunnel floor.
C = [W(y_heel, z_heel), W(LEG_FOOT_Y + LEG_FOOT_L, zb - (LEG_FOOT_Y + LEG_FOOT_L - y_piv) * math.tan(th))]
ground = C[0][1]
A_P = PANEL_X * PANEL_Y / 1e6
A_B = (L_IN + 2 * WALL) * (FLOOR + H_IN + LID_T) / 1e6
C_P, C_A, C_B = 1.3, 1.1, 1.2
ANT = {
    "5 dBi, 15 cm, 30 g": (150, 30, 12),
    "5 dBi, 30 cm, 70 g": (300, 70, 16),
    "10 dBi, 45 cm, 150 g": (450, 150, 22),
}
print(f"legs: {LEG_ANGLE:.0f} deg tilt, leg {leg.Volume / 1000:.1f} cm3 (~{leg.Volume / 1000 * 1.01:.0f} g) each")
print(
    f"heel contact at y {y_heel:.1f}, z {z_heel:.1f}: the heel rides in the tunnel envelope, so it "
    f"meets the ground line {(y_heel - y_piv):.1f} mm forward of the old pivot"
)
print(f"contact span on the ground: {C[1][0] - C[0][0]:.0f} mm (flat pose: {(W_IN + 2 * WALL + 2 * EAR_L):.0f} mm)\n")


def cfg(pose, ant, extra_mass=0.0, extra_y=None):
    L, m, dia = ANT[ant]
    it = list(items) + [(m, SMA_Y, SMA_Z + L / 2)]
    t = th if pose == "legs" else 0.0
    if pose == "legs":
        it = it + [(x, y, z) for x, y, z in legs]
    if extra_mass:
        it = it + [(extra_mass * 1000, extra_y if extra_y is not None else W_IN / 2, zb + 10)]
    M = sum(i[0] for i in it)
    cy = sum(i[0] * i[1] for i in it) / M
    cz = sum(i[0] * i[2] for i in it) / M
    R = (lambda y, z: W(y, z)) if pose == "legs" else (lambda y, z: (y, z))
    Cc = (
        [R(y_heel, z_heel), R(LEG_FOOT_Y + LEG_FOOT_L, zb - (LEG_FOOT_Y + LEG_FOOT_L - y_piv) * math.tan(th))]
        if pose == "legs"
        else [(-(WALL + EAR_L), zb), (W_IN + WALL + EAR_L, zb)]
    )
    g = min(c[1] for c in Cc)
    cgw = R(cy, cz)
    return dict(
        M=M / 1000,
        t=t,
        L=L / 1000,
        dia=dia / 1000,
        C=[c[0] for c in Cc],
        cg=(cgw[0], cgw[1] - g),
        pan=(R(W_IN / 2, panel_z0)[0], R(W_IN / 2, panel_z0)[1] - g),
        sma=(R(SMA_Y, SMA_Z)[0], R(SMA_Y, SMA_Z)[1] - g),
    )


def over(cf, v, wind):
    q = 0.5 * RHO_A * v * v
    edge = max(cf["C"]) if wind > 0 else min(cf["C"])
    n = (-math.sin(cf["t"]) * wind, math.cos(cf["t"]))
    Fp = q * A_P * C_P
    Fa = q * C_A * cf["L"] * cf["dia"]
    Fb = q * C_B * A_B
    Mo = (
        abs(Fp * n[0]) * cf["pan"][1] / 1000
        + Fa * (cf["sma"][1] + cf["L"] * 1000 / 2) / 1000
        + Fb * cf["cg"][1] * 0.6 / 1000
        + Fp * n[1] * abs(cf["pan"][0] - edge) / 1000
    )
    Mr = cf["M"] * G * (edge - cf["cg"][0]) * wind / 1000
    return Mo, Mr, abs(Fp * n[0]) + Fa + Fb


def vtip(cf, wind):
    lo, hi = 0.1, 150.0
    for _ in range(70):
        mid = (lo + hi) / 2
        Mo, Mr, _ = over(cf, mid, wind)
        if Mo < Mr:
            lo = mid
        else:
            hi = mid
    return lo


print(
    f"{'antenna':22s} {'pose':6s} {'m':>6s} {'CG h':>6s} {'margins':>13s} {'tips at':>9s}  {'peg force 30/40 m/s':>20s}"
)
for ant in ANT:
    for pose in ("flat", "legs"):
        cf = cfg(pose, ant)
        a, b = min(cf["C"]), max(cf["C"])
        v = min(vtip(cf, 1), vtip(cf, -1))
        pf = []
        for vv in (30, 40):
            f = []
            for w in (1, -1):
                Mo, Mr, _ = over(cf, vv, w)
                f.append(max(0.0, (Mo - Mr) / ((b - a) / 1000)))
            pf.append(f"{max(f):3.0f} N")
        print(
            f"{ant:22s} {pose:6s} {cf['M'] * 1000:5.0f}g {cf['cg'][1]:5.0f}mm  "
            f"{cf['cg'][0] - a:5.0f}/{b - cf['cg'][0]:<5.0f}mm {v:6.1f} m/s  " + " / ".join(pf)
        )
print("\nballast needed instead of pegs (stone on/against the box, tilted pose):")
for ant in ANT:
    for vdes in (30, 40):
        lo, hi = 0.0, 40.0
        for _ in range(50):
            mid = (lo + hi) / 2
            cf = cfg("legs", ant, mid, -(WALL + EAR_L) + 20)
            _, _, Fh = over(cf, vdes, 1)
            ok = min(vtip(cf, 1), vtip(cf, -1)) >= vdes and Fh < 0.5 * cf["M"] * G
            if ok:
                hi = mid
            else:
                lo = mid
        print(f"  {ant:22s} {vdes} m/s -> {hi:.1f} kg")

# The README quotes a wind table. This block regenerates its rows for stone in the trays, and not
# for stone against the box. The panel mass scales with its area.
print("\nWind table, 135 x 90 mm panel, 5 dBi 15 cm antenna. The claim column holds the values of an")
print("earlier table: 12.0 / 16.4 / 19.7 m/s. A ballast row only reproduces if the stone sits at the")
print("back of the heel rail, so the tool shows both placements.")
print(f"{'setup':16} {'ballast at':18} {'model':>8} {'claim':>8} {'delta':>8}  weight")
for label, kg, claim in (("bare", 0.0, 12.0), ("1 kg", 1.0, 16.4), ("2 kg", 2.0, 19.7)):
    for where, y in (
        (("tray center", -WALL - LEG_HEEL + BALLAST_L / 2), ("back of the heel rail", -WALL - LEG_HEEL + 2.0))
        if kg
        else (("-", None),)
    ):
        cf = cfg("legs", "5 dBi, 15 cm, 30 g", kg, y if kg else None)
        v = min(vtip(cf, 1), vtip(cf, -1))
        print(
            f"{label:16} {where if kg else '-':18} {v:7.1f} {claim:7.1f} {v - claim:+7.1f} m/s  {cf['M'] * 1000:.0f} g"
        )
print("\nA different panel size changes these rows. Set PANEL_X in the macro and run the tool again.")
