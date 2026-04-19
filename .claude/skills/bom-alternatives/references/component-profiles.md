# Component Profile Fields by Type

When building the reference profile in Phase 1.3, collect these fields based on
the component category. The universal fields apply to every component; add the
type-specific fields on top.

## Universal Fields (all components)

| Field | Description | Example |
|---|---|---|
| MPN | Manufacturer Part Number as received | LM358DR |
| Manufacturer | | Texas Instruments |
| Category | Component type | Op-Amp |
| Subcategory | More specific classification | Dual Op-Amp |
| Package / Footprint | Physical package | SOIC-8 |
| Pin Count | Number of pins | 8 |
| Lifecycle Status | Active / NRND / EOL / Discontinued | Active |
| RoHS Compliant | Yes / No / Unknown | Yes |
| Operating Temp Range | Min to max | –40°C to +85°C |
| Datasheet URL | Direct link to PDF | |
| Product Image URL | From distributor or cse_search | |
| LCSC Part Code | Needed for jlc_find_alternatives | C7950 |

---

## Passive Components

### Resistors
- Resistance value + units (10kΩ)
- Tolerance (±1%, ±5%)
- Power rating (0.1W, 0.25W)
- Voltage rating (max working voltage)
- Temperature coefficient (±100ppm/°C)
- Resistor type (thick film, thin film, wirewound)

### Capacitors
- Capacitance value + units (100nF, 10µF)
- Tolerance (±10%, ±20%)
- Voltage rating (16V, 50V)
- Dielectric type (C0G/NP0, X5R, X7R, X7S, Y5V) — critical for matching
- ESR (equivalent series resistance)
- Ripple current rating (for electrolytics)
- Capacitance vs temperature/voltage derating characteristics

### Inductors
- Inductance value + units (10µH, 4.7µH)
- Tolerance (±20%)
- DC resistance (DCR)
- Saturation current (Isat) — current at which inductance drops by a defined %
- Rated current (Irms) — thermal limit
- Self-resonant frequency (SRF)
- Shielding (shielded / unshielded)
- Inductor type (multilayer, wirewound, molded)

---

## Semiconductors

### MOSFETs
- Channel type (N-channel / P-channel)
- Vds (drain-source voltage) — absolute max
- Vgs(th) (gate threshold voltage) — min/max
- Id (continuous drain current)
- Rds(on) (on-resistance) — at specified Vgs
- Qg (total gate charge)
- Ciss, Coss, Crss (input, output, reverse transfer capacitance)
- Body diode: Vsd, Is
- Turn-on/turn-off times

### BJTs
- Type (NPN / PNP)
- Vceo (collector-emitter voltage)
- Ic (collector current)
- hFE / β (current gain) — min/max at specified Ic
- fT (transition frequency)
- Vce(sat) (saturation voltage)
- Pd (power dissipation)

### Diodes
- Type (Rectifier, Schottky, Zener, TVS, LED)
- Vr (reverse voltage) / Vz (zener voltage)
- If (forward current)
- Vf (forward voltage) — at specified If
- Ir (reverse leakage current)
- trr (reverse recovery time) — for switching applications
- Capacitance (Cj)
- Clamping voltage (for TVS)

---

## Integrated Circuits

### Op-Amps / Amplifiers
- Supply voltage range (single/dual)
- Number of channels (single, dual, quad)
- GBW (gain-bandwidth product)
- Slew rate
- Input offset voltage
- Input bias current
- CMRR (common-mode rejection ratio)
- PSRR (power supply rejection ratio)
- Output current drive
- Rail-to-rail input/output capability
- Quiescent current

### Voltage Regulators (LDO / Switching)
- Input voltage range
- Output voltage (fixed or adjustable + range)
- Output current (max)
- Dropout voltage (for LDOs)
- Quiescent current / ground current
- Line/load regulation
- Output noise
- Switching frequency (for switching regulators)
- Efficiency curves
- Shutdown/enable pin
- Soft-start
- Protection features (OCP, OTP, UVLO)

### MCUs / Microcontrollers
- Core architecture (ARM Cortex-M0/M3/M4/M7, RISC-V, etc.)
- Flash memory size
- RAM size
- Clock speed (max)
- I/O count (GPIO)
- Peripherals: UART, SPI, I2C, USB, CAN, ADC, DAC, timers, PWM, DMA
- ADC resolution and channels
- Supply voltage range
- Low-power modes and consumption

### Logic ICs (74xx, etc.)
- Logic family (HC, HCT, LVC, AHC, etc.)
- Function (AND, OR, NAND, buffer, mux, flip-flop, etc.)
- Supply voltage range
- Propagation delay
- Input/output compatibility (CMOS/TTL levels)
- Output drive current
- Schmitt trigger input (yes/no)

---

## Connectors & Electromechanical

### Connectors
- Connector type (header, socket, USB, FPC/FFC, terminal block, barrel jack, etc.)
- Pitch (1.0mm, 1.27mm, 2.0mm, 2.54mm, etc.)
- Number of positions / pins
- Number of rows
- Gender (male/female/hermaphroditic)
- Mating type and mating part number — critical for compatibility
- Orientation (vertical, right-angle, SMD, THT)
- Current rating per contact
- Voltage rating
- Contact material / plating
- Housing material and color
- Locking mechanism (yes/no, type)
- Physical dimensions (L × W × H, mating height)
- Operating temperature range

### Switches & Buttons
- Switch type (tactile, toggle, slide, rocker, DIP)
- Circuit configuration (SPST, SPDT, DPDT, etc.)
- Actuator type and height
- Travel distance and force
- Contact rating (current, voltage)
- Mounting type (SMD, THT, panel-mount)
- Lifespan (number of operations)
- Physical dimensions

### Relays
- Coil voltage and current
- Contact configuration (SPST-NO, SPDT, DPDT, etc.)
- Contact rating (resistive, inductive loads)
- Operate/release time
- Isolation voltage
- Coil resistance
- Physical dimensions and pin pitch

---

## How to Use This Reference

1. Identify the component category from Phase 1.1 API results
2. Collect all universal fields first
3. Add every applicable type-specific field
4. When a field cannot be determined from any source, mark it as "Unknown" rather
   than omitting it — this prevents falsely matching an alternative that differs on
   an unmeasured parameter
5. For the comparison in Phase 4.2, only parameters that appear in the reference
   profile can be compared — so completeness here directly affects match quality
