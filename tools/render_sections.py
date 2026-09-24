"""Draws docs/validation_sections.png from sections.json. sections_export.py writes that file.

    freecadcmd sections_export.py      # from tools/, needs the macro and writes sections.json
    python3 render_sections.py         # host python: matplotlib only, no CAD

Both steps are necessary. The image is a claim about the model, so you must regenerate it whenever the
macro changes. sections.json is an intermediate and is not committed.
"""

import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "docs", "validation_sections.png")
# One color per section tag. The panels compare the printed part against these sections.
COLOR = {
    "base": "black",
    "lid": "steelblue",
    "nut": "orange",
    "plug": "tomato",
    "leg": "brown",
    "pcb": "grey",
    "parts": "green",
}
PANELS = [
    # name, x label, y label, title, x limits, y limits. The crops frame the feature in the title. An
    # uncropped panel shows the whole box, where a 0.4 mm lead-in is invisible
    ("vent_xz", "x", "z", "Vent axis y=25: base, lid, nut, plug", (48, 96), (-2, 34)),
    ("rim_xz", "x", "z", "Rim and O-ring groove", (-8, 4), (23, 33)),
    ("column_xz", "x", "z", "Screw column, captive neck", (-11, 7), (-11, 41)),
    ("tie_yz", "y", "z", "Leg in the tunnel: tongue, snap barb, heel rail", (-60, 100), (-26, 26)),
    ("sma_xz", "x", "z", "SMA axis", (-20, 80), (0, 31)),
    ("floor_xy", "x", "y", "Floor level: lashing tunnels", (-10, 85), (-15, 62)),
]

with open(os.path.join(HERE, "sections.json")) as fh:
    sec = json.load(fh)
fig = plt.figure(figsize=(19, 11), dpi=90)
for i, (name, ax1, ax2, title, xlim, ylim) in enumerate(PANELS):
    ax = fig.add_subplot(2, 3, i + 1)
    for tag, pts in sec[name]:
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=COLOR.get(tag, "magenta"), lw=1.0)
    ax.set_title(title)
    ax.set_xlabel(ax1)
    ax.set_ylabel(ax2)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal")
    ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(OUT)
print("wrote", OUT, [f"{n}:{len(sec[n])} segs" for n, *_ in PANELS])
