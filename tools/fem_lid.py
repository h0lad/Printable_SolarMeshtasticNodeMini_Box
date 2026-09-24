# ruff: noqa: F821, E402  (names come from the macro exec'd below)
"""Loads the lid deck with every load it can meet.

FEM_CASE selects the load case, SMN_LID_RELIEF sets the relief depth, and both are read from the
environment.

    FEM_CASE=foot SMN_LID_RELIEF=1.5 freecadcmd fem_lid.py

The cases are these:
  service  Wind plus snow on the panel, over the nine standoffs. This case is cyclic, so it wants 2.0.
  press    A hand presses the panel onto the glue points, over the nine standoffs.
  foot     A person stands on the panel with a flat foot, 800 N over the nine standoffs.
  screw    The four heat set inserts are pulled down at 0.5 Nm, which is the collar at every column.
  heel     800 N on one inner standoff. This case is informational, because the 3 mm panel breaks
           before the deck does.

The wall of the base presses on the rim of the lid, so the rim is held in z and the four columns are
bolted. The standoffs carry the load, as they do in the part.

Every run appends itself to fem_lid_report.json. The outcome is that the deck ships at its full
3.5 mm, which is LID_RELIEF 0. A relief of 0.5 mm takes the p99 safety factor of the one-standoff case
from 3.03 to 1.04. A relief of 1.0 mm takes it to 0.77. The inside step of the relief is the stress
raiser that decides that case.

Read the p99 in that file rather than the peak. The peak sits on the corner of the step, so it moves
with the mesh: 14.67 MPa on the coarse mesh against 147.14 MPa on the fine one, for the same case.
"""

import json
import math
import os
import re

os.environ["SMN_NO_EXPORT"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
exec(
    open(os.path.join(HERE, "..", "freecad", "SolarMeshtasticNodeMini_Enclosure.FCMacro"), encoding="utf-8").read(),
    globals(),
)
import FreeCAD as App
import ObjectsFem
from femtools import ccxtools
from femmesh.gmshtools import GmshTools

CASE = os.environ.get("FEM_CASE", "foot")
ORDER = os.environ.get("FEM_ORDER", "2nd")
MESH = os.environ.get("FEM_MESH", "coarse")
LMAX, LMIN = {"coarse": ("1.6 mm", "0.7 mm"), "fine": ("1.1 mm", "0.5 mm")}[MESH]
if os.environ.get("FEM_SIZE"):  # A retry with a slightly different element size clears a bad element.
    LMAX, LMIN = os.environ["FEM_SIZE"].split("/")
TENSILE = 48.0  # MPa, PA12
LT = ltop + STANDOFF_H
CASES = {
    # name: total newtons, where the load lands, and how many standoffs share it
    "service": (2.7 + 2.4, "deck", 9),  # wind at the tipping speed plus 20 kg/m2 of snow
    "press": (200.0, "deck", 9),  # a hand on the panel while the glue cures
    "foot": (800.0, "deck", 9),  # a person on the panel, flat foot
    "screw": (833.0, "corner", 4),  # M3 into a heat set insert at 0.5 Nm, T / (0.2 d)
    "heel": (800.0, "centre", 1),  # one standoff, informational
}
total, where, share = CASES[CASE]
force = total / share

sl = lid.copy().Solids[0]
doc = App.newDocument("femlid")
part = doc.addObject("Part::Feature", "Lid")
part.Shape = sl

fix_z, fix_xy, load = [], [], []
for i, f in enumerate(sl.Faces):
    c = f.CenterOfMass
    if f.Surface.TypeId == "Part::GeomPlane":
        nz = f.normalAt(0, 0).z
        # The underside of the lid: the rim, the collars and the deck bands.
        if abs(c.z - H_IN) < 0.05 and abs(nz) > 0.9:
            fix_z.append(f"Face{i + 1}")
    elif f.Surface.TypeId == "Part::GeomCylinder" and abs(f.Surface.Radius - BOSS_R) < 0.05:
        near = min(math.hypot(c.x - cx, c.y - cy) for cx, cy in corners)
        if near < 1.0 and H_IN < c.z < LT:  # The column barrel at a corner, which the insert holds.
            fix_xy.append(f"Face{i + 1}")
    if f.Surface.TypeId == "Part::GeomPlane" and abs(c.z - LT) < 0.05 and f.normalAt(0, 0).z > 0.9:
        near = min(math.hypot(c.x - cx, c.y - cy) for cx, cy in corners)
        corner = near < 4.0
        centre = math.hypot(c.x - L_IN / 2, c.y - W_IN / 2) < 3.0
        if where == "corner" and corner:
            load.append(f"Face{i + 1}")
        elif where == "centre" and centre:
            load.append(f"Face{i + 1}")
        elif where == "deck":
            load.append(f"Face{i + 1}")
print(f"{CASE}: held in z {len(fix_z)}, held in x/y {len(fix_xy)}, loaded {len(load)}, {force:.1f} N on each")

an = ObjectsFem.makeAnalysis(doc, "A")
solver = ObjectsFem.makeSolverCalculiXCcxTools(doc)
an.addObject(solver)
solver.WorkingDir = os.path.join(HERE, "femrun_lid")
os.makedirs(solver.WorkingDir, exist_ok=True)
mat = ObjectsFem.makeMaterialSolid(doc, "PA")
m = mat.Material
m.update({"Name": "PA", "YoungsModulus": "1700 MPa", "PoissonRatio": "0.40", "Density": "1010 kg/m^3"})
mat.Material = m
an.addObject(mat)
dz = ObjectsFem.makeConstraintDisplacement(doc, "RimZ")
dz.References = [(part, fix_z)]
dz.xFree, dz.yFree, dz.zFree = True, True, False
dz.zDisplacement = 0.0
an.addObject(dz)
dxy = ObjectsFem.makeConstraintDisplacement(doc, "ColumnXY")
dxy.References = [(part, fix_xy)]
dxy.xFree, dxy.yFree, dxy.zFree = False, False, True
dxy.xDisplacement = dxy.yDisplacement = 0.0
an.addObject(dxy)
# A pressure and not a force. The force constraint splits the total over the nodes by their share of
# the face area, and on these small discs that split comes out empty, which applies nothing at all and
# reports no error. The writer emits a pressure as *DLOAD on the element faces, so the file carries
# exactly the load that the model asked for.
area = sum(f.Area for i, f in enumerate(sl.Faces) if f"Face{i + 1}" in load)
pr = ObjectsFem.makeConstraintPressure(doc, "P")
pr.References = [(part, load)]
# The intensity, so the total over every loaded face adds up to the applied force.
pr.Pressure = f"{-total / area:.5f} MPa"
an.addObject(pr)
print(f"pressure {total / area:.3f} MPa over {area:.1f} mm2 of {len(load)} faces, {force:.1f} N each on average")
mesh = ObjectsFem.makeMeshGmsh(doc, "Mesh")
mesh.Shape = part
mesh.CharacteristicLengthMax = LMAX
mesh.CharacteristicLengthMin = LMIN
mesh.ElementOrder = ORDER
# A second-order mesh carries a few elements with a non-positive jacobian often enough that CalculiX
# stops with exit 201 and the case then goes missing without a word. The high order optimizers in gmsh
# are not the answer: "Optimization" and "Elastic+Optimization" both cost FreeCAD its element tables
# ("Neither solid nor face nor edge femmesh"), and "Fast curving" still leaves the bad elements. The
# answer is to leave the mesh alone and to retry a case that fails with a slightly different element
# size (FEM_SIZE).
if os.environ.get("FEM_OPT"):
    mesh.HighOrderOptimize = os.environ["FEM_OPT"]
an.addObject(mesh)
GmshTools(mesh).create_mesh()
print("nodes", mesh.FemMesh.NodeCount, "order", ORDER, "mesh", MESH, LMAX, LMIN)
doc.recompute()
fea = ccxtools.FemToolsCcx(an, solver)
fea.update_objects()
fea.setup_working_dir()
fea.setup_ccx()
fea.check_prerequisites()
fea.write_inp_file()
# A self-check on what the writer put in the file, rather than on what the model asked for. A face
# force splits the total over the nodes by area, and it warns when the mesh nodes do not cover the
# face. A silent shortfall would flatter every number below.
import glob  # noqa: E402

inp = sorted(glob.glob(os.path.join(fea.working_dir, "*.inp")))[-1]
faces, p_used, reading = 0, [], False
for line in open(inp):
    t = line.strip()
    if t.startswith("*DLOAD"):
        reading = True
        continue
    if reading and t.startswith("**"):
        continue  # The writer labels each face it loaded with a comment line.
    if reading and t.startswith("*"):
        reading = False
    elif reading and t:
        parts = t.split(",")
        if len(parts) >= 3 and re.match(r"^P[1-9]$", parts[2].strip()):
            faces += 1
            p_used.append(abs(float(parts[3])))
print(
    f"in the solver input: {faces} loaded faces at {sum(p_used) / max(faces, 1):.4f} MPa, "
    f"total {sum(p_used) / max(faces, 1) * area:.1f} N of {total:.1f} N intended"
)
fea.ccx_run()
fea.load_results()
res = [o for o in doc.Objects if o.isDerivedFrom("Fem::FemResultObject")][0]
# Second-order tetrahedra sometimes come back with the stress field loaded and the displacement field
# empty, so the tool assumes neither one is there.
raw = getattr(res, "vonMises", None) or []
if not raw:
    raise SystemExit(f"{CASE}: the solver returned no stress field")
vm = sorted(raw)
dl = sorted(getattr(res, "DisplacementLengths", None) or [])
dmax = dl[-1] if dl else float("nan")
# The location of the peak. A sharp internal corner is a singularity in a linear model, so where the
# peak sits says whether the peak is a real hot spot or the mesh chasing a corner.
hot = mesh.FemMesh.getNodeById(res.NodeNumbers[raw.index(max(raw))])
# Equilibrium: what the constraints actually took out of the part, read from the .dat file the solver
# wrote.
dat = sorted(glob.glob(os.path.join(fea.working_dir, "*.dat")))[-1]
react, want = [], False
for line in open(dat):
    t = line.strip()
    if t.startswith("total force"):
        want = True
        continue
    if want and t:
        f = [float(v) for v in t.replace(",", " ").split()]
        if len(f) == 3:
            react.append(f[2])
        want = False
print(f"reactions in z: {sum(react):.1f} N against {total:.1f} N applied ({100 * abs(sum(react)) / total:.0f} %)")
row = {
    "case": CASE,
    "relief_mm": LID_RELIEF,
    "deck_mm": round(LID_T - LID_RELIEF, 2),
    "order": ORDER,
    "mesh": MESH,
    "element_size": [LMAX, LMIN],
    "nodes": mesh.FemMesh.NodeCount,
    "total_n": total,
    "max_vm_mpa": round(vm[-1], 2),
    "p99_vm_mpa": round(vm[int(0.99 * len(vm))], 2),
    "max_deflection_mm": round(dmax, 3),
    "safety_max_vm": round(TENSILE / vm[-1], 2),
    "safety_p99": round(TENSILE / vm[int(0.99 * len(vm))], 2),
    "reaction_z_n": round(sum(react), 1),
    "hot_spot_mm": [round(v, 1) for v in (hot.x, hot.y, hot.z)],
    "load_at": where,
}
print(
    f"lid relief {LID_RELIEF:.1f} mm (deck {LID_T - LID_RELIEF:.2f} mm) case {CASE} order {ORDER} "
    f"mesh {MESH}: MAX_VM {vm[-1]:.2f} MPa at ({hot.x:.1f}, {hot.y:.1f}, {hot.z:.1f}), "
    f"p99 {vm[int(0.99 * len(vm))]:.2f} MPa, max deflection {dmax:.3f} mm, safety {TENSILE / vm[-1]:.2f}"
)
rep_path = os.path.join(HERE, "fem_lid_report.json")
report = (
    json.load(open(rep_path))
    if os.path.exists(rep_path)
    else {
        "tool": "fem_lid.py",
        "material": {"youngs_modulus_mpa": 1700, "poisson": 0.40, "tensile_mpa": TENSILE},
        "cases": {k: {"total_n": v[0], "applied_to": v[1], "faces": v[2]} for k, v in CASES.items()},
        "runs": {},
    }
)
report["runs"][f"{CASE}|relief={LID_RELIEF}|order={ORDER}|mesh={MESH}"] = row
json.dump(report, open(rep_path, "w"), indent=1)
print("wrote fem_lid_report.json")
