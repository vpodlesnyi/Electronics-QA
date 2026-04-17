#!/usr/bin/env python3
"""
gen_asc.py  -  Generate Optocoupler_Digital_Input.asc for LTspice 26.

Stub rule:
  Every component pin has a 3-grid-unit (48 px) stub before any wire
  junction or connection.  Junctions never sit at pin origins.
  Exception: when node_distance < body_height + 2*STUB, place pin directly
  at the node (zero stub) to avoid routing through the component body.

Bus rule:
  Power and GND rails use physical horizontal bus wires + one flag per rail.
  Net labels (FLAG) are used only where physical wires would cross or clutter.

Isolation:
  GND (node 0, input domain) and GND_OUT (output domain) are separate buses
  at the same y-level with a gap between them.  They are never connected.

Model resolution applied here (matches Optocoupler_Digital_Input.cir):
  QVT1  BC846ALT1G -> BC846B    (lib.zip Tier-5, same NXP die)
  MVT2  FQD11P06TM -> FQB11P06  (lib.zip Tier-5, same Fairchild die, D2PAK vs DPAK)
  XDA1  HCPL-817-300E -> PC817D  (lib.zip Tier-5, PC817 D-grade Igain=3.4m = CTR 300-600%)
  DVD1  SMBJ24CA               (lib.zip Tier-2, exact match)
  DHL1  FYLS-0603UBC -> BLUE_LED (Tier-7 custom, Vf=3.22V @ 20mA per Foryard datasheet)

H    = 2  : horizontal scale factor applied to SX coordinates only
STUB = 48 : 3 x 16-px grid units of pin clearance
"""
from __future__ import annotations
import pathlib

H    = 2
STUB = 48   # 3 grid units

# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def rot(lx, ly, r):
    if r == 'R0'  : return ( lx,  ly)
    if r == 'R90' : return (-ly,  lx)
    if r == 'R180': return (-lx, -ly)
    if r == 'R270': return ( ly, -lx)
    if r == 'M0'  : return (-lx,  ly)
    if r == 'M90' : return ( ly,  lx)
    if r == 'M180': return ( lx, -ly)
    if r == 'M270': return (-ly, -lx)
    raise ValueError(r)

def pin(sx, sy, lx, ly, r='R0'):
    dx, dy = rot(lx, ly, r)
    return (sx + dx, sy + dy)

# Pin local offsets per symbol (verified against lib.zip .asy files)
RES_A, RES_B           = (16, 16), (16, 96)   # res.asy  R0 vertical
CAP_A, CAP_B           = (16,  0), (16, 64)   # cap.asy  R0 vertical
DIO_P, DIO_N           = (16,  0), (16, 64)   # diode.asy R0 anode-top
VOL_P, VOL_N           = ( 0, 16), ( 0, 96)   # voltage.asy R0
NPN_C, NPN_B, NPN_E    = (64,  0), ( 0, 48), (64, 96)   # npn.asy
PMOS_D, PMOS_G, PMOS_S = (48,  0), ( 0, 80), (48, 96)   # pmos.asy
PC817_A = (-96, -48);  PC817_K = (-96, 48)    # PC817x.asy (symbol origin at centre)
PC817_C = ( 96, -48);  PC817_E = ( 96, 48)

# ---------------------------------------------------------------------------
# ASC line emitter  +  label-placement engine
# ---------------------------------------------------------------------------

lines:  list[str]                     = []
_wires: list[tuple[int,int,int,int]]  = []   # normalised (x1≤x2, y1≤y2)

LABEL_CLEARANCE = 16   # 1 grid unit — minimum text-to-wire perpendicular distance
INFO_OFFSET     = 32   # 2 grid units — stub length for informational net-label flags

FONT = 2

# Per-(symbol-stem, rotation) WINDOW overrides: list of (win_num, dx, dy, just, size)
# Offsets are screen-space (not rotated).  Verified clear of all wires in this circuit.
_WINDOWS: dict[tuple[str,str], list[tuple]] = {
    ('res',   'R0')  : [(0, 36,  24, 'Left', FONT), (3, 36,  64, 'Left', FONT)],
    ('res',   'R270'): [(0, 56, -52, 'Left', FONT), (3, 56,  16, 'Left', FONT)],
    ('cap',   'R0')  : [(0, 36,  -8, 'Left', FONT), (3, 36,  56, 'Left', FONT)],
    ('diode', 'R0')  : [(0, 36,  -8, 'Left', FONT), (3, 36,  56, 'Left', FONT)],
    # npn, pmos, voltage, PC817x: use .asy defaults (no override needed)
}

def _sym_stem(name: str) -> str:
    """Return the bare symbol file stem in lower-case, e.g. 'Optos/PC817D' → 'pc817d'."""
    return name.split('/')[-1].lower()

def _wire_clearance(px: int, py: int) -> float:
    """Return the minimum perpendicular distance from (px,py) to any registered wire."""
    min_d = float('inf')
    for x1, y1, x2, y2 in _wires:
        if x1 == x2:          # vertical wire
            if y1 <= py <= y2:
                d = abs(px - x1)
            else:
                d = abs(px - x1) + min(abs(py - y1), abs(py - y2))
        else:                  # horizontal wire
            if x1 <= px <= x2:
                d = abs(py - y1)
            else:
                d = abs(py - y1) + min(abs(px - x1), abs(px - x2))
        if d < min_d:
            min_d = d
    return min_d

def _safe_window(sx: int, sy: int, dx: int, dy: int) -> tuple[int, int]:
    """Shift (dx,dy) in ±LABEL_CLEARANCE steps (dy first) until text clears all wires."""
    if _wire_clearance(sx + dx, sy + dy) >= LABEL_CLEARANCE:
        return dx, dy
    for step in range(LABEL_CLEARANCE, 6 * LABEL_CLEARANCE, LABEL_CLEARANCE):
        for sign in (1, -1):
            ndy = dy + sign * step
            if _wire_clearance(sx + dx, sy + ndy) >= LABEL_CLEARANCE:
                return dx, ndy
    return dx, dy   # fallback: return original if no clear position found


def emit(*a): lines.append(" ".join(str(x) for x in a))

def wire(x1: int, y1: int, x2: int, y2: int) -> None:
    emit("WIRE", x1, y1, x2, y2)
    # Register normalised segment for clearance checks
    _wires.append((min(x1,x2), min(y1,y2), max(x1,x2), max(y1,y2)))

def flag(x, y, n):  emit(f"FLAG {x} {y} {n}")
def text(x, y, s):  emit(f"TEXT {x} {y} Left 2 !{s}")

def sym(name, sx, sy, r, inst, val, val2=None, extra=None):
    emit(f"SYMBOL {name} {sx} {sy} {r}")
    wins = _WINDOWS.get((_sym_stem(name), r))
    if wins:
        for win_num, dx, dy, just, size in wins:
            adx, ady = _safe_window(sx, sy, dx, dy)
            emit(f"WINDOW {win_num} {adx} {ady} {just} {size}")
    emit(f"SYMATTR InstName {inst}")
    emit(f"SYMATTR Value {val}")
    if val2 is not None: emit(f"SYMATTR Value2 {val2}")
    if extra:
        for k, v in extra.items(): emit(f"SYMATTR {k} {v}")

# Stub helpers — emit STUB-length wire, return stub-end coordinate
def sup  (px, py): wire(px, py, px, py - STUB); return (px, py - STUB)
def sdn  (px, py): wire(px, py, px, py + STUB); return (px, py + STUB)
def sleft(px, py): wire(px, py, px - STUB, py); return (px - STUB, py)
def sright(px,py): wire(px, py, px + STUB, py); return (px + STUB, py)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

emit("Version 4")
emit(f"SHEET 1 {1840*H} 1600")

# ---------------------------------------------------------------------------
# Bus y-levels
# ---------------------------------------------------------------------------

Y_PWR5B  = 32    # +5V bus  (input domain)
Y_PWR24B = 80    # +24V bus (output domain)
Y_LED_A  = 400   # N_LED_A signal bus y
Y_LED_K  = Y_LED_A + STUB + (RES_B[1] - RES_A[1]) + STUB   # 400+48+80+48 = 576
Y_GND    = 960   # GND / node-0 bus (input domain)
Y_GNDO   = 960   # GND_OUT bus (output domain, same y, separate wire with gap)

# ===========================================================================
# INPUT DOMAIN  (GND / +5V)
# ===========================================================================

# --- V5B : 5 V supply -------------------------------------------------------
SX_V5B, SY_V5B = 80*H, 464
pP_v5b = pin(SX_V5B, SY_V5B, *VOL_P)   # (160, 480)
pN_v5b = pin(SX_V5B, SY_V5B, *VOL_N)   # (160, 560)
sym("voltage", SX_V5B, SY_V5B, "R0", "V5B", "DC 5")
sP_v5b = sup(*pP_v5b)                    # (160, 432) -> route to PWR5B bus
wire(*sP_v5b, sP_v5b[0], Y_PWR5B)
sN_v5b = sdn(*pN_v5b)                    # (160, 608) -> route to GND bus
wire(*sN_v5b, sN_v5b[0], Y_GND)

# --- VDINA : pulse stimulus -------------------------------------------------
SX_DIN, SY_DIN = 288*H, 464
pP_din = pin(SX_DIN, SY_DIN, *VOL_P)   # (576, 480)
pN_din = pin(SX_DIN, SY_DIN, *VOL_N)   # (576, 560)
sym("voltage", SX_DIN, SY_DIN, "R0", "VDINA",
    "PULSE(0 5 0 10n 10n 500u 1m)")
# DINA label kept as net label; R1-A is far to the right
flag(*sup(*pP_din), "DINA")
sN_din = sdn(*pN_din)
wire(*sN_din, sN_din[0], Y_GND)

# --- DHL1 : blue LED indicator (FYLS-0603UBC -> BLUE_LED) ------------------
# SUBSTITUTE: FYLS-0603UBC; using BLUE_LED custom model (Tier-7).
# Vf = 3.22 V @ 20 mA derived from Foryard datasheet.
SX_HL1, SY_HL1 = 160*H, 80
pP_hl1 = pin(SX_HL1, SY_HL1, *DIO_P)   # (336, 80)  anode  - on PWR5B bus
pN_hl1 = pin(SX_HL1, SY_HL1, *DIO_N)   # (336, 144) cathode
sym("diode", SX_HL1, SY_HL1, "R0", "DHL1", "BLUE_LED")
sP_hl1 = sup(*pP_hl1)                   # (336, 32) = Y_PWR5B ✓ (stub lands on bus)
sN_hl1 = sdn(*pN_hl1)                   # (336, 192)
wire(*sN_hl1, sN_hl1[0], Y_LED_A)       # (336,192) -> (336,400)
N_HL1_X = sN_hl1[0]                     # 336

# --- R3 : 18 ohm (after DHL1, into N_LED_A node) ---------------------------
# Horizontal resistor R270; pin B (right) at N_LED_A = (1232, 400) via sright stub
SX_R3 = 544*H;  SY_R3 = Y_LED_A + RES_A[1]   # 1088, 416
pA_r3 = pin(SX_R3, SY_R3, *RES_A, 'R270')     # (1104, 400)
pB_r3 = pin(SX_R3, SY_R3, *RES_B, 'R270')     # (1184, 400)
sym("res", SX_R3, SY_R3, "R270", "R3", "18")
sA_r3 = sleft(*pA_r3)     # (1056, 400)
sB_r3 = sright(*pB_r3)    # (1232, 400) = N_LED_A node

N_LED_A_X, N_LED_A_Y = sB_r3   # (1232, 400)
N_LED_K_X = N_LED_A_X           # 1232  (same column)

# --- R5 : 1 kohm vertical (N_LED_A -> N_LED_K) -----------------------------
# pA stub UP must reach N_LED_A bus (y=400); pB stub DOWN gives N_LED_K (y=576)
SX_R5 = N_LED_A_X - RES_A[0]              # 1216
SY_R5 = N_LED_A_Y + STUB - RES_A[1]       # 400+48-16 = 432
pA_r5 = pin(SX_R5, SY_R5, *RES_A)   # (1232, 448)
pB_r5 = pin(SX_R5, SY_R5, *RES_B)   # (1232, 528)
sym("res", SX_R5, SY_R5, "R0", "R5", "1k")
sup(*pA_r5)            # (1232, 400) = N_LED_A ✓
sB_r5 = sdn(*pB_r5)   # (1232, 576) = N_LED_K ✓

# --- C1 : 100 nF filter (N_LED_A -> N_LED_K) --------------------------------
SX_C1 = 720*H;  SY_C1 = N_LED_A_Y + STUB - CAP_A[1]   # 1440, 448
pA_c1 = pin(SX_C1, SY_C1, *CAP_A)   # (1456, 448)
pB_c1 = pin(SX_C1, SY_C1, *CAP_B)   # (1456, 512)
sym("cap", SX_C1, SY_C1, "R0", "C1", "100n")
sup(*pA_c1)                     # (1456, 400) = N_LED_A bus ✓
sB_c1 = sdn(*pB_c1)             # (1456, 560)
wire(*sB_c1, sB_c1[0], Y_LED_K) # (1456,560) -> (1456,576) = N_LED_K bus

# --- XDA1 : PC817D (HCPL-817-300E substitute) ------------------------------
# SUBSTITUTE: HCPL-817-300E; using PC817D from lib.zip (Igain=3.4m = CTR 300-600%)
# PC817 pins: 1=A  2=K  3=E(emitter)  4=C(collector)
SX_DA1, SY_DA1 = 944*H, 448   # (1888, 448)
pA_da1 = pin(SX_DA1, SY_DA1, *PC817_A)   # (1792, 400)
pK_da1 = pin(SX_DA1, SY_DA1, *PC817_K)   # (1792, 496)
pC_da1 = pin(SX_DA1, SY_DA1, *PC817_C)   # (1984, 400)
pE_da1 = pin(SX_DA1, SY_DA1, *PC817_E)   # (1984, 496)
sym("Optos/PC817D", SX_DA1, SY_DA1, "R0", "XDA1", "PC817D",
    val2="PC817 Igain=3.4m")
sA_da1 = sleft(*pA_da1)    # (1744, 400) = right end of N_LED_A bus
sK_da1 = sleft(*pK_da1)    # (1744, 496)
wire(*sK_da1, sK_da1[0], Y_LED_K)   # (1744,496) -> (1744,576) = N_LED_K bus
sC_da1 = sright(*pC_da1)   # (2032, 400) = N_OPT_C node
sE_da1 = sdn(*pE_da1)      # (1984, 544)
wire(*sE_da1, sE_da1[0], Y_GNDO)    # (1984,544) -> (1984,960) = GND_OUT bus

N_OPT_C_X, N_OPT_C_Y = sC_da1   # (2032, 400)

# --- N_LED_A bus (one wire spanning all connections) -----------------------
wire(N_HL1_X, Y_LED_A, sA_da1[0], Y_LED_A)    # 336 -> 1744

# --- N_LED_K bus -----------------------------------------------------------
wire(N_LED_K_X, Y_LED_K, sK_da1[0], Y_LED_K)  # 1232 -> 1744

# --- R4 : 18 ohm vertical (N_LED_K -> N_COLL, cathode limiter) -------------
SX_R4 = N_LED_K_X - RES_A[0]              # 1216
SY_R4 = Y_LED_K + STUB - RES_A[1]         # 576+48-16 = 608
pA_r4 = pin(SX_R4, SY_R4, *RES_A)   # (1232, 624)
pB_r4 = pin(SX_R4, SY_R4, *RES_B)   # (1232, 704)
sym("res", SX_R4, SY_R4, "R0", "R4", "18")
sup(*pA_r4)              # (1232, 576) = N_LED_K bus ✓
sB_r4 = sdn(*pB_r4)     # (1232, 752) = N_COLL node

# --- QVT1 : NPN BC846B (BC846ALT1G substitute) -----------------------------
# SUBSTITUTE: BC846ALT1G; using BC846B (NXP lib.zip).  Same die, package suffix only.
# C stub UP meets sB_r4 (N_COLL); E stub DOWN routes to GND bus.
SX_Q = N_LED_K_X - NPN_C[0]     # 1232-64 = 1168
SY_Q = sB_r4[1] + STUB           # 752+48 = 800
pC_q = pin(SX_Q, SY_Q, *NPN_C)   # (1232, 800)
pB_q = pin(SX_Q, SY_Q, *NPN_B)   # (1168, 848)
pE_q = pin(SX_Q, SY_Q, *NPN_E)   # (1232, 896)
sym("npn", SX_Q, SY_Q, "R0", "QVT1", "BC846B")
sup(*pC_q)               # (1232, 752) = N_COLL ✓ (meets sB_r4)
sB_q  = sleft(*pB_q)     # (1120, 848) = N_BASE node
sE_q  = sdn(*pE_q)       # (1232, 944)
wire(*sE_q, sE_q[0], Y_GND)    # (1232,944) -> (1232,960) = GND bus

N_BASE_X, N_BASE_Y = sB_q   # (1120, 848)

# --- R2 : 10 kohm vertical (N_BASE -> GND) ----------------------------------
# pA sits directly at N_BASE — no stub (R2 body < STUB clearance to QVT1-B).
# See asc_generation_rules.md §Session learnings / R2 body-crossing stub fix.
SX_R2 = N_BASE_X - RES_A[0]          # 1104
SY_R2 = N_BASE_Y - RES_A[1]          # 848-16 = 832   pA lands at N_BASE directly
pA_r2 = pin(SX_R2, SY_R2, *RES_A)   # (1120, 848) = N_BASE
pB_r2 = pin(SX_R2, SY_R2, *RES_B)   # (1120, 928)
sym("res", SX_R2, SY_R2, "R0", "R2", "10k")
# pA at N_BASE — no extra wire needed
wire(*pB_r2, pB_r2[0], Y_GND)       # (1120,928) -> (1120,960) = GND bus

# --- R1 : 10 kohm horizontal R270 (DINA -> N_BASE) -------------------------
SX_R1 = N_BASE_X - STUB - 96          # 1120-48-96 = 976
SY_R1 = N_BASE_Y + RES_A[1]           # 848+16 = 864
pA_r1 = pin(SX_R1, SY_R1, *RES_A, 'R270')   # (992, 848)
pB_r1 = pin(SX_R1, SY_R1, *RES_B, 'R270')   # (1072, 848)
sym("res", SX_R1, SY_R1, "R270", "R1", "10k")
flag(*sleft(*pA_r1), "DINA")   # R1-A stub <- DINA net label
sright(*pB_r1)                  # (1120, 848) = N_BASE ✓

# ===========================================================================
# OUTPUT DOMAIN  (GND_OUT / +24V)
# ===========================================================================

# --- R6 : 100 ohm horizontal R270 (N_OPT_C -> N_GATE) ----------------------
SX_R6 = N_OPT_C_X + STUB - RES_A[0]   # 2032+48-16 = 2064
SY_R6 = N_OPT_C_Y + RES_A[0]          # 400+16 = 416
pA_r6 = pin(SX_R6, SY_R6, *RES_A, 'R270')   # (2080, 400)
pB_r6 = pin(SX_R6, SY_R6, *RES_B, 'R270')   # (2160, 400)
sym("res", SX_R6, SY_R6, "R270", "R6", "100")
sleft(*pA_r6)              # (2032, 400) = N_OPT_C ✓
sB_r6 = sright(*pB_r6)    # (2208, 400) = N_GATE node

N_GATE_X, N_GATE_Y = sB_r6   # (2208, 400)

# --- R7 : 10 kohm vertical (PWR24B -> N_GATE) --------------------------------
SX_R7 = N_GATE_X - RES_A[0]                   # 2192
SY_R7 = N_GATE_Y - STUB - RES_B[1]            # 400-48-96 = 256
pA_r7 = pin(SX_R7, SY_R7, *RES_A)   # (2208, 272)
pB_r7 = pin(SX_R7, SY_R7, *RES_B)   # (2208, 352)
sym("res", SX_R7, SY_R7, "R0", "R7", "10k")
sA_r7 = sup(*pA_r7)                    # (2208, 224)
wire(*sA_r7, sA_r7[0], Y_PWR24B)      # (2208,224) -> (2208,80) = PWR24B bus
sdn(*pB_r7)                            # (2208, 400) = N_GATE ✓

# --- MVT2 : PMOS FQB11P06 (FQD11P06TM substitute) --------------------------
# SUBSTITUTE: FQD11P06TM; using FQB11P06 (Fairchild lib.zip standard.mos).
# Same die: Vds=-60V, Ron=175mohm, Qg=13nC.  D2PAK vs DPAK — no electrical diff.
# G stub <- must reach N_GATE; S stub DOWN per body-clearance rule; D stub UP.
SX_VT2 = N_GATE_X + STUB               # 2208+48 = 2256
SY_VT2 = N_GATE_Y - PMOS_G[1]          # 400-80 = 320
pD_vt2 = pin(SX_VT2, SY_VT2, *PMOS_D)   # (2304, 320)
pG_vt2 = pin(SX_VT2, SY_VT2, *PMOS_G)   # (2256, 400)
pS_vt2 = pin(SX_VT2, SY_VT2, *PMOS_S)   # (2304, 416)
sym("pmos", SX_VT2, SY_VT2, "R0", "MVT2", "FQB11P06")
sleft(*pG_vt2)               # (2208, 400) = N_GATE ✓
sD_vt2 = sup(*pD_vt2)        # (2304, 272) = DOUTA node (exits above body ✓)
# S stubs DOWN (rule: PMOS S never stubs UP — would cross D through body).
# Detour right to VT2S_X before routing up to PWR24B.
# See asc_generation_rules.md §Session learnings / PMOS S-pin body-crossing fix.
sS_vt2   = sdn(*pS_vt2)      # (2304, 464) — below body ✓
VT2S_X   = 2368
wire(*sS_vt2, VT2S_X, sS_vt2[1])            # (2304,464) -> (2368,464) horizontal
wire(VT2S_X, sS_vt2[1], VT2S_X, Y_PWR24B)   # (2368,464) -> (2368,80) vertical

# --- RLOAD : 1 Meg dummy load (SIMULATION ONLY) ----------------------------
# Provides DOUTA a DC path to GND_OUT when MVT2 is OFF to prevent floating node.
# NOT on the physical schematic.
SX_RL = SX_VT2 + 160    # 2256+160 = 2416
SY_RL = SY_VT2          # 320
pA_rl = pin(SX_RL, SY_RL, *RES_A)   # (2432, 336)
pB_rl = pin(SX_RL, SY_RL, *RES_B)   # (2432, 416)
sym("res", SX_RL, SY_RL, "R0", "RLOAD", "1Meg")
sA_rl    = sup(*pA_rl)               # (2432, 288) = DOUTA
sB_rl_dn = sdn(*pB_rl)              # (2432, 464)
wire(*sB_rl_dn, sB_rl_dn[0], Y_GNDO) # (2432,464) -> (2432,960) = GND_OUT bus

# --- DVD1 : SMBJ24CA bidirectional TVS (DOUTA -> GND_OUT) ------------------
# Exact lib.zip match (Tier-2).
# pP (anode) at y=272 on DOUTA horizontal wire; pN (cathode) routes down to GND_OUT.
# x=2480 chosen: right of RLOAD body (ends ~x=2448), left of C2 (starts x=2528).
SX_VD1, SY_VD1 = 2464, 272   # pP = (2480, 272) on DOUTA wire
pP_vd1 = pin(SX_VD1, SY_VD1, *DIO_P)   # (2480, 272)
pN_vd1 = pin(SX_VD1, SY_VD1, *DIO_N)   # (2480, 336)
sym("diode", SX_VD1, SY_VD1, "R0", "DVD1", "SMBJ24CA")
# pP sits directly on the DOUTA wire (no stub needed; zero clearance, no body conflict)
sN_vd1 = sdn(*pN_vd1)                # (2480, 384)
wire(*sN_vd1, sN_vd1[0], Y_GNDO)    # (2480,384) -> (2480,960) = GND_OUT bus

# --- C2 : 100 nF decoupling (PWR24B -> GND_OUT) ----------------------------
SX_C2 = 1264*H;  SY_C2 = 200   # (2528, 200)
pA_c2 = pin(SX_C2, SY_C2, *CAP_A)   # (2544, 200)
pB_c2 = pin(SX_C2, SY_C2, *CAP_B)   # (2544, 264)
sym("cap", SX_C2, SY_C2, "R0", "C2", "100n")
sA_c2 = sup(*pA_c2)                   # (2544, 152)
wire(*sA_c2, sA_c2[0], Y_PWR24B)     # (2544,152) -> (2544,80) = PWR24B bus
sB_c2 = sdn(*pB_c2)                  # (2544, 312)
wire(*sB_c2, sB_c2[0], Y_GNDO)       # (2544,312) -> (2544,960) = GND_OUT bus

# --- V24 : 24 V isolated supply --------------------------------------------
SX_V24, SY_V24 = 1648*H, 464   # (3296, 464)
pP_v24 = pin(SX_V24, SY_V24, *VOL_P)   # (3296, 480)
pN_v24 = pin(SX_V24, SY_V24, *VOL_N)   # (3296, 560)
sym("voltage", SX_V24, SY_V24, "R0", "V24", "DC 24")
sP_v24 = sup(*pP_v24)                   # (3296, 432)
wire(*sP_v24, sP_v24[0], Y_PWR24B)     # (3296,432) -> (3296,80) = PWR24B bus
sN_v24 = sdn(*pN_v24)                  # (3296, 608)
wire(*sN_v24, sN_v24[0], Y_GNDO)       # (3296,608) -> (3296,960) = GND_OUT bus

# ===========================================================================
# PHYSICAL BUSES
# ===========================================================================

# PWR5B bus (input domain): V5B+ to DHL1 anode
wire(sP_v5b[0], Y_PWR5B, sP_hl1[0], Y_PWR5B)   # (160,32) -> (336,32)
flag(sP_v5b[0], Y_PWR5B, "PWR5B")

# GND bus (input domain, node 0): V5B- to QVT1-E
wire(sN_v5b[0], Y_GND, sE_q[0], Y_GND)   # (160,960) -> (1232,960)
flag(sN_v5b[0], Y_GND, "0")

# PWR24B bus (output domain): R7-A stub .. V24+
# (VT2-S detour at x=2368, C2 top at x=2544 also connect to this bus)
wire(sA_r7[0], Y_PWR24B, sP_v24[0], Y_PWR24B)   # (2208,80) -> (3296,80)
flag(sP_v24[0], Y_PWR24B, "PWR24B")

# GND_OUT bus (output domain, isolated): DA1-E stub .. V24-
# All output-domain GND wires land between x=1984 and x=3296
wire(sE_da1[0], Y_GNDO, sN_v24[0], Y_GNDO)   # (1984,960) -> (3296,960)
flag(sN_v24[0], Y_GNDO, "GND_OUT")

# ===========================================================================
# DOUTA wire  (VT2-D stub -> RLOAD-A stub and DVD1-pP)
# ===========================================================================
# Horizontal DOUTA segment: extends from VT2-D stub to DVD1-pP at x=2480
wire(sD_vt2[0], sD_vt2[1], 2480, sD_vt2[1])   # (2304,272) -> (2480,272)
# Vertical jog from DOUTA y=272 down to RLOAD-pA stub at y=288
wire(sA_rl[0], sD_vt2[1], *sA_rl)              # (2432,272) -> (2432,288)
# Net label for .save reference
flag(*sD_vt2, "DOUTA")

# ===========================================================================
# INFORMATIONAL NET LABELS (short stubs so flag clears the bus wire)
# ===========================================================================

wire(N_LED_A_X, N_LED_A_Y, N_LED_A_X, N_LED_A_Y - INFO_OFFSET)
flag(N_LED_A_X, N_LED_A_Y - INFO_OFFSET, "N_LED_A")

wire(N_LED_K_X, Y_LED_K, N_LED_K_X, Y_LED_K + INFO_OFFSET)
flag(N_LED_K_X, Y_LED_K + INFO_OFFSET, "N_LED_K")

wire(N_OPT_C_X, N_OPT_C_Y, N_OPT_C_X, N_OPT_C_Y - INFO_OFFSET)
flag(N_OPT_C_X, N_OPT_C_Y - INFO_OFFSET, "N_OPT_C")

wire(sB_r4[0], sB_r4[1], sB_r4[0] + INFO_OFFSET, sB_r4[1])
flag(sB_r4[0] + INFO_OFFSET, sB_r4[1], "N_COLL")

wire(N_GATE_X, N_GATE_Y, N_GATE_X, N_GATE_Y + INFO_OFFSET)
flag(N_GATE_X, N_GATE_Y + INFO_OFFSET, "N_GATE")

# ===========================================================================
# SPICE DIRECTIVES  (placed below the main circuit area)
# ===========================================================================

DX, DY = 96, 1040
text(DX, DY,    ".tran 0 10m 0 1u")
text(DX, DY+24, ".op")
text(DX, DY+48, ".param Igain=3.4m")
text(DX, DY+72,
     ".model BLUE_LED D(Is=2.2e-20 N=3.0 Rs=0.5 Cjo=3p BV=5 Iave=25m Vpk=5)")
text(DX, DY+96,
     ".save V(DINA) V(N_BASE) V(N_COLL) V(N_LED_A) V(N_LED_K)"
     " V(N_OPT_C) V(N_GATE) V(DOUTA)")

# ===========================================================================
# WRITE OUTPUT
# ===========================================================================

OUT_PATH = pathlib.Path(
    r"C:\Users\emuni\Documents\electronics-qa\OUTPUT\SCH\Optocoupler_Digital_Input.asc")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

print(f"Written {len(lines)} lines -> {OUT_PATH}")
print()
print("Bus levels:")
print(f"  PWR5B    y={Y_PWR5B}  x={sP_v5b[0]}..{sP_hl1[0]}")
print(f"  PWR24B   y={Y_PWR24B}  x={sA_r7[0]}..{sP_v24[0]}")
print(f"  GND(0)   y={Y_GND}  x={sN_v5b[0]}..{sE_q[0]}")
print(f"  GND_OUT  y={Y_GNDO}  x={sE_da1[0]}..{sN_v24[0]}")
print()
print("Signal nodes:")
print(f"  N_LED_A  ({N_LED_A_X}, {N_LED_A_Y})  bus: y={Y_LED_A}  x={N_HL1_X}..{sA_da1[0]}")
print(f"  N_LED_K  ({N_LED_K_X}, {Y_LED_K})  bus: y={Y_LED_K}  x={N_LED_K_X}..{sK_da1[0]}")
print(f"  N_OPT_C  ({N_OPT_C_X}, {N_OPT_C_Y})")
print(f"  N_COLL   ({sB_r4[0]}, {sB_r4[1]})")
print(f"  N_BASE   ({N_BASE_X}, {N_BASE_Y})")
print(f"  N_GATE   ({N_GATE_X}, {N_GATE_Y})")
print(f"  DOUTA    x={sD_vt2[0]}..2480, y={sD_vt2[1]}  (jog to RLOAD at ({sA_rl[0]},{sA_rl[1]}))")
print(f"  DVD1     pP=({SX_VD1+16},{SY_VD1}) pN=({SX_VD1+16},{SY_VD1+64})")
print(f"  STUB = {STUB} px = {STUB//16} grid units")
