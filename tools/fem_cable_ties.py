"""Cable-tie tunnels, complete base. Support on the trunk contact line, sqrt(2)*TIE_LOAD_N per exit on
the bend radii. Run: freecadcmd SolarMeshtasticNodeMini_FEM_cable_ties.py (FreeCAD 1.0 with gmsh + ccx)"""

# ruff: noqa: F821, E402  (names and FreeCAD modules come from the macro exec'd below)
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

tx = TIE_X[0]
sl = base.copy()  # complete base
for x_, y_ in corners:  # screw holes filled, they are not in the tie load path and only upset the mesh
    sl = sl.fuse(cyl(x_, y_, -FLOOR, CBORE_D / 2 + 0.01, FLOOR + H_IN))
sl = sl.removeSplitter()
pad = box(-WALL, W_IN / 2 - 6, -FLOOR - 0.5, L_IN + 2 * WALL, 12, 0.51)  # support: trunk contact (centre line)
sl = sl.fuse(pad).removeSplitter()
doc = App.newDocument("fem")
part = doc.addObject("Part::Feature", "Slice")
part.Shape = sl
fix_faces = []
load_faces = []
for i, f in enumerate(sl.Faces):
    c = f.CenterOfMass
    if abs(c.z - (-FLOOR - 0.5)) < 1e-3 and f.Surface.TypeId == "Part::GeomPlane":
        fix_faces.append(f"Face{i + 1}")
    if f.Surface.TypeId == "Part::GeomCylinder" and abs(f.Surface.Radius - TIE_R_EXIT) < 1e-3 and c.z < tz0 + 0.1:
        load_faces.append((f"Face{i + 1}", f.Area))
print("fix", fix_faces, "load", load_faces)
an = ObjectsFem.makeAnalysis(doc, "Analysis")
solver = ObjectsFem.makeSolverCalculiXCcxTools(doc)
an.addObject(solver)
solver.WorkingDir = os.path.join(HERE, "femrun")
os.makedirs(solver.WorkingDir, exist_ok=True)
mat = ObjectsFem.makeMaterialSolid(doc, "PA11")
m = mat.Material
m.update({"Name": "PA11", "YoungsModulus": "1800 MPa", "PoissonRatio": "0.40", "Density": "1010 kg/m^3"})
mat.Material = m
an.addObject(mat)
fx = ObjectsFem.makeConstraintFixed(doc, "Fix")
fx.References = [(part, fix_faces)]
an.addObject(fx)
# 90 deg tie bend: resultant per exit = sqrt(2)*T, applied as pressure on the bend radius
for n, A in load_faces:
    pr = ObjectsFem.makeConstraintPressure(doc, "P_" + n)
    pr.References = [(part, [n])]
    # pressure as if the 5 mm tie loaded the full 6 mm tunnel width (x1.2, conservative)
    # quarter-cylinder projection
    pr.Pressure = f"{math.sqrt(2) * TIE_LOAD_N / (A * 5.0 / TIE_W) / (2 / math.pi * math.sqrt(2)):.3f} MPa"
    pr.Reversed = False
    an.addObject(pr)
    print(n, "p =", pr.Pressure)
import ObjectsFem as OF

mesh = OF.makeMeshGmsh(doc, "Mesh")
mesh.Shape = part
mesh.CharacteristicLengthMax = "2.6 mm"
mesh.CharacteristicLengthMin = "0.6 mm"
mesh.ElementOrder = "2nd"
an.addObject(mesh)
reg = OF.makeMeshRegion(doc, mesh, 0.6, "Ref")
reg.References = [(part, [n for n, _ in load_faces])]
from femmesh.gmshtools import GmshTools

g = GmshTools(mesh)
err = g.create_mesh()
print("mesh err:", err, "nodes", mesh.FemMesh.NodeCount)
doc.recompute()
fea = ccxtools.FemToolsCcx(an, solver)
fea.update_objects()
fea.setup_working_dir()
fea.setup_ccx()
msg = fea.check_prerequisites()
print("prereq:", msg)
fea.write_inp_file()
fea.ccx_run()
fea.load_results()
res = [o for o in doc.Objects if o.isDerivedFrom("Fem::FemResultObject")][0]
vm = res.vonMises
dz = res.DisplacementLengths
print("MAX_VM_MPa %.1f  MAX_DISP_mm %.3f" % (max(vm), max(dz)))
# 99.5th percentile (ignores single-node singularities)
s_ = sorted(vm)
print("P99.5_VM_MPa %.1f  P99_VM %.1f" % (s_[int(0.995 * len(s_))], s_[int(0.99 * len(s_))]))
fm = mesh.FemMesh
pts = [(fm.getNodeById(n), v) for n, v in zip(res.NodeNumbers, vm)]


def region(p):
    if p.z < -FLOOR + 0.2 and abs(p.y - W_IN / 2) < 7:
        return "support edge (boundary condition)"
    if p.z < tz0 + TIE_R_EXIT + 0.3 and (p.y < -WALL + TIE_R_EXIT + 0.5 or p.y > W_IN + WALL - TIE_R_EXIT - 0.5):
        return "tie bend radius (contact)"
    return "structure"


agg = {}
for p, v in pts:
    r = region(p)
    agg.setdefault(r, []).append(v)
for r, values in agg.items():
    values.sort()
    print("REG %-32s max %.1f  p99 %.1f MPa" % (r, values[-1], values[int(0.99 * len(values))]))
