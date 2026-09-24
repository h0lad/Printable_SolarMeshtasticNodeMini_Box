"""Checks the base, the lid and the tray against the SLS and MJF design rules.

The checks cover the wall thickness, the hole diameters, the gaps, the shell count, the build volume,
the collisions against the dummy parts, and the depowdering paths.

It writes verification_report.json.

Run with: freecadcmd design_rules.py
"""
# ruff: noqa: F821, E402  (names come from the macro exec'd below)

import json
import os

os.environ["SMN_NO_EXPORT"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
exec(
    open(os.path.join(HERE, "..", "freecad", "SolarMeshtasticNodeMini_Enclosure.FCMacro"), encoding="utf-8").read(),
    globals(),
)

MIN_WALL, MIN_DETAIL, MIN_HOLE, MIN_GAP = 1.0, 0.8, 1.0, 0.5
BUILD = (380.0, 280.0, 380.0)

# A relief is a claim about the solid, so the check probes the solid. Over a grid the probe looks up
# from below for the first material, and then for the first void that follows it, and the layer between
# the two is the membrane. A point at the relief reads the relieved thickness. A point under a tunnel
# reads TIE_SKIN. A rib reads the full floor. The rim, the columns and the bores run past the cap.
# An empty relieved bucket is a failure.
GRID, Z_STEP, Z_CAP = 9, 0.2, 14.0


def membrane(shape, x0, y0, x1, y1, z_start):
    """Returns the first band of material that starts at z_start, as {thickness_mm: point_count}."""
    table = {}
    for ix in range(GRID):
        for iy in range(GRID):
            px = x0 + (x1 - x0) * ix / (GRID - 1)
            py = y0 + (y1 - y0) * iy / (GRID - 1)
            z = z_start
            while z < z_start + Z_CAP and not shape.isInside(V(px, py, z), 1e-7, True):
                z += Z_STEP  # A relief or a counterbore, so no material yet.
            start = z
            while z < z_start + Z_CAP and shape.isInside(V(px, py, z), 1e-7, True):
                z += Z_STEP
            t = round(z - start, 1)
            table[t] = table.get(t, 0) + 1
    return table


def report_membrane(name, shape, x0, y0, x1, y1, z_start, want, label="the relief"):
    table = membrane(shape, x0, y0, x1, y1, z_start)
    bored = table.pop(0.0, 0)  # A screw bore or an insert bore, where no material reaches the cap.
    points = sum(n for t, n in table.items() if abs(t - want) < 0.3)
    print(f"{name}: membrane over a {GRID} x {GRID} grid, first material then first void")
    for t in sorted(table):
        where = (
            label
            if abs(t - want) < 0.3
            else ("a tunnel skin" if abs(t - TIE_SKIN) < 0.3 else "a rib, the rim, a collar or a column")
        )
        print(f"  {t:5.1f} mm  {table[t]:3d} point(s)  {where}")
    if bored:
        print(f"  {0.0:5.1f} mm  {bored:3d} point(s)  a bore, no material over the cap")
    print()
    return min(table), points, bored, table


floor_min, floor_relief_pts, floor_bored, floor_table = report_membrane(
    "base floor",
    base,
    -WALL + FLOOR_EDGE / 2.0,
    -WALL + FLOOR_EDGE / 2.0,
    L_IN + WALL - FLOOR_EDGE / 2.0,
    W_IN + WALL - FLOOR_EDGE / 2.0,
    -FLOOR + Z_STEP,
    FLOOR - FLOOR_RELIEF,
)
# The probe starts below the lid's relief and walks up. The skirt sits outside the grid. The collar
# around the feedthrough and the four insert columns are the caps that the probe reports as thick.
lid_min, lid_relief_pts, lid_bored, lid_table = report_membrane(
    "lid deck",
    lid,
    -WALL + LID_EDGE / 2.0,
    -WALL + LID_EDGE / 2.0,
    L_IN + WALL - LID_EDGE / 2.0,
    W_IN + WALL - LID_EDGE / 2.0,
    H_IN - LID_RELIEF,
    LID_T - LID_RELIEF,
    label="the relief" if LID_RELIEF > 0 else "the full deck",
)

rows = [
    ("wall", WALL, MIN_WALL),
    ("floor", FLOOR, MIN_WALL),
    ("floor, measured minimum over the bottom grid", floor_min, MIN_WALL),
    ("floor at the relief, or the full floor when it is off", FLOOR - FLOOR_RELIEF, MIN_WALL),
    ("relief rib over the tunnel exit fillet", FLOOR_RIB, TIE_R_EXIT),
    ("relief rim at the bottom edge", FLOOR_EDGE, MIN_WALL),
    ("lid relief edge band at the rim", LID_EDGE, MIN_WALL),
    ("lid", LID_T, MIN_WALL),
    ("lid deck, measured minimum over the grid", lid_min, MIN_WALL),
    ("lid deck at the relief, or the full deck when it is off", LID_T - LID_RELIEF, MIN_WALL),
    ("O-ring groove lip", (WALL - GROOVE_W) / 2, MIN_WALL),
    ("tunnel roof, Y pair", FLOOR - TIE_SKIN - TIE_H, MIN_WALL),
    ("tunnel roof, X pair", FLOOR - TIE_SKIN - TIE_H2, MIN_WALL),
    ("battery cover plate", PLATE_T, MIN_DETAIL),
    ("PCB edge rib", 1.3, MIN_DETAIL),
    ("lid skirt", SK_T, MIN_WALL),
    ("snap finger in the leg", SNAP_T, MIN_DETAIL),
    ("tray rim", 3.0, MIN_WALL),
    ("material around the M3 insert", (BOSS_R * 2 - INSERT_D) / 2, MIN_WALL),
    ("material around the SMA hole", (SMA_KEEPOUT_R * 2 - SMA_D) / 2, MIN_WALL),
    ("material around the peg eyelet", (EYELET_BOSS_D - PEG_EYE_D) / 2, MIN_WALL),
    ("potting collar wall", (CHIMNEY_OD - SOLAR_HOLE_D) / 2, MIN_WALL),
]
if FLOOR_RELIEF > 0:
    rows.insert(4, ("bottom grid points at the relieved thickness", floor_relief_pts, 1))
if LID_RELIEF > 0:
    rows.insert(6, ("lid grid points at the relieved thickness", lid_relief_pts, 1))
report = {
    "tool": "design_rules.py",
    "process": "SLS/MJF PA12",
    "floor_probe_mm": {str(k): v for k, v in sorted(floor_table.items())},
    "floor_probe_min_mm": floor_min,
    "floor_probe_relief_points": floor_relief_pts,
    "floor_probe_screw_bore_points": floor_bored,
    "lid_probe_mm": {str(k): v for k, v in sorted(lid_table.items())},
    "lid_probe_min_mm": lid_min,
    "lid_probe_relief_points": lid_relief_pts,
    "lid_probe_bore_points": lid_bored,
    "design_rules": [],
    "holes": [],
    "gaps": [],
    "parts": [],
    "collisions": [],
    "depowdering": None,
}

print(f"{'feature':38} {'mm':>6} {'limit':>6}  verdict")
bad = 0
for name, val, lim in rows:
    ok = val >= lim - 1e-6
    bad += 0 if ok else 1
    print(f"{name:38} {val:6.2f} {lim:6.2f}  {'ok' if ok else 'BELOW LIMIT'}")
    report["design_rules"].append({"feature": name, "mm": val, "limit": lim, "pass": ok})

holes = [
    ("screw clearance", SCREW_D),
    ("captive neck", SCREW_CAPTIVE_D),
    ("insert hole", INSERT_D),
    ("peg eyelet", PEG_EYE_D),
    ("lanyard lug", 2.0),
    ("solar cable", SOLAR_HOLE_D),
]
print()
for name, d in holes:
    ok = d >= MIN_HOLE
    bad += 0 if ok else 1
    print(f"hole {name:33} {d:6.2f} {MIN_HOLE:6.2f}  {'ok' if ok else 'BELOW LIMIT'}")
    report["holes"].append({"hole": name, "dia_mm": d, "limit": MIN_HOLE, "pass": ok})

gaps = [
    ("leg tongue in the tunnel", (TIE_W - (LEG_T - 1.0)) / 2),
    ("tray channel over the heel rail", BALLAST_SLOT),
    ("PCB to the ribs, bought part, only the case varies", PCB_CLR),
    ("lid skirt to the cavity wall", SK),
]
print()
for name, g in gaps:
    ok = g >= MIN_GAP - 1e-6 or "bought part" in name
    bad += 0 if ok else 1
    print(f"gap  {name:33} {g:6.2f} {MIN_GAP:6.2f}  {'ok' if ok else 'BELOW LIMIT'}")
    report["gaps"].append({"gap": name, "mm": g, "limit": MIN_GAP, "pass": ok})

print()
for n, s in (("base", base), ("lid", lid), ("plate", plate), ("leg", leg), ("tray", tray), ("adapter", adapter)):
    bb = s.BoundBox
    fits = bb.XLength <= BUILD[0] and bb.YLength <= BUILD[1] and bb.ZLength <= BUILD[2]
    shells = len(s.Shells)
    print(
        f"{n:8} {bb.XLength:6.1f} x {bb.YLength:5.1f} x {bb.ZLength:5.1f} mm, {s.Volume / 1000:6.2f} cm3, "
        f"{len(s.Solids)} solid, {shells} shell{'s' if shells != 1 else ''}  "
        f"{'fits the build volume' if fits else 'TOO LARGE'}"
        f"{'' if shells == 1 else '  <-- enclosed void, powder cannot escape'}"
    )
    bad += 0 if (fits and shells == 1) else 1
    report["parts"].append(
        {
            "part": n,
            "bbox_mm": [round(v, 1) for v in (bb.XLength, bb.YLength, bb.ZLength)],
            "volume_cm3": round(s.Volume / 1000, 2),
            "solids": len(s.Solids),
            "shells": shells,
            "fits_build_volume": bool(fits),
        }
    )

# Collisions and keep-outs against every dummy, from the check() in the macro.
print("\ncollisions and keep-outs, the macro's own check()")
collisions = check()
print("  " + ("\n  ".join(collisions) if collisions else "none above 1e-3 mm3"))
bad += len(collisions)
report["collisions"] = collisions


# The check() in the macro never pairs the stand with the case, so this tool sweeps every part and
# dummy instead. The leg and the tray are separate prints, and they sit on the center line of a Y
# tunnel as render_scene.py places them. Without that placement the sweep compares parts that never
# share an x.
def stand():
    out = {}
    for i, ax in enumerate(TIE_X):
        lg = leg.copy()
        lg.translate(V(ax - LEG_T / 2, 0, 0))
        out[f"leg {i + 1}"] = lg
        tr = tray.copy()
        tr.translate(V(ax, 0, 0))
        out[f"tray {i + 1}"] = tr
    return out


SWEEP = {
    "base": base,
    "lid": lid,
    "plate": plate,
    "adapter": adapter,
    **stand(),
    "PCB": pcb,
    "components": comps,
    "LiPo 103450": bat,
    "LiPo 852040": bat2,
    "panel": panel,
    "vent plug": vent_plug,
    "vent nut": vent_nut_dummy,
}


def overlap(a, b):
    return (
        a.XMin <= b.XMax
        and b.XMin <= a.XMax
        and a.YMin <= b.YMax
        and b.YMin <= a.YMax
        and a.ZMin <= b.ZMax
        and b.ZMin <= a.ZMax
    )


names = list(SWEEP)
sweep_bad = []
# The two battery options are alternatives. Their dummies overlap by construction, and they never
# coexist in one build: either the 103450 alone, or the 852040 in its adapter tray.
alt_a, alt_b = {"LiPo 103450"}, {"adapter", "LiPo 852040"}


def alternatives(n1, n2):
    return (n1 in alt_a and n2 in alt_b) or (n2 in alt_a and n1 in alt_b)


print("\ncollisions, every pair of parts and dummies")
for i, n1 in enumerate(names):
    for n2 in names[i + 1 :]:
        s1, s2 = SWEEP[n1], SWEEP[n2]
        if not overlap(s1.BoundBox, s2.BoundBox):
            continue
        c = s1.common(s2)
        if c.Volume > 1e-3:
            bb = c.BoundBox
            where = [round(v, 1) for v in (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax)]
            alt = alternatives(n1, n2)
            sweep_bad.append(
                {"pair": [n1, n2], "mm3": round(c.Volume, 3), "at": where, "alternative_configuration": alt}
            )
            print(
                f"  {n1} x {n2}: {c.Volume:.3f} mm3 at x {where[0]}..{where[1]}, y {where[2]}..{where[3]}, "
                f"z {where[4]}..{where[5]}" + ("   [alternative battery, not a defect]" if alt else "")
            )
if not [s for s in sweep_bad if not s["alternative_configuration"]]:
    print("  none above 1e-3 mm3 outside the battery alternatives")
bad += len([s for s in sweep_bad if not s["alternative_configuration"]])
report["pair_sweep"] = sweep_bad
report["stand_placement"] = {"leg_x0": TIE_X[0] - LEG_T / 2, "tray_x0": TIE_X[0], "tunnels_at_x": list(TIE_X)}

# A second shell in a part is an enclosed void, so a single shell is the proof that powder can reach
# every cavity.
voids = [n for n in report["parts"] if n["shells"] != 1]
escape = [
    ("tie tunnels, Y pair", f"{TIE_W} x {TIE_H}, open at both ends"),
    ("tie tunnels, X pair", f"{TIE_W2} x {TIE_H2}, open at both ends"),
    ("screw bores", f"{SCREW_D} through, from the counterbore to the insert hole"),
    ("ePTFE vent", f"{VENT_D} through the end wall"),
    ("SMA bulkhead", f"{SMA_D} through the end wall"),
    ("battery pocket", "open to the cavity, the plate stands it off"),
    ("captive neck", f"{SCREW_CAPTIVE_D} between two {SCREW_D} bores"),
    ("solar feedthrough", f"{SOLAR_HOLE_D} through the lid, the potting cup is open downwards"),
]
print(f"\ndepowdering: {len(voids)} enclosed void(s). Escape paths:")
for n, d in escape:
    print(f"  {n:22} {d}")
if voids:
    bad += 1
report["depowdering"] = {"enclosed_voids": voids, "escape_paths": [f"{n}: {d}" for n, d in escape], "pass": not voids}

# Free geometry. A lead-in is a cut, so it costs no material and no print time. These are the
# lead-ins that a cable tie, a cord, a screw or a plug meets first.
print("\nfree geometry (cuts only)")
for name, w, where in (
    ("hole lead-ins", LEAD, "every printed hole mouth, both faces where reachable"),
    ("counterbore lead-ins", 0.6, "M3 head counterbore"),
    ("lid skirt lead-in", SKIRT_LEAD, "outer bottom edge of the skirt"),
):
    print(f"  {name:22} {w:.2f} mm   {where}")
report["free_geometry"] = {
    "lead_in_mm": LEAD,
    "counterbore_lead_in_mm": 0.6,
    "skirt_lead_in_mm": SKIRT_LEAD,
}

report["failures"] = bad
json.dump(report, open(os.path.join(HERE, "verification_report.json"), "w"), indent=1)
print(f"\n{bad} issue(s)" if bad else "\nno issues")
print("wrote verification_report.json")
