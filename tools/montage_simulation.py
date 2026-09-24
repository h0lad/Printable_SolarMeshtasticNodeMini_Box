"""Walks the build order and measures the space at each step of the assembly.

Each step reports the worst overlap during the full insertion travel and the smallest gap at the seat.
For a step that needs a tool, the report gives the free radius on the tool axis.

The tool walks the travel at 0.25 mm. It computes the window in which the part and an obstruction can
overlap, and it then clips the part to the range that can reach the obstruction. Six samples across a
50 mm travel can miss a 1.35 mm lip.

The leg and the tray sit on the center line of a Y tunnel, as they do in render_scene.py and in the
assembly export. A row marked informational is a closed path that the record keeps, and the intended
motion is a different one.

Run with: freecadcmd montage_simulation.py
"""

# ruff: noqa: F821, E402  (names and FreeCAD modules come from the macro exec'd below)
import json
import os

os.environ["SMN_NO_EXPORT"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
exec(
    open(os.path.join(HERE, "..", "freecad", "SolarMeshtasticNodeMini_Enclosure.FCMacro"), encoding="utf-8").read(),
    globals(),
)

TONGUE_Z = -FLOOR + TIE_SKIN + 0.2
TZ0 = -FLOOR + TIE_SKIN  # The tunnel floor.
STEP_MM = 0.25  # The travel resolution. The tool can miss a feature that is thinner than this.
CAP = 600  # The sample cap per obstruction. The tool reports a step that needs more samples than this.

REG = {
    "base": base,
    "lid": lid,
    "plate": plate,
    "adapter": adapter,
    "PCB": pcb,
    "components": comps,
    "LiPo 103450": bat,
    "LiPo 852040": bat2,
    "panel": panel,
    "vent plug": vent_plug,
    "vent nut": vent_nut_dummy,
    "screws": fuse(*screws),
}
# The captive neck is a deliberate press fit, so the screw passes through it once. The check() in the
# macro excludes it for the same reason.
base_noneck = base
for xx, yy in corners:
    base_noneck = base_noneck.cut(cyl(xx, yy, -FLOOR - 1, SCREW_D / 2, FLOOR + H_IN + 2))
REG["base, neck relieved"] = base_noneck
lg_relieved = leg.copy()
lg_relieved = lg_relieved.cut(box(-30.0, -15.5, TZ0 + TIE_H, 60.0, 10.0, 60.0))  # The two barbs.
lg_relieved = lg_relieved.cut(box(-30.0, -15.5, -60.0, 60.0, 10.0, TZ0 + 60.0))
lg1 = lg_relieved.copy()
lg1.translate(V(TIE_X[0] - LEG_T / 2, 0, 0))  # On the center line of tunnel 1, as the real leg sits.
REG["leg, snap relieved"] = lg1
lg2 = lg_relieved.copy()
lg2.translate(V(TIE_X[1] - LEG_T / 2, 0, 0))
REG["leg 2, snap relieved"] = lg2
pcb_fwd = pcb.copy()
pcb_fwd.translate(V(0, -0.6, 0))  # The insertion start of the board, forward of its seat.
REG["PCB, forward"] = pcb_fwd
for i, ax in enumerate(TIE_X):
    lg = leg.copy()
    lg.translate(V(ax - LEG_T / 2, 0, 0))
    REG[f"leg {i + 1}"] = lg
    tr = tray.copy()
    tr.translate(V(ax, 0, 0))
    REG[f"tray {i + 1}"] = tr

CASE = ["base", "plate", "adapter", "PCB", "components", "LiPo 103450", "LiPo 852040"]
hx_, hy_ = hx, hy


def swings(travel):
    """The one axis a travel moves along, its sign, and its length."""
    v = (travel.x, travel.y, travel.z)
    for i in range(3):
        if abs(v[i]) > 1e-9:
            assert all(abs(v[j]) < 1e-9 for j in range(3) if j != i), "only single axis travels"
            return i, v[i], abs(v[i])
    raise ValueError("zero travel")


def bb(o):
    """(xmin, xmax, ymin, ymax, zmin, zmax) of a shape or a bound box."""
    b = o if hasattr(o, "XMin") else o.BoundBox
    return b.XMin, b.XMax, b.YMin, b.YMax, b.ZMin, b.ZMax


def window(part_box, ob_box, axis, d):
    """Fraction of the travel in [0, 1] where the two intervals on the moving axis can overlap."""
    pa, pb = bb(part_box)[2 * axis : 2 * axis + 2]
    oa, ob = bb(ob_box)[2 * axis : 2 * axis + 2]
    t0 = (oa - pb) / d  # The offset applied to the part at fraction f is d * (f - 1).
    t1 = (ob - pa) / d
    lo, hi = sorted((t0, t1))
    return max(0.0, lo + 1.0), min(1.0, hi + 1.0)


def still_overlaps(part_box, ob_box, axis):
    for i in range(3):
        if i == axis:
            continue
        pa, pb = bb(part_box)[2 * i : 2 * i + 2]
        oa, ob = bb(ob_box)[2 * i : 2 * i + 2]
        if pa > ob or oa > pb:
            return False
    return True


def reach_clip(sh, ob, travel, axis, d):
    """Clips sh to the part that can meet ob during the travel from seat - travel into the seat.

    A point p of the part moves over p + off. The offset off runs from -d to 0. The point can meet the
    obstruction only if p + off is inside its box. The part needs only the range
    [ob_lo - off_hi, ob_hi - off_lo]. The clip is safe, and it keeps the boolean operations small.
    """
    off_lo, off_hi = min(0.0, -d), max(0.0, -d)
    mn, mx = [], []
    for i in range(3):
        pl, ph = bb(sh)[2 * i : 2 * i + 2]
        ol, oh = bb(ob)[2 * i : 2 * i + 2]
        lo, hi = off_lo, off_hi
        if i != axis:
            lo = hi = 0.0
        mn.append(max(pl, ol - hi))
        mx.append(min(ph, oh - lo))
        if mx[i] - mn[i] <= 0:
            return None
    out = sh.common(Part.makeBox(mx[0] - mn[0], mx[1] - mn[1], mx[2] - mn[2], V(*mn)))
    return None if out.isNull() or out.Volume < 1e-6 else out


def sweep(sh, travel, fitted, note):
    """Worst overlap of sh sliding from seat - travel into the seat, over the whole travel."""
    axis, d, length = swings(travel)
    worst, who, at = 0.0, None, None
    for n in fitted:
        ob = REG[n]
        if not still_overlaps(sh.BoundBox, ob.BoundBox, axis):
            continue
        lo, hi = window(sh.BoundBox, ob.BoundBox, axis, d)
        if hi <= lo + 1e-9:
            continue
        part = reach_clip(sh, ob, travel, axis, d)
        if part is None:
            continue
        steps = max(1, min(CAP, int((hi - lo) * length / STEP_MM) + 1))
        if steps >= CAP and note is not None:
            note.append(f"{n} needed more than {CAP} samples")
        for i in range(steps + 1):
            f = lo + (hi - lo) * i / steps
            moved = part.copy()
            moved.translate(travel * (f - 1.0))
            c = moved.common(ob)
            if c.Volume > worst:
                v = c.BoundBox
                worst, who = c.Volume, n
                at = [round(x, 1) for x in (v.XMin, v.XMax, v.YMin, v.YMax, v.ZMin, v.ZMax)]
    return worst, who, at


def hits(shape, names):
    """Worst overlap of a static shape with a set of fitted parts, and where."""
    s0, s1, s2, s3, s4, s5 = bb(shape)
    worst, who, at = 0.0, None, None
    for n in names:
        o = REG[n]
        o0, o1, o2, o3, o4, o5 = bb(o)
        if not (s0 <= o1 and o0 <= s1 and s2 <= o3 and o2 <= s3 and s4 <= o5 and o4 <= s5):
            continue
        c = shape.common(o)
        if c.Volume > worst:
            v = c.BoundBox
            worst, who = c.Volume, n
            at = [round(x, 1) for x in (v.XMin, v.XMax, v.YMin, v.YMax, v.ZMin, v.ZMax)]
    return worst, who, at


def free_radius(p0, p1, names):
    d = p1 - p0
    names = list(dict.fromkeys(names))

    def touch(r):
        return hits(Part.makeCylinder(r, d.Length, p0, d), names)[0]

    if touch(CAP) <= 1e-3:
        return CAP, "nothing within 30 mm"
    lo, hi = 0.0, 30.0
    while hi - lo > 0.02:
        mid = (lo + hi) / 2.0
        if touch(mid) > 1e-3:
            hi = mid
        else:
            lo = mid
    return lo, hits(Part.makeCylinder(hi, d.Length, p0, d), names)[1]


def step(name, shape=None, travel=None, fitted=(), tool=None, note="", informational=False):
    return {
        "name": name,
        "shape": shape,
        "travel": travel,
        "fitted": list(fitted),
        "tool": tool,
        "note": note,
        "informational": informational,
    }


STEPS = [
    step(
        "ePTFE plug through the right wall",
        "vent plug",
        V(-40, 0, 0),
        ["base"],
        note="from outside, through the 12.6 mm hole",
    ),
    step(
        "ePTFE nut, lowered in from above",
        "vent nut",
        V(0, 0, -45),
        ["base"],
        note="The cavity is open until the lid goes on. The nut drops straight onto the thread.",
    ),
    step(
        "ePTFE nut, slid on along the axis instead",
        "vent nut",
        V(30, 0, 0),
        ["base"],
        note="Closed path. The 16 mm nut passes the battery pocket rib at x 57.5 to 59. The rib ends "
        "at z 12. The vent axis is at z 13.",
        informational=True,
    ),
    step(
        "SMA bulkhead nut, SW8",
        None,
        None,
        ["base"],
        tool=(V(0.5, SMA_Y, SMA_Z), V(10.0, SMA_Y, SMA_Z), 8.0, "spanner"),
        note="fit it before the battery plate",
    ),
    step("adapter tray into the pocket", "adapter", V(0, 0, -60), ["base"]),
    step("LiPo 852040 into the tray", "LiPo 852040", V(0, 0, -50), ["base", "adapter"]),
    step(
        "LiPo 103450 into the pocket, the other option",
        "LiPo 103450",
        V(0, 0, -50),
        ["base"],
        note="This is the alternative to the adapter with the 852040. Do not fit both.",
    ),
    step(
        "battery plate onto the pocket walls", "plate", V(0, 0, -60), ["base", "adapter", "LiPo 852040", "LiPo 103450"]
    ),
    step(
        "PCB down onto the pillars, 0.6 forward for the lips",
        "PCB, forward",
        V(0, 0, -40),
        ["base", "plate", "adapter", "LiPo 852040", "LiPo 103450"],
        note="The board is 47 mm long in a 47.8 mm slot. It starts forward of its seat.",
    ),
    step(
        "PCB slid back 0.6 under the hold-down lips",
        "PCB",
        V(0, 0.6, 0),
        ["base", "plate", "adapter", "LiPo 852040", "LiPo 103450"],
        note="A horizontal slide at board height. The board top is at 17.3 mm. The underside of the "
        "lip is at 17.8 mm.",
    ),
    step(
        "M2.5x6 driver",
        None,
        None,
        ["base", "plate", "adapter", "PCB", "components", "LiPo 103450"],
        tool=(V(hx_, hy_, PCB_Z + PCB_T + 1.0), V(hx_, hy_, PCB_Z + PCB_T + 40.0), 1.75, "2.5 mm driver"),
    ),
    step("lid onto the base, skirt into the cavity", "lid", V(0, 0, -40), CASE + ["vent plug", "vent nut"]),
    step(
        "M3x40 x4 from below, into the inserts",
        "screws",
        V(0, 0, 50),
        ["base, neck relieved", "lid", "plate", "leg 1", "leg 2", "tray 1", "tray 2"],
        note="The 2.7 mm captive neck is a press fit by design. The tool relieves it here, as the "
        "check() in the macro does",
    ),
    step(
        "leg 1 tongue into the Y tunnel, pushed -Y",
        "leg, snap relieved",
        V(0, -90, 0),
        ["base", "lid", "plate", "PCB", "leg 2", "tray 2"],
        note=f"Push the leg in from the +Y side. The tongue, web and heel cross the tunnel. The barbs "
        f"deflect {SNAP_T:.1f} mm on each side. The wall pad, plate and foot stay at "
        f"y >= {W_IN + WALL:.1f} mm, outside the box.",
    ),
    step(
        "leg 1 tongue into the Y tunnel, pushed +Y",
        "leg 1",
        V(0, 90, 0),
        ["base", "lid", "plate", "PCB", "leg 2", "tray 2"],
        note="Closed path. The wall pad leads and must cross the 4.6 mm end walls",
        informational=True,
    ),
    step("tray 1 channel onto the heel rail", "tray 1", V(0, 40, 0), ["base", "leg 1"]),
    step(
        "leg 2 tongue into the Y tunnel, pushed -Y",
        "leg 2, snap relieved",
        V(0, -90, 0),
        ["base", "lid", "plate", "PCB", "leg 1", "tray 1"],
    ),
    step("tray 2 channel onto the heel rail", "tray 2", V(0, 40, 0), ["base", "leg 2"]),
    step(
        "solar panel onto the spacers",
        "panel",
        V(0, 0, -40),
        ["base", "lid", "plate", "leg 1", "leg 2", "tray 1", "tray 2"],
    ),
]
SKIPPED = {
    "components onto the PCB": "The components are soldered on before the board goes in. The PCB step "
    "carries the envelope",
    "U.FL pigtail onto the PCB socket": "The pigtail is flexible and has no rigid insertion path. The "
    "static keep-out check in the macro covers it",
    "O-ring cord into the groove": "The cord is flexible and is pressed in. The groove depth is the "
    "design rule that applies",
    "solar panel leads into the feedthrough": "The leads are flexible and are potted after the lid is "
    "on. The macro checks the bore, the potting cup and the wire path",
    "pegs and cable ties through the eyelets": "They are flexible. They go in last and block no step",
}

print(f"travel walked at {STEP_MM} mm. A feature thinner than that can be missed.")
print(f"{'step':46} {'path':>7} {'seat':>6} {'tool':>6} {'need':>6}  verdict")
print("-" * 112)
rows, bad = [], []
for s in STEPS:
    notes = []
    path_v, path_who, path_at = 0.0, None, None
    seat, seat_who = None, None
    if s["shape"]:
        sh = REG[s["shape"]]
        path_v, path_who, path_at = sweep(sh, s["travel"], s["fitted"], notes)
        d = [(sh.distToShape(REG[n])[0], n) for n in s["fitted"]]
        if d:
            seat, seat_who = min(d)
    tool_r = None
    need = None
    if s["tool"]:
        p0, p1, need, _ = s["tool"]
        tool_r = free_radius(p0, p1, s["fitted"])[0]
    blocked = path_v > 1e-3 or (need is not None and tool_r < need - 0.02)
    ok = blocked and s["informational"] or not blocked
    if blocked and not s["informational"]:
        bad.append(s["name"])
    tag = "ok" if not blocked else ("closed, as expected" if s["informational"] else "BLOCKED")
    print(
        f"{s['name']:46} {path_v:6.1f}{'!' if blocked and path_v > 1e-3 else ' '} "
        f"{seat if seat is not None else -1:6.2f} {tool_r if tool_r is not None else -1:6.2f} "
        f"{need if need else 0:6.2f}  {tag}"
        + (f"  {path_who} at " if blocked and path_v > 1e-3 else "")
        + (
            f"x {path_at[0]}..{path_at[1]} y {path_at[2]}..{path_at[3]} z {path_at[4]}..{path_at[5]}"
            if path_at and blocked
            else ""
        )
        + (f"  {seat_who}" if seat is not None and seat < 0.25 else "")
    )
    for nt in notes:
        print(f"{'':46} note: {nt}")
    rows.append(
        {
            "step": s["name"],
            "path_clash_mm3": round(path_v, 3),
            "clashing_with": path_who,
            "clash_at": path_at,
            "seat_gap_mm": None if seat is None else round(seat, 3),
            "seat_limited_by": seat_who,
            "tool_free_radius_mm": None if tool_r is None else round(tool_r, 2),
            "tool_required_mm": need,
            "informational": s["informational"],
            "note": s["note"],
            "pass": bool(ok),
        }
    )

print("\nnot walked, with the reason:")
for k, v in SKIPPED.items():
    print(f"  {k}: {v}")
print(f"\n{len(bad)} blocked step(s): " + ", ".join(bad) if bad else "\nevery step fits")
json.dump(
    {"tool": "montage_simulation.py", "travel_step_mm": STEP_MM, "order": rows, "skipped": SKIPPED, "blocked": bad},
    open(os.path.join(HERE, "assembly_simulation_report.json"), "w"),
    indent=1,
)
print("wrote assembly_simulation_report.json")
