"""Wind load on the antenna, stress around the SMA hole (CalculiX).
The antenna is a stub bonded to the wall through flange and nut; the wind force acts on the stub.
V_WIND [m/s] and L_ANT [mm] can be set as environment variables."""
# ruff: noqa: F821, E402  (names and FreeCAD modules come from the macro exec'd below)
import os
os.environ["SMN_NO_EXPORT"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
exec(open(os.path.join(HERE, "..", "freecad", "SolarMeshtasticNodeMini_Enclosure.FCMacro"), encoding="utf-8").read(), globals())
import ObjectsFem
import FreeCAD as App
from femtools import ccxtools
from femmesh.gmshtools import GmshTools
V_WIND = float(os.environ.get("V_WIND", "45"))
L_ANT = float(os.environ.get("L_ANT", "300")) / 1000.0
D_ANT = 0.016
CD = 1.1
q = 0.5 * 1.25 * V_WIND**2
F = q * CD * L_ANT * D_ANT
print(f"wind {V_WIND} m/s, antenna {L_ANT *
    1000:.0f} mm x {D_ANT *
    1000:.0f} mm -> F = {F:.1f} N, M at the wall = {F *
    (L_ANT /
    2 +
    0.02) *
     1000:.0f} Nmm")
# antenna stub: whip (vertical, hinge at x=-19.5) reduced to a straight cantilever for the load path
sl = base.common(box(-40, -20, -FLOOR - 5, 70, W_IN + 40, FLOOR + H_IN + 10))   # left part of the base
stub = cyl(-WALL - 2.0, SMA_Y, SMA_Z, 8.0, 14.0, V(-1, 0, 0))                  # connector + hinge body
stub = stub.fuse(cyl(-16.0, SMA_Y, SMA_Z, D_ANT * 1000 / 2, L_ANT * 1000))       # whip, standing up
sl = sl.fuse(cyl(-18.0, SMA_Y, SMA_Z, 3.6, 24.0, V(1, 0, 0)))                  # bulkhead shank through the wall
sl = sl.fuse(cyl(-WALL, SMA_Y, SMA_Z, 8.0, 2.0, V(-1, 0, 0)))                  # flange on the outer wall face
sl = sl.fuse(cyl(0.0, SMA_Y, SMA_Z, 5.0, 3.0, V(1, 0, 0)))                     # nut on the inner wall face
sl = sl.fuse(stub).removeSplitter()
print("solids in the model:", len(sl.Solids))
sl = sl.removeSplitter()
print("valid", sl.isValid(), "type", sl.ShapeType, "solids", len(sl.Solids), "shells", len(sl.Shells))
if len(sl.Solids) == 1:
    sl = sl.Solids[0]
doc = App.newDocument("fem")
part = doc.addObject("Part::Feature", "Slice")
part.Shape = sl
fix = []
load = []
for i, f in enumerate(sl.Faces):
    c = f.CenterOfMass
    if f.Surface.TypeId == "Part::GeomPlane" and (abs(c.z + FLOOR) < 1e-3 or abs(c.x - 30.0) < 1e-3):
        fix.append(f"Face{i + 1}")
    if f.Surface.TypeId == "Part::GeomCylinder" and abs(f.Surface.Radius - D_ANT * 1000 / 2) < 1e-3:
        load.append(f"Face{i + 1}")
print("fixed faces", len(fix), "loaded faces", len(load))
an = ObjectsFem.makeAnalysis(doc, "A")
solver = ObjectsFem.makeSolverCalculiXCcxTools(doc)
an.addObject(solver)
solver.WorkingDir = os.path.join(HERE, "femrun2")
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
fc.Force = f"{F:.3f} N"
fc.DirectionVector = App.Vector(0, 1, 0)
fc.Reversed = False
an.addObject(fc)
mesh = ObjectsFem.makeMeshGmsh(doc, "Mesh")
mesh.Shape = part
mesh.CharacteristicLengthMax = "2.5 mm"
mesh.CharacteristicLengthMin = "1.0 mm"
mesh.ElementOrder = "1st"
an.addObject(mesh)
g = GmshTools(mesh)
g.create_mesh()
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
vm = res.vonMises
disp = res.DisplacementLengths
fm = mesh.FemMesh
wall = [v for n, v in zip(res.NodeNumbers, vm) if fm.getNodeById(n).x < WALL + 6 and fm.getNodeById(n).x > -WALL - 1]
wall.sort()
print(f"MAX_VM {max(vm):.1f} MPa, tip deflection {max(disp):.1f} mm")
print(f"wall around the SMA: max {wall[-1]:.1f} MPa, p99 {wall[int(0.99 * len(wall))]:.1f} MPa")
