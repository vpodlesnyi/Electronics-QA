#!/usr/bin/env python3
"""
gen_asc_astable.py -- Generate astable-multivibrator.asc for LTspice 26.

BC548  -> BC547B  (Tier 2, standard.bjt, same family 45V/100mA)
QTLP690C          (Tier 2, standard.dio, red LED Vf~2V@15mA)
C1=C2=1uF, R2=R3=47k  ->  f ~ 15 Hz (fast flicker)
Analysis: .tran 0 500m 0 10u  (500 ms = ~7 cycles)
"""
from __future__ import annotations
import pathlib

STUB = 48

def rot(lx, ly, r):
    if r == 'R0':   return ( lx,  ly)
    if r == 'R270': return ( ly, -lx)
    raise ValueError(r)

def pin(sx, sy, lx, ly, r='R0'):
    dx, dy = rot(lx, ly, r)
    return (sx + dx, sy + dy)

RES_A, RES_B = (16, 16), (16, 96)
CAP_A, CAP_B = (16,  0), (16, 64)
DIO_P, DIO_N = (16,  0), (16, 64)
VOL_P, VOL_N = ( 0, 16), ( 0, 96)
NPN_C, NPN_B, NPN_E = (64, 0), (0, 48), (64, 96)

lines: list[str] = []
def emit(*a): lines.append(" ".join(str(x) for x in a))
def wire(x1,y1,x2,y2): emit(f"WIRE {x1} {y1} {x2} {y2}")
def flag(x,y,n):        emit(f"FLAG {x} {y} {n}")
def text(x,y,s):        emit(f"TEXT {x} {y} Left 2 !{s}")
def comment(x,y,s):     emit(f"TEXT {x} {y} Left 2 ;{s}")
def sym(name,sx,sy,r,inst,val):
    emit(f"SYMBOL {name} {sx} {sy} {r}")
    emit(f"SYMATTR InstName {inst}")
    emit(f"SYMATTR Value {val}")

def sup(px,py):   wire(px,py,px,py-STUB); return (px,py-STUB)
def sdn(px,py):   wire(px,py,px,py+STUB); return (px,py+STUB)
def sleft(px,py): wire(px,py,px-STUB,py); return (px-STUB,py)

emit("Version 4")
emit("SHEET 1 1600 1000")

Y_VCC = 32
Y_GND = 800

# ── V1: 9V supply ─────────────────────────────────────────────
SX_V1, SY_V1 = 64, 432
pP_v1 = pin(SX_V1, SY_V1, *VOL_P)   # (64, 448)
pN_v1 = pin(SX_V1, SY_V1, *VOL_N)   # (64, 528)
sym("voltage", SX_V1, SY_V1, "R0", "V1", "DC 9")
sup_v1 = sup(*pP_v1)                  # (64, 400)
wire(*sup_v1, sup_v1[0], Y_VCC)
sdn_v1 = sdn(*pN_v1)                  # (64, 576)
wire(*sdn_v1, sdn_v1[0], Y_GND)

# ── Left branch: L1, R1, Q1 ───────────────────────────────────
X_L1 = 416   # x for left LED/collector column
SX_Q1, SY_Q1 = 352, 400
pC_Q1 = pin(SX_Q1, SY_Q1, *NPN_C)   # (416, 400)
pB_Q1 = pin(SX_Q1, SY_Q1, *NPN_B)   # (352, 448)
pE_Q1 = pin(SX_Q1, SY_Q1, *NPN_E)   # (416, 496)
sym("npn", SX_Q1, SY_Q1, "R0", "Q1", "BC547B")
sB_Q1 = sleft(*pB_Q1)                # (304, 448) = N_B1
sE_Q1 = sdn(*pE_Q1)                  # (416, 544)
wire(*sE_Q1, sE_Q1[0], Y_GND)

# R1 470 ohm: pB stub reaches Q1-C; pA stub reaches L1-N
SX_R1, SY_R1 = X_L1 - RES_A[0], 256     # (400, 256)
pA_R1 = pin(SX_R1, SY_R1, *RES_A)        # (416, 272)
pB_R1 = pin(SX_R1, SY_R1, *RES_B)        # (416, 352)
sym("res", SX_R1, SY_R1, "R0", "R1", "470")
sdn(*pB_R1)                               # wire (416,352)->(416,400) = Q1-C ✓

# L1 LED: pN stub reaches R1-A; pP stubs up to VCC
SX_L1s, SY_L1s = X_L1 - DIO_P[0], 160   # (400, 160)
pP_L1 = pin(SX_L1s, SY_L1s, *DIO_P)     # (416, 160)
pN_L1 = pin(SX_L1s, SY_L1s, *DIO_N)     # (416, 224)
sym("diode", SX_L1s, SY_L1s, "R0", "DL1", "QTLP690C")
sP_L1 = sup(*pP_L1)                       # (416, 112)
wire(*sP_L1, sP_L1[0], Y_VCC)
sdn(*pN_L1)                               # (416,224)->(416,272) = R1-A ✓

N_C1_X, N_C1_Y = 416, 352   # Q1 collector node
N_B1_X, N_B1_Y = 304, 448   # Q1 base node

# Flag N_C1 (stub right, clears R1 body)
wire(N_C1_X, N_C1_Y, N_C1_X+48, N_C1_Y)
flag(N_C1_X+48, N_C1_Y, "N_C1")

# R2 47k: pB at N_B1; pA stubs up to VCC
SX_R2 = N_B1_X - RES_A[0]              # 288
SY_R2 = N_B1_Y - RES_B[1]              # 352
pA_R2 = pin(SX_R2, SY_R2, *RES_A)      # (304, 368)
pB_R2 = pin(SX_R2, SY_R2, *RES_B)      # (304, 448) = N_B1 ✓
sym("res", SX_R2, SY_R2, "R0", "R2", "47k")
sA_R2 = sup(*pA_R2)                     # (304, 320)
wire(*sA_R2, sA_R2[0], Y_VCC)

# ── Right branch: L2, R4, Q2 ──────────────────────────────────
X_L2 = 1216
SX_Q2, SY_Q2 = 1152, 400
pC_Q2 = pin(SX_Q2, SY_Q2, *NPN_C)   # (1216, 400)
pB_Q2 = pin(SX_Q2, SY_Q2, *NPN_B)   # (1152, 448)
pE_Q2 = pin(SX_Q2, SY_Q2, *NPN_E)   # (1216, 496)
sym("npn", SX_Q2, SY_Q2, "R0", "Q2", "BC547B")
sB_Q2 = sleft(*pB_Q2)                # (1104, 448) = N_B2
sE_Q2 = sdn(*pE_Q2)                  # (1216, 544)
wire(*sE_Q2, sE_Q2[0], Y_GND)

SX_R4, SY_R4 = X_L2 - RES_A[0], 256     # (1200, 256)
pA_R4 = pin(SX_R4, SY_R4, *RES_A)        # (1216, 272)
pB_R4 = pin(SX_R4, SY_R4, *RES_B)        # (1216, 352)
sym("res", SX_R4, SY_R4, "R0", "R4", "470")
sdn(*pB_R4)                               # (1216,352)->(1216,400) = Q2-C ✓

SX_L2s, SY_L2s = X_L2 - DIO_P[0], 160
pP_L2 = pin(SX_L2s, SY_L2s, *DIO_P)     # (1216, 160)
pN_L2 = pin(SX_L2s, SY_L2s, *DIO_N)     # (1216, 224)
sym("diode", SX_L2s, SY_L2s, "R0", "DL2", "QTLP690C")
sP_L2 = sup(*pP_L2)                       # (1216, 112)
wire(*sP_L2, sP_L2[0], Y_VCC)
sdn(*pN_L2)                               # (1216,224)->(1216,272) = R4-A ✓

N_C2_X, N_C2_Y = 1216, 352
N_B2_X, N_B2_Y = 1104, 448

# Flag N_C2 (stub left, clears R4 body)
wire(N_C2_X, N_C2_Y, N_C2_X-48, N_C2_Y)
flag(N_C2_X-48, N_C2_Y, "N_C2")

SX_R3 = N_B2_X - RES_A[0]              # 1088
SY_R3 = N_B2_Y - RES_B[1]              # 352
pA_R3 = pin(SX_R3, SY_R3, *RES_A)      # (1104, 368)
pB_R3 = pin(SX_R3, SY_R3, *RES_B)      # (1104, 448) = N_B2 ✓
sym("res", SX_R3, SY_R3, "R0", "R3", "47k")
sA_R3 = sup(*pA_R3)                     # (1104, 320)
wire(*sA_R3, sA_R3[0], Y_VCC)

# ── Cross-coupling caps ────────────────────────────────────────
# C1: N_C2 (flag) -> pA -- cap -- pB -> N_B1
# Place C1 at x=570, collector level
SX_C1, SY_C1 = 554, 352
pA_C1 = pin(SX_C1, SY_C1, *CAP_A)   # (570, 352)
pB_C1 = pin(SX_C1, SY_C1, *CAP_B)   # (570, 416)
sym("cap", SX_C1, SY_C1, "R0", "C1", "1u")
sA_C1 = sup(*pA_C1)                  # (570, 304) <- flag N_C2
flag(*sA_C1, "N_C2")
sB_C1 = sdn(*pB_C1)                  # (570, 464)
wire(*sB_C1, N_B1_X, sB_C1[1])      # (570,464)->(304,464)
wire(N_B1_X, sB_C1[1], N_B1_X, N_B1_Y)  # (304,464)->(304,448) = N_B1

# C2: N_C1 (flag) -> pA -- cap -- pB -> N_B2
# Place C2 at x=1010, collector level
SX_C2, SY_C2 = 994, 352
pA_C2 = pin(SX_C2, SY_C2, *CAP_A)   # (1010, 352)
pB_C2 = pin(SX_C2, SY_C2, *CAP_B)   # (1010, 416)
sym("cap", SX_C2, SY_C2, "R0", "C2", "1u")
sA_C2 = sup(*pA_C2)                  # (1010, 304) <- flag N_C1
flag(*sA_C2, "N_C1")
sB_C2 = sdn(*pB_C2)                  # (1010, 464)
wire(*sB_C2, N_B2_X, sB_C2[1])      # (1010,464)->(1104,464)
wire(N_B2_X, sB_C2[1], N_B2_X, N_B2_Y)  # (1104,464)->(1104,448) = N_B2

# ── Power buses ────────────────────────────────────────────────
wire(sup_v1[0], Y_VCC, X_L2, Y_VCC)
flag(X_L2, Y_VCC, "VCC")
wire(sdn_v1[0], Y_GND, X_L2, Y_GND)
flag(sdn_v1[0], Y_GND, "0")

# ── SPICE directives ───────────────────────────────────────────
DX, DY = 96, 848
text(DX, DY,     ".tran 0 500m 0 10u")
text(DX, DY+24,  ".ic V(N_C1)=9 V(N_C2)=0.2 V(N_B1)=0 V(N_B2)=0.7")
text(DX, DY+48,  ".save V(N_C1) V(N_C2) V(N_B1) V(N_B2)")
comment(DX, DY+72,  "BC548 -> BC547B (Tier 2 standard.bjt, same family, 45V/100mA)")
comment(DX, DY+88,  "LEDs -> QTLP690C (Tier 2 standard.dio, red, Vf~2V@15mA, Iave=160mA)")
comment(DX, DY+104, "C1=C2=1uF, R2=R3=47k => f~15Hz fast flicker")

# ── Write output ───────────────────────────────────────────────
out = pathlib.Path(
    r"C:\Users\emuni\Documents\electronics-qa\OUTPUT\SCH\astable-multivibrator.asc")
out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Written {len(lines)} lines -> {out}")
