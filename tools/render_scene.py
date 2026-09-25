"""Tessellates the render scenes into .npz files for render_raster.py.
Needs the macro in ../freecad and the .kicad_pcb in this folder. Run: freecadcmd render_scene.py"""
# ruff: noqa: F821, E402  (names and FreeCAD modules come from the macro exec'd below)
import os
import math
import re
os.environ["SMN_NO_EXPORT"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
exec(open(os.path.join(HERE, "..", "freecad", "SolarMeshtasticNodeMini_Enclosure.FCMacro"), encoding="utf-8").read(), globals())
KICAD_PCB = os.environ.get("KICAD_PCB", os.path.join(HERE, "SolarMeshtasticNodeMini.kicad_pcb"))
import numpy as np


def parse(txt):
    tok = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', txt)
    st = [[]]
    for t_ in tok:
        if t_ == '(':
            st.append([])
        elif t_ == ')':
            x_ = st.pop()
            st[-1].append(x_)
        else:
            st[-1].append(t_.strip('"') if t_.startswith('"') else t_)
    return st[0][0]


def sub(e, k): return [x_ for x_ in e if isinstance(x_, list) and x_ and x_[0] == k]


C = dict(
    base=(
        0.74, 0.77, 0.81), lid=(
            0.66, 0.69, 0.74), plate=(
                0.30, 0.31, 0.34), pcb=(
                    0.07, 0.40, 0.18), silver=(
                        0.82, 0.83, 0.86), beige=(
                            0.94, 0.91, 0.80), black=(
                                0.10, 0.10, 0.11), tan=(
                                    0.72, 0.56, 0.36), gold=(
                                        0.86, 0.68, 0.26), bat=(
                                            0.25, 0.50, 0.85), bat2=(
                                                0.85, 0.45, 0.20), pcm=(
                                                    0.85, 0.66, 0.18), red=(
                                                        0.80, 0.10, 0.08), cable=(
                                                            0.18, 0.18, 0.19), oring=(
                                                                0.92, 0.36, 0.18), steel=(
                                                                    0.62, 0.63, 0.66), white=(
                                                                        0.95, 0.95, 0.93), adapter=(
                                                                            0.93, 0.93, 0.90))
ZT = PCB_Z + PCB_T
def rot_dims(w, h, r): return (h, w) if abs(round(r)) % 180 == 90 else (w, h)


parts = []
def add(s, c): parts.append((s, c))


def cbox(x, y, w, h, z0, hz, col, r=0):
    ex, ey = kc(x, y)
    w, h = rot_dims(w, h, r)
    add(box(ex - w / 2, ey - h / 2, z0, w, h, hz), col)


t = parse(open(KICAD_PCB, encoding="utf-8").read())
for fp in sub(t, "footprint"):
    at = sub(fp, "at")[0]
    x, y = float(at[1]), float(at[2])
    r = float(at[3]) if len(at) > 3 else 0
    name = fp[1]

    def chip(w, h, hz, col, caps=True):
        cbox(x, y, w, h, ZT, hz, col, r)
        if caps:
            ww, hh = rot_dims(w, h, r)
            ex, ey = kc(x, y)
            if ww >= hh:
                for s_ in (-1, 1):
                    add(box(ex + s_ * ww / 2 - (0.4 if s_ > 0 else 0), ey - hh / 2, ZT, 0.4, hh, hz + 0.02), C["silver"])
            else:
                for s_ in (-1, 1):
                    add(box(ex - ww / 2, ey + s_ * hh / 2 - (0.4 if s_ > 0 else 0), ZT, ww, 0.4, hz + 0.02), C["silver"])
    if "R_0805" in name:
        chip(2.0, 1.25, 0.5, C["black"])
    elif "C_0805" in name:
        chip(2.0, 1.25, 1.0, C["tan"])
    elif "R_1206" in name or "C_1206" in name:
        chip(3.2, 1.6, 1.1, C["tan"])
    elif "SOT-23-6" in name or "SOT23-3" in name or "SOT-23-3" in name:
        chip(2.9, 1.6, 1.1, C["black"], False)
    elif "SON40" in name:
        chip(2.2, 2.0, 0.8, C["black"], False)
    elif "SMA_L4.3" in name or "D_SMA" in name:
        chip(4.3, 2.6, 2.2, C["black"])
    elif "HT-CT62" in name:
        a, b = kc(222.15, 37.77), kc(241.93, 56.55)
        add(box(min(a[0], b[0]) + 0.5, min(a[1], b[1]) + 0.5, ZT,
            abs(a[0] - b[0]) - 1, abs(a[1] - b[1]) - 1, 2.6), C["silver"])
        for (ux, uy) in ((224.6, 53.8), (239.9, 40.4)):
            e1, e2 = kc(ux, uy)
            add(cyl(e1, e2, ZT + 2.6, 1.3, 1.2), C["gold"])
    elif "B4B-PH" in name or "B2B-PH" in name:
        n = 4 if "B4B" in name else 2
        pads = sub(fp, "pad")
        xs, ys = [], []
        for p in pads:
            a_ = sub(p, "at")[0]
            px, py = float(a_[1]), float(a_[2])
            rr = math.radians(-r)
            xs.append(x + px * math.cos(rr) - py * math.sin(rr))
            ys.append(y + px * math.sin(rr) + py * math.cos(rr))
        cx_, cy_ = sum(xs) / len(xs), sum(ys) / len(ys)
        ex, ey = kc(cx_, cy_)
        ww, hh = rot_dims(2.0 * (n - 1) + 3.9, 4.5, r)
        add(box(ex - ww / 2, ey - hh / 2, ZT, ww, hh, 6.0).cut(box(ex - ww / 2 + \
            0.6, ey - hh / 2 + 0.6, ZT + 1.5, ww - 1.2, hh - 1.2, 5)), C["beige"])
    elif "SSSS811101" in name:
        ex, ey = kc(237.6, 34.7)
        add(box(ex - 3.4, ey - 1.4, ZT, 6.8, 2.8, 1.5), C["silver"])
        add(box(ex - 0.8, ey + 1.4, ZT + 0.3, 1.6, 1.5, 1.0), C["black"])
pcb_s = pcb

# ---- batteries, wires, SMA, antenna


def wire(pts, r, col):
    s = None
    for a, b in zip(pts[:-1], pts[1:]):
        a, b = V(*a), V(*b)
        d = b - a
        seg = Part.makeCylinder(r, d.Length, a, d).fuse(Part.makeSphere(r, b))
        s = seg if s is None else s.fuse(seg)
    return (s, col)


bx0, by0 = bat.BoundBox.XMin, bat.BoundBox.YMin
bat103 = [(box(bx0 + 4, by0, 0.2, bl3 - 4, bw3, bt3), C["bat"]), (box(bx0, by0 + 3, 2.0, 4.0, bw3 - 6, 5.5), C["pcm"])]
j4x, j4y = kc(219.3, 72.05)


def bat_wires(x_tab, yc, zc):
    return [wire([(x_tab +
    0.3, yc +
    dy, zc), (1.0, yc +
    dy, zc +
    1), (1.0 +
    dy, 16.0, 8.0), (5.0 +
    dy, 12.2, 10.0), (6.0 +
    dy, 9.0, 13.0), (21.0 +
    dy, 8.8, 14.0), (26.0 +
    dy, 9.2, 21.0), (j4x -
    2 +
    dy, j4y +
    2.5, 25.0), (j4x +
     dy, j4y, 24.0)], 0.5, col) for dy, col in ((0.0, C["red"]), (1.2, C["black"]))]


w103 = bat_wires(bx0, by0 + bw3 / 2, 5.0)
b2x0, b2y0 = bat2.BoundBox.XMin, bat2.BoundBox.YMin
bat852 = [(box(b2x0 + 4, b2y0, 1.4, bl - 4, bw, bt), C["bat2"]), (box(b2x0, b2y0 + 1, 3.0, 4.0, bw - 2, 4.5), C["pcm"])]
w852 = bat_wires(b2x0, b2y0 + bw / 2, 5.6)


def hexp(x0, x1, yc, zc, af, col):
    s = Part.makePolygon([V(0, af / math.sqrt(3) * math.cos(math.radians(a)), af / \
                         math.sqrt(3) * math.sin(math.radians(a))) for a in range(0, 361, 60)])
    f = Part.Face(s).extrude(V(x1 - x0, 0, 0))
    f.translate(V(x0, yc, zc))
    return (f, col)


sma = [(cyl(-8.0, SMA_Y, SMA_Z, 3.1, 16.0, V(1, 0, 0)), C["gold"]), (cyl(8.0, SMA_Y, SMA_Z, 2.4, SMA_NOSE - 8.0,
        V(1, 0, 0)), C["gold"]), hexp(0.2, 3.0, SMA_Y, SMA_Z, 8, C["gold"]), hexp(-6.2, -4.0, SMA_Y, SMA_Z, 8, C["gold"])]


def antenna(straight=False):
    a = [(cyl(-6.4, SMA_Y, SMA_Z, 9.0, 8.0, V(-1, 0, 0)), C["black"])]
    if straight:
        a += [(cyl(-14.4, SMA_Y, SMA_Z, 5.0, 90, V(-1, 0, 0)), C["black"]),
               (Part.makeCone(5.0, 2.5, 8, V(-104.4, SMA_Y, SMA_Z), V(-1, 0, 0)), C["black"])]
    else:
        a += [(Part.makeSphere(5.5, V(-19.5, SMA_Y, SMA_Z)), C["black"]),
              (cyl(-14.4, SMA_Y, SMA_Z, 4.0, 5.1, V(-1, 0, 0)), C["black"]),
              (cyl(-19.5, SMA_Y, SMA_Z, 5.0, 70), C["black"]),
              (Part.makeCone(5.0, 2.5, 8, V(-19.5, SMA_Y, SMA_Z + 70)), C["black"])]
    return a


ant = antenna()
pig = wire([(SMA_NOSE, SMA_Y, SMA_Z)] + PIGTAIL + [(ULX - 0.5, ULY + 0.2, 23.5), (ULX, ULY, ZT + 3.6)], 0.6, C["cable"])
# ---- 135 x 90 panel on the printed standoffs, vent plug, solar wires
PX0, PY0 = PANEL_X0, W_IN / 2 - PANEL_Y / 2
panel_s = [(box(PX0, PY0, panel_z0, PANEL_X, PANEL_Y, PANEL_T), (0.07, 0.10, 0.22))]
for i in range(1, 6):
    panel_s.append((box(PX0 + i * PANEL_X / 6 - 0.2, PY0 + 2, panel_z0 + PANEL_T, 0.4, PANEL_Y - 4, 0.05), C["silver"]))
for j in range(1, 4):
    panel_s.append((box(PX0 + 2, PY0 + j * PANEL_Y / 4 - 0.7, panel_z0 + PANEL_T, PANEL_X - 4, 1.4, 0.05), C["silver"]))
vo = L_IN + WALL
vent = [(cyl(vo, VENT_Y, VENT_Z, VENT_CAP_D /
    2 -
    1, 1.5, V(1, 0, 0)).fuse(cyl(vo +
    1.5, VENT_Y, VENT_Z, VENT_CAP_D /
    2 -
    2.5, 6.0, V(1, 0, 0))), (0.15, 0.15, 0.16)), (cyl(vo -
    VENT_THREAD, VENT_Y, VENT_Z, VENT_D /
    2 -
     0.3, VENT_THREAD, V(1, 0, 0)), (0.20, 0.20, 0.21))]
_nut = Part.Face(Part.makePolygon([V(L_IN - VENT_NUT_H,
    VENT_Y + VENT_NUT_D / 2 * math.cos(math.radians(a_)),
    VENT_Z + VENT_NUT_D / 2 * math.sin(math.radians(a_))) for a_ in range(0,
    361,
    60)])).extrude(V(VENT_NUT_H,
    0,
     0))
vent.append((_nut.cut(cyl(L_IN - VENT_NUT_H - 1, VENT_Y, VENT_Z, VENT_D / 2 - 0.3, VENT_NUT_H + 2, V(1, 0, 0))),
             (0.93, 0.93, 0.90)))
shx, shy = SOLAR_HOLE_XY
j2x, j2y = kc(241.75, 68.75)
sol = [wire([(shx + dx, shy, panel_z0 - 0.2), (shx + dx, shy, H_IN - CHIMNEY_L + 0.5), (j2x - 1 + dx * 0.3, j2y + \
            3, 25.0), (j2x + dx * 0.4, j2y, 24.0)], 0.5, col) for dx, col in ((-0.55, C["red"]), (0.55, C["black"]))]
sol_out = [wire([(shx + dx, shy, ltop + 0.2), (shx + dx, shy, panel_z0 - 0.2)], 0.5, col)
                for dx, col in ((-0.55, C["red"]), (0.55, C["black"]))]
glue = [(cyl(shx, shy, H_IN - CHIMNEY_L - 0.3, 1.55, 1.0), (0.95, 0.85, 0.35))]


def oring():
    rr = rbox(-WALL / 2, -WALL / 2, 0, L_IN + WALL, W_IN + WALL, 1, R_IN + WALL / 2)
    f = [f for f in rr.Faces if abs(f.Surface.Axis.z) > 0.9 and f.BoundBox.ZMax < 0.01][0]
    w = f.OuterWire
    e = [e for e in w.Edges if e.Curve.TypeId == "Part::GeomLine"][0]
    p0 = e.Vertexes[0].Point
    d = (e.Vertexes[1].Point - p0)
    d.normalize()
    s = w.makePipeShell([Part.Wire(Part.Circle(p0, d, 1.0).toShape())], True, True)
    s.translate(V(0, 0, H_IN - GROOVE_D + 1.0))
    return (s, C["oring"])


screws_s = [(sc, C["steel"]) for sc in screws]
# ---- ties on a trunk, stones, ground


def hull(pts):
    pts = sorted(set(pts))
    def cr(o, a, b): return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cr(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


TRUNK_R = 55.0
trunk_c = (W_IN / 2, -FLOOR - TRUNK_R)


def tie_band(tx, off):
    cs = [((-WALL + TIE_R_EXIT, tz0 - TIE_R_EXIT), TIE_R_EXIT + off),
           ((W_IN + WALL - TIE_R_EXIT, tz0 - TIE_R_EXIT), TIE_R_EXIT + off), (trunk_c, TRUNK_R + off)]
    pts = [(round(c[0] + r * math.cos(2 * math.pi * k / 180), 4), round(c[1] + r * math.sin(2 * math.pi * k / 180), 4))
            for c, r in cs for k in range(180)]
    h = hull(pts)
    return Part.Face(Part.makePolygon([V(tx - 2.5, y, z) for y, z in h] + [V(tx - 2.5, h[0][0], h[0][1])]))


ties = [(tie_band(tx, 1.5).cut(tie_band(tx, 0.0)).extrude(V(5, 0, 0)).fuse(
    box(tx - 4, trunk_c[0] - 4, trunk_c[1] - TRUNK_R - 7.5, 8, 8, 6)), C["black"]) for tx in TIE_X]
trunk = [(cyl(-45, trunk_c[0], trunk_c[1], TRUNK_R, 160, V(1, 0, 0)), (0.42, 0.30, 0.20))]


def stone(cx, cy_, cz, a, b, c):
    s = Part.makeSphere(1.0)
    m = App.Matrix()
    m.scale(a, b, c)
    s = s.transformGeometry(m)
    s.translate(V(cx, cy_, cz))
    return s


ground = [(box(-70, -80, -FLOOR - 3, 210, 215, 3), (0.55, 0.60, 0.45))]
stones = [(stone(30, -9.5 - 17.5, 6, 42, 18, 17), (0.50, 0.49, 0.47)),
           (stone(32, W_IN + 9.5 + 16.5, 4, 38, 17, 15), (0.58, 0.56, 0.53))]

inside = [(pcb_s, C["pcb"])] + parts + [pig] + sma + vent
inside103 = inside + bat103 + w103
inside852 = inside + [(adapter, C["adapter"])] + bat852 + w852
shell = [(base, C["base"]), (plate, C["plate"]), oring()]
lidp = [(lid, C["lid"])] + panel_s + sol_out


def tess(items, dz=0.0, cut=None):
    out = []
    for s, col in items:
        s = s.copy()
        if cut is not None:
            s = s.common(cut)
            if s.Volume < 1e-3:
                continue
        if dz:
            s.translate(V(0, 0, dz))
        pts, tri = s.tessellate(0.03)
        if not tri:
            continue
        P = np.array([[p.x, p.y, p.z] for p in pts])
        out.append((P[np.array(tri)], col))
    return out


def save(name, groups):
    d = {}
    for i, (tr, col) in enumerate(groups):
        d[f"t{i}"] = tr
        d[f"c{i}"] = np.array(col)
    np.savez_compressed(os.path.join(HERE, f"{name}.npz"), **d)
    print(name, len(groups), sum(len(g[0]) for g in groups))


def rotX2Z(items):
    out = []
    for sh, col in items:
        sh = sh.copy()
        sh.rotate(V(0, 0, 0), V(0, 1, 0), 90)
        out.append((sh, col))
    return out


cutS = box(-150, SMA_Y, -50, 400, 200, 300)
# --- tilted stand pose (rest angle from the geometry), with ground pegs and a ballast stone
import json as _json
_pose = _json.load(open(os.path.join(HERE, "pose.json"))) if os.path.exists(os.path.join(HERE, "pose.json")) else None


def tilt_scene(items, ant_len=300.0, stone=False):
    deg = LEG_ANGLE
    Rz = App.Rotation(V(1, 0, 0), deg)
    legs = [(leg.copy(), C["adapter"]) for _ in TIE_X]
    for (lg, _c), ax in zip(legs, TIE_X):
        lg.translate(V(ax - LEG_T / 2, 0, 0))
    out = []
    for sh, col in list(items) + legs:
        sh = sh.copy()
        sh.rotate(V(0, 0, 0), V(1, 0, 0), deg)
        out.append((sh, col))
    zmin = min(s_.BoundBox.ZMin for s_, _ in out)
    out = [(_shift(s_, -zmin), c) for s_, c in out]
    kn = Rz.multVec(V(-19.5, SMA_Y, SMA_Z))
    kx, ky, kz = kn.x, kn.y, kn.z - zmin
    out += [(Part.makeSphere(5.5, V(kx, ky, kz)), C["black"]), (cyl(kx, ky, kz, 5.0, ant_len), C["black"]),
            (Part.makeCone(5.0, 2.5, 8, V(kx, ky, kz + ant_len)), C["black"])]
    th_ = math.radians(LEG_ANGLE)
    for ax in TIE_X:                                         # pegs through the eyelets in the leg feet
        y_f = LEG_FOOT_Y + LEG_FOOT_L / 2
        zg = -FLOOR - (y_f - (-(WALL + EAR_L) - LEG_HEEL)) * math.tan(th_)
        pt = Rz.multVec(V(ax, y_f, zg))
        out.append((cyl(pt.x, pt.y, pt.z - zmin - 45, 2.4, 62), (0.45, 0.45, 0.48)))
        out.append((cyl(pt.x, pt.y, pt.z - zmin + 17, 4.5, 3), (0.45, 0.45, 0.48)))
    if stone:                                                # optional ballast, always behind the panel
        st = Part.makeSphere(1.0)
        m = App.Matrix()
        m.scale(42, 30, 22)
        st = st.transformGeometry(m)
        pr = Rz.multVec(V(L_IN / 2, LEG_FOOT_Y + 20, -FLOOR))
        st.translate(V(pr.x, pr.y + 10, 21))
        out.append((st, (0.52, 0.51, 0.49)))
    out.append((box(-80, -140, -3, 240, 300, 3), (0.55, 0.60, 0.45)))
    return out


def _shift(sh, dz):
    sh = sh.copy()
    sh.translate(V(0, 0, dz))
    return sh


# A exploded, B section through the vent, C top view, D battery, E 852040 adapter, F tree, G stones,
# H bottom, I/J tilted on the legs, K plain assembly
save("viewA", tess(shell + inside103 + ant) + tess(lidp, 55) + tess(screws_s, -40))
save("viewB", tess(shell + inside103 + sol + glue + lidp + screws_s + ant, cut=box(-150, VENT_Y, -80, 400, 200, 300)))
save("viewC", tess(shell + inside103 + sol + glue + ant))
save("viewD", tess([(base, C["base"]), oring()] + bat103 + sma + vent + ant) + \
     tess([(plate, C["plate"]), (pcb_s, C["pcb"])] + parts, 34))
save("viewE", tess([(base, C["base"]), oring()] + inside852 + ant, cut=box(-150, 30.0, -50, 400, 200, 300)) + \
     tess([(plate, C["plate"])], 0, cut=box(-150, 30.0, -50, 400, 200, 300)))
save("viewF", tess(rotX2Z(shell + inside103 + lidp + screws_s + antenna(True) + ties + trunk)))
save("viewG", tess(shell + inside103 + lidp + screws_s + ant + stones + ground))
save("viewI", tess(tilt_scene(shell + inside103 + lidp + screws_s + sma, 300.0)))
save("viewJ", tess(tilt_scene(shell + inside103 + lidp + screws_s + sma, 300.0)))   # same scene, other camera
save("viewK", tess(shell + inside103 + lidp + screws_s + ant))   # plain assembly
save("viewH", tess(shell + lidp + screws_s + ant + [(sma[0][0], C["gold"])]))
