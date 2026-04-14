#!/usr/bin/env python3
"""
gen_asc.py - Generate Optocoupler_Digital_Input.asc for LTspice 26.
All wires are strictly horizontal or vertical (LTspice requirement).
Spacing ~2x for readability.

DA1 is placed as a proper SYMBOL Optos/PC817D (CTR grade D = 300-600%,
matching HCPL-817-300E), using the built-in PC817.sub model from lib.zip.
The hand-drawn box and custom HCPL817 subckt have been removed.

PC817D pin local coords (R0):
  A: (-96, -48)   K: (-96, +48)
  C: (+96, -48)   E: (+96, +48)

Other pin local coords from lib/sym/*.asy:
  res     R0: A=(16,16) B=(16,96)
  cap     R0: A=(16,0)  B=(16,64)
  diode   R0: +=(16,0)  -=(16,64)
  voltage R0: +=(0,16)  -=(0,96)
  npn     R0: C=(64,0)  B=(0,48)   E=(64,96)
  pmos    R0: D=(48,0)  G=(0,80)   S=(48,96)

Rotation: R270 = (x,y)->(y,-x), R180 = (x,y)->(-x,-y)
LTspice y-axis: y increases downward.
"""

from __future__ import annotations
import pathlib

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

# Local pin coords
RES_A, RES_B       = (16,16),(16,96)
CAP_A, CAP_B       = (16,0),(16,64)
DIO_P, DIO_N       = (16,0),(16,64)
VOL_P, VOL_N       = (0,16),(0,96)
NPN_C, NPN_B, NPN_E = (64,0),(0,48),(64,96)
PMOS_D,PMOS_G,PMOS_S = (48,0),(0,80),(48,96)
# PC817D local (R0)
PC817_A = (-96,-48)
PC817_K = (-96, 48)
PC817_C = ( 96,-48)
PC817_E = ( 96, 48)

lines: list[str] = []
def emit(*a): lines.append(" ".join(str(x) for x in a))
def wire(x1,y1,x2,y2): emit("WIRE",x1,y1,x2,y2)
def flag(x,y,lbl): emit(f"FLAG {x} {y} {lbl}")
def text(x,y,s): emit(f"TEXT {x} {y} Left 2 !{s}")
def sym(name,sx,sy,rot_,inst,val,val2=None,extra=None):
    emit(f"SYMBOL {name} {sx} {sy} {rot_}")
    emit(f"SYMATTR InstName {inst}")
    emit(f"SYMATTR Value {val}")
    if val2 is not None:
        emit(f"SYMATTR Value2 {val2}")
    if extra:
        for k,v in extra.items(): emit(f"SYMATTR {k} {v}")

emit("Version 4")
emit("SHEET 1 1840 1600")

# ============================================================
# Layout constants
# ============================================================
Y_PWR5  = 80    # PWR5B rail - top
Y_GND   = 960   # GND        - bottom
Y_PWR24 = 80    # PWR24B     - top
Y_GNDO  = 960   # GND_OUT    - bottom

Y_LED_A = 400   # N_LED_A row
Y_LED_K = 560   # N_LED_K row  (gap 160)
Y_COLL  = 720   # N_COLL row   (gap 160)

# ============================================================
# INPUT DOMAIN
# ============================================================

# ---- V5B : 5V supply ----
SX_V5B, SY_V5B = 80, 464
pP_v5b = pin(SX_V5B, SY_V5B, *VOL_P)   # (80, 480)
pN_v5b = pin(SX_V5B, SY_V5B, *VOL_N)   # (80, 560)
sym("voltage", SX_V5B, SY_V5B, "R0", "V5B", "DC 5")
wire(80, Y_PWR5, *pP_v5b)
wire(*pN_v5b, 80, Y_GND)
flag(80, Y_PWR5, "PWR5B")
flag(80, Y_GND,  "0")

# ---- VDINA : pulse source ----
SX_DIN, SY_DIN = 288, 464
pP_din = pin(SX_DIN, SY_DIN, *VOL_P)   # (288, 480) = DINA
pN_din = pin(SX_DIN, SY_DIN, *VOL_N)   # (288, 560)
sym("voltage", SX_DIN, SY_DIN, "R0", "VDINA", "PULSE(0 5 0 10n 10n 500u 1m)")
wire(*pN_din, 288, Y_GND)
wire(288, Y_GND, 80, Y_GND)
flag(*pP_din, "DINA")

# ---- HL1 : blue LED (PWR5B -> N_HL1) ----
SX_HL1, SY_HL1 = 160, 80
pP_hl1 = pin(SX_HL1, SY_HL1, *DIO_P)  # (176,  80) = PWR5B
pN_hl1 = pin(SX_HL1, SY_HL1, *DIO_N)  # (176, 144) = N_HL1
sym("diode", SX_HL1, SY_HL1, "R0", "DHL1", "BLUELED")
wire(80, Y_PWR5, *pP_hl1)
wire(*pN_hl1, 176, Y_LED_A)            # N_HL1 drop to LED_A row

# ---- R3 : 18R horizontal (N_HL1 bus -> N_LED_A) ----
# R270: A=(sx+16,sy-16), B=(sx+96,sy-16). B at (640,400)
SX_R3, SY_R3 = 544, 416
pA_r3 = pin(SX_R3, SY_R3, *RES_A, 'R270')  # (560, 400)
pB_r3 = pin(SX_R3, SY_R3, *RES_B, 'R270')  # (640, 400) = N_LED_A
sym("res", SX_R3, SY_R3, "R270", "R3", "18")
wire(176, Y_LED_A, *pA_r3)

N_LED_A_X, N_LED_A_Y = pB_r3  # (640, 400)

# ---- R5 : 1k vertical (N_LED_A -> N_LED_K, with stub wire) ----
SX_R5, SY_R5 = N_LED_A_X-16, N_LED_A_Y-16   # (624, 384)
pA_r5 = pin(SX_R5, SY_R5, *RES_A)            # (640, 400)
pB_r5 = pin(SX_R5, SY_R5, *RES_B)            # (640, 480)
sym("res", SX_R5, SY_R5, "R0", "R5", "1k")
wire(*pB_r5, 640, Y_LED_K)                    # (640,480)->(640,560)

N_LED_K_X, N_LED_K_Y = 640, Y_LED_K  # (640, 560)

# ---- C1 : 100n vertical (parallel with R5), one column right ----
SX_C1, SY_C1 = 720, Y_LED_A             # cap A=(736,400), B=(736,464)
pA_c1 = pin(SX_C1, SY_C1, *CAP_A)      # (736, 400)
pB_c1 = pin(SX_C1, SY_C1, *CAP_B)      # (736, 464)
sym("cap", SX_C1, SY_C1, "R0", "C1", "100n")
wire(N_LED_A_X, N_LED_A_Y, *pA_c1)     # (640,400)->(736,400)
wire(*pB_c1, 736, N_LED_K_Y)            # (736,464)->(736,560)
wire(736, N_LED_K_Y, N_LED_K_X, N_LED_K_Y)  # (736,560)->(640,560)

# ---- R4 : 18R vertical (N_LED_K -> N_COLL, with stub wire) ----
SX_R4, SY_R4 = N_LED_K_X-16, N_LED_K_Y-16   # (624, 544)
pA_r4 = pin(SX_R4, SY_R4, *RES_A)  # (640, 560)
pB_r4 = pin(SX_R4, SY_R4, *RES_B)  # (640, 640)
sym("res", SX_R4, SY_R4, "R0", "R4", "18")
wire(*pB_r4, 640, Y_COLL)           # (640,640)->(640,720) = N_COLL

N_COLL_X, N_COLL_Y = 640, Y_COLL  # (640, 720)

# ---- QVT1 : NPN BC547 ----
# C at N_COLL (640,720): sx=576, sy=720
SX_Q, SY_Q = 576, 720
pC_q = pin(SX_Q, SY_Q, *NPN_C)  # (640, 720)
pB_q = pin(SX_Q, SY_Q, *NPN_B)  # (576, 768)
pE_q = pin(SX_Q, SY_Q, *NPN_E)  # (640, 816)
sym("npn", SX_Q, SY_Q, "R0", "QVT1", "BC547B")
wire(*pE_q, 640, Y_GND)
flag(640, Y_GND, "0")

N_BASE_X, N_BASE_Y = pB_q  # (576, 768)

# ---- R2 : 10k vertical (N_BASE -> GND) ----
SX_R2, SY_R2 = N_BASE_X-16, N_BASE_Y-16   # (560, 752)
pA_r2 = pin(SX_R2, SY_R2, *RES_A)  # (576, 768)
pB_r2 = pin(SX_R2, SY_R2, *RES_B)  # (576, 848)
sym("res", SX_R2, SY_R2, "R0", "R2", "10k")
wire(*pB_r2, 576, Y_GND)
wire(576, Y_GND, 640, Y_GND)

# ---- R1 : 10k horizontal (DINA -> N_BASE) ----
# R270: B at N_BASE (576,768): sx=480, sy=784
SX_R1, SY_R1 = 480, 784
pA_r1 = pin(SX_R1, SY_R1, *RES_A, 'R270')  # (496, 768)
pB_r1 = pin(SX_R1, SY_R1, *RES_B, 'R270')  # (576, 768)
sym("res", SX_R1, SY_R1, "R270", "R1", "10k")
wire(pP_din[0], pP_din[1], 288, N_BASE_Y)   # DINA: (288,480)->(288,768)
wire(288, N_BASE_Y, *pA_r1)                  # (288,768)->(496,768)

# ============================================================
# DA1 : PC817D optocoupler from [Optos] library
# PC817D local pins (R0): A=(-96,-48) K=(-96,+48) C=(+96,-48) E=(+96,+48)
# Place at sx=944, sy=448:
#   A -> (848, 400) = N_LED_A level    (connects to horizontal N_LED_A bus)
#   K -> (848, 496)                    (stub wire down to N_LED_K at y=560)
#   C -> (1040, 400) = N_OPT_C
#   E -> (1040, 496)                   (stub wire down to GND_OUT at y=960)
# ============================================================
SX_DA1, SY_DA1 = 944, 448
pA_da1 = pin(SX_DA1, SY_DA1, *PC817_A)  # (848, 400)
pK_da1 = pin(SX_DA1, SY_DA1, *PC817_K)  # (848, 496)
pC_da1 = pin(SX_DA1, SY_DA1, *PC817_C)  # (1040, 400)
pE_da1 = pin(SX_DA1, SY_DA1, *PC817_E)  # (1040, 496)

sym("Optos/PC817D", SX_DA1, SY_DA1, "R0", "XDA1", "PC817D",
    val2="PC817 Igain=3.4m")

# N_LED_A -> A: extend horizontal bus from C1 right edge to A pin
wire(736, Y_LED_A, *pA_da1)             # (736,400)->(848,400)

# N_LED_K -> K: extend horizontal bus then stub up to K pin
wire(736, Y_LED_K, pK_da1[0], Y_LED_K) # (736,560)->(848,560)
wire(pK_da1[0], Y_LED_K, *pK_da1)      # (848,560)->(848,496) up to K

# E -> GND_OUT: stub wire straight down
wire(*pE_da1, pE_da1[0], Y_GNDO)
flag(pE_da1[0], Y_GNDO, "GND_OUT")

N_OPT_C_X, N_OPT_C_Y = pC_da1   # (1040, 400)

# ============================================================
# OUTPUT DOMAIN
# ============================================================

# ---- R6 : 100R horizontal (N_OPT_C -> N_GATE) ----
# R270: A=(sx+16,sy-16), B=(sx+96,sy-16). A just right of opto C.
SX_R6, SY_R6 = N_OPT_C_X, N_OPT_C_Y+16   # (1040, 416)
pA_r6 = pin(SX_R6, SY_R6, *RES_A, 'R270')  # (1056, 400)
pB_r6 = pin(SX_R6, SY_R6, *RES_B, 'R270')  # (1136, 400) = N_GATE
sym("res", SX_R6, SY_R6, "R270", "R6", "100")
wire(N_OPT_C_X, N_OPT_C_Y, *pA_r6)
N_GATE_X, N_GATE_Y = pB_r6               # (1136, 400)

# ---- R7 : 10k vertical (PWR24B -> N_GATE) ----
SX_R7, SY_R7 = N_GATE_X-16, Y_PWR24-16   # (1120, 64)
pA_r7 = pin(SX_R7, SY_R7, *RES_A)        # (1136,  80)
pB_r7 = pin(SX_R7, SY_R7, *RES_B)        # (1136, 160)
sym("res", SX_R7, SY_R7, "R0", "R7", "10k")
flag(*pA_r7, "PWR24B")
wire(*pB_r7, N_GATE_X, N_GATE_Y)         # (1136,160)->(1136,400)

# ---- VT2 : P-ch MOSFET IRF9540 ----
# G at N_GATE (1136,400): sx=1136, sy=320
SX_VT2, SY_VT2 = 1136, 320
pD_vt2 = pin(SX_VT2, SY_VT2, *PMOS_D)  # (1184, 320) = DOUTA
pG_vt2 = pin(SX_VT2, SY_VT2, *PMOS_G)  # (1136, 400) = N_GATE
pS_vt2 = pin(SX_VT2, SY_VT2, *PMOS_S)  # (1184, 416) -> PWR24B
sym("pmos", SX_VT2, SY_VT2, "R0", "MVT2", "IRF9540")
wire(*pS_vt2, pS_vt2[0], Y_PWR24)
flag(pS_vt2[0], Y_PWR24, "PWR24B")
wire(N_GATE_X, Y_PWR24, pS_vt2[0], Y_PWR24)   # PWR24B rail segment

N_DOUTA_X, N_DOUTA_Y = pD_vt2   # (1184, 320)

# ---- C2 : 100n decoupling (PWR24B -> GND_OUT) ----
SX_C2, SY_C2 = 1264, Y_PWR24
pA_c2 = pin(SX_C2, SY_C2, *CAP_A)   # (1280,  80)
pB_c2 = pin(SX_C2, SY_C2, *CAP_B)   # (1280, 144)
sym("cap", SX_C2, SY_C2, "R0", "C2", "100n")
wire(pS_vt2[0], Y_PWR24, *pA_c2)
wire(*pB_c2, 1280, Y_GNDO)
flag(1280, Y_GNDO, "GND_OUT")

# ---- DOUTA vertical bus ----
DOUTA_BUS_X = N_DOUTA_X   # 1184
wire(DOUTA_BUS_X, N_DOUTA_Y, DOUTA_BUS_X, Y_LED_K)  # (1184,320)->(1184,560)
flag(DOUTA_BUS_X, Y_LED_K, "DOUTA")

# ---- RLOAD : 1Meg (DOUTA -> GND_OUT) ----
SX_RL, SY_RL = DOUTA_BUS_X+160, Y_LED_K-16   # (1344, 544)
pA_rl = pin(SX_RL, SY_RL, *RES_A)  # (1360, 560)
pB_rl = pin(SX_RL, SY_RL, *RES_B)  # (1360, 640)
sym("res", SX_RL, SY_RL, "R0", "RLOAD", "1Meg")
# DOUTA horizontal bus: (1184,560)->(1360,560)
wire(DOUTA_BUS_X, Y_LED_K, *pA_rl)
wire(*pB_rl, 1360, Y_GNDO)
flag(1360, Y_GNDO, "GND_OUT")

# ---- V24 : 24V supply ----
SX_V24, SY_V24 = 1648, 464
pP_v24 = pin(SX_V24, SY_V24, *VOL_P)   # (1648, 480)
pN_v24 = pin(SX_V24, SY_V24, *VOL_N)   # (1648, 560)
sym("voltage", SX_V24, SY_V24, "R0", "V24", "DC 24")
wire(*pP_v24, 1648, Y_PWR24)
flag(1648, Y_PWR24, "PWR24B")
wire(1280, Y_PWR24, 1648, Y_PWR24)     # PWR24B rail: C2 -> V24
wire(*pN_v24, 1648, Y_GNDO)
flag(1648, Y_GNDO, "GND_OUT")

# ============================================================
# SPICE DIRECTIVES
# Note: DA1 now uses the built-in PC817D/PC817.sub from lib.zip.
# The custom HCPL817 subckt has been removed.
# ============================================================
DX, DY = 48, 1040
text(DX, DY,       ".tran 0 5m 0 1u")
text(DX, DY+24,    ".op")
text(DX, DY+48,    ".options gmin=1e-10 abstol=1e-9")
text(DX, DY+72,    ".model BC547 NPN(Is=7.59e-15 Xti=3 Eg=1.11 Vaf=73.4 Bf=480"
                   " Ise=3.28e-14 Ne=1.679 Ikf=0.05821 Nk=0.5 Xtb=1.5 Var=100"
                   " Br=5.394 Rc=0.5 Cjc=5.25p Mjc=0.3333 Vjc=0.75 Fc=0.5"
                   " Cje=11.5p Mje=0.3333 Vje=0.75 Tr=10.01n Tf=0.4074n"
                   " Itf=0.05 Vtf=5 Xtf=1.237 Rb=10)")
text(DX, DY+96,    ".model IRF9540 PMOS(Level=3 Gamma=0 Delta=0 Eta=0 Theta=0"
                   " Kappa=0.2 Vmax=0 Xj=0 Tox=97.5n Uo=157 Phi=0.6 Rs=0.7017m"
                   " Kp=10.15u W=0.35 L=2u Vto=-3.93 Rd=0.3571 Rds=1.667Meg"
                   " Cbd=3.229n Pb=0.8 Mj=0.5 Fc=0.5 Cgso=9.027e-9"
                   " Cgdo=2.071e-10 Is=0.3456p N=1 Tt=880n)")
text(DX, DY+120,   ".model BLUELED D(Is=1e-28 N=1.8 Rs=3 BV=10 Vj=0.75 M=0.5 Cjo=2p)")
text(DX, DY+144,   ".save V(DINA) V(N_BASE) V(N_COLL) V(N_LED_A) V(N_LED_K) V(N_OPT_C) V(N_GATE) V(DOUTA)")

# ============================================================
# OUTPUT
# ============================================================
out = pathlib.Path(r"C:\Users\emuni\Documents\electronics-qa\OUTPUT\SCH\Optocoupler_Digital_Input.asc")
out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Written {len(lines)} lines -> {out}")

print("\nPin summary:")
print(f"  V5B    V+={pP_v5b}  V-={pN_v5b}")
print(f"  VDINA  V+={pP_din}  V-={pN_din}")
print(f"  HL1    anode={pP_hl1}  cathode={pN_hl1}")
print(f"  R3     A={pA_r3}  B={pB_r3}")
print(f"  R5     A={pA_r5}  B={pB_r5}")
print(f"  C1     A={pA_c1}  B={pB_c1}")
print(f"  R4     A={pA_r4}  B={pB_r4}")
print(f"  QVT1   C={pC_q}  B={pB_q}  E={pE_q}")
print(f"  R1     A={pA_r1}  B={pB_r1}")
print(f"  R2     A={pA_r2}  B={pB_r2}")
print(f"  DA1    A={pA_da1}  K={pK_da1}  C={pC_da1}  E={pE_da1}")
print(f"  R6     A={pA_r6}  B={pB_r6}  (N_GATE)")
print(f"  R7     A={pA_r7}  B={pB_r7}")
print(f"  VT2    D={pD_vt2}  G={pG_vt2}  S={pS_vt2}")
print(f"  C2     A={pA_c2}  B={pB_c2}")
print(f"  RLOAD  A={pA_rl}  B={pB_rl}")
print(f"  V24    V+={pP_v24}  V-={pN_v24}")
