"""Steady-state thermal study of the closed case in the sun, with a lumped model.

The model has two nodes and the panel. The panel is a flat plate that sits 8 mm off the lid. It takes
the sun, loses part of that heat upward, and pushes the rest across the gap into the lid. The case
shell takes the remaining sun on its sides and loses heat to the air and to the sky. The shell passes
the rest to the internal air, which also takes the electronics dissipation.

    T_case = T_amb + (Q_solar + P_int) / (h_out * A_sb + A_top * U_gap)
    T_air  = T_case + P_int / (h_in * A_in)

A_in is the inner wetted area. U_gap = h_gap * h_out / (h_gap + h_out) describes the panel, air and
case sandwich. Q_solar = A_sun * alpha_case * G + A_top * h_gap * alpha_panel * G / (h_gap + h_out).

h_out carries convection and radiation against a sky at 20 C, and it sets the temperature of a small
dark box in full sun. The model is rough. The fraction of the shell that sees sun and the coupling
inside the cavity are the two uncertainties that matter, so the model sweeps both.

Two lumped nodes and one internal coupling constant are the whole model. The sweep brackets the
answer, so the decision this model drives does not depend on the exact value. That decision is
whether to shade the case or to change its color. The upgrade path is CFD, as OpenFOAM conjugate heat
transfer, or a thermocouple inside the first print.

Run with: freecadcmd thermal_lumped.py
"""

# ruff: noqa: F821, E402  (geometry comes from the macro exec'd below)
import json
import os

os.environ["SMN_NO_EXPORT"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
exec(
    open(os.path.join(HERE, "..", "freecad", "SolarMeshtasticNodeMini_Enclosure.FCMacro"), encoding="utf-8").read(),
    globals(),
)

# The geometry comes straight out of the macro, so a change to the case moves this model with it.
L, W, H = (L_IN + 2 * WALL) / 1000, (W_IN + 2 * WALL) / 1000, (FLOOR + H_IN + LID_T) / 1000
A_TOP = L * W
A_SIDE = 2 * (L + W) * H
A_BOT = L * W
# The surfaces that can see the sun or the sky. The panel shades the top, so the top does not count.
A_SB = A_SIDE + A_BOT
A_IN = (2 * L_IN * W_IN + 2 * (L_IN + W_IN) * H_IN) / 1e6
A_PANEL = PANEL_X * PANEL_Y / 1e6
V_IN_L = L_IN * W_IN * H_IN / 1e6

K_PA12 = 0.25  # W/m/K, SLS PA12
WALL_M = WALL / 1000
EPS = 0.9
SIGMA = 5.67e-8
SKY_C = 20.0  # The effective sky temperature for the radiative term, in C.
H_IN_CONV = 3.0  # W/m2K from the internal air to the wall. The sensitivity block sweeps it.
H_GAP = 7.0  # W/m2K across the 8 mm panel gap, by convection and through the open edges
# The fraction of the incident light that the panel turns into heat. The rest leaves as electricity or
# as reflection.
ALPHA_PANEL = 0.60
CASES = [
    ("bright nylon, shaded or diffuse light", 150.0, 0.40, 1.0),
    ("bright nylon, full sun", 1000.0, 0.40, 0.5),
    ("black nylon, full sun", 1000.0, 0.90, 0.5),
]
T_AMB = float(os.environ.get("T_AMB", "40"))  # Air temperature in C. A hot summer day.
V_WIND = float(os.environ.get("V_WIND", "1.0"))  # m/s. Barely any breeze.
P_AVG = 0.3  # W. The ESP32 and the LoRa radio at a typical duty cycle.
P_TX = 1.3  # W. A burst from the radio.


def h_out(T_s, v):
    """Convection and linearized radiation against the sky, in W/m2K."""
    T = T_s + 273.15
    T_sky = SKY_C + 273.15
    h_rad = EPS * SIGMA * (T**4 - T_sky**4) / max(T - T_sky, 1e-6)
    return 5.7 + 3.8 * v + h_rad


def solve(G, alpha_case, sun_frac, P_int, T_amb=T_AMB, v=V_WIND, h_in=H_IN_CONV):
    A_sun = sun_frac * A_SB
    T_s = T_amb
    T_air = T_amb + P_int / (h_in * A_IN)
    # h_out depends on the surface temperature and h_in depends on the internal rise, so the loop
    # iterates both
    for _ in range(80):
        ho = h_out(T_s, v)
        U_gap = H_GAP * ho / (H_GAP + ho)
        q_solar = A_sun * alpha_case * G + A_TOP * H_GAP * ALPHA_PANEL * G / (H_GAP + ho)
        G_case = ho * A_SB + A_TOP * U_gap
        new_s = T_amb + (q_solar + P_int) / G_case
        # Natural convection in a small cavity. h rises with the temperature gradient, and the
        # reference is 3 W/m2K at a 10 K rise.
        h_eff = h_in * max(1.0, (max(T_air - new_s, 0.0) / 10.0) ** 0.25)
        new_air = new_s + P_int / (h_eff * A_IN)
        if abs(new_s - T_s) < 1e-7 and abs(new_air - T_air) < 1e-7:
            T_s, T_air = new_s, new_air
            break
        T_s, T_air = new_s, new_air
    ho = h_out(T_s, v)
    T_panel = (ALPHA_PANEL * G + H_GAP * T_s + ho * T_amb) / (H_GAP + ho)
    return {
        "case": T_s,
        "air": T_air,
        "panel": T_panel,
        "q_solar": A_sun * alpha_case * G + A_TOP * H_GAP * ALPHA_PANEL * G / (H_GAP + ho),
        "q_int": P_int,
        "h_out": ho,
        "h_in_eff": h_in * max(1.0, (max(T_air - T_s, 0.0) / 10.0) ** 0.25),
        "r_wall_k_per_w": WALL_M / (K_PA12 * A_IN),
    }


print(
    f"case {L * 1000:.1f} x {W * 1000:.1f} x {H * 1000:.1f} mm, shell {A_SB:.4f} m2, "
    f"top {A_TOP:.4f} m2, inner {A_IN:.4f} m2, cavity {V_IN_L * 1000:.0f} ml"
)
print(
    f"panel {PANEL_X:.0f} x {PANEL_Y:.0f} = {A_PANEL:.4f} m2 over a {STANDOFF_H:.0f} mm gap, "
    f"{ALPHA_PANEL:.0%} of the light ends up as heat"
)
print(f"ambient {T_AMB:.0f} C, wind {V_WIND:.1f} m/s, PA12 k {K_PA12} W/m/K, wall {WALL:.1f} mm\n")
print(f"{'case':36} {'T air':>7} {'T case':>7} {'T panel':>8} {'Q solar':>8} {'h out':>6}  verdict")
print("-" * 110)
out = []
bad = 0
for name, G, alpha, sun in CASES:
    for tag, P in (("avg", P_AVG), ("1.3 W continuous TX, fault case", P_TX)):
        r = solve(G, alpha, sun, P)
        hot_lipo = r["air"] > 45.0
        hot_elec = r["air"] > 85.0
        bad += 1 if hot_lipo else 0
        v = "LiPo over 45 C" if hot_lipo else "within the LiPo corridor"
        v = "ELECTRONICS OVER 85 C" if hot_elec else v
        print(
            f"{name + ', ' + tag:50} {r['air']:6.1f}C {r['case']:6.1f}C {r['panel']:7.1f}C "
            f"{r['q_solar']:7.2f}W {r['h_out']:5.1f}  {v}"
        )
        out.append(
            {
                "scenario": name,
                "duty": tag,
                "P_int_w": P,
                "G_w_m2": G,
                "alpha_case": alpha,
                "sun_fraction": sun,
                **r,
                "lipo_ok": not hot_lipo,
                "electronics_ok": not hot_elec,
            }
        )

# A burst from the radio is not a steady state. It fills the thermal mass of the board and of the air.
# The board in cm3 at 1.2 g/cm3 and 1.5 J/g/K, times 1.5 for the parts on it.
M_BOARD = PCB_W * PCB_L * PCB_T / 1000 * 1.2 * 1.5
M_AIR = V_IN_L / 1000 * 1.2 * 1005  # Litres of air at 1.2 kg/m3 and 1005 J/kg/K.
print(
    f"\na 1 s transmit burst puts {P_TX:.1f} J into {M_BOARD + M_AIR:.1f} J/K of board and air: "
    f"+{P_TX / (M_BOARD + M_AIR):.2f} K. The average column above is the value the case settles at."
)

print("\nsensitivity, bright nylon in full sun, average duty:")
print(f"{'what':38} {'T air':>7}  note")
print("-" * 96)
for label, kw in (
    ("sun on 30 % of the shell instead of 50 %", {"sun_frac": 0.30}),
    ("sun on 70 % of the shell instead of 50 %", {"sun_frac": 0.70}),
    ("ambient 25 C instead of 40 C", {"T_amb": 25.0}),
    ("ambient 50 C instead of 40 C", {"T_amb": 50.0}),
    ("10 m/s wind instead of 1 m/s", {"v": 10.0}),
    ("internal coupling 1 W/m2K instead of 3", {"h_in": 1.0}),
    ("internal coupling 10 W/m2K instead of 3", {"h_in": 10.0}),
):
    r = solve(1000.0, 0.40, kw.pop("sun_frac", 0.50), P_AVG, **kw)
    print(f"{label:38} {r['air']:6.1f}C  {'over 45 C' if r['air'] > 45 else 'ok'}")

# The question this model exists to answer: at which ambient does the 0 to 45 C corridor close?
print("\nambient sweep, bright nylon, average duty. corridor is 0-45 C for the LiPo:")
print(f"{'ambient':>9} {'diffuse light':>14} {'full sun':>10}")
for ta in (20.0, 25.0, 30.0, 35.0, 40.0, 45.0):
    d = solve(150.0, 0.40, 1.0, P_AVG, T_amb=ta)["air"]
    s = solve(1000.0, 0.40, 0.5, P_AVG, T_amb=ta)["air"]
    print(f"{ta:8.0f}C {d:13.1f}C{s:9.1f}C" + ("   <- corridor closed" if d > 45.0 else ""))

# The ePTFE vent equalizes pressure, and the path it offers carries no useful heat. This block shows
# what it would have to move if it did.
need = P_AVG / 5.0  # W/K wanted at a 5 K rise
cp, rho = 1005.0, 1.2
mdot = need / cp
q_m3_h = mdot / rho * 3600
print(
    f"\nthe vent: removing {P_AVG} W at a 5 K rise needs {mdot * 1e6:.0f} mg/s = "
    f"{q_m3_h * 1000:.1f} l/h through the plug, which is {q_m3_h / (V_IN_L * 1000 / 1e6):.0f} air "
    f"changes per hour of a {V_IN_L * 1000:.0f} ml cavity."
)
print(
    "an M12 ePTFE plug breathes on the order of a millilitre per thermal cycle, so the vent keeps "
    "pressure and moisture in check and carries no useful heat. All of it leaves through the wall."
)

wall = WALL_M / (K_PA12 * A_IN)
print(
    f"\nwall resistance alone {wall:.2f} K/W, at {P_AVG} W that is {P_AVG * wall:.1f} K from wall "
    f"to internal air; everything else is the outside film."
)
json.dump(
    {
        "tool": "thermal_lumped.py",
        "model": "steady state, two nodes plus the panel, no CFD",
        "geometry": {
            "outer_mm": [L * 1000, W * 1000, H * 1000],
            "shell_m2": A_SB,
            "top_m2": A_TOP,
            "inner_m2": A_IN,
            "cavity_ml": V_IN_L * 1000,
            "panel_m2": A_PANEL,
        },
        "limits": {"electronics_max_c": 85.0, "lipo_corridor_c": [0.0, 45.0], "lipo_hard_max_c": 60.0},
        "scenarios": out,
        "scenarios_over_lipo_corridor": bad,
        "board_and_air_j_per_k": M_BOARD + M_AIR,
        "tx_burst_rise_k_per_s": P_TX / (M_BOARD + M_AIR),
        "wall_resistance_k_per_w": wall,
        "vent_required_air_changes_per_hour": q_m3_h / (V_IN_L * 1000 / 1e6),
    },
    open(os.path.join(HERE, "thermal_report.json"), "w"),
    indent=1,
)
print("\nwrote thermal_report.json")
