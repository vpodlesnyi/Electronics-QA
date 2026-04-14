# Circuit Templates

Canonical SPICE skeletons for common topologies. Use as scaffolds when the vision pass clearly identifies one of these circuits; populate with the user's component values; add/remove nets as needed. Don't copy blindly — always reconcile against the actual schematic.

---

## Non-inverting op-amp amplifier

```
* Non-inverting amplifier, gain = 1 + Rf/Rg
V1 VCC 0 9
V2 VEE 0 0                    ; single-supply: VEE = 0
V3 IN  0 SINE(0 0.05 1k) AC 1

* Midpoint bias (if single supply)
R3 VCC  NBIAS 100k
R4 NBIAS 0    100k
C2 NBIAS 0    10u

* AC coupling
C1 IN NPLUS 1u
R5 NPLUS NBIAS 1Meg            ; keeps NPLUS biased at midpoint

* Feedback
Rg NMINUS 0    1k
Rf NMINUS OUT  10k

* Op-amp
XU1 NPLUS NMINUS VCC VEE OUT UniversalOpAmp2 Avol=1Meg GBW=1.1Meg Slew=0.5Meg

.ac dec 100 1 1Meg
.tran 0 5m 0 1u
.save V(IN) V(OUT) V(NPLUS)
.end
```

For a dual-supply version, set `V2 VEE 0 -9` and remove the midpoint bias network; connect `NPLUS` directly (through the input coupling cap or not) to the signal source.

---

## Inverting op-amp amplifier

```
* Inverting amplifier, gain = -Rf/Rin
V1 VCC 0 15
V2 VEE 0 -15
V3 IN  0 SINE(0 0.1 1k) AC 1

Rin IN     NMINUS 10k
Rf  NMINUS OUT    100k

XU1 0 NMINUS VCC VEE OUT UniversalOpAmp2 Avol=1Meg GBW=1.1Meg

.ac dec 100 1 1Meg
.save V(IN) V(OUT)
.end
```

---

## RC low-pass filter (single pole)

```
* RC low-pass, fc = 1 / (2*pi*R*C)
V1 IN 0 AC 1 SINE(0 1 1k)

R1 IN  OUT 1k
C1 OUT 0   100n

.ac dec 100 1 10Meg
.save V(IN) V(OUT)
.end
```

fc for R=1k, C=100n → ~1.59 kHz. Pick `.ac` limits spanning ~2 decades below and above fc.

---

## RC high-pass filter (single pole)

```
V1 IN 0 AC 1

C1 IN  OUT 100n
R1 OUT 0   1k

.ac dec 100 1 10Meg
.save V(IN) V(OUT)
.end
```

---

## RLC band-pass / resonator

```
V1 IN 0 AC 1

R1 IN  N1  10
L1 N1  OUT 10m
C1 OUT 0   100n

.ac dec 100 100 100k
.save V(IN) V(OUT)
.end
```

Resonance: f0 = 1 / (2π·sqrt(L·C)).

---

## Common-emitter BJT amplifier

```
V1 VCC 0 12
V2 IN  0 SINE(0 0.01 1k) AC 1

* Bias network
R1 VCC NB 47k
R2 NB  0  10k

* Collector / emitter
RC VCC NC  4.7k
RE NE  0   1k
CE NE  0   100u            ; emitter bypass

* AC coupling
C1 IN  NB 10u
C2 NC  OUT 10u
RL OUT 0 100k

* Transistor
Q1 NC NB NE 2N3904

.ac dec 100 1 10Meg
.tran 0 5m 0 1u
.save V(IN) V(OUT) V(NC) V(NB)
.end
```

---

## 555 astable (oscillator)

```
* NE555 astable; T1 = 0.693*(R1+R2)*C1, T2 = 0.693*R2*C1
V1 VCC 0 5

R1 VCC  NDIS 10k
R2 NDIS NTHR 10k
C1 NTHR 0    10n
CB CTRL 0    10n         ; bypass on control pin

* NE555 subcircuit — if not in library, use the behavioral model from references
XU1 NTHR NDIS OUT 0 CTRL NTHR VCC VCC NE555

* Load
RL OUT 0 1k

.tran 0 1m 0 100n
.save V(OUT) V(NTHR)
.end
```

If `NE555` is not in the user's LTspice install, emit a behavioral subckt using two comparators (E-sources), an SR latch (behavioral B-source), and a discharge transistor — and comment the reference to where the user can drop in a vendor model.

---

## Buck converter (simplified, open-loop)

```
* Buck converter, Vin=12 → Vout~5, fsw=100kHz, D=0.42
V1 VIN 0 12
Vg  NG  0 PULSE(0 10 0 10n 10n 4.2u 10u)   ; gate drive, 42% duty

M1 VIN NG NSW NSW IRF540                    ; high-side switch
D1 0   NSW 1N5819                           ; catch diode
L1 NSW NOUT 100u
C1 NOUT 0   220u
RL NOUT 0   5                               ; 1A load

.tran 0 2m 1m 100n
.save V(VIN) V(NOUT) V(NSW) I(L1)
.end
```

Note the `Tstart=1m` in `.tran` — throws away startup transient so the plot shows steady-state ripple.

---

## Diode bridge rectifier + reservoir cap

```
V1 NAC 0 SINE(0 15 60)

D1 NAC  NP 1N4001
D2 0    NP 1N4001
D3 NN   NAC 1N4001
D4 NN   0   1N4001

C1 NP  NN 470u
RL NP  NN 100

.tran 0 100m 0 100u
.save V(NP) V(NN) V(NAC)
.end
```

---

## Differential pair (BJT long-tailed pair)

```
V1 VCC 0 15
V2 VEE 0 -15

Iee NEE VEE DC 1m          ; tail current
RC1 VCC NC1 10k
RC2 VCC NC2 10k
Q1  NC1 INP NEE 2N3904
Q2  NC2 INN NEE 2N3904

V3 INP 0 AC 0.5 SINE(0 0.005 1k)
V4 INN 0 AC -0.5

.ac dec 100 1 10Meg
.save V(NC1) V(NC2) V(INP) V(INN)
.end
```

---

## Optocoupler digital input isolation (NPN driver + PC817 + P-ch MOSFET output)

A common industrial pattern: a 5 V logic signal drives an optocoupler LED through an NPN transistor; the phototransistor output controls a P-channel MOSFET on an isolated 24 V rail.

```spice
* Optocoupler digital input isolation
* 5V logic (GND domain) → PC817D → P-ch switch → 24V load (GND_OUT domain)
* GND and GND_OUT share no common node — the isolation barrier is inside the optocoupler.

* --- Sources ---
V5B    PWR5B   0        DC 5
V24    PWR24B  GND_OUT  DC 24
VDIN   DIN     0        PULSE(0 5 0 10n 10n 500u 1m)   ; 1kHz logic pulse

* --- Input stage: DIN → R1/R2 base divider → NPN → LED chain ---
R1     DIN      N_BASE  10k
R2     N_BASE   0       10k
QNP    N_COLL   N_BASE  0   BC547B   ; NPN, C B E — library model

* LED chain: PWR5B → LED → R_series → optocoupler anode
R_LED  PWR5B    N_LED_A  330         ; sets IF ≈ 5mA at Vf~1.2V LED + Vce_sat
DA1_LED N_LED_A N_LED_K  ...         ; LED inside optocoupler (or use subckt below)
R4     N_LED_K  N_COLL   18

* --- Optocoupler: use LTspice built-in PC817D if available ---
* Option A — LTspice library (preferred):
*   XDA1 N_LED_A N_LED_K N_OPT_C GND_OUT PC817 Igain=3.4m
*   (Igain encodes CTR grade: A=1m B=1.5m C=2.3m D=3.4m)
*
* Option B — custom model (when PC817 not in lib.zip, e.g. different LTspice version):
XDA1   N_LED_A  N_LED_K  N_OPT_C  GND_OUT  HCPL817

* --- Output stage: 24V / GND_OUT domain ---
R7     PWR24B   N_GATE   10k        ; pull gate high → P-ch OFF by default
R6     N_OPT_C  N_GATE   100        ; opto collector drives gate low to turn P-ch ON
MVP    DOUTA    N_GATE   PWR24B  PWR24B  IRF9540   ; P-ch: D G S Bulk
C2     PWR24B   GND_OUT  100n       ; supply decoupling
RLOAD  DOUTA    GND_OUT  1Meg       ; dummy load — keeps DOUTA defined when MVP is off

* --- Custom optocoupler model (Option B) ---
* Use Rsense + VCCS instead of Vsense + CCCS to avoid floating internal node.
* CTR = 300% min → Gm = CTR / Rsense = 3.0 / 0.001 = 3000
.subckt HCPL817 A K C E
DLED    A   N_K  HCPL817_LED
Rsense  N_K K    1m               ; 1mΩ sense: V(N_K,K) = I_LED × 1e-3
G1      C   E    N_K  K   3000    ; VCCS: I(C→E) = 3000 × V(N_K,K) = 3 × I_LED
DCBE    E   C    HCPL817_CLM      ; reverse-clamp (prevents negative Ic)
Ciso    A   E    0.5p             ; isolation capacitance typ
Rleak   K   E    100Meg           ; DC path for node K (>10^9Ω physically)
.model HCPL817_LED D(Is=1e-25 N=1.7 Rs=10 BV=6 Vj=0.75)
.model HCPL817_CLM D(Is=1e-14 N=1 Rs=1)
.ends HCPL817

* IRF9540 P-ch (not in LTspice 26 lib.zip — embed required)
.model IRF9540 PMOS(Level=3 Gamma=0 Delta=0 Eta=0 Theta=0 Kappa=0.2 Vmax=0 Xj=0
+ Tox=97.5n Uo=157 Phi=0.6 Rs=0.7017m Kp=10.15u W=0.35 L=2u Vto=-3.93
+ Rd=0.3571 Rds=1.667Meg Cbd=3.229n Pb=0.8 Mj=0.5 Fc=0.5
+ Cgso=9.027e-9 Cgdo=2.071e-10 Is=0.3456p N=1 Tt=880n)

* --- Analysis ---
.tran 0 5m 0 1u         ; 5ms = 5 cycles, maxstep 1µs
.op
.options gmin=1e-10 abstol=1e-9
.save V(DIN) V(N_BASE) V(N_COLL) V(N_LED_A) V(N_LED_K) V(N_OPT_C) V(N_GATE) V(DOUTA)
.end
```

**Key design notes for this topology:**
- `GND` and `GND_OUT` must never share a node — all components must be on one side of the barrier.
- The P-ch gate pull-up (R7) ensures the output is **off by default** (fail-safe) when the LED is dark.
- `RLOAD` (1 MΩ) is not a real circuit component — it gives `DOUTA` a DC return path for `.op` / `.tran` startup. Remove or replace with the real load.
- If using the LTspice PC817 subcircuit (Option A), delete the custom `.subckt HCPL817` block entirely.
- LTspice `.asc` placement: use `SYMBOL Optos/PC817D sx sy R0` with pin offsets A=(-96,-48), K=(-96,+48), C=(+96,-48), E=(+96,+48) relative to symbol center.

