"""Grows a cylinder on every fastener and nut axis and reports the free radius around it.

The tool bisects a cylinder on the tool axis against the parts that sit in the case at that step, and
the bisection stops at 0.02 mm. The result is the radial clearance. The distance from the axis line is
a different measurement and a weaker one: it reports the step where the segment ends, which is 1.8 mm
against a 3.25 mm counterbore.

Each probe carries two obstruction sets. The set at_step applies to the step that needs the tool, and
it decides the verdict. The set after is the closed case, and it reports whether the joint stays
serviceable.

Run with: freecadcmd clearance_probe.py
"""

# ruff: noqa: F821, E402  (names and FreeCAD modules come from the macro exec'd below)
import os
import json

os.environ["SMN_NO_EXPORT"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
exec(
    open(os.path.join(HERE, "..", "freecad", "SolarMeshtasticNodeMini_Enclosure.FCMacro"), encoding="utf-8").read(),
    globals(),
)

CAP = 30.0  # Beyond this a joint counts as unobstructed. Every tool here is smaller than 60 mm across.
CLASH_MM3 = 1e-3

FITTED = {
    "base": base,
    "lid": lid,
    "plate": plate,
    "adapter": adapter,
    "PCB": pcb,
    "components": comps,
    "LiPo": bat,
    "leg L": leg,
    "leg R": leg,
    "ballast tray": tray,
    "pigtail": pig_tube,
}
CASE = ["base", "plate", "adapter", "PCB", "components", "LiPo"]
CASE_LID = CASE + ["lid"]
CASE_STAND = CASE_LID + ["leg L", "leg R", "ballast tray"]
hx_, hy_ = hx, hy


def free_radius(p0, p1, names):
    """Largest cylinder radius on p0..p1 that clears every named obstruction."""
    d = p1 - p0
    names = list(dict.fromkeys(names))

    def hits(r):
        cyl = Part.makeCylinder(r, d.Length, p0, d)
        for n in names:
            if cyl.common(FITTED[n]).Volume > CLASH_MM3:
                return n
        return None

    first = hits(CAP)
    if first is None:
        return CAP, f"nothing within {CAP:.0f} mm"
    lo, hi = 0.0, CAP
    while hi - lo > 0.02:
        mid = (lo + hi) / 2.0
        if hits(mid):
            hi = mid
        else:
            lo = mid
    return lo, hits(hi) or first


def probe(name, p0, p1, at_step, need, note, after=None):
    r, who = free_radius(p0, p1, at_step)
    ra, whoa = free_radius(p0, p1, after) if after else (r, who)
    return {
        "probe": name,
        "free_radius_mm": round(r, 2),
        "required_mm": need,
        "limited_by": who,
        "pass": r >= need - 0.02,
        "unobstructed": r >= CAP - 1e-6,
        "service_free_radius_mm": round(ra, 2),
        "service_limited_by": whoa,
        "note": note,
    }


PROBES = [
    *[
        probe(
            f"M3x40 column {'ABCD'[i]}, key from below",
            V(x, y, -FLOOR - 12.0),
            V(x, y, -FLOOR + CBORE_H),
            CASE_STAND,
            CBORE_D / 2,
            f"An M3 socket head sits in the {CBORE_D} x {CBORE_H} counterbore. The same space remains "
            "when both legs and a ballast tray are fitted",
        )
        for i, (x, y) in enumerate(corners)
    ],
    probe(
        "SMA bulkhead nut, SW8 spanner",
        V(0.5, SMA_Y, SMA_Z),
        V(10.0, SMA_Y, SMA_Z),
        ["base"],
        8.0,
        "A thin open end spanner needs a free radius of 8 mm. Fit the nut before the battery plate",
        after=CASE,
    ),
    probe(
        "ePTFE vent nut, fingers",
        V(L_IN - VENT_FREE_L, VENT_Y, VENT_Z),
        V(L_IN - 0.5, VENT_Y, VENT_Z),
        ["base"],
        VENT_FREE_D / 2,
        f"The M12 nut is {VENT_NUT_D} mm across. The macro reserves {VENT_FREE_D} dia x {VENT_FREE_L} "
        "mm. Fit it before the battery plate",
        after=CASE,
    ),
    probe(
        "M2.5x6 driver, PCB screw",
        V(hx_, hy_, PCB_Z + PCB_T + 1.0),
        V(hx_, hy_, PCB_Z + PCB_T + 40.0),
        ["base", "plate", "adapter", "LiPo", "components"],
        1.75,
        "The PCB dummy is excluded. A 2.5 mm driver meets its own 2.7 mm hole, not this case",
    ),
]

print(f"{'probe':38} {'free':>6} {'need':>6}  {'verdict':>7} {'service':>8}  limited by")
print("-" * 104)
bad = []
for p in PROBES:
    if not p["pass"]:
        bad.append(p)
    free = f">={CAP:.0f}" if p["unobstructed"] else f"{p['free_radius_mm']:.2f}"
    serv = "-" if p["unobstructed"] else f"{p['service_free_radius_mm']:.2f}"
    print(
        f"{p['probe']:38} {free:>6} {p['required_mm']:6.2f}  {'ok' if p['pass'] else 'BELOW':>7} "
        f"{serv:>8}  {p['limited_by']}"
    )

print()
for p in PROBES:
    if p["service_limited_by"] != p["limited_by"]:
        print(
            f"service access, {p['probe']}: {p['service_free_radius_mm']} mm, limited by "
            f"{p['service_limited_by']} once the case is closed"
        )
print(
    f"\n{len(bad)} of {len(PROBES)} probe(s) below their required free radius"
    if bad
    else f"\nall {len(PROBES)} probes clear"
)
json.dump(
    {"tool": "clearance_probe.py", "process": "SLS/MJF PA12", "probes": PROBES, "failures": len(bad)},
    open(os.path.join(HERE, "clearance_report.json"), "w"),
    indent=1,
)
print("wrote clearance_report.json")
