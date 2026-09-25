import numpy as np
import sys
import math
import time
from PIL import Image, ImageFilter


def render(npz, az, el, W=1500, H=1100, SS=2, pad=0.05, fname="out.png"):
    d = np.load(npz)
    n = len([k for k in d.files if k.startswith("t")])
    groups = [(d[f"t{i}"].astype(np.float64), d[f"c{i}"]) for i in range(n)]
    a, e = math.radians(az), math.radians(el)
    cam = np.array([math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)])
    up0 = np.array([0, 0, 1.0]) if abs(el) < 89 else np.array([0, 1.0, 0])
    r = np.cross(-cam, up0)
    r /= np.linalg.norm(r)
    u = np.cross(r, -cam)
    M = np.stack([r, u, cam])
    allp = np.vstack([g[0].reshape(-1, 3) for g in groups]) @ M.T
    mn, mx = allp.min(0), allp.max(0)
    w, h = W * SS, H * SS
    s = min(w * (1 - 2 * pad) / (mx[0] - mn[0]), h * (1 - 2 * pad) / (mx[1] - mn[1]))
    ox = w / 2 - s * (mn[0] + mx[0]) / 2
    oy = h / 2 + s * (mn[1] + mx[1]) / 2
    zb = np.full((h, w), -1e9)
    col = np.ones((h, w, 3))
    idb = np.full((h, w), -1, np.int32)
    nb = np.zeros((h, w, 3))
    L1 = np.array([-0.35, -0.5, 0.8])
    L1 /= np.linalg.norm(L1)
    L1v = M @ L1
    L2v = np.array([0.6, 0.3, 0.75])
    L2v /= np.linalg.norm(L2v)
    for gi, (T, c) in enumerate(groups):
        P = T @ M.T                                   # view coords
        nrm = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
        ln = np.linalg.norm(nrm, axis=1)
        ok = ln > 1e-12
        P, nrm = P[ok], nrm[ok] / ln[ok, None]
        nrm[nrm[:, 2] < 0] *= -1
        dif = 0.28 + 0.55 * np.clip(nrm @ L1v, 0, 1) + 0.22 * np.clip(nrm @ L2v, 0, 1)
        Hh = (L1v + np.array([0, 0, 1.0]))
        Hh /= np.linalg.norm(Hh)
        spec = 0.22 * np.clip(nrm @ Hh, 0, 1)**40
        shade = np.clip(np.outer(dif, c) + spec[:, None], 0, 1)
        X = ox + s * P[:, :, 0]
        Y = oy - s * P[:, :, 1]
        Z = P[:, :, 2]
        for k in range(len(P)):
            x0, x1, x2 = X[k]
            y0, y1, y2 = Y[k]
            xmin = max(int(math.floor(min(x0, x1, x2))), 0)
            xmax = min(int(math.ceil(max(x0, x1, x2))), w - 1)
            ymin = max(int(math.floor(min(y0, y1, y2))), 0)
            ymax = min(int(math.ceil(max(y0, y1, y2))), h - 1)
            if xmax < xmin or ymax < ymin:
                continue
            den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
            if abs(den) < 1e-9:
                continue
            xs = np.arange(xmin, xmax + 1) + 0.5
            ys = np.arange(ymin, ymax + 1) + 0.5
            gx, gy = np.meshgrid(xs, ys)
            l0 = ((y1 - y2) * (gx - x2) + (x2 - x1) * (gy - y2)) / den
            l1 = ((y2 - y0) * (gx - x2) + (x0 - x2) * (gy - y2)) / den
            l2 = 1 - l0 - l1
            m = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
            if not m.any():
                continue
            z = l0 * Z[k, 0] + l1 * Z[k, 1] + l2 * Z[k, 2]
            sub = zb[ymin:ymax + 1, xmin:xmax + 1]
            upd = m & (z > sub)
            if not upd.any():
                continue
            sub[upd] = z[upd]
            col[ymin:ymax + 1, xmin:xmax + 1][upd] = shade[k]
            idb[ymin:ymax + 1, xmin:xmax + 1][upd] = gi
            nb[ymin:ymax + 1, xmin:xmax + 1][upd] = nrm[k]
    # Kanten
    edge = np.zeros((h, w), bool)
    for dy, dx in ((0, 1), (1, 0)):
        a_ = idb[:h - dy, :w - dx]
        b_ = idb[dy:, dx:]
        e1 = (a_ != b_)
        nd = (nb[:h - dy, :w - dx] * nb[dy:, dx:]).sum(-1) < 0.75
        zd = np.abs(zb[:h - dy, :w - dx] - zb[dy:, dx:]) > 1.2
        ee = e1 | ((a_ >= 0) & nd) | ((a_ >= 0) & (b_ >= 0) & zd)
        edge[:h - dy, :w - dx] |= ee
    edge = np.array(Image.fromarray(edge.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(3))) > 0 if SS > 1 else edge
    bg = (idb < 0)
    # Hintergrund: leichter Verlauf
    grad = np.linspace(0.97, 0.88, h)[:, None, None] * np.ones((1, w, 3))
    col[bg] = grad[bg]
    col[edge] = col[edge] * 0.25
    img = Image.fromarray((col * 255).astype(np.uint8)).resize((W, H), Image.LANCZOS)
    img.save(fname)
    return img


if __name__ == "__main__":
    t = time.time()
    render(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), fname=sys.argv[4])
    print("t", time.time() - t)
