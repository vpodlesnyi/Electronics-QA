# Search Strategies by Phase

Detailed query patterns and strategies for each search phase.

---

## Phase 2.1 — Second-Source Search Strategies

The goal is to find the exact same component from a different manufacturer.

### Strategy A: Industry-Standard Base Number

Many components have a standard designation used by multiple manufacturers. Strip the
manufacturer-specific suffix/prefix to get the base number, then search broadly.

**Examples of base numbers and their second-sources:**

| Base Number | Manufacturers |
|---|---|
| LM358 | TI, ON Semi, STMicro, Diodes Inc., Runic, HGSEMI |
| NE555 | TI, ON Semi, STMicro, Diodes Inc., HGSEMI |
| LM7805 | TI, ON Semi, STMicro, Diodes Inc., UTC |
| 1N4148 | ON Semi, Nexperia, Vishay, Diodes Inc. |
| 2N2222 | ON Semi, Nexperia, Central Semi |
| LM317 | TI, ON Semi, STMicro, Diodes Inc. |
| TL431 | TI, ON Semi, STMicro, Diodes Inc. |
| STM32F103 | STMicro (also clones: GD32F103, APM32F103, CH32F103) |

**How to extract the base number:**
- Remove package suffix: LM358**DR** → LM358, NE555**P** → NE555
- Remove manufacturer prefix: **SN**74HC595 → 74HC595
- Remove temperature grade suffix: STM32F103C8**T6** → STM32F103C8
- For 74xx logic: keep the family (HC, HCT, LVC) as it determines I/O levels

**MCP query:**
```
jlc_search(query="[base number]", package="[same package]", sort_by="stock", limit=50)
```
Then filter results to parts from different manufacturers.

**Web query:**
```
WebSearch: "[base number]" cross reference equivalent -"[original manufacturer]"
WebSearch: "[base number]" alternative manufacturer
```

### Strategy B: Distributor Cross-Reference Pages

Some distributors offer explicit cross-reference tools:

```
WebSearch: "[MPN]" cross reference site:mouser.com
WebSearch: "[MPN]" cross reference site:digikey.com
WebSearch: "[MPN]" alternative site:octopart.com
WebSearch: "[MPN]" equivalent site:lcsc.com
```

### Strategy C: Manufacturer Cross-Reference Tools

Major semiconductor manufacturers publish their own cross-reference databases:

```
WebSearch: "[MPN]" site:ti.com cross-reference
WebSearch: "[MPN]" replacement site:onsemi.com
WebSearch: "[MPN]" alternative site:st.com
WebSearch: "[MPN]" site:diodes.com parametric-search
```

Also check if the original manufacturer's product page lists recommended replacements
(common for discontinued parts).

### Strategy D: MCU/SoC Clone Families

Some popular MCUs have licensed clones with different MPNs but identical peripherals
and pin mappings:

| Original | Common Clones |
|---|---|
| STM32F103 | GD32F103 (GigaDevice), APM32F103 (Geehy), CH32F103 (WCH) |
| STM32F030 | GD32F030, APM32F030 |
| STM32F401 | APM32F401 |
| ESP8266 | (generally single-source, but modules vary) |
| ATmega328P | LGT8F328P (Logic Green) |

```
WebSearch: "[MCU part number]" compatible clone alternative
```

---

## Phase 2.3 — Parametric Search Strategies

### Relaxation Rules

When building parametric searches, relax filters slightly to catch near-matches:

| Parameter | Reference Value | Search Filter |
|---|---|---|
| Vds | 30V | ≥ 25V (–15%) |
| Vgs(th) | 1.0–2.5V | ≤ 3.0V (+20%) |
| Id | 2A | ≥ 1.5A (–25%) |
| Capacitance | 100nF | search 100nF exact (tolerance handles variation) |
| Resistance | 10kΩ | search 10kΩ exact |
| Voltage rating | 50V | ≥ 50V (equal or higher — never lower) |
| Current rating | 1A | ≥ 0.8A (–20%) |
| Temperature | –40 to +85°C | ≥ +85°C max (equal or higher) |

**Safety-critical parameters** (voltage ratings, isolation, current limits) should
never be relaxed below the reference value — only equal or higher.

### Category-Specific Search Tips

**Capacitors:** Always include dielectric type. X7R ≠ Y5V in stability. C0G/NP0
for precision circuits.

**MOSFETs:** Vgs(th) is the trickiest parameter — too low causes false turn-on,
too high prevents the gate driver from fully enhancing. Match the range, not just max.

**Op-amps:** GBW and slew rate matter most in signal-path applications. For power
supply decoupling (e.g., reference buffers), quiescent current and PSRR matter more.

**Regulators:** Dropout voltage is the key LDO parameter. For switching regulators,
efficiency and switching frequency are more important than max output current.

---

## Phase 3.1 — Distributor Website Queries

### Octopart (aggregator)
Best for: broad cross-distributor search, seeing all manufacturers of a standard part.
```
WebSearch: [component description] [key parameter] site:octopart.com
WebSearch: [base part number] specifications site:octopart.com
```

### DigiKey
Best for: deep parametric search, comprehensive datasheets.
```
WebSearch: [component type] [parameter] [package] site:digikey.com
```

### Mouser
Best for: lifecycle data, detailed attributes, batch lookup.
```
WebSearch: [MPN] cross reference site:mouser.com
WebSearch: [component type] [parameter] site:mouser.com
```

### Farnell / element14
Best for: European sourcing, RS/Farnell-only brands.
```
WebSearch: [component description] [parameters] site:farnell.com
WebSearch: [MPN] equivalent site:element14.com
```

### LCSC (web, beyond API)
Best for: Chinese-market parts, JLCPCB assembly candidates, competitive pricing.
```
WebSearch: [component type] [parameters] site:lcsc.com
```

---

## Phase 3.2 — Manufacturer Replacement Searches

### Product Change Notifications (PCN)
```
WebSearch: "[MPN]" "product change notification" site:[manufacturer domain]
WebSearch: "[MPN]" "end of life" "recommended replacement" site:[manufacturer domain]
WebSearch: "[MPN]" "last time buy" replacement
```

### Migration Guides
```
WebSearch: "[MPN]" migration guide site:[manufacturer domain]
WebSearch: "[old MPN]" to "[candidate MPN]" migration
WebSearch: "[MPN]" application note replacement
```

---

## Phase 3.3 — Image Comparison Guidance

### When Image Comparison is Essential
- **Connectors**: pitch, housing shape, retention features, keying
- **Modules**: board outline, antenna placement, pin header positions
- **Switches/buttons**: actuator height, travel, mounting holes
- **Power inductors**: shielding, physical height profile
- **Heatsinks and thermal**: mounting hole pattern, fin orientation

### What to Compare
1. **Overall outline and dimensions** — Same form factor?
2. **Pin/terminal arrangement** — Same positions and spacing?
3. **Mounting style** — Same type (SMD vs THT, vertical vs right-angle)?
4. **Notable features** — Keying, locking tabs, color coding
5. **Marking/labeling** — Confirms part identity

### Visual Match Classification
- **Visually identical** — Same shape, same pin layout, dimensions match
- **Similar form factor** — Same general shape but minor differences (e.g.,
  slightly different housing height, different terminal style)
- **Different appearance** — Clearly different form factor — needs engineer
  review to confirm mechanical compatibility
