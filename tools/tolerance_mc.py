"""Monte Carlo study of every fit that has to go together.

The model treats a printed feature as N(nominal, 0.3 / 3). JLC3DP holds +-0.3 mm on features below
100 mm for SLS and MJF PA12, taken as three sigma. The model treats a bought part as
N(nominal, catalogue / 3). The tool takes 20000 samples per fit, and a fit passes when the chance of
failure is below 0.1 percent.

The tool reads every nominal from the macro, so a change to the case moves the study with it.

Run with: freecadcmd tolerance_mc.py
"""

# ruff: noqa: F821, E402  (names and FreeCAD modules come from the macro exec'd below)
import json
import os

import numpy as np

os.environ["SMN_NO_EXPORT"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
exec(
    open(os.path.join(HERE, "..", "freecad", "SolarMeshtasticNodeMini_Enclosure.FCMacro"), encoding="utf-8").read(),
    globals(),
)

N = 20000
SIGMA = 0.30 / 3.0  # printed, +-3 sigma
rng = np.random.default_rng(7)


def printed(nominal):
    return rng.normal(nominal, SIGMA, N)


def bought(nominal, tol):
    return rng.normal(nominal, tol / 3.0, N)


_, fy = kc(0, 77.0)
_, by_ = kc(0, 30.0)
POCKET_W = POCKET_Y1 - POCKET_Y0
RIB_GAP = (by_ + PCB_CLR) - (fy - PCB_CLR)

# Each entry is a name, the sampled clearance where a positive value means the parts go together,
# the failure modes, and what a failure means. A hard mode is a real functional failure. The tool
# reports a soft mode as a trend, because the part is not scrap yet.
LIP_Y = by_ - LIP_OVER  # inner face of the PCB hold-down lips, the tightest thing over the pocket
BAT_103450_Y1 = POCKET_Y0 + 0.5 + BAT_103450[1]
AD_Y1 = POCKET_Y0 + 0.4 + (POCKET_Y1 - POCKET_Y0 - 1.5)
FITS = [
    (
        "lid skirt in the cavity, total",
        printed(W_IN) - printed(W_IN - 2 * SK),
        [("skirt jams, the O-ring never touches", lambda c: c <= 0, True)],
        "0.7 mm per side, the tighter of the two axes",
    ),
    (
        "PCB 33 x 47 between the ribs, total",
        printed(RIB_GAP) - bought(PCB_L, 0.15),
        [("board does not drop in", lambda c: c <= 0, True)],
        "0.8 mm nominal, bought part",
    ),
    (
        "LiPo 103450 in the pocket, total",
        printed(POCKET_W) - bought(BAT_103450[1], 0.5),
        [("cell does not drop in", lambda c: c <= 0, True)],
        "1.5 mm nominal, the cell is the loose part",
    ),
    (
        "LiPo 852040 in the adapter tray, total",
        printed(BAT_852040[1] + 1.0) - bought(BAT_852040[1], 0.5),
        [("cell does not drop in", lambda c: c <= 0, True)],
        "1.0 mm nominal",
    ),
    (
        "adapter tray in the pocket, y",
        printed(POCKET_W) - printed(POCKET_W - 0.8),
        [("tray does not drop in", lambda c: c <= 0, True)],
        "printed against printed",
    ),
    (
        "adapter tray past the PCB hold-down lip",
        printed(LIP_Y) - printed(AD_Y1),
        [("tray fouls the lip on the way in", lambda c: c <= 0, True)],
        "The lips start at y 48.3. The tray reaches 47.4 mm. The montage walks the same travel.",
    ),
    (
        "LiPo 103450 past the PCB hold-down lip",
        printed(LIP_Y) - bought(BAT_103450_Y1, 0.5),
        [("cell fouls the lip on the way in", lambda c: c <= 0, True)],
        "the cell sits 0.5 off the front wall so it clears the lip by 0.8",
    ),
    (
        "battery plate past the PCB hold-down lip",
        printed(LIP_Y) - printed(PLATE_Y1),
        [("plate fouls the lip on the way in", lambda c: c <= 0, True)],
        "the plate stops 0.6 short of the lips, so it drops straight in",
    ),
    (
        "PCB under the hold-down lip",
        printed(lip_z) - PCB_Z - bought(PCB_T, 0.2),
        [("board is too thick to pass the lip", lambda c: c <= 0, True)],
        "0.5 mm over a 1.6 mm board: the first 0.15 sat inside the board's own thickness tolerance",
    ),
    (
        "leg crossing section, vertical in the tunnel",
        printed(TIE_H - (TIE_H - 0.6)),
        [("leg binds in the tunnel", lambda c: c <= 0, True)],
        "a removable leg is a moving part, so 0.6 mm total, 0.3 a side",
    ),
    (
        "M3 through the base column",
        printed(SCREW_D) - bought(3.0, 0.05),
        [("screw does not pass", lambda c: c <= 0, True)],
        "generous bore, also the powder escape path",
    ),
    (
        "SMA bulkhead 6.35 shank in the wall",
        printed(SMA_D) - bought(6.35, 0.05),
        [("bulkhead does not pass", lambda c: c <= 0, True)],
        "opened from 6.7 to 6.9 after the first study",
    ),
    (
        "ePTFE vent thread 12 through the wall",
        printed(VENT_D) - bought(12.0, 0.1),
        [("plug does not pass", lambda c: c <= 0, True)],
        "",
    ),
    (
        "cable tie 5 x 1.5 in the Y tunnel",
        printed(TIE_W) - bought(5.0, 0.1),
        [("tie does not pass", lambda c: c <= 0, True)],
        "",
    ),
    (
        "leg tongue in the Y tunnel",
        printed(TIE_W) - printed(LEG_T - 1.0),
        [("tongue does not pass", lambda c: c <= 0, True)],
        "1.0 mm total, printed against printed",
    ),
    (
        "ballast tray channel over the heel rail",
        printed(BALLAST_SLOT * 2) - printed(0.0),
        [("tray does not slide on", lambda c: c <= 0, True)],
        "0.6 mm per side",
    ),
    (
        "peg 5 mm in the eyelets",
        printed(PEG_EYE_D) - bought(PEG_MAX, 0.1),
        [("peg does not start in the eyelet", lambda c: c <= 0, True)],
        (
            "the foot eyelet and the ballast tray pin bore are the same PEG_EYE_D, and the peg has to "
            "reach the rail notch behind them. A bought wire stake, so 0.3 mm a side like the SMA and "
            "the vent. At the first build's 5.0 bore this fit read a 50 % hard failure, which is what "
            "no peg would go in means."
        ),
    ),
    (
        "M3 heat set insert, lid column",
        printed(INSERT_D) - bought(4.6, 0.05),
        [("bore is over the insert, nothing melts in to grip", lambda c: c >= 0, False)],
        (
            "the makers all specify a 4.0 bore in plastic for a 4.6 knurl (Ruthex M3x5.7, JLC DPLK-M3). "
            "The bore spread does not decide this fit: the iron reflows the plastic, so what matters is "
            "the 2.0 mm of boss left around it and the 7.0 mm depth against a 5.7 mm insert. Both are "
            "checked in design_rules.py, and a loose one is one drop of epoxy."
        ),
    ),
    (
        "M3 captive neck",
        printed(SCREW_CAPTIVE_D) - bought(2.93, 0.02),
        [
            ("screw is no longer captive, it pushes straight through", lambda c: c >= 0, False),
            ("cannot be pressed in by hand", lambda c: c <= -0.55, True),
        ],
        "a deliberate press fit: the screw goes through once and then turns freely",
    ),
    (
        "M2.5 pilot in the PA boss",
        printed(M25_PILOT) - bought(2.45, 0.03),
        [("pilot is at or over the major diameter, the screw cannot bite", lambda c: c >= 0, True)],
        (
            "thread forming: a 2.1 pilot for a 2.45 screw leaves 0.35 to cut into, and the boss wall is "
            "1.85 mm against a 1.5 mm rule of thumb, so splitting is not the binding mode"
        ),
    ),
]

print(f"{N} samples per fit, printed +-{SIGMA * 3:.2f} mm at 3 sigma, all values in mm")
print(f"{'fit':44} {'mean':>7} {'0.1 %':>8} {'99.9 %':>8} {'fail %':>8}  verdict   mode")
print("-" * 104)
rows, bad, watch = [], [], []
for name, c, modes, note in FITS:
    worst_mode, worst_p, worst_hard = "", 0.0, False
    found = []
    for label, fails, hard in modes:
        p = float(np.mean(fails(c))) * 100.0
        found.append({"mode": label, "percent": round(p, 4), "hard": hard})
        if p > worst_p and (hard or not worst_hard):
            worst_mode, worst_p, worst_hard = label, p, hard
    over = [f for f in found if f["hard"] and f["percent"] >= 0.1]
    soft = [f for f in found if not f["hard"] and f["percent"] >= 0.1]
    verdict = "OVER" if over else ("watch" if soft else "ok")
    if over:
        bad.append(name)
    elif soft:
        watch.append(name)
    print(
        f"{name:44} {c.mean():7.2f} {np.percentile(c, 0.1):8.2f} {np.percentile(c, 99.9):8.2f} "
        f"{worst_p:8.3f}  {verdict:8}  {worst_mode}"
    )
    rows.append(
        {
            "fit": name,
            "mean_mm": round(float(c.mean()), 3),
            "p0_1_mm": round(float(np.percentile(c, 0.1)), 3),
            "p99_9_mm": round(float(np.percentile(c, 99.9)), 3),
            "limit_percent": 0.1,
            "modes": found,
            "verdict": verdict,
            "note": note,
        }
    )
    if over:
        for f in over:
            print(f"{'':44} {f['percent']:8.3f} %  {f['mode']}")

# The O-ring is not a clearance, so what matters is the squeeze on the cord.
cord_d = 2.0
compression = (bought(cord_d, 0.08) - printed(GROOVE_D)) / bought(cord_d, 0.08)
lo = float(np.mean(compression < 0.09)) * 100.0
hi = float(np.mean(compression > 0.41)) * 100.0
print(
    f"\nO-ring cord {cord_d:.1f} mm in a {GROOVE_D:.1f} mm deep groove: compression mean "
    f"{compression.mean() * 100:.0f} %, 0.1 % {np.percentile(compression, 0.1) * 100:.0f} %, "
    f"99.9 % {np.percentile(compression, 99.9) * 100:.0f} %"
)
print(f"outside the 9-41 % band the playbook quotes: {lo:.3f} % too little, {hi:.3f} % too much")

print()
if bad:
    print(f"{len(bad)} fit(s) over the 0.1 % limit: " + ", ".join(bad))
else:
    print(f"all {len(FITS)} fits are under the 0.1 % limit for a hard failure")
for w in watch:
    print(f"  watch, {w}: the loose tail is over 0.1 %")
# An independent implementation of the same two numbers, which checks the numpy arithmetic.
try:
    import mcerp

    mcerp.npts = N
    CHECK = [
        (
            "battery plate past the PCB hold-down lip",
            "plate fouls the lip on the way in",
            LIP_Y,
            SIGMA,
            PLATE_Y1,
            SIGMA,
            0.0,
            "le",
        ),
        (
            "M2.5 pilot in the PA boss",
            "pilot is at or over the major diameter, the screw cannot bite",
            M25_PILOT,
            SIGMA,
            2.45,
            0.03 / 3.0,
            0.0,
            "ge",
        ),
    ]
    print("\ncross-check with mcerp, same nominals, sigmas and threshold:")
    for name, mode, m1, s1, m2, s2, thr, kind in CHECK:
        c = mcerp.N(m1, s1) - mcerp.N(m2, s2)
        hit = np.mean(c._mcpts <= thr) if kind == "le" else np.mean(c._mcpts >= thr)
        modes = next(r["modes"] for r in rows if r["fit"] == name)
        mine = next(f["percent"] for f in modes if f["mode"] == mode)
        print(f"  {name:44} mcerp {float(hit) * 100:7.3f} %   numpy {mine:7.3f} %   {mode}")
except ImportError:
    print("\nmcerp is not installed, so the tool skips the cross-check. Run pip install mcerp for it.")

json.dump(
    {
        "tool": "tolerance_mc.py",
        "samples_per_fit": N,
        "printed_sigma_mm": SIGMA,
        "limit_percent": 0.1,
        "fits": rows,
        "failures": bad,
        "watch": watch,
        "oring": {
            "compression_mean": round(float(compression.mean()), 4),
            "too_little_percent": round(lo, 4),
            "too_much_percent": round(hi, 4),
        },
    },
    open(os.path.join(HERE, "tolerance_report.json"), "w"),
    indent=1,
)
print("wrote tolerance_report.json")
