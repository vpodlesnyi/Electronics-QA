# MCP Tools Reference

All tools available to this skill with signatures, return values, and usage context.

---

## JLCPCB / LCSC Database Tools

### jlc_get_part
**Purpose:** Get full details for a specific part by LCSC code or MPN.
```
jlc_get_part(lcsc="C7950")        # by LCSC code
jlc_get_part(mpn="LM358DR")       # by MPN — searches local DB
```
**Returns:** Description, pricing tiers, datasheet URL, component attributes,
EasyEDA footprint availability, library type (basic/preferred/extended).
**When:** Phase 1 (reference profiling), Phase 3.4 (cross-referencing new candidates).
**Note:** The `lcsc` code returned here is needed for `jlc_find_alternatives`.

### jlc_find_alternatives
**Purpose:** Find alternative parts similar to a given LCSC component.
```
jlc_find_alternatives(
    lcsc="C7950",
    same_package=True,         # only same package
    min_stock=500,             # minimum stock
    library_type="no_fee",     # basic or preferred (no assembly fee)
    limit=20                   # max alternatives
)
```
**Returns:** Original part info + list of alternatives sorted by stock.
**When:** Phase 2.2 — after obtaining LCSC code from Phase 1.

### jlc_search
**Purpose:** Fast parametric search with natural language + spec filters.
```
jlc_search(
    query="n-channel mosfet",
    subcategory_name="MOSFETs",
    package="SOT-23",
    spec_filters=[
        {"name": "Vds", "op": ">=", "value": "30V"},
        {"name": "Vgs(th)", "op": "<=", "value": "2.5V"}
    ],
    min_stock=500,
    library_type="no_fee",
    sort_by="stock",           # or "price"
    limit=50
)
```
**Returns:** Matching components with specs, total count, filters applied.
**When:** Phase 2.1 (second-source search by base number), Phase 2.3 (parametric search).

### jlc_search_help
**Purpose:** Browse categories and discover filterable attributes.
```
jlc_search_help()                           # list all categories
jlc_search_help(category="Transistors")     # list subcategories
jlc_search_help(subcategory="MOSFETs")      # list filterable attributes
```
**Returns:** Categories/subcategories with part counts, or filterable attributes
with names, aliases, types, and example values.
**When:** Phase 2.3 — before building parametric searches.

### jlc_get_pinout
**Purpose:** Get pin mapping from EasyEDA symbol data.
```
jlc_get_pinout(lcsc="C7950")
```
**Returns:** Pin count, list of pins with number/name/electrical type, symbol UUID.
**When:** Phase 2.6 — IC pinout verification.

### jlc_stock_check
**Purpose:** Real-time stock verification via live JLCPCB API.
```
jlc_stock_check(query="LM358", min_stock=0, limit=20)
```
**Returns:** Results with live stock data and pagination.
**When:** Final stock verification before generating report. Also useful for finding
out-of-stock or low-stock parts (min_stock=0).
**Note:** Slower than jlc_search. Use jlc_search for most queries.

---

## Distributor Cross-Reference Tools

### mouser_get_part
**Purpose:** Full Mouser lookup with detailed attributes.
```
mouser_get_part(part_number="LM358DR")
mouser_get_part(part_number="LM358DR|AO3400|STM32F103C8T6")  # batch, up to 10
```
**Returns:** All attributes (lifecycle, RoHS, temp range), pricing tiers,
availability, datasheet link.
**When:** Phase 1 (reference profiling), Phase 3.4 (cross-referencing).
**Tip:** Use pipe-delimited batch lookup for efficiency on large lists.

### digikey_get_part
**Purpose:** Full DigiKey lookup with comprehensive parameters.
```
digikey_get_part(product_number="LM358DR")
```
**Returns:** Comprehensive parameters, pricing, availability, datasheet URL.
**When:** Phase 1 (reference profiling), Phase 3.4 (cross-referencing).

---

## ECAD & Reference Design Tools

### cse_search
**Purpose:** Search ComponentSearchEngine for ECAD models and datasheets.
```
cse_search(query="LM358DR", limit=5)
```
**Returns:** Parts with MPN, manufacturer, description, datasheet_url,
has_model, has_3d, image_url.
**When:** Phase 1 (getting product images and datasheets).
**Warning:** Slow (up to 45s). Don't use for general part search.

### board_search
**Purpose:** Find open-source hardware boards using a specific component.
```
board_search(component="LM358")
board_search(component="STM32F103", tag="motor-control")
```
**Returns:** Matching boards with details. When 2+ boards share the IC,
includes cross-board consensus on decoupling, pin connections.
**When:** Phase 2.5 — understanding real-world usage context.

### sensor_recommend
**Purpose:** Recommend sensor ICs and modules for a measurement need.
```
sensor_recommend(query="BME280", measure="temperature", protocol="i2c")
```
**Returns:** Sensors sorted by platform support, with datasheets and specs.
**When:** Phase 2.4 — only for sensor component alternatives.

---

## Web Tools

### WebSearch
**Purpose:** General web search.
**When:** Phases 1–4 for manufacturer sites, cross-references, datasheets, PCN notices.
**Query patterns:** See `references/search-strategies.md`.

### WebFetch
**Purpose:** Fetch and read web page content (including PDFs and images).
**When:** Phases 1–4 for reading product pages, datasheets, and product images.

---

## Efficiency Tips

- **Parallel execution:** In Phase 1.1, run jlc_get_part + mouser_get_part +
  digikey_get_part + cse_search simultaneously for each MPN.
- **Mouser batching:** Use pipe-delimited format for up to 10 MPNs at once.
- **jlc_search vs jlc_stock_check:** Prefer jlc_search (faster, supports filters).
  Only use jlc_stock_check for real-time verification or out-of-stock parts.
- **cse_search is slow:** Only use when you specifically need product images or
  ECAD model info. Don't use for general part searches.
- **API quotas:** Mouser and DigiKey have daily quotas. If you hit a limit, fall back
  to web search on the distributor's site.
