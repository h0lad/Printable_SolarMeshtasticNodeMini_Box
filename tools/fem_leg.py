# ruff: noqa: F821, E402  (names and FreeCAD modules come from the macro exec'd below)
"""Tilt leg under foot load (weight plus peg hold-down). F_FOOT [N] as environment variable."""

import os
import math

os.environ["SMN_NO_EXPORT"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
exec(
    open(os.path.join(HERE, "..", "freecad", "SolarMeshtasticNodeMini_Enclosure.FCMacro"), encoding="utf-8").read(),
    globals(),
)
import ObjectsFem
import FreeCAD as App
from femtools import ccxtools
from femmesh.gmshtools import GmshTools

F_FOOT = float(os.environ.get("F_FOOT", "30"))  # N per leg: ~2 N weight + peg hold-down at 40 m/s + reserve
sl = leg.copy().Solids[0]
doc = App.newDocument("femleg")
part = doc.addObject("Part::Feature", "Leg")
part.Shape = sl
th = math.radians(LEG_ANGLE)
n = App.Vector(0, math.sin(th), math.cos(th))
fix = []
load = []
tongue_z = -FLOOR + TIE_SKIN + 0.2
for i, f in enumerate(sl.Faces):
    c = f.CenterOfMass
    if f.Surface.TypeId == "Part::GeomPlane":
        if abs(c.z - tongue_z) < 0.3 or abs(c.z - (tongue_z + TIE_H - 0.4)) < 0.3:  # tongue top/bottom in the tunnel
            if -WALL < c.y < W_IN + WALL:
                fix.append(f"Face{i + 1}")
        if abs(c.y - (W_IN + WALL)) < 0.3:
            fix.append(f"Face{i + 1}")  # pad against the side wall
        if abs(n.dot(App.Vector(*f.normalAt(0, 0)))) > 0.95 and c.y > LEG_FOOT_Y - 2 and c.z < -FLOOR - 20:
            load.append(f"Face{i + 1}")
print("fixed", len(fix), "loaded", len(load))
an = ObjectsFem.makeAnalysis(doc, "A")
solver = ObjectsFem.makeSolverCalculiXCcxTools(doc)
an.addObject(solver)
solver.WorkingDir = os.path.join(HERE, "femrun3")
os.makedirs(solver.WorkingDir, exist_ok=True)
mat = ObjectsFem.makeMaterialSolid(doc, "PA")
m = mat.Material
m.update({"Name": "PA", "YoungsModulus": "1700 MPa", "PoissonRatio": "0.40", "Density": "1010 kg/m^3"})
mat.Material = m
an.addObject(mat)
fx = ObjectsFem.makeConstraintFixed(doc, "Fix")
fx.References = [(part, fix)]
an.addObject(fx)
fc = ObjectsFem.makeConstraintForce(doc, "F")
fc.References = [(part, load)]
fc.Force = f"{F_FOOT:.1f} N"
fc.DirectionVector = App.Vector(n.x, n.y, n.z)
fc.Reversed = True
an.addObject(fc)
mesh = ObjectsFem.makeMeshGmsh(doc, "Mesh")
mesh.Shape = part
mesh.CharacteristicLengthMax = "2.5 mm"
mesh.CharacteristicLengthMin = "0.8 mm"
mesh.ElementOrder = "1st"
an.addObject(mesh)
GmshTools(mesh).create_mesh()
print("nodes", mesh.FemMesh.NodeCount)
doc.recompute()
fea = ccxtools.FemToolsCcx(an, solver)
fea.update_objects()
fea.setup_working_dir()
fea.setup_ccx()
fea.check_prerequisites()
fea.write_inp_file()
fea.ccx_run()
fea.load_results()
res = [o for o in doc.Objects if o.isDerivedFrom("Fem::FemResultObject")][0]
vm = sorted(res.vonMises)
print(
    f"load {F_FOOT:.0f} N per foot -> MAX_VM {vm[-1]:.1f} MPa, p99 {vm[int(0.99 * len(vm))]:.1f} MPa, "
    f"max deflection {max(res.DisplacementLengths):.2f} mm"
)
