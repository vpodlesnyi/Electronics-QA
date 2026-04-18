#!/usr/bin/env python3
"""
gen_asc.py  –  Generate Optocoupler_Digital_Input.asc for LTspice 26.

Stub rule (Altium-style):
  Every component pin has a 3-grid-unit (48 px) stub before any wire
  junction or connection.  Junctions never sit at pin origins.

Bus rule:
  Power and GND rails use physical horizontal bus wires.
  Net labels are used only where physical wires would cross or clutter.
  DINA is kept as a net label (R1-A and VDINA+ are too far apart to route cleanly).

H    = 2  : horizontal scale factor
STUB = 48 : 3 × 16-px grid units of clearance per pin

Library lookups (query_lib.py results):
  BC846ALT1G  → BC846B  in standard.bjt  (Tier 2: same die, alt package)
  HCPL-817-300E → PC817D in lib/sub/PC817.sub (Tier 5: same die, CTR grade via Igain=3.4m)
  FQD11P06TM  → FQB11P06 VDMOS(pchan) in standard.mos (Tier 5: same die, alt package, 60V 11A)
  SMBJ24CA    → SMBJ24CA in standard.dio  (Tier 2: direct match)
  FYLS-0603UBC → NSPW500BS (Nichia white 30mA, Vf≈3.1V@10mA, Tier 2 standard.dio; color irrelevant, Vf match chosen)
"""
from __future__ import annotations
import pathlib

H    = 2
STUB = 48   # 3 grid units

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

RES_A, RES_B           = (16, 16), (16, 96)
CAP_A, CAP_B           = (16,  0), (16, 64)
DIO_P, DIO_N           = (16,  0), (16, 64)
VOL_P, VOL_N           = ( 0, 16), ( 0, 96)
NPN_C, NPN_B, NPN_E    = (64,  0), ( 0, 48), (64, 96)
PMOS_D, PMOS_G, PMOS_S = (48,  0), ( 0, 80), (48, 96)
PC817_A = (-96, -48);  PC817_K = (-96, 48)
PC817_C = ( 96, -48);  PC817_E = ( 96, 48)

lines: list[str] = []
def emit(*a): lines.append(" ".join(str(x) for x in a))
def wire(x1,y1,x2,y2): emit("WIRE",x1,y1,x2,y2)
def flag(x,y,n):        emit(f"FLAG {x} {y} {n}")
def text(x,y,s):        emit(f"TEXT {x} {y} Left 2 !{s}")
def comment(x,y,s):     emit(f"TEXT {x} {y} Left 2 ;{s}")
def sym(name,sx,sy,r,inst,val,val2=None,extra=None):
    emit(f"SYMBOL {name} {sx} {sy} {r}")
    emit(f"SYMATTR InstName {inst}")
    emit(f"SYMATTR Value {val}")
    if val2 is not None: emit(f"SYMATTR Value2 {val2}")
    if extra:
        for k,v in extra.items(): emit(f"SYMATTR {k} {v}")

# ── Stub helpers: emit STUB-length wire, return stub-end coord ────────────────
def sup  (px,py): wire(px,py,px,py-STUB); return (px,py-STUB)
def sdn  (px,py): wire(px,py,px,py+STUB); return (px,py+STUB)
def sleft(px,py): wire(px,py,px-STUB,py); return (px-STUB,py)
def sright(px,py): wire(px,py,px+STUB,py); return (px+STUB,py)

emit("Version 4")
emit(f"SHEET 1 {1840*H} 1600")

# ── Bus y-levels ──────────────────────────────────────────────────────────────
Y_PWR5B  = 32    # 5 V supply bus (input domain)
Y_PWR24B = 80    # 24 V supply bus (output domain)
Y_LED_A  = 400   # N_LED_A signal bus
# Y_LED_K derived from R5 body (80 px) + two STUB clearances
Y_LED_K  = Y_LED_A + STUB + (RES_B[1]-RES_A[1]) + STUB   # 400+48+80+48 = 576
Y_GND    = 960   # GND / node-0 bus (input domain)
Y_GNDO   = 960   # GND_OUT bus — same node as GND (grounds connected per simulation request)

# ============================================================
# INPUT DOMAIN  (GND / 5 V)
# ============================================================

# ── V5B ──────────────────────────────────────────────────────
SX_V5B, SY_V5B = 80*H, 464
pP_v5b = pin(SX_V5B, SY_V5B, *VOL_P)   # (160, 480)
pN_v5b = pin(SX_V5B, SY_V5B, *VOL_N)   # (160, 560)
sym("voltage", SX_V5B, SY_V5B, "R0", "V5B", "DC 5")
sP_v5b = sup(*pP_v5b)                    # (160, 432)
wire(*sP_v5b, sP_v5b[0], Y_PWR5B)       # route up to PWR5B bus  (160,432)→(160,32)
sN_v5b = sdn(*pN_v5b)                    # (160, 608)
wire(*sN_v5b, sN_v5b[0], Y_GND)         # route down to GND bus  (160,608)→(160,960)

# ── VDINA ─────────────────────────────────────────────────────
SX_DIN, SY_DIN = 288*H, 464
pP_din = pin(SX_DIN, SY_DIN, *VOL_P)   # (576, 480)
pN_din = pin(SX_DIN, SY_DIN, *VOL_N)   # (576, 560)
sym("voltage", SX_DIN, SY_DIN, "R0", "VDINA", "PULSE(0 5 0 10n 10n 500u 1m)")
flag(*sup(*pP_din), "DINA")             # keep net label — R1-A is far away at x=944
sN_din = sdn(*pN_din)                   # (576, 608)
wire(*sN_din, sN_din[0], Y_GND)         # route down to GND bus  (576,608)→(576,960)

# ── HL1 : blue LED (FYLS-0603UBC → NSPW500BS, Nichia white Iave=30mA, Vf≈3.1V@10mA, Tier 2 standard.dio) ──
SX_HL1, SY_HL1 = 160*H, 80
pP_hl1 = pin(SX_HL1, SY_HL1, *DIO_P)   # (336, 80)
pN_hl1 = pin(SX_HL1, SY_HL1, *DIO_N)   # (336, 144)
sym("diode", SX_HL1, SY_HL1, "R0", "DHL1", "NSPW500BS")
sP_hl1 = sup(*pP_hl1)                   # (336, 32) — stub end lands on Y_PWR5B ✓
sN_hl1 = sdn(*pN_hl1)                   # (336, 192)
wire(*sN_hl1, sN_hl1[0], Y_LED_A)       # drop to N_LED_A bus  (336,192)→(336,400)
N_HL1_X = sN_hl1[0]                     # 336

# ── R3 : 18 Ω horizontal ─────────────────────────────────────
# Pins at y = Y_LED_A = 400  →  SY_R3 = Y_LED_A + RES_A_rot_y = 400+16 = 416
SX_R3, SY_R3 = 544*H, Y_LED_A + 16     # (1088, 416)
pA_r3 = pin(SX_R3, SY_R3, *RES_A, 'R270')  # (1104, 400)
pB_r3 = pin(SX_R3, SY_R3, *RES_B, 'R270')  # (1184, 400)
sym("res", SX_R3, SY_R3, "R270", "R3", "18")
sA_r3 = sleft(*pA_r3)    # (1056, 400)
sB_r3 = sright(*pB_r3)   # (1232, 400)  ← N_LED_A node

N_LED_A_X, N_LED_A_Y = sB_r3   # (1232, 400)
N_LED_K_X = N_LED_A_X           # same column  1232

# ── R5 : 1 kΩ vertical (N_LED_A → N_LED_K) ──────────────────
# Pin A must be STUB below N_LED_A_Y so stub ↑ reaches bus
SX_R5 = N_LED_A_X - 16                          # 1216
SY_R5 = N_LED_A_Y + STUB - RES_A[1]             # 400+48-16 = 432
pA_r5 = pin(SX_R5, SY_R5, *RES_A)   # (1232, 448)
pB_r5 = pin(SX_R5, SY_R5, *RES_B)   # (1232, 528)
sym("res", SX_R5, SY_R5, "R0", "R5", "1k")
sup(*pA_r5)   # (1232, 400) = N_LED_A ✓  (no extra routing needed)
sB_r5 = sdn(*pB_r5)   # (1232, 576) = N_LED_K ✓

# ── C1 : 100 nF vertical (N_LED_A → N_LED_K) ────────────────
SX_C1 = 720*H                              # 1440
SY_C1 = N_LED_A_Y + STUB - CAP_A[1]       # 400+48-0 = 448
pA_c1 = pin(SX_C1, SY_C1, *CAP_A)   # (1456, 448)
pB_c1 = pin(SX_C1, SY_C1, *CAP_B)   # (1456, 512)
sym("cap", SX_C1, SY_C1, "R0", "C1", "100n")
sup(*pA_c1)                   # (1456, 400) on N_LED_A bus ✓
sB_c1 = sdn(*pB_c1)           # (1456, 560)
wire(*sB_c1, sB_c1[0], Y_LED_K)   # route 560→576 to N_LED_K bus

# ── DA1 : PC817D  (SUBSTITUTE: HCPL-817-300E → PC817D, same die, CTR via Igain=3.4m) ──
SX_DA1, SY_DA1 = 944*H, 448
pA_da1 = pin(SX_DA1, SY_DA1, *PC817_A)   # (1792, 400)
pK_da1 = pin(SX_DA1, SY_DA1, *PC817_K)   # (1792, 496)
pC_da1 = pin(SX_DA1, SY_DA1, *PC817_C)   # (1984, 400)
pE_da1 = pin(SX_DA1, SY_DA1, *PC817_E)   # (1984, 496)
sym("Optos/PC817D", SX_DA1, SY_DA1, "R0", "XDA1", "PC817D",
    val2="PC817 Igain=3.4m")
sA_da1 = sleft(*pA_da1)   # (1744, 400) — right end of N_LED_A bus
sK_da1 = sleft(*pK_da1)   # (1744, 496)
wire(*sK_da1, sK_da1[0], Y_LED_K)   # route 496→576 to N_LED_K bus
sC_da1 = sright(*pC_da1)  # (2032, 400) = N_OPT_C node
sE_da1 = sdn(*pE_da1)     # (1984, 544)
wire(*sE_da1, sE_da1[0], Y_GNDO)   # route down to GND_OUT bus (= node 0)

N_OPT_C_X, N_OPT_C_Y = sC_da1   # (2032, 400)

# ── N_LED_A bus (single wire, full span) ──────────────────────
wire(N_HL1_X, Y_LED_A, sA_da1[0], Y_LED_A)   # 336 → 1744

# ── N_LED_K bus (single wire, full span) ──────────────────────
wire(N_LED_K_X, Y_LED_K, sK_da1[0], Y_LED_K)  # 1232 → 1744

# ── R4 : 18 Ω vertical (N_LED_K → N_COLL) ───────────────────
SX_R4 = N_LED_K_X - 16                    # 1216
SY_R4 = Y_LED_K + STUB - RES_A[1]         # 576+48-16 = 608
pA_r4 = pin(SX_R4, SY_R4, *RES_A)   # (1232, 624)
pB_r4 = pin(SX_R4, SY_R4, *RES_B)   # (1232, 704)
sym("res", SX_R4, SY_R4, "R0", "R4", "18")
sup(*pA_r4)              # (1232, 576) = N_LED_K bus ✓
sB_r4 = sdn(*pB_r4)     # (1232, 752) = N_COLL node

# ── QVT1 : NPN BC846B  (SUBSTITUTE: BC846ALT1G → BC846B, same die, Tier 2 lib.zip) ──
# Collector stub ↑ must reach N_COLL = sB_r4 = (1232, 752)
SX_Q = N_LED_K_X - NPN_C[0]    # 1232-64 = 1168
SY_Q = sB_r4[1] + STUB          # 752+48 = 800
pC_q = pin(SX_Q, SY_Q, *NPN_C)   # (1232, 800)
pB_q = pin(SX_Q, SY_Q, *NPN_B)   # (1168, 848)
pE_q = pin(SX_Q, SY_Q, *NPN_E)   # (1232, 896)
sym("npn", SX_Q, SY_Q, "R0", "QVT1", "BC846B")
sup(*pC_q)               # (1232, 752) = N_COLL ✓  (meets sB_r4)
sB_q  = sleft(*pB_q)     # (1120, 848) = N_BASE node
sE_q  = sdn(*pE_q)       # (1232, 944)
wire(*sE_q, sE_q[0], Y_GND)     # route down to GND bus  (1232,944)→(1232,960)

N_BASE_X, N_BASE_Y = sB_q   # (1120, 848)

# ── R2 : 10 kΩ vertical (N_BASE → GND) ──────────────────────
# pA sits directly at N_BASE — no stub wire (avoids routing into body).
# pB is below and connects down to GND bus.
SX_R2 = N_BASE_X - 16                          # 1104
SY_R2 = N_BASE_Y - RES_A[1]                    # 848-16 = 832  (pA lands on N_BASE)
pA_r2 = pin(SX_R2, SY_R2, *RES_A)   # (1120, 848) = N_BASE directly
pB_r2 = pin(SX_R2, SY_R2, *RES_B)   # (1120, 928)
sym("res", SX_R2, SY_R2, "R0", "R2", "10k")
# pA is at N_BASE — R1-B, QVT1-B stubs also land here; no extra wire needed
wire(*pB_r2, pB_r2[0], Y_GND)       # route pB straight down to GND bus  (1120,928)→(1120,960)

# ── R1 : 10 kΩ horizontal (DINA → N_BASE) ───────────────────
# pB stub → must land on N_BASE; pA stub ← gets DINA flag
# pB_r1 = (SX_R1+96, SY_R1-16);  stub right end = (SX_R1+96+STUB, SY_R1-16)
# RES_B R270 → (96,-16); x-offset is 96, NOT RES_B[0]=16
SX_R1 = N_BASE_X - STUB - 96          # 1120-48-96 = 976
SY_R1 = N_BASE_Y + RES_A[1]           # 848+16 = 864
pA_r1 = pin(SX_R1, SY_R1, *RES_A, 'R270')   # (992, 848)
pB_r1 = pin(SX_R1, SY_R1, *RES_B, 'R270')   # (1072, 848)
sym("res", SX_R1, SY_R1, "R270", "R1", "10k")
flag(*sleft(*pA_r1), "DINA")   # R1-A stub ← → DINA net label
sright(*pB_r1)                 # (1120, 848) = N_BASE ✓

# N_BASE net label — flag directly at the junction node
flag(N_BASE_X, N_BASE_Y, "N_BASE")

# ============================================================
# OUTPUT DOMAIN  (GND / 24 V — grounds connected to node 0)
# ============================================================

# ── R6 : 100 Ω horizontal (N_OPT_C → N_GATE) ────────────────
# pA stub ← must reach N_OPT_C_X; pB stub → becomes N_GATE
SX_R6 = N_OPT_C_X + STUB - RES_A[0]   # 2032+48-16 = 2064
SY_R6 = N_OPT_C_Y + RES_A[0]          # 400+16 = 416
pA_r6 = pin(SX_R6, SY_R6, *RES_A, 'R270')   # (2080, 400)
pB_r6 = pin(SX_R6, SY_R6, *RES_B, 'R270')   # (2160, 400)
sym("res", SX_R6, SY_R6, "R270", "R6", "100")
sleft(*pA_r6)              # (2032, 400) = N_OPT_C ✓
sB_r6 = sright(*pB_r6)    # (2208, 400) = N_GATE node

N_GATE_X, N_GATE_Y = sB_r6   # (2208, 400)

# ── R7 : 10 kΩ vertical (PWR24B → N_GATE) ───────────────────
# pB stub ↓ must reach N_GATE_Y; pA stub ↑ routes to PWR24B bus
SX_R7 = N_GATE_X - RES_A[0]                   # 2208-16 = 2192
SY_R7 = N_GATE_Y - STUB - RES_B[1]            # 400-48-96 = 256
pA_r7 = pin(SX_R7, SY_R7, *RES_A)   # (2208, 272)
pB_r7 = pin(SX_R7, SY_R7, *RES_B)   # (2208, 352)
sym("res", SX_R7, SY_R7, "R0", "R7", "10k")
sA_r7 = sup(*pA_r7)                    # (2208, 224)
wire(*sA_r7, sA_r7[0], Y_PWR24B)      # route up to PWR24B bus  (2208,224)→(2208,80)
sdn(*pB_r7)                            # (2208, 400) = N_GATE ✓

# ── VT2 : FQB11P06 P-ch MOSFET (SUBSTITUTE: FQD11P06TM → FQB11P06, same die, Tier 3 lib.zip) ──
# SX_VT2 = N_GATE_X + 80 (5 grid) — keeps 4-grid body gap from R7 right edge (~2224)
SX_VT2 = N_GATE_X + 80                 # 2208+80 = 2288  (R7 right ~2224, gap=64px=4 grid ✓)
SY_VT2 = N_GATE_Y - PMOS_G[1]          # 400-80 = 320
pD_vt2 = pin(SX_VT2, SY_VT2, *PMOS_D)   # (2336, 320)
pG_vt2 = pin(SX_VT2, SY_VT2, *PMOS_G)   # (2288, 400)
pS_vt2 = pin(SX_VT2, SY_VT2, *PMOS_S)   # (2336, 416)
sym("pmos", SX_VT2, SY_VT2, "R0", "MVT2", "FQB11P06")
wire(*pG_vt2, N_GATE_X, N_GATE_Y)      # (2288,400)→(2208,400) = N_GATE (80px = 5-grid stub ✓)
sD_vt2 = sup(*pD_vt2)       # (2336, 272) = DOUTA node  (exits above body ✓)
sS_vt2 = sdn(*pS_vt2)       # (2336, 464) — stub DOWN exits body ✓
flag(*sS_vt2, "PWR24B")     # source = +24V via net label; avoids U-shaped cross-domain route

# ── RLOAD : 1 MΩ dummy load (not on physical schematic — provides DC path when VT2 off) ──
# Hangs 4 grid (64px) BELOW DOUTA bus (y=272+64=336). Clean vertical drop — no dangling stub.
# Spacing from VT2 D stub (x=2336): 192 px = 12 grid ✓
SX_RL = 2512                          # pA at x=2528, 12 grid right of VT2 D
SY_RL = 320                           # pA at y=336 — 4 grid below DOUTA ✓
pA_rl = pin(SX_RL, SY_RL, *RES_A)   # (2528, 336)
pB_rl = pin(SX_RL, SY_RL, *RES_B)   # (2528, 416)
sym("res", SX_RL, SY_RL, "R0", "RLOAD", "1Meg")
wire(pA_rl[0], sD_vt2[1], *pA_rl)    # (2528,272)→(2528,336) clean drop; no dangling stub
sB_rl_dn = sdn(*pB_rl)               # (2528, 464)
wire(*sB_rl_dn, sB_rl_dn[0], Y_GNDO) # route down to GND bus

# ── VD1 : SMBJ24CA bidirectional TVS (direct lib.zip Tier 2 match, standard.dio) ──
# Hangs 4 grid (64px) BELOW DOUTA bus (y=272+64=336). Clean vertical drop — no dangling stub.
# Spacing from RLOAD pA (x=2528): 192 px = 12 grid ✓
SX_VD1 = 2704                         # pP at x=2720, 12 grid right of RLOAD
SY_VD1 = 336                          # pP at y=336 — 4 grid below DOUTA ✓
pP_vd1 = pin(SX_VD1, SY_VD1, *DIO_P) # (2720, 336)
pN_vd1 = pin(SX_VD1, SY_VD1, *DIO_N) # (2720, 400)
sym("diode", SX_VD1, SY_VD1, "R0", "DVD1", "SMBJ24CA")
wire(pP_vd1[0], sD_vt2[1], *pP_vd1)  # (2720,272)→(2720,336) clean drop; no dangling stub
sN_vd1 = sdn(*pN_vd1)    # (2720, 448)
wire(*sN_vd1, sN_vd1[0], Y_GNDO)   # route down to GND bus

# ── C2 : 100 nF decoupling ────────────────────────────────────
# Spacing from VD1 (x=2720): 176 px = 11 grid units ✓
SX_C2 = 2880
SY_C2 = 200
pA_c2 = pin(SX_C2, SY_C2, *CAP_A)   # (2896, 200)
pB_c2 = pin(SX_C2, SY_C2, *CAP_B)   # (2896, 264)
sym("cap", SX_C2, SY_C2, "R0", "C2", "100n")
sA_c2 = sup(*pA_c2)                   # (2896, 152)
wire(*sA_c2, sA_c2[0], Y_PWR24B)     # route up to PWR24B bus  (2896,152)→(2896,80)
sB_c2_dn = sdn(*pB_c2)               # (2896, 312)
wire(*sB_c2_dn, sB_c2_dn[0], Y_GNDO) # route down to GND bus

# ── V24 : 24 V supply ────────────────────────────────────────
SX_V24, SY_V24 = 1648*H, 464
pP_v24 = pin(SX_V24, SY_V24, *VOL_P)   # (3296, 480)
pN_v24 = pin(SX_V24, SY_V24, *VOL_N)   # (3296, 560)
sym("voltage", SX_V24, SY_V24, "R0", "V24", "DC 24")
sP_v24    = sup(*pP_v24)                # (3296, 432)
wire(*sP_v24, sP_v24[0], Y_PWR24B)     # route up to PWR24B bus  (3296,432)→(3296,80)
sN_v24_dn = sdn(*pN_v24)               # (3296, 608)
wire(*sN_v24_dn, sN_v24_dn[0], Y_GNDO) # route down to GND bus (node 0)

# ============================================================
# PHYSICAL BUSES
# ============================================================

# PWR5B bus: V5B+ to HL1-anode
wire(sP_v5b[0], Y_PWR5B, sP_hl1[0], Y_PWR5B)   # (160,32)→(336,32)
flag(sP_v5b[0], Y_PWR5B, "PWR5B")

# GND (node 0) bus — input domain: V5B- to QVT1-E
wire(sN_v5b[0], Y_GND, sE_q[0], Y_GND)   # (160,960)→(1232,960)
flag(sN_v5b[0], Y_GND, "0")

# PWR24B bus — output domain: R7-A to V24+  (C2-A at 2896 in between)
# VT2 source connects via "PWR24B" net label flag — no physical bus tap needed there
wire(sA_r7[0], Y_PWR24B, sP_v24[0], Y_PWR24B)   # (2208,80)→(3296,80)
flag(sP_v24[0], Y_PWR24B, "PWR24B")

# GND bus — output domain (node 0, same net as input GND): DA1-E to V24-
wire(sE_da1[0], Y_GNDO, sN_v24_dn[0], Y_GNDO)   # (1984,960)→(3296,960)
flag(sN_v24_dn[0], Y_GNDO, "0")

# DOUTA: horizontal from VT2-D stub to VD1 drop point
# RLOAD (x=2528) and VD1 (x=2720) connect via clean vertical drops — T-junctions at y=272
wire(*sD_vt2, pP_vd1[0], sD_vt2[1])   # (2336,272)→(2720,272)  horizontal
flag(*sD_vt2, "DOUTA")

# ============================================================
# INFORMATIONAL NET LABELS
# ============================================================

# N_LED_A : upward from bus (16 px stub — flag clears the bus wire)
wire(N_LED_A_X, N_LED_A_Y, N_LED_A_X, N_LED_A_Y-16)
flag(N_LED_A_X, N_LED_A_Y-16, "N_LED_A")

# N_LED_K : short downward stub (free space between bus and R4-A pin)
wire(N_LED_K_X, Y_LED_K, N_LED_K_X, Y_LED_K+16)
flag(N_LED_K_X, Y_LED_K+16, "N_LED_K")

# N_OPT_C : upward from node
wire(N_OPT_C_X, N_OPT_C_Y, N_OPT_C_X, N_OPT_C_Y-16)
flag(N_OPT_C_X, N_OPT_C_Y-16, "N_OPT_C")

# N_COLL : rightward from the shared stub-end node (1232, 752)
wire(sB_r4[0], sB_r4[1], sB_r4[0]+48, sB_r4[1])
flag(sB_r4[0]+48, sB_r4[1], "N_COLL")

# N_GATE : downward from node into free space below VT2 body
wire(N_GATE_X, N_GATE_Y, N_GATE_X, N_GATE_Y+48)
flag(N_GATE_X, N_GATE_Y+48, "N_GATE")

# ============================================================
# SPICE DIRECTIVES
# ============================================================
DX, DY = 96, 1040
text(DX, DY,      ".tran 0 5m 0 1u")
text(DX, DY+24,   ".op")
text(DX, DY+48,
    ".save V(DINA) V(N_BASE) V(N_COLL) V(N_LED_A) V(N_LED_K)"
    " V(N_OPT_C) V(N_GATE) V(DOUTA)")
comment(DX, DY+72,  "BC846ALT1G -> BC846B  (same die, Tier 2 lib.zip standard.bjt)")
comment(DX, DY+88,  "FQD11P06TM -> FQB11P06 VDMOS(pchan) (same die, Tier 3 lib.zip standard.mos, Vds=-60V Ron=175m)")
comment(DX, DY+104, "HCPL-817-300E -> PC817D (same die, CTR=300% via Igain=3.4m, Tier 5 lib/sub/PC817.sub)")
comment(DX, DY+120, "FYLS-0603UBC -> NSPW500BS (Nichia white 30mA, Vf=3.1V@10mA, Tier 2 standard.dio)")
comment(DX, DY+136, "SMBJ24CA direct match in standard.dio (Tier 2)")
comment(DX, DY+152, "RLOAD=1Meg not on physical schematic; gives DC path to GND when VT2 is off")

# ============================================================
# WRITE OUTPUT
# ============================================================
out = pathlib.Path(
    r"C:\Users\emuni\Documents\electronics-qa\OUTPUT\SCH\Optocoupler_Digital_Input.asc")
out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Written {len(lines)} lines -> {out}")
print()
print("Bus levels:")
print(f"  PWR5B   y={Y_PWR5B}   x={sP_v5b[0]}..{sP_hl1[0]}")
print(f"  PWR24B  y={Y_PWR24B}  x={sA_r7[0]}..{sP_v24[0]}")
print(f"  GND(0)  y={Y_GND}   x={sN_v5b[0]}..{sE_q[0]}")
print(f"  GND_OUT->0 y={Y_GNDO} x={sE_da1[0]}..{sN_v24_dn[0]}")
print()
print("Signal nodes:")
print(f"  N_LED_A  ({N_LED_A_X}, {N_LED_A_Y})   bus y={Y_LED_A}  x={N_HL1_X}..{sA_da1[0]}")
print(f"  N_LED_K  ({N_LED_K_X}, {Y_LED_K})   bus y={Y_LED_K}  x={N_LED_K_X}..{sK_da1[0]}")
print(f"  N_OPT_C  ({N_OPT_C_X}, {N_OPT_C_Y})")
print(f"  N_COLL   ({sB_r4[0]}, {sB_r4[1]})")
print(f"  N_BASE   ({N_BASE_X}, {N_BASE_Y})")
print(f"  N_GATE   ({N_GATE_X}, {N_GATE_Y})")
print(f"  DOUTA    ({sD_vt2[0]}, {sD_vt2[1]}) -> ({pP_vd1[0]}, {sD_vt2[1]}) [horizontal bus y={sD_vt2[1]}]")
print(f"  VD1 pP   ({pP_vd1[0]}, {pP_vd1[1]})  pN  ({pN_vd1[0]}, {pN_vd1[1]})  [drop from y={sD_vt2[1]}]")
print(f"  STUB = {STUB} px = {STUB//16} grid units")
