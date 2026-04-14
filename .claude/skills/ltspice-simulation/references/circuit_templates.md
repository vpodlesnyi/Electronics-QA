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
