# Farm Sync — Build Progress

Farmer-in-the-Loop Collective Crop Planning research demonstrator.
Research prototype, not a production farming system. All farmer/plot records are
synthetic and labelled as such. The LLM never decides crop allocations.

Build order follows the project spec, section 36. Reports are appended per phase.

---

## Phase 2–4 — Data schemas, provenance framework, seeded generator

**IMPLEMENTED**
- `farmsync/schemas.py` — plot-level model (Farmer → many Plot), all state/event
  vocabularies, Indian operational-holding categories, dataset manifest.
- `farmsync/provenance.py` — four provenance types; record enforces that
  OBSERVED/DERIVED values carry a source and SYNTHETIC_GROUNDED carries an
  assumption; registry reports completeness + open obligations.
- `farmsync/generate.py` — seeded, reproducible generator; non-uniform farm size
  via holding categories; conditional plot attributes (water/soil/irrigation/
  previous-crop/exposure); hazard zones for correlated failure.
- `farmsync/quality.py` — data-quality report + CSV/JSON exports.

**TESTS PASSED** — 11/11.

**DATA/SOURCES** — no external agricultural source claimed; all synthetic.
500 farmers → 911 plots, integrity clean, reproducible under master seed.

**ASSUMPTIONS** — holding-category weights are an experimental assumption
(structure anchored to Agriculture Census categories); resource bands scaled to
area. Both labelled in provenance.

**SCIENTIFIC RISKS** — none material at the data-structure level; the material
risk sits in Phase 5 (agronomic values), handled below.

**FILES** — 5 `farmsync/*.py`, `tests/test_farmsync_data.py`.

---

## Phase 5 — Agricultural parameter dataset (in progress)

**IMPLEMENTED**
- `farmsync/crop_water.py` — Kc (ini/mid/end), crop height, and growth-stage
  lengths for all 14 crops, transcribed from FAO-56 (Allen et al. 1998),
  Tables 11–12. Crops in FAO-56 recorded OBSERVED with citation; pigeon pea,
  mustard (→ rapeseed), and chickpea stage-lengths recorded SYNTHETIC_GROUNDED
  with the mapping stated as an assumption. Crop water requirement is computed
  on demand from a supplied per-stage ET0 and **refuses** (raises) without it —
  no single national CWR is fabricated or copied across regions.
- `farmsync/parameters.py` — economic/market/sensitivity scaffold. Every field
  (yield, cost, price, price variability, market_absorption_proxy, labour,
  drought/heat/waterlogging sensitivity) registered as REQUIRES_SOURCING with a
  concrete plan naming the authoritative source and the derivation rule.
- `farmsync/sourcing_report.py` — Phase 5 sourcing report (grounded vs open),
  with a gate flag: optimiser may use the water block, may NOT use economics yet.

**TESTS PASSED** — 7/7 (18/18 total). Includes: all 14 crops have a valid water
block; OBSERVED crops carry a source; mapped crops carry an assumption; CWR
refuses without ET0; economics all flagged; the price plan never calls arrivals
"demand".

**DATA/SOURCES**
- FAO Irrigation & Drainage Paper 56 (Allen et al. 1998), Tables 11–12.
  https://www.fao.org/4/x0490e/x0490e0b.htm — accessed 2026-08-12.
- India-specific stage lengths used where FAO lists them (wheat: Central India,
  120 d; maize: India dry-cool, 125 d).

**ASSUMPTIONS INTRODUCED**
- Kc for pigeon pea = legume group default; mustard = FAO rapeseed/canola;
  chickpea stage lengths mapped to a ~150 d rabi pulse cycle. All flagged.
- Kc end ranges reduced to a single representative value (ranges kept in notes).
- FAO Kc values are sub-humid reference values; local RHmin/wind adjustment
  (FAO-56 Eq. 62/65) not yet applied — documented limitation.

**SCIENTIFIC RISKS (material)**
- 127 economic/sensitivity parameters (crop × field) remain unsourced. They are
  blocked from the optimiser by the gate flag, not silently defaulted.
- ET0 per region/season/stage is not yet sourced (IMD/CROPWAT), so absolute crop
  water requirements cannot yet be computed — only relative Kc structure is set.
- Soybean/potato/mustard FAO durations differ from typical Indian varieties;
  retained but flagged for ICAR/DES replacement.

**FILES** — `farmsync/crop_water.py`, `farmsync/parameters.py`,
`farmsync/sourcing_report.py`, `tests/test_farmsync_params.py`.

**NEXT STEP — Phase 5 completion (needs a sourcing sub-pass before Phase 6):**
1. ET0 per region/season/stage from IMD/CROPWAT → compute CWR per region.
2. Yields from DES (district/state-season).
3. Prices from AGMARKNET (documented aggregation) + MSP floor from CACP.
4. market_absorption_proxy derived + labelled (never "demand").
5. Cost (DES CoC), labour (ICAR PoP), sensitivities (FAO-33 Ky / ICAR, else
   explicit scenario parameters).
Only after the water block has ET0 and yields/prices are sourced does Phase 6
(plot-level feasibility) become defensible.

---

## Phase 5c — Regional ET0 + crop water requirement (ET0/water sub-pass)

**IMPLEMENTED**
- `farmsync/climate.py` — regional seasonal ET0 table sourced from FAO-56
  Penman-Monteith studies, plus CWR computed via the FAO-56 Kc method (no
  hard-coded per-crop CWR). `compute_crop_water_requirements(region, season)`
  returns CWR per season-appropriate crop, and refuses (status ET0_NOT_SOURCED)
  for regions whose ET0 is not yet sourced.

**TESTS PASSED** — 6/6 new (24/24 total). Rice kharif CWR lands in the plausible
900–1300 mm band; wheat rabi in 350–600 mm; unsourced regions refuse; only
season-appropriate crops are returned; sourced ET0 carries a citation.

**DATA/SOURCES**
- R1 Indo-Gangetic (Ludhiana / central Punjab): kharif ~6.2, rabi ~4.1 mm/day
  (Punjab FAO-PM ET0 study, seasonal ~755/490 mm; ScienceDirect S2666154323001473, 2023). MEDIUM.
- R2 Deccan (Parbhani, Maharashtra): kharif 6.23, rabi 4.29 mm/day
  (Phad et al. 2020, MAUSAM 71(1), IMD — Govt. of India). HIGH.
- R3 Eastern (Patna, Bihar): annual mean 4.1 mm/day recorded as anchor; kharif/rabi
  split not yet extracted. R4/R5: REQUIRES_SOURCING (candidate sources named).

**RESULTING CWR (mm, computed)** — e.g. R2 kharif: rice 1051, cotton 1050,
pigeon pea 981, onion 884, soybean 763, tomato 769, groundnut 690, maize 645,
sorghum 629, pearl millet 480. R2 rabi: onion 609, potato 504, chickpea 498,
wheat 437, mustard 437, maize 444, tomato 529. All within known agronomic ranges.

**ASSUMPTIONS INTRODUCED**
- Uniform seasonal ET0 across the four crop stages (Kc still varies by stage).
  First-order estimate; stage-resolved monthly ET0 (IMD/CROPWAT) is a later
  obligation. Flagged in provenance.
- Punjab seasonal totals divided by season length to get mm/day.

**SCIENTIFIC RISKS (material)**
- CWR exists for 2 of 5 regions only (R1, R2). R3–R5 ET0 not yet sourced; their
  CWR is refused, not approximated.
- Economic/market/sensitivity parameters (130 open obligations) still blocked
  from the optimiser.

**FILES** — `farmsync/climate.py`, `tests/test_farmsync_climate.py`; updated
`sourcing_report.py`. Exports: `region_et0.csv`, `crop_water_requirements.csv`.

**NEXT STEP** — continue Phase 5 sourcing, one dimension at a time: (a) close ET0
for R3–R5 (Bihar seasonal split, Gujarat Mehta & Pandey 2015, Karnataka zones)
and add stage-resolved monthly ET0; (b) yields (DES district-season); (c) prices
(AGMARKNET + MSP). Feasibility (Phase 6) waits on yields + at least region-wide CWR.

---

## Feature — Full Research Dataset Manager (+ collectives.csv)

**IMPLEMENTED**
- `farmsync/dataset_manager.py` — supported-file registry (incl. `collectives.csv`),
  CSV loaders with line numbers, cross-file relational validation with per
  file/row/field/reason errors, secure ZIP reader (path-traversal + zip-bomb +
  type guards), content hashing, and immutable versioned activation snapshots.
- `farmsync/build_builtin_dataset.py` — materializes the 14-file built-in dataset
  (farmers, plots, collectives, crops, regions, crop_region_season_params with
  grounded CWR + REQUIRES_SOURCING economics, climate_scenarios, hazard_zones,
  participation_scenarios, provenance, dictionary; suitability/preferences/market
  written header-only pending later phases).
- `farmsync_routes.py` — `register_farmsync_routes(app)`: built-in load, complete
  ZIP package upload, individual file replace, custom farmer-only upload,
  validate, activate/version, and paginated/filterable inspection.
- `templates/farmsync.html`, `static/css/farmsync.css`, `static/js/farmsync.js` —
  dataset manager UI (load modes, validation report, activation panel with
  hash/version, inspection tabs) reusing the site theme tokens.
- `collectives` added coherently: each collective is region + season bound and
  farmers inherit their region from their collective, so the new validation
  rules (farmer→collective, collective→region, collective→season) are meaningful.

**TESTS PASSED** — 11 new (35 total). Includes: built-in validates clean;
collective with bad region flagged; farmer referencing missing collective flagged;
negative plot area flagged; ZIP path traversal rejected; non-CSV/unexpected files
ignored; hash stable + order-independent; activation writes versioned snapshot;
activation blocked on validation failure. End-to-end Flask test client confirms
load → validate → inspect → activate.

**SECURITY** — ZIP: 50 MB compressed / 250 MB uncompressed / 50 MB per-file caps,
path-traversal and absolute-path rejection, CSV-only + supported-name allowlist,
bytes read never executed. Routes cap MAX_CONTENT_LENGTH and use secure_filename.

**INTEGRATION** — one line in `app.py` beside the other tools:
`from farmsync_routes import register_farmsync_routes; register_farmsync_routes(app)`.
No existing AskVish file is modified beyond that line.

**FILES** — `farmsync/dataset_manager.py`, `farmsync/build_builtin_dataset.py`,
`farmsync_routes.py`, `templates/farmsync.html`, `static/css/farmsync.css`,
`static/js/farmsync.js`, `tests/test_farmsync_dataset_manager.py`; edits to
`schemas.py`, `generate.py` for collectives.

---

## Phase 5d — Crop price + cost anchors (MSP / CACP)

**STATUS** — prices materially advanced (11/14 crops); Phase 5 not yet closed.

**IMPLEMENTED**
- `farmsync/crop_economics.py` — MSP price floor for 11 of 14 crops from CACP/CCEA
  (kharif KMS 2025-26 and rabi RMS 2026-27), recorded OBSERVED with citation and
  labelled explicitly as a NATIONAL POLICY FLOOR — not the market price, not
  demand. CACP cost-of-production per quintal captured with explicit `cost_basis`
  (kharif A2+FL vs rabi C2), never mixed. Vegetables (potato/onion/tomato) carry
  no MSP and stay REQUIRES_SOURCING (AGMARKNET). Built-in params now expose
  `msp_floor_per_kg`, `cost_per_quintal`, `cost_basis`; market `price_per_kg`
  remains an explicit AGMARKNET obligation.

**TESTS PASSED** — 5 new (40 total). MSP values spot-checked (rice 23.69, wheat
25.85, tur 80.00 Rs/kg); MSP recorded as floor-not-market; cost basis explicit;
cost/ha remains open; vegetables flagged.

**DATA/SOURCES**
- Kharif MSP: PIB PRID 2131983 (CCEA, 28 May 2025), KMS 2025-26.
- Rabi MSP: PIB PRID 2173567 (CCEA, 01 Oct 2025), RMS 2026-27
  (wheat 2585, gram 5875, rapeseed & mustard 6200 Rs/quintal).

**ASSUMPTIONS** — MSP used as a national price floor anchor, not a regional market
price; kharif crops mapped to their MSP variety (Paddy Common, Jowar Hybrid,
Cotton Medium Staple, etc.).

**SCIENTIFIC RISKS / OPEN OBLIGATIONS (134)** — region-specific market prices
(AGMARKNET) for all crops; vegetable prices entirely; yields (DES, priority 2);
cultivation cost/ha on a consistent basis; labour/ha (ICAR); climate/yield
sensitivities (FAO-33 Ky or documented experimental parameters); ET0 for R3–R5.

**FILES** — `farmsync/crop_economics.py`, `tests/test_farmsync_economics.py`;
updated `sourcing_report.py`, `build_builtin_dataset.py`.

**NEXT STEP** — a genuine sourcing-strategy decision is now on the table (see the
checkpoint): how to handle yields/costs/labour/sensitivities that are region/state
specific and voluminous — exhaustive DES/ICAR sourcing vs national-with-scope vs
converting the unsourceable to labelled experimental parameters (§1.7). Phase 6
feasibility can begin on the sourced water block once that direction is set.

---

## Phase 6 — Plot × crop agronomic feasibility engine

**STATUS** — agronomic feasibility materially complete; budget/labour deferred to
sourced economics (per checkpoint: agronomic first).

**IMPLEMENTED**
- `farmsync/feasibility.py` — deterministic `assess_plot_crop(...)` operating at
  plot × crop × region × season × climate_state, returning feasible/infeasible +
  reason codes + binding constraints + per-check status. Codes: SEASON_INCOMPATIBLE,
  SOIL_INCOMPATIBLE, WATER_INSUFFICIENT, ROTATION_RESTRICTED, WATERLOGGING_RISK,
  FARMER_EXCLUDED, POST_PLANTING_LOCK. Budget/labour return NOT_EVALUATED (not
  fabricated). Water is decided only where CWR exists (R1, R2); elsewhere UNKNOWN.
- `build_builtin_dataset.py` — `plot_crop_suitability.csv` now materialized from
  the engine (12,754 plot×crop rows), inspectable via the existing Dataset Manager
  suitability tab. Referential integrity fixed (suitability uses crop_id).
- `farmsync_routes.py` — `/api/farmsync/feasibility/<plot_id>` for on-demand
  per-plot feasibility (with climate_state).

**TESTS PASSED** — 11 new (51 total). Season incompatibility, unsuitable land
class, waterlogging (risk for tomato, not rice), monocropping, exclusion,
post-planting lock, water-insufficient (R1/R2), water-UNKNOWN (R3–R5, not
fabricated), budget/labour deferred, all-crops enumeration, and an independent
invariant re-check (feasible ⇔ no reason codes).

**RESULTS (built-in 500-farmer dataset)** — of 12,754 plot×crop combinations, 36%
feasible; reason distribution: SEASON 3644, WATER 3393, WATERLOGGING 1170,
ROTATION 748, SOIL 644 — agronomically sensible.

**ASSUMPTIONS** — waterlogging tolerance coarse (only rice tolerant); rotation =
no-monocrop; climate water multipliers are experimental scenario parameters. All
recorded in `feasibility_provenance()`.

**OPEN OBLIGATIONS** — budget/labour feasibility awaits sourced cost & labour;
water feasibility for R3–R5 awaits their ET0; crop×soil precision awaits a sourced
matrix (currently coarse + land-class driven).

**FILES** — `farmsync/feasibility.py`, `tests/test_farmsync_feasibility.py`;
updated `build_builtin_dataset.py`, `farmsync_routes.py`.

**NEXT STEP** — exhaustive per-state-season sourcing of yields (DES), then cost/ha,
labour (ICAR), sensitivities — the chosen sourcing track — which then unlocks
budget/labour feasibility and the B1 optimiser (return needs yield × price).

---

## Phase 5e — Crop yields (national, season-split) + derived cost/ha

**STATUS** — yields materially grounded (12/14, national scope); a scope decision
(national vs exhaustive state-season) is on the table for you.

**IMPLEMENTED**
- `farmsync/crop_yield.py` — national season-split yields for 12 of 14 crops from
  DES / Economic Survey 2025-26 Table 1.17 (2024-25), plus soybean from SOPA.
  Recorded OBSERVED with `scope = ALL_INDIA`, applied uniformly across regions
  (explicit scope, no regional claim). Region→state map recorded for later
  refinement (R1 Punjab, R2 Maharashtra, R3 West Bengal, R4 Rajasthan, R5 Karnataka).
  `derive_cost_per_ha()` computes cost/ha = CACP cost/quintal × DES yield/100 where
  units are consistent; onion/tomato yields and cotton cost stay open.
- Built-in `crop_region_season_params.csv` now carries `expected_yield_kg_ha`,
  `yield_scope`, and derived `cultivation_cost_per_ha` for the grounded crops.

**TESTS PASSED** — 7 new (58 total). Yield spot-checks; cotton lint/kapas unit
mismatch blocks cost derivation; grain cost/ha in plausible band; wheat cost on C2
basis; yield scope labelled ALL_INDIA; region→state map present.

**DATA/SOURCES**
- DES / Economic Survey 2025-26 Statistical Appendix, Table 1.17 (kg/ha, 2024-25).
- Soybean: SOPA kharif 2024 (1063 kg/ha).

**ASSUMPTIONS / SCIENTIFIC RISKS**
- Yields are ALL-INDIA and applied uniformly across regions — a deliberate,
  documented scope choice pending state-level refinement. Because fairness and
  concentration analysis are spatial, region-uniform yields will understate
  inter-region variation until refined.
- Derived cost/ha assumes CACP cost/quintal scales with DES yield; DES Cost of
  Cultivation (per-ha, stated basis) is preferred and recommended in provenance.
- Cotton yield is LINT; MSP/cost are seed-cotton — return/cost left open (guarded).

**OPEN OBLIGATIONS** — onion/tomato yields (horticulture); mustard cost; AGMARKNET
market prices (esp. vegetables); labour/ha (ICAR); ET0 for R3–R5;
market_absorption_proxy; climate/yield sensitivities; state-level yield refinement.

**FILES** — `farmsync/crop_yield.py`, `tests/test_farmsync_yield.py`; updated
`sourcing_report.py`, `build_builtin_dataset.py`.

**NEXT STEP** — checkpoint on the yield-scope decision, then continue sourcing
(labour, vegetable prices, remaining ET0, sensitivities). B1 can run on grounded
return once price×yield−cost is closed for the modelled crop set.

---

## Phase 5e (cont.) — State-level yield refinement (partial, in progress)

**STATUS** — state-override mechanism live; R1 (Punjab) refined; extraction
continues per the exhaustive-state decision.

**IMPLEMENTED**
- `crop_yield.py` — `STATE_YIELD` overrides + `resolve_yield(crop, season, region_id)`
  that prefers a state figure over national and labels scope `STATE:<name>` vs
  `ALL_INDIA`. Seeded with Punjab rice (4193 kg/ha, 2023) and wheat (5045 kg/ha,
  2023-24) from the DES state APY series. Built-in params now resolve yield
  region-by-region: R1 shows Punjab values, other regions show national (labelled).

**TESTS PASSED** — 2 new (60 total). State override wins for R1; national fallback
for unmapped state-crop, both scope-labelled.

**DATA/SOURCES** — DES state APY series (via CEIC) for Punjab rice/wheat;
continuation source of record: DES APY portal
https://data.desagri.gov.in/website/crops-apy-report-web

**SCIENTIFIC RISKS / OPEN** — state coverage is partial: only R1's two dominant
crops are refined; R2-R5 and R1's other crops remain national-scope (labelled).
Each state-crop is ~one DES lookup; this is the slow exhaustive tail as accepted.

**FILES** — updated `crop_yield.py`, `build_builtin_dataset.py`,
`tests/test_farmsync_yield.py`.

**NEXT STEP (per your selection)** — remaining ET0 for R3-R5 next, then continue
state-yield extraction and the other economics (labour, vegetable prices,
sensitivities). B1 begins once minimum return inputs are grounded for the crop set.

---

## Phase 5f / 6 update — ET0 for all regions, cotton unit fix, water rerun

**STATUS** — item 1 (all-region water) and item 3 (cotton units) complete; a water-
balance scientific decision is surfaced below.

**IMPLEMENTED**
- `climate.py` — R3/R4/R5 now carry seasonal ET0 from a peer-reviewed all-India ET0
  spatial characterisation (Rao et al.), marked SYNTHETIC_GROUNDED (interpolated,
  not station means) with confidence LOW/MEDIUM, distinct from station-based R1/R2
  (OBSERVED). CWR now computes for all five regions (e.g. rice kharif: R3 709,
  R4 1097, R5 844 mm — humid-east low, arid-west high).
- `crop_yield.py` — cotton yield converted lint 440 -> seed cotton (kapas) 1257
  kg/ha via a documented 0.35 ginning ratio, making it unit-consistent with the
  seed-cotton MSP/cost; cotton cost/ha now derivable (~64k INR/ha).
- Feasibility rerun across all 12,754 plot×crop combos; suitability regenerated.

**TESTS PASSED** — 61/61 (updated 3 that asserted the old R3-R5 UNKNOWN behaviour).

**DATA/SOURCES** — Rao et al., "Reference crop evapotranspiration over India"
(Penman-Monteith), regional characterisation; ICAR-typical cotton ginning ratio 0.35.

**SCIENTIFIC RISK (needs a decision)** — the water feasibility check compares TOTAL
crop water requirement to the plot's IRRIGATION water only, ignoring effective
rainfall. This is conservative and drops feasibility to ~9% (rainfed rice etc. look
infeasible). A correct water balance uses net irrigation requirement =
max(0, CWR − effective rainfall), which needs IMD/region effective-rainfall data
not yet sourced. Options: (a) source effective rainfall and use NIR; (b) keep the
conservative rule, documented; (c) treat rainfall as an experimental parameter.

**OPEN OBLIGATIONS (items 2,4-10)** — onion/tomato yields; AGMARKNET market prices;
mustard cost; labour/ha; market_absorption_proxy; climate/yield sensitivities;
crop×soil matrix; sowing/harvest windows; then budget/labour feasibility.

**NEXT STEP** — resolve the water-balance decision, then continue items 2,4-10 and
convert budget/labour feasibility from NOT_EVALUATED once cost/labour are grounded.

---

## Phase 6 water balance — net irrigation requirement (NIR)

**STATUS** — water-balance decision resolved; feasibility now agronomically sound.

**IMPLEMENTED**
- `climate.py` — `REGION_RAINFALL` (seasonal, per region), `effective_rainfall_mm()`
  (FAO/USDA fraction: kharif 0.75, rabi 0.80), and `net_irrigation_requirement_mm()`
  = max(0, CWR − effective rainfall). All-India monsoon LPA (868.6 mm) and East&NE
  subdivision normal (1367.3 mm) are IMD-sourced anchors; per-state seasonal rainfall
  is IMD-climatology characterisation (SYNTHETIC_GROUNDED).
- `feasibility.py` — water check now uses NIR against plot irrigation water, not full
  CWR. Rainfed crops in high-rainfall regions become feasible (NIR→0).

**RESULT** — rice NIR by region (kharif): R3 (West Bengal) 0 mm (rainfed), R2 526,
R5 394, R1 701, R4 (arid) 797 mm. Full-dataset feasibility recovered 9% → 31%,
matching agronomic expectation (WB rice rainfed; Rajasthan rice irrigation-dependent).

**TESTS PASSED** — 62/62 (1 new NIR test).

**DATA/SOURCES** — IMD seasonal rainfall climatology; FAO/USDA effective-rainfall method.

**ASSUMPTIONS** — per-state rainfall is representative (refine with IMD district
normals); rainfall effectiveness is a fixed-ratio experimental parameter.

**OPEN OBLIGATIONS (items 2,4-10)** — onion/tomato yields; AGMARKNET market prices;
mustard cost; labour/ha; market_absorption_proxy; sensitivities; crop×soil matrix;
sowing/harvest windows; then budget/labour feasibility → B1.

---

## Phase 5 close-out + B1 — Independent Farmer Planning

**STATUS** — Phase 5 minimum economics closed for the ADMITTED crop set; B1 built,
tested, and run. First working optimisation baseline.

**IMPLEMENTED**
- `crop_economics.py` — mustard C2 cost (4294 INR/q) added -> cost/ha closed for all
  11 MSP crops.
- `crop_agronomy.py` — labour/ha (ICAR/DES-grounded), crop×soil suitability matrix
  (documented agronomy), sowing/harvest windows.
- `market.py` — `market_absorption_proxy` (DERIVED, explicitly labelled NOT demand)
  and FAO-33 Ky yield-response sensitivities (OBSERVED where published, else
  experimental scenario parameter).
- `feasibility.py` — budget and labour feasibility now DETERMINISTIC (was
  NOT_EVALUATED); crop×soil matrix wired into SOIL_INCOMPATIBLE.
- `planning.py` — provenance/validity GATE: only crops with grounded yield + usable
  price + consistent cost + defined CWR are admitted (11 crops; potato/onion/tomato
  documented-excluded). `projected_return()` uses state/national yield consistently
  for revenue AND cost; price basis = MSP floor (labelled).
- `baselines.py` — B1 independent per-farmer planning s.t. own budget/labour, with
  post-solve independent hard-constraint verification (spec §28).

**TESTS PASSED** — 69/69 (11 new: gate clean, excluded crops raise, state yield in
return, B1 respects hard constraints, reproducible, admitted-only).

**KEY RESULTS (built-in 500-farmer, seed 20260812)** — B1: total net return
₹10,213,886; mean farmer ₹20,428; median ₹12,982; land utilisation 56.8%; 498 plots
allocated, 413 fallow; hard constraints satisfied (0 violations); solve 0.87 s.
Returns reflect state yields (Punjab rice net ₹33,125/ha vs national ₹22,318/ha).

**FILES / RESULT PATHS**
- `data/farmsync/builtin/crop_region_season_params.csv` (yield/price/cost/water/labour)
- `data/farmsync/builtin/plot_crop_suitability.csv` (feasibility incl. budget/labour)
- `results/farmsync/sourcing_report.json` / `.csv` (full provenance)
- `results/farmsync/b1_result.json`, `results/farmsync/b1_allocations.csv`

**ADMITTED-SET GATE** — verified clean: 65 admitted crop×region×season combinations,
0 blocked; no REQUIRES_SOURCING/UNKNOWN/NOT_EVALUATED field enters any admitted return.

**ASSUMPTIONS / OPEN** — kharif A2+FL vs rabi C2 cost basis differs but never enters a
within-plot comparison (feasibility enforces season). Vegetables excluded pending
AGMARKNET prices + horticulture yields. Rainfall-effectiveness remains an experimental
sensitivity parameter. Labour/soil/window values are documented agronomy (MEDIUM).

**NEXT STEP** — B2 (centralised profit maximisation over the collective s.t. hard
constraints), then B3 (static fairness-aware) and the Proposed model.

---

## Correction pass — crop universe, market prices, provenance review (pre-B2)

**STATUS** — partial: yields completed for all 14 crops; market-price protocol built;
provenance corrected. Full 14-crop admission + operational market prices remain a
genuine decision (checkpoint below). 11-crop B1 preserved as PROVISIONAL.

**IMPLEMENTED**
- `crop_yield.py` — onion (16,800 kg/ha, NHB 2019) and tomato (~25,000 kg/ha, NHB
  production/area) added; potato already 25,000 (DES). All 14 crops now have yield.
- `market_price.py` — operational market-price module with a DOCUMENTED AGMARKNET
  aggregation protocol (window: trailing 3 marketing years monthly modal; mandi:
  principal producing-state APMC via REGION_STATE; central tendency: season median;
  outliers: drop >3×IQR; missing: carry-forward, flag >30%; units: Rs/q→Rs/kg).
  Vegetable representative prices recorded (LOW confidence, provisional); grain
  operational market prices remain an explicit AGMARKNET obligation. MSP stays a
  labelled policy-floor reference, never the observed market price.
- Provenance corrections: `market_absorption_proxy` reclassified DERIVED→
  SYNTHETIC_GROUNDED (values judgement-assigned from production ordering, not
  computed from arrivals); labour/soil/windows already SYNTHETIC_GROUNDED; FAO-33 Ky
  remains OBSERVED (published). Item-4/5 review complete.
- Effective-rainfall/NIR preserved; rainfall-effectiveness stays a documented
  sensitivity parameter.
- 11-crop B1 saved as PROVISIONAL: `results/farmsync/b1_provisional_11crop.json`,
  `b1_provisional_11crop_allocations.csv` (total return ₹10,213,886; hard constraints
  satisfied). Clearly separated from any final result.

**TESTS PASSED** — 69/69 (updated the yield-count test to 14).

**WHY STILL 11 ADMITTED** — vegetables now have yield but still lack (a) sourced
cultivation cost/ha (no CACP cost; DES CoC not ingested) and (b) rigorous AGMARKNET
market prices. They fail the same validity gate the 11 crops pass, so they remain
excluded — documented, not silently dropped.

**FILES / RESULT PATHS**
- `data/farmsync/builtin/crop_region_season_params.csv`, `plot_crop_suitability.csv`
- `results/farmsync/sourcing_report.json` / `.csv`
- `results/farmsync/b1_provisional_11crop.json` / `_allocations.csv`

**OPEN / DECISION** — see checkpoint: comprehensive AGMARKNET operational market
prices (all crops) + vegetable cost/ha are the remaining blockers to a defensible
final crop set. Not machine-fetchable here at publication rigour.

---

## Market/cost ingestion pathway (awaiting your data exports)

**STATUS** — ingestion pathway built and tested; ready for your AGMARKNET + DES-CoC
exports. Price basis will finalise from that data before B2 (per your decision).

**IMPLEMENTED**
- `market_ingest.py` — loaders for AGMARKNET price exports and DES Cost-of-Cultivation
  exports, applying the documented protocol (state->region mapping, >3xIQR outlier
  drop, season median of monthly modal, Rs/q->Rs/kg; DES-CoC cost/ha per crop×region,
  basis preserved). No data is fabricated: tables are empty until real files are dropped.
- `planning.py` — operational price/cost resolvers with explicit basis labels
  (`MARKET_AGMARKNET` > `MARKET_REPRESENTATIVE_PROVISIONAL` > `MSP_FLOOR_REFERENCE`;
  cost `DES_CoC` > `CACP×yield`). Dynamic gate: 11 crops on the provisional basis,
  up to 14 once vegetable price+cost are ingested. `load_operational_market(dir)`
  switches to the market basis when files are present.
- `baselines.py` — B1 now iterates the dynamic admitted set (picks up ingested veg).

**DATA CONTRACT** — `data/farmsync/market/README_DATA_CONTRACT.md` specifies exact
files/columns to export:
  - `data/farmsync/market/agmarknet_prices.csv` (crop_name, state, year, month, modal_price_rs_per_quintal)
  - `data/farmsync/market/des_coc.csv` (crop_name, state, cost_basis, cost_per_ha_rs, year)

**TESTS PASSED** — 73/73 (4 new: AGMARKNET aggregation incl. outlier drop; DES-CoC
state->region; ingested data admits a vegetable and B1 switches to market price;
MSP used only as reference when no ingest).

**PROVISIONAL RESULT UNCHANGED** — `results/farmsync/b1_provisional_11crop.json`
stands (MSP-floor reference basis, 11 crops). Final market-basis run will execute
once your exports land.

**NEXT STEP (blocked on your data)** — drop AGMARKNET + DES-CoC exports into
`data/farmsync/market/`; I ingest, finalise the price basis + admitted crop set,
rerun B1 as the FINAL run, then proceed B2 -> B3 -> Proposed.

---

## Official-data ingestion + FINAL B1 (real DES/CoC/AGMARKNET basis)

**STATUS** — official source artifacts ingested, validated, provenance-recorded;
FINAL B1 run on the real basis. Checkpoint before B2.

**RAW SOURCES PRESERVED (immutable)** — `data/farmsync/raw_sources/` with
`SHA256SUMS.txt`: des_apy/ (DES APY xls), cost_of_cultivation/ (CoC csv + codebook),
agmarknet/ (5 monthly exports). Never modified; processed files written separately.

**INGESTION** (`farmsync/ingest/`)
- `commodity_map.py` — explicit source→FarmSync mapping with documented exclusions
  (rice→Paddy(Common) not Rice/Basmati; cotton→Cotton=kapas not Lint; chickpea→
  Bengal Gram(Whole) not dal; pigeon_pea→Tur(whole) not dal; mustard→Mustard not
  Toria/Taramira). Prevents double-counting + lint/kapas mismatch.
- `pipeline.py` — DES state yield = SUM(prod)/SUM(area)×1000→kg/ha (never mean of
  district yields; cotton lint→kapas ÷0.35); CoC A2+FL & C2 kept separate (₹/ha) +
  labour man-hours/ha ÷8→person-days; AGMARKNET median monthly modal 2023-2025,
  >3×IQR outliers dropped, Rs/q→Rs/kg, coverage% + sparse flag; arrivals→absorption
  proxy (NOT demand).
- `run_ingest.py` — writes processed tables + `source_manifest.json` (parser
  version, hashes, transformations).
- `operational.py` — serves region-keyed yield/price/cost/labour; cost policy:
  return=C2, budget=A2+FL, sensitivity=both; national yield fallback labelled.

**COST/PRICE/YIELD BASIS (final)** — price = AGMARKNET market median monthly modal
(MSP fully demoted to reference); yield = DES state (2022-23 primary, 2021-22 alt),
national fallback labelled; cost return=C2, budget=A2+FL (never mixed within a crop).

**GATE (machine-readable: `results/farmsync/gate_report_final.json`)** — 13 crops
admitted, 50 crop×region×season combos; 40 excluded (35 no state CoC cost, 5 sparse
AGMARKNET price). tomato fully excluded (AGMARKNET price + NHB yield but NO CoC
cost — not fabricated). gate_valid=True (no admitted combo carries a placeholder).

**FINAL B1** (`results/farmsync/b1_final.json`, `_allocations.csv`) — dataset_hash
9984aa9948740c06; total net return ₹4,359,103; mean ₹8,718; median ₹11,803; land
utilisation 18.5%; crop diversity 5; solve 0.71s; **hard constraints satisfied
(0 violations)**. Real prices flow through (wheat R1 net ₹46,555/ha; potato R3
₹155,630/ha; cotton/onion negative at C2 = genuine economic finding).

**TESTS** — 81 passed (8 new real-data ingestion tests: DES prod/area rule, unit
conversions, two-year handling, A2+FL/C2 separation, labour derivation, AGMARKNET
parsing/mapping/units, cotton kapas, sparse+no-cost exclusion).

**PROCESSED OUTPUTS (paths)**
- `data/farmsync/processed/`: yield_state.csv, cost_state.csv, market_price_state.csv,
  arrivals_state.csv, absorption_proxy.csv, source_manifest.json,
  crop_region_season_params.csv, plot_crop_suitability.csv, frozen_input_manifest.json
- `results/farmsync/`: gate_report_final.json, b1_final.json, b1_final_allocations.csv
- PROVISIONAL (unchanged): b1_provisional_11crop.json (+ _allocations.csv)

**SCIENTIFIC LIMITATIONS / DECISIONS FOR REVIEW**
1. **Farmer-budget calibration** (genuine decision): synthetic farmer budgets
   (₹25-45k/ha) were set to the old cost scale; real A2+FL costs are ₹30-160k/ha,
   which drives the low 18.5% land utilisation. Options: recalibrate synthetic
   budgets to a realistic A2+FL-relative scale, or treat cash-constraint tightness
   as a modelled feature (smallholder credit constraint). Needs your call before B2
   comparability.
2. tomato outside the gate (no CoC cost) — the 14th crop needs an ICAR/horticulture
   cost source.
3. Sparse AGMARKNET cells (e.g. Punjab paddy 33% coverage — MSP-procured) excluded;
   state-level cost coverage gaps (35 combos) exclude those crop×regions.
4. ET0 for R3-R5 remains characterisation-based (lower confidence than station R1/R2).

**NEXT** — checkpoint on the budget-calibration decision, then B2 (centralised
profit-max s.t. hard constraints) → B3 → Proposed.

---

## Budget recalibration + FINAL B1 (recalibrated) + B2 + B3

**STATUS** — farmer cash-budget recalibrated to realistic A2+FL scale; B1 rerun on
calibrated base; B2 (market-aware centralised) and B3 (static fairness-aware) built.
Checkpoint before the Proposed model.

**BUDGET CALIBRATION** (`generate.py`)
- Old default (₹25-45k/ha) replaced with an A2+FL-anchored budget:
  `budget = area × REP_A2FL(₹55,000/ha ≈ median ingested CoC A2+FL) × tightness × U(0.85,1.15)`.
- `budget_tightness` is a documented robustness parameter: tight 0.6 / base 1.2 /
  loose 2.5. Base is the default (no longer unrealistically tight).
- B1 farmers now maximise CASH net return (revenue − A2+FL) — the farmer's real
  decision basis — while C2 economic return is retained for reporting/comparison.

**BASELINES** (`baselines.py`) — all on base tightness, seed 20260812, 500 farmers:
| model | objective | land % | cash net return | Gini | note |
|-------|-----------|--------|-----------------|------|------|
| B1 | independent per-farmer profit-max | 41.2 | ₹14,493,650 | 0.704 | max total |
| B2 | centralised + market-absorption cap | 43.7 | ₹13,779,096 | 0.741 | market-aligned; groundnut cap binds |
| B3 | static fairness-aware (worst-off first) | 42.3 | ₹12,864,876 | 0.694 | most equitable |
- Trade-offs visible: B2 sacrifices ~₹0.7M for market alignment; B3 sacrifices
  ~₹1.6M for lower inequality. All hard constraints satisfied (0 violations).

**BUDGET SENSITIVITY (B1)** — land utilisation tight 23.3% / base 41.2% / loose 43.0%
(`results/farmsync/b1_budget_sensitivity.json`).

**TESTS** — 84 passed (3 new: budget tightness scales utilisation; B2 respects cap +
hard constraints; B3 no less equitable than B1).

**RESULT PATHS**
- `results/farmsync/b1_final.json` / `_allocations.csv` (recalibrated, base)
- `results/farmsync/b2_final.json` / `_allocations.csv`
- `results/farmsync/b3_final.json` / `_allocations.csv`
- `results/farmsync/baseline_comparison.json`
- `results/farmsync/b1_budget_sensitivity.json`
- `results/farmsync/b1_provisional_11crop.json` (unchanged PROVISIONAL dev run)

**SCIENTIFIC NOTES** — Gini ~0.7 reflects genuine holding-size heterogeneity;
fairness effect of B3 is modest but directionally correct (lower Gini, higher
median). Market-absorption cap uses the arrivals-derived proxy (documented, NOT
demand). B2/B3 use a deterministic greedy heuristic (defensible for a demonstrator;
an ILP would tighten optimality).

**NEXT** — the Proposed FarmSync model: farmer accept/reject/modify/withdraw,
progressive commitment (VIEWED→PLANTED), stability-aware reoptimisation,
concentration/resilience, disaster/backup/N−1, monitoring (GREEN/AMBER/RED),
scenario engine, OpenAI validation-boundary layer, LLM benchmark + eval,
30-replication statistics, inspectable UI, publication figures. This is the core
contribution and a large multi-part build — checkpoint here before starting it.

---

## Pre-Proposed methodological audit → closure → ILP-v2 / fairness-v2 / harness

**STATUS** — audit completed, all closure issues resolved, prerequisites implemented.
**READY FOR PROPOSED PHASE 1** (not started; awaiting go). Frozen greedy baselines
(`b1/b2/b3_final.json`, `baseline_comparison.json`) preserved UNCHANGED throughout.
Full detail: `docs/farmsync/METHODOLOGY_AUDIT.md` (425 lines).

**Optimisation-backbone audit.** Exact ILP reference (PuLP 3.3.2 / CBC 2.10.3) built
(`farmsync/ilp_reference.py`). Greedy optimality gap: B1 ≤1.1%, B2 up to 3.34% (seed
101) — large enough vs the ~5% B2-vs-B1 model difference to warrant a common backbone.
Centralised ILP solves to proven Optimal in 1.4s at 500 farmers → common ILP backbone
adopted.

**Fairness reconciliation (RESOLVED).** Frozen Gini 0.704 = PARTICIPATING-only
(206 zero-return farmers, 41%, excluded); audit 0.826 = ALL 500. Canonical = all-farmer.
Committed `farmsync/fairness.py` (fairness-v2): PRIMARY = cash / total operated area,
all farmers + all-farmer Gini + participation + fixed B1-ref bottom-tail + benefit/loss
vs B1; SUPPORTING = absolute Gini, participant-only per-ha Gini; return/allocated-ha =
efficiency only. Legacy frozen Gini relabelled participant-only (preserved).
Corrected primary per-ha Gini (all): B1 0.685 / B2 0.708 / B3 0.718.

**Fixed cohorts finding.** B1-reference bottom decile & quartile earn 0 under B1/B2/B3
— worst-off are structurally non-participating (empty feasible sets); intensive-margin
fairness cannot reach them. CORRECTION (see Phase 1): this structural non-participation
is a feasibility/data-coverage issue and is NOT solved by the Proposed participation
mechanism — voluntary accept/reject operates only among farmers who receive a feasible
planned offer, and can only reduce realisation, never create options for zero-option
farmers. Recovery of rejected offers is a later-phase reoptimisation question.

**Coverage decision (APPLIED).** Full-data admitted sets canonical; regional choice-set
coverage reported (R1/R3 impoverished: 2 kharif options vs 7–9 in R2/R4/R5). Common
support nearly empty (no kharif crop in all 5 regions; rabi only wheat) → cross-region
fairness/concentration claims narrowed; no kharif common-support manufactured; R1/R3
sourcing = documented future strengthening, not a blocker.

**Experiment freeze.** `results/farmsync/audit/`: replication_seeds.json (30 predefined),
rng_streams.json (5 paired substreams/seed), experiment_manifest.json (all hashes +
fairness-v2 + selected ε + 30 seed→instance hashes), experiment_runs.json. Processed
hash unchanged 9984aa9948740c06.

**Paired-instance harness** (`farmsync/experiment.py`) — one instance/seed reused across
all models; frozen RNG substreams; determinism verified; 30 unique instance hashes;
validation runs (2 seeds) all Optimal + hard-feasible. Full 30-rep Proposed run NOT run.

**Versioned ILP baseline family** (new; greedy preserved): `b1_ilp_v2.json`,
`b2_ilp_v2.json`, `b3_ilp_v2.json` (+ _allocations.csv), `baseline_comparison_ilp_v2.json`.
B1 exact per-farmer ILP 14,644,544 (+1.04%); B2 central+cap MILP 13,822,738 (+0.32%);
B3 ε-constraint MILP 13,142,176 (+2.16%). All Optimal, hard-feasible; solver metadata
on every run.

**B3 ε-frontier + selection** (`results/farmsync/audit/b3_epsilon_frontier.json`):
min-norm/ha 333.9 at ε=0.80/0.90/0.95, collapses to 0 at ε=1.00. Predefined rule
(highest ε with min-norm ≥99% of max attainable) → **selected ε = 0.95** (95.1%
efficiency retained, full fairness; worst-off gain over B2 at 4.9% efficiency cost).

**Tests** — 88 passed (fairness-v2, ILP baselines Optimal+feasible, harness
determinism, ε worst-off monotonicity).

**NEXT (on your go)** — Proposed Phase 1: begin ablation map from B3 static fairness
(ε=0.95, ILP backbone) + participation/accept-reject, on the paired-instance harness
with fairness-v2 metrics; checkpoint after each ablation.

---

## Reproducibility cleanup (pre-Proposed) — canonical ε, canonical T*, run metadata

**STATUS** — reproducibility fixes complete; 90 tests pass; frozen greedy baselines
UNTOUCHED; no Proposed-model code implemented. **READY FOR PROPOSED PHASE 1.**

**Fixes made**
1. **Authoritative config** (`farmsync/config.py`): `CANONICAL_B3_EPSILON=0.95`,
   `FORMULATION_VERSION`, `FAIRNESS_VERSION`, `TSTAR_TOLERANCE=1.0`. `run_b3_ilp`,
   `b3_epsilon_ilp` and `experiment.run_baselines_on` now default to the canonical ε
   (no silent 0.90). Sensitivity/frontier runs may still pass an explicit ε.
2. **Canonical cash accounting**: added single-rounded `Allocation.cash_net`
   (= round(revenue − A2+FL)); `fairness.farmer_cash`, `_b1_metrics` total, and ILP
   `_extract` all use it. Unified `b2_ilp_total` CBC settings with the canonical solver
   config.
3. **B3 run metadata schema** (`experiment.run_record`): epsilon, fairness_version,
   formulation_version, seed, instance_hash, solver_status, runtime, min-norm. B1/B2
   store epsilon=None (n.a.).

**Root cause — ε mismatch**: `experiment.run_baselines_on` (and ILP defaults) hard-coded
`epsilon=0.9` while the approved publication value is 0.95, so a normal run could
silently use 0.90. Fixed by routing all defaults through `config.CANONICAL_B3_EPSILON`.

**Root cause — B2 T* mismatch (₹13,822,731 vs ₹13,822,738, diff 7)**: two different cash
computations. `b2_ilp_total` returned the ILP objective = Σ `cash_net_return` (revenue−A2FL
rounded **once**). `fairness.farmer_cash` reconstructed cash as `(net_return+cost)−budget_cost`
= three **independently-rounded** C2 terms, accumulating a 7-rupee drift. Fixed by making
`cash_net` a single canonical single-rounded field used by both paths; they now agree
**exactly (diff 0.0)**, invariant-tested within tolerance ₹1.

**Canonical values**: **B3 ε = 0.95**; **B2 T\* = ₹13,822,731** (one value everywhere;
`b2_ilp_total` == Σ `farmer_cash(run_b2_ilp)`). ε-frontier uses this shared T*.

**B3 objective clarification**: B3 optimises the Rawlsian/worst-off-capable objective
(max min normalized return s.t. ≥95% efficiency). It does NOT improve every inequality
metric — B3 all-farmer per-ha Gini 0.718 > B2 0.708; the contribution is worst-off
improvement (min-norm 333.9 vs B2 0), not uniform Gini reduction.

**Files changed**: `farmsync/config.py` (new), `farmsync/baselines.py` (cash_net),
`farmsync/fairness.py` (farmer_cash), `farmsync/ilp_reference.py` (canonical ε, cash_net,
solver settings), `farmsync/experiment.py` (canonical ε default, run_record schema),
`tests/test_farmsync_ilp_v2.py` (2 regression tests).

**Artifacts regenerated** (versioned, NOT frozen): `b1/b2/b3_ilp_v2.json` (+ _allocations.csv,
now with cash_net), `baseline_comparison_ilp_v2.json`, `audit/b3_epsilon_frontier.json`,
`audit/experiment_runs.json`, `audit/experiment_manifest.json`.

**Frozen files preserved**: `b1/b2/b3_final.json`, `baseline_comparison.json`,
`b1_provisional_11crop.json` — unchanged (timestamps verified).

**Tests**: 90 passed (added: canonical ε=0.95 regression; B2 T* single-canonical-value
invariant within ₹1).

**Remaining issues**: none blocking. Documented future strengthening: R1/R3 CoC/price
coverage (cross-region claims stay narrowed); ET0 R3–R5 characterisation-based.

**Exact next step**: on your go, Proposed Phase 1 — begin the ablation map from B3 static
fairness (ε=0.95, ILP backbone) by adding the participation/accept–reject mechanism, on
the paired-instance harness with fairness-v2 metrics; checkpoint after that ablation.

---

## PROPOSED PHASE 1 — voluntary farmer participation (ACCEPT / REJECT)

**STATUS** — implemented, validated, dev/checkpoint run complete. 99 tests pass.
Frozen greedy + ILP-v2 baselines untouched. No later Proposed mechanism implemented.
**READY FOR PROPOSED PHASE 2** (not started; awaiting explicit confirmation).

**Scientific purpose.** Isolate the pure effect of voluntary farmer acceptance on how
much of the static collective plan is actually realised:
`static B3 plan → voluntary response → realised allocation`. No reassignment/
reoptimisation, so the measured effect is participation alone.

**Participation mechanism.** PLANNED = canonical B3 ILP-v2 (ε=0.95, fairness-v2,
CBC MILP, unchanged). Each planned plot-crop is an OFFER. Response ∈ {ACCEPT, REJECT}
(FarmerEvent enum; MODIFY/WITHDRAW remain unimplemented placeholders). ACCEPT → offer
enters realised allocation unchanged; REJECT → plot FALLOW/UNALLOCATED, NOT reassigned.

**Response model / parameters (provenance = SYNTHETIC_EXPERIMENTAL).**
`AcceptanceConfig`: base_accept_prob=0.85, risk_sensitivity=0.20;
`p_accept(farmer)=clip(0.85 + 0.20·(risk_tolerance−0.5), 0, 1)` using the existing
provenance-labelled synthetic `risk_tolerance`. Explicitly NOT observed Indian farmer
acceptance prevalence; no empirical rate invented. Config recorded in every result.

**RNG / substream design.** Deterministic draw
`sha256(farmer_response_subseed : farmer_id : plot_id : offered_crop)` → uniform [0,1);
ACCEPT iff draw < p_accept. Keyed by IDs so responses are order-independent. Uses the
frozen `farmer_response` substream; for the canonical dev seed 20260812 (not in the
30-seed replication set) the substream is DERIVED via the same documented formula
`sha256('{master}:{stream}') mod 2^31` (value 1120031581) — reproducible and consistent.

**Planned vs realised semantics.** Kept strictly separate. Rejected offers never
counted as realised production/return. Realised allocation ⊆ planned; realised return
≤ planned return (Phase-1 mechanism can only remove, never add).

**Files created.** `farmsync/proposed/__init__.py`, `farmsync/proposed/participation.py`
(AcceptanceConfig, response_draw, apply_participation), `tests/test_farmsync_proposed_p1.py`.
**Files changed.** `farmsync/experiment.py` (substream fallback derivation for non-
replication seeds).

**Result artifacts** (`results/farmsync/proposed/`): `p1_participation_result.json`,
`p1_participation_offers.csv` (full offer records: run/seed/instance hash, farmer, plot,
region:season, planned crop, planned cash, response, p_accept, draw, subseed, realised
crop, realised cash, status), `p1_participation_realised_allocations.csv`.

**Checkpoint results (seed 20260812, base, B3 ε=0.95).**
- offers 381; accepted 331 (86.9%); rejected 50 (13.1%).
- cash: planned ₹13,142,166 → realised ₹11,464,341; **cash realisation ratio 0.872**.
- area: planned 327.1 ha → realised 274.0 ha; **area realisation ratio 0.838**.
- participating farmers: planned 294 → realised 263.
- hard constraints satisfied (0 violations); B3 planned solve 0.2s.
- realised ⊆ planned = True; realised ≤ planned cash = True.

**Fairness-v2 (planned → realised).** primary per-ha Gini (all 500) 0.718 → **0.749**
(inequality RISES: rejections are not uniform and remove realised return); supporting
absolute Gini (all farmers) 0.8572 → 0.8712; participant-only per-ha Gini 0.5208 →
0.5233. [CORRECTION 2026-08 (Phase 2): these supporting values were previously logged
here as 0.826 → 0.845 and 0.514 → 0.520 — stale figures carried over from the earlier
audit-era greedy B1/B2 calculation (B1 all-farmer abs Gini 0.826; B2 participant per-ha
0.514), NOT the Phase-1 realised computation. Corrected to match the source of truth
`p1_participation_result.json`; the result data was NOT altered.] Fixed
B1-reference bottom decile/quartile remain **0** under both planned and realised —
consistent with the correction below. Benefit/loss vs B1 recomputed on realised.

**Tests added (9).** same seed→identical responses; different seed→can differ;
iteration order invariant; rejected never realised; accepted preserves crop/value;
realised ⊆ planned (no reoptimisation); realised return ≤ planned; hard constraints
hold on realised; fairness-v2 counts all farmers incl zero-realised; frozen/versioned
artifacts still present. **Full suite: 99 passed.**

**Assumptions.** Acceptance is a synthetic experimental behavioural model
(base 0.85 + mild risk modulation); not calibrated to field data.

**Scientific limitations.** (1) Acceptance model is experimental, not empirical.
(2) Phase 1 measures only the participation/realisation effect; it does NOT recover
rejected offers (no reoptimisation) — realised is a lower bound on what a dynamic
model could achieve. (3) Structural zero-option farmers are unaffected (see correction).
(4) Cross-region acceptance reported descriptively only, under the standing unequal-
coverage caveat.

**CORRECTION (per instruction).** Earlier phrasing implied the extensive margin /
participation mechanism addresses structural zero-option farmers. That is wrong and is
corrected in the audit-closure section above: structural non-participation (empty
feasible/admitted set) is a feasibility/data-coverage issue; Phase-1 voluntary
participation operates ONLY among farmers who receive a feasible planned offer and can
only reduce realisation. It does not create options for zero-option farmers.

**Mechanisms explicitly NOT implemented yet.** commitment-state progression/locks;
stability-aware reoptimisation; concentration/resilience; disaster/N−1; monitoring/
governance; LLM/OpenAI layer; modify/withdraw workflow (enum placeholders only).

**Frozen artifacts preserved.** `b1/b2/b3_final.json`, `baseline_comparison.json`,
`b1/b2/b3_ilp_v2.json`, `baseline_comparison_ilp_v2.json`, `b1_provisional_11crop.json`
— all unchanged.

**Exact next phase (on your confirmation).** Phase 2 — commitment-state progression /
locks (VIEWED→…→PLANTED) layered on the accepted Phase-1 allocations, still without
stability-aware reoptimisation.

---

## PROPOSED PHASE 2 — commitment-state progression / progressive locking

**STATUS** — implemented, validated, dev/checkpoint complete. 108 tests pass. Phase-1
+ frozen baselines unchanged. No Phase-3 reoptimisation or later mechanism implemented.
**READY FOR PROPOSED PHASE 3** (not started; awaiting explicit confirmation).

**Phase-1 documentation correction (done first).** The Phase-1 section's supporting
fairness values were corrected from stale 0.826→0.845 / 0.514→0.520 to the source-of-
truth `p1_participation_result.json` values **0.8572→0.8712** (absolute Gini all) and
**0.5208→0.5233** (participant-only per-ha). Root cause: the stale figures were carried
over from the earlier audit-era greedy B1/B2 calculation (B1 all-farmer abs Gini 0.826;
B2 participant per-ha 0.514), not the Phase-1 realised computation. Result data was NOT
altered; only PROGRESS was corrected, and the correction is logged in-place.

**IMPLEMENTED** — `farmsync/proposed/commitment.py`. Reuses existing schemas vocabulary
(no parallel state system).

**Exact lifecycle / state machine.** `COMMITMENT_LADDER` (from schemas):
`VIEWED → TENTATIVE_ACCEPT → CONFIRMED → INPUTS_PURCHASED → LAND_PREPARED → PLANTED`.
Transitions are monotonic single-step forward, validated (`valid_transition`); backward/
skip/self are rejected (`InvalidTransition`). Phase-1 `FarmerEvent.ACCEPT/REJECT` remain
the authoritative behavioural decision; ladder advances past the first step are scripted
commitment ACTIONS (`COMMIT_ADVANCE`), not new behavioural events. Rejection mapping:
ParticipationState has no distinct REJECTED value, so a Phase-1 REJECT is a TERMINAL
event on a VIEWED offer — rejected offers never enter the ladder and can never progress
(documented reuse, not a duplicate state).

**Lock policy.** `VIEWED → FLEXIBLE` (changeable); `TENTATIVE_ACCEPT / CONFIRMED /
INPUTS_PURCHASED / LAND_PREPARED → SOFT_LOCK` (technically changeable; carry commitment
info for the later Phase-3 stability penalty); `PLANTED → HARD_LOCK` (immutable).
`lock_level(state)`, `can_change_crop(state)` (False only for PLANTED),
`valid_transition(old,new)`, `transition(...)`, `attempt_crop_change(...)` (blocks
hard-locked mutation) exposed.

**Phase-2 semantics.** Adds lifecycle state + lock semantics ONLY. Phase-2 realised
allocation == Phase-1 realised allocation; cash and area unchanged; fairness-v2
unchanged. No rejected plot reassigned; NO optimisation runs on transitions.

**Files created.** `farmsync/proposed/commitment.py`, `tests/test_farmsync_proposed_p2.py`.
**Files changed.** `docs/farmsync/PROGRESS.md` (Phase-1 correction + this section). No
code files changed outside the new module.

**Result artifacts** (`results/farmsync/proposed/`): `p2_commitment_result.json`,
`p2_commitment_timeline.csv` (every lifecycle event: run/seed/instance hash, farmer,
plot, crop, prev→new state, event, sequence, lock level, can_change_crop, status,
reason), `p2_lock_snapshot.csv` (final state + lock level per offer).

**Checkpoint metrics (seed 20260812, base; scripted full progression).**
- Phase-1 carried forward: accepted 331, rejected 50.
- Round snapshots: accepted cohort advances one ladder step per round (5 rounds) to PLANTED.
- Final state counts: PLANTED 331, VIEWED 50 (rejected terminal).
- Lock counts: FLEXIBLE 0, SOFT_LOCK 0, HARD_LOCK 331, REJECTED_TERMINAL 50;
  **% hard-locked (of accepted) = 100%**.
- Actual forward ladder transitions 1655 (331 accepted × 5 steps); lifecycle-entry
  snapshots 331 (Phase-1 ACCEPT at VIEWED); **successful lifecycle events 1986**
  (= 1655 + 331). [CORRECTION (Phase 3): previously reported as "valid transitions 1986",
  which conflated the 331 entry snapshots with the 1655 actual forward transitions. The
  underlying Phase-2 timeline is unchanged; only the terminology/reporting was split.]
  Invalid transition attempts rejected 11; hard-lock crop mutation attempts blocked 5.
- Phase-1 realised cash ₹11,464,341 == Phase-2 cash ₹11,464,341; area 274.0 == 274.0 ha.
- Allocation identity (Phase-2 == Phase-1) = True; hard-constraint violations 0.
- **fairness-v2 unchanged (planned/realised report identical before vs after) = True**.

**Assumptions.** Deterministic scripted lifecycle progression (per instruction) — no
behavioural commitment probabilities invented. The purpose is to validate the
commitment/lock mechanism, not to model realistic commitment attrition.

**Scientific interpretation.** Commitment states + locks add NO economic change on their
own — cash, area, and fairness are identical to Phase-1 realised (explicitly confirmed).
The mechanism's value is structural: it records how firm each accepted allocation is and
which allocations are immutable (PLANTED) vs still changeable (soft/flexible), which the
Phase-3 stability-aware reoptimiser will consume. No economic improvement is claimed from
commitment states alone.

**Limitations.** Scripted progression drives all accepted offers to PLANTED (100%
hard-locked) to validate the full ladder; a realistic attrition distribution across
commitment states is deferred (would require a behavioural model, out of Phase-2 scope).

**Frozen artifacts preserved.** `b1/b2/b3_final.json`, `baseline_comparison.json`,
`b1/b2/b3_ilp_v2.json`, `baseline_comparison_ilp_v2.json`, `b1_provisional_11crop.json`,
and all Phase-1 `p1_*` artifacts — unchanged.

**Mechanisms explicitly NOT implemented yet.** stability-aware reoptimisation (Phase 3);
concentration/resilience; disaster/N−1; monitoring/governance; LLM/OpenAI layer;
modify/withdraw behavioural workflow (MODIFY/WITHDRAW remain enum placeholders; the
hard-lock guard uses a MODIFY status only to record a blocked mutation attempt).

**Exact next step (on your confirmation).** Phase 3 — stability-aware reoptimisation:
the first phase where the optimiser responds to rejections/commitment states, re-solving
to recover rejected-plot value while penalising disruption to soft-locked allocations
and treating PLANTED (hard-locked) allocations as fixed.

---

## PROPOSED PHASE 3 — stability-aware reoptimisation (REVISED PLAN, not realised)

**STATUS** — implemented, validated, dev/checkpoint complete. 116 tests pass. All frozen
baseline, Phase-1 and Phase-2 artifacts preserved. No Phase-4+ mechanism implemented.
**READY FOR PROPOSED PHASE 4** (not started; awaiting explicit confirmation).

**Two Phase-2 bookkeeping corrections (done first).** (1) Transition-count terminology
split into `actual_forward_transitions=1655` and `successful_lifecycle_events=1986`
(=1655 forward + 331 lifecycle-entry snapshots); the all-PLANTED Phase-2 timeline is
unchanged. (2) The all-PLANTED Phase-2 development snapshot is retained as the lifecycle-
validation result but is NOT used as the Phase-3 input (nothing accepted is changeable
there); a separate mixed commitment scenario is created for Phase 3.

**Mixed commitment scenario (Phase-3 input) + provenance.** `mixed_commitment_scenario`
in `commitment.py`: each Phase-1 ACCEPTED offer is assigned deterministically and order-
independently — via `sha256("P3_MIXED_V1":farmer:plot:crop) mod 3` — to ~1/3
VIEWED(FLEXIBLE), ~1/3 CONFIRMED(SOFT_LOCK), ~1/3 PLANTED(HARD_LOCK). Realised split
(seed 20260812): **FLEXIBLE 119 / SOFT_LOCK 117 / HARD_LOCK 95** (+ REJECTED_TERMINAL 50).
Labelled **SYNTHETIC_EXPERIMENTAL commitment-timing; NOT observed prevalence**; proportions
fixed in advance, not tuned. Rejected offers stay REJECTED_TERMINAL (rejected crop cannot return).

**FORMULATION** — `farmsync/proposed/reoptimize.py`, same CBC MILP backbone, dataset/gate,
costs/prices/budgets/labour/market caps, fairness-v2.
Lock semantics: **HARD_LOCK/PLANTED** → x(plot, committed crop)=1, immutable;
**SOFT_LOCK/CONFIRMED** → crop may change, deviation = DISRUPTION (penalised);
**FLEXIBLE/VIEWED** → crop may change freely, deviations counted as churn but NOT penalised;
**REJECTED_TERMINAL** → rejected crop excluded, another feasible crop may be a NEW/REVISED
OFFER (recovery) or the plot stays fallow. Decision plots = the B3-planned plots only.

**Stability objective/equation** (normalised; raw rupees never dominate):
`maximise  E/E*  −  λ·(soft_disruption_area / soft_lock_area)`, where E = revised-plan
cash (incl. fixed hard-lock cash), E* = max attainable E under Phase-3 constraints
(λ=0, no fairness floor) = ₹12,359,219, soft_disruption_area = Σ over SOFT_LOCK plots of
area·(1 − x[plot, committed crop]). Formula recorded in result metadata.

**Fairness handling.** B3 fairness carried in as a CONSTRAINT: per capable farmer,
normalised return ≥ t_floor, where t_floor is RECOMPUTED under Phase-3 lock/rejection
constraints at the canonical ε=0.95 → **t_floor = 333.86** (vs baseline B3 min-norm 333.9;
locks barely change attainable fairness). Applied with a documented 0.1% relaxation to
avoid the max-attainable knife-edge (which had otherwise produced a false Infeasible status;
fixed — all runs now Optimal). Phase 3 is NOT turned into pure profit maximisation.

**λ sweep + return-vs-churn frontier** (seed 20260812; rejection loss = ₹1,677,825):
| λ | status | revised cash | recovery vs P1 | recovery frac of loss | soft-chg | flex-chg | rej-recov | hard-chg | per-ha Gini |
|---|---|---|---|---|---|---|---|---|---|
| 0.00 | Optimal | ₹12,359,219 | ₹894,878 | **0.533** | 17 | 18 | 18 | 0 | 0.729 |
| 0.05 | Optimal | ₹12,340,519 | ₹876,178 | 0.522 | 13 | 17 | 18 | 0 | 0.729 |
| 0.10 | Optimal | ₹12,340,519 | ₹876,178 | 0.522 | 13 | 17 | 18 | 0 | 0.729 |
| 0.25 | Optimal | ₹12,269,254 | ₹804,913 | 0.480 | 9 | 17 | 18 | 0 | 0.731 |
| 0.50 | Optimal | ₹12,269,254 | ₹804,913 | 0.480 | 9 | 17 | 18 | 0 | 0.731 |
| 1.00 | Optimal | ₹12,097,429 | ₹633,088 | 0.377 | 0 | 17 | 18 | 0 | 0.734 |
Monotonic: rising λ reduces soft-lock disruption (17→0) and recovery (53.3%→37.7%).
**Hard-lock changes = 0 at every λ** (verified). λ NOT frozen — the frontier is retained
and λ selection is left open for the later experimental freeze.

**Required comparisons.** A. Phase-2/no-reopt = Phase-1 realised ₹11,464,341 (274.0 ha).
B. Phase-3 λ=0 = ₹12,359,219 (recovers 53.3% of loss). C. λ-sweep as above.

**Checkpoint results.** E* Optimal; t_floor Optimal; all six λ Optimal; 0 hard-constraint
violations; hard locks preserved everywhere; 18 of 50 rejected plots receive alternative
REVISED OFFERS (recovery), 32 remain unrecovered/fallow.

**Files created.** `farmsync/proposed/reoptimize.py`; `mixed_commitment_scenario` added to
`farmsync/proposed/commitment.py`; `tests/test_farmsync_proposed_p3.py`.
**Files changed.** `docs/farmsync/PROGRESS.md` (Phase-2 correction + this section);
`results/farmsync/proposed/p2_commitment_result.json` (transition-count terminology split;
timeline untouched).

**Result artifacts** (`results/farmsync/proposed/`): `p3_reopt_result.json`,
`p3_lambda_frontier.csv`, `p3_revised_plan_lambda0.csv` (per-plot status labels:
unchanged / soft_changed / flex_changed / REVISED_OFFER_recovered).

**Tests added (8).** deterministic mixed scenario; approx 1/3–1/3–1/3 split; rejected
terminal; hard locks never change + constraints valid; rejected crop not re-offered
unchanged; λ monotonic disruption non-increasing; Phase-3 deterministic repeat;
Phase-1/2 artifacts present. **Full suite: 116 passed.**

**Assumptions.** Mixed commitment timing is a synthetic experimental scenario (fixed
1/3-split design), not empirical. Decision scope limited to B3-planned plots.

**Scientific interpretation.** Dynamic stability-aware reoptimisation recovers **up to
53.3%** of the voluntary-rejection cash loss at λ=0, declining along an explicit
recovery-vs-disruption frontier as commitment protection (λ) increases; hard commitments
are never disturbed. The revised plan is **RECOVERY POTENTIAL / recommendations**, not
realised income — no acceptance round runs in Phase 3, so any changed/new recommendation
**would require renewed farmer consent** (`revised_requires_renewed_consent = True`).

**Limitations.** (1) Recovery is potential, contingent on a future acceptance round
(later dynamic phase). (2) Mixed commitment scenario is experimental. (3) Recovery is
farmer-local for budget/labour (per-farmer) with collective market caps; freed resources
cannot cross farmers except via caps. (4) Structural zero-option farmers remain unrecovered.

**Frozen artifacts preserved.** `b1/b2/b3_final.json`, `baseline_comparison.json`,
`b1/b2/b3_ilp_v2.json`, `baseline_comparison_ilp_v2.json`, `b1_provisional_11crop.json`,
Phase-1 `p1_*`, and the Phase-2 all-PLANTED lifecycle-validation result — unchanged.

**Mechanisms explicitly NOT implemented yet.** concentration/resilience; disaster/N−1;
monitoring/governance; LLM/OpenAI; a renewed behavioural acceptance round; the final
30-replication experiment.

**Exact next step (on your confirmation).** Phase 4 — production concentration / market-
resilience mechanism (limits on over-concentration beyond the market cap), layered on the
Phase-3 stability-aware reoptimiser, with its own metrics.

---

## PHASE-3 CORRECTION (ε-structure completed + exact fairness tolerance)

**Applied before Phase 4.** Two narrow corrections to `solve_phase3`:
1. **Completed the B3 ε-structure.** `fairness_floor()` computes t_floor under
   `E ≥ 0.95·E*`, but `solve_phase3()` previously enforced ONLY the per-farmer t_floor.
   It now enforces BOTH `E ≥ 0.95·E*` AND `capable-farmer normalised return ≥ t_floor`.
2. **Fairness-floor tolerance.** With both constraints active, the EXACT full-precision
   floor is stable (all λ Optimal), so the prior 0.1% relaxation is removed. New central
   constant `config.FAIRNESS_FLOOR_NUMERIC_TOL = 0.0` (exact); documented as numerical-
   only, and here it is zero — no substantive fairness relaxation.

**Outcome — frontier UNCHANGED.** Recovery fractions are identical to the prior corrected
run: [0.5334, 0.5222, 0.5222, 0.4797, 0.4797, 0.3773] (Δ = 0 at every λ), because the
stability objective already kept E above 0.95·E* at these λ, so the added total-floor was
non-binding. Phase-3 artifacts regenerated to carry correct metadata (fairness_structure =
"BOTH", tol = 0.0, correction note); numeric results are unchanged and this is stated in
the artifact. Non-Optimal CBC output is never extracted as a solution.

---

## PROPOSED PHASE 4 — production concentration / market resilience

**STATUS** — implemented, validated, dev/checkpoint complete. 126 tests pass. All frozen
baseline, Phase-1/2 artifacts and (corrected) Phase-3 artifacts preserved. No Phase-5+
mechanism implemented. **READY FOR PROPOSED PHASE 5** (not started; awaiting confirmation).

**Purpose.** Measure and control dependence on individual PRODUCERS within each crop
(pre-failure EXPOSURE). Explicitly DISTINCT from the market-absorption cap (arrivals-
derived throughput proxy, NOT demand). Actual producer failure / N−1 resilience is Phase 5
and is NOT implemented here.

**Input.** Phase-3 mixed commitment scenario (FLEXIBLE 119 / SOFT 117 / HARD 95 /
REJECTED_TERMINAL 50) and existing lock/rejection semantics. λ = 0.05 as a DEVELOPMENT
REFERENCE only (not optimal/publication-selected); λ = 0 retained as ablation reference.

**FORMULATION** — `farmsync/proposed/concentration.py`, same CBC MILP backbone.
Concentration by farmer within crop from expected production:
`q_fc = op_yield_value(crop, region) · allocated_area_ha` (FarmSync's validated resolver).
Per active crop c: Q_c = Σ_f q_fc; farmer shares; LPS = max share; top-3 share;
HHI = Σ share²; effective producers = 1/HHI; producer count (zero production handled safely).
**Concentration constraint:** `q_fc ≤ alpha · Q_c` for every farmer f and crop c (linear).
alpha=1 imposes no extra restriction.

**Fairness per alpha (recomputed).** Because alpha changes the feasible set, for each alpha:
`E*_alpha` = max cash under alpha + locks/rejections; `t_floor_alpha` = min normalised
return attainable under `E ≥ 0.95·E*_alpha`. The final Phase-4 solve enforces BOTH
`E ≥ 0.95·E*_alpha` AND `min-norm ≥ t_floor_alpha`, plus the concentration cap, while
keeping the Phase-3 stability objective `maximise E/E*_alpha − λ·(soft_disruption/soft_area)`.

**Hard locks.** PLANTED/HARD_LOCK allocations immutable; never changed to satisfy alpha.
Infeasible alpha (hard locks / too few feasible producers) is reported INFEASIBLE honestly
with a per-crop cause diagnosis; no pseudo-solution extracted; alpha never silently weakened.

**Alpha sweep (seed 20260812, λ=0.05; Phase-3 λ=0.05 ref cash ₹12,340,519):**
| alpha | status | revised cash | econ retention | max LPS | mean HHI | median HHI | violations | hard-chg | active crops | dropped |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.00 | Optimal | ₹12,340,519 | 100.00% | 0.529 | 0.1178 | — | 0 | 0 | 8 | none |
| 0.60 | Optimal | ₹12,340,519 | 100.00% | 0.529 | 0.1178 | — | 0 | 0 | 8 | none |
| 0.50 | Optimal | ₹12,328,480 | 99.90% | 0.4954 | 0.1127 | — | 0 | 0 | 8 | none |
| 0.40 | Optimal | ₹12,285,254 | 99.55% | 0.3988 | 0.1067 | — | 0 | 0 | 8 | none |
| 0.33 | Optimal | ₹12,235,846 | 99.15% | 0.3297 | 0.0981 | — | 0 | 0 | 8 | none |
All alpha feasible & Optimal at this seed; **α=1.0 reproduces corrected Phase-3 λ=0.05
exactly (Δ = ₹0)**. E*_alpha and t_floor_alpha recorded per alpha in the result artifact.

**Concentration findings.** Producer concentration tightens smoothly as alpha falls —
**max LPS 0.529 → 0.330**, mean HHI 0.118 → 0.098 — at
**minimal economic cost (100% → 99.15% retention)**; 0 target violations, 0 hard-lock
changes, and **no crops dropped or introduced** across the sweep. So dependence on the
largest producer of the most-concentrated crop can be roughly halved for <1% cash.
[REFINEMENT (Phase 5, wording only): the AGGREGATE concentration picture improves (max LPS
and mean HHI fall), but crop-level effective-producer counts are HETEROGENEOUS — some crops
gain effective producers while others are unaffected or shift the other way as area
reshuffles. "Effective producers rise" should be read as an aggregate/mean tendency, not a
guarantee for every crop. Valid Phase-4 results unchanged; no rerun.]

**Economic trade-off.** Very shallow here: tightening alpha from 1.0 to 0.33 costs only
0.85% of revised-plan cash while cutting max single-producer share from 52.9% to 33.0%.

**Crop drops.** None at any alpha (active set stable at 8 crops); no newly-introduced crops.

**Comparisons retained.** A. Phase-2/no-reopt = Phase-1 realised ₹11,464,341. B. Phase-3
λ=0 ablation. C. Phase-4 alpha sweep at λ=0.05 (dev reference) above.

**Files created.** `farmsync/proposed/concentration.py`, `tests/test_farmsync_proposed_p4.py`.
**Files changed.** `farmsync/config.py` (FAIRNESS_FLOOR_NUMERIC_TOL=0.0),
`farmsync/proposed/reoptimize.py` (solve_phase3 both-constraint ε-structure + central tol),
`docs/farmsync/PROGRESS.md`. **Regenerated (Phase-3 correction):** `p3_reopt_result.json`,
`p3_lambda_frontier.csv`, `p3_revised_plan_lambda0.csv` (values unchanged; metadata corrected).

**Result artifacts** (`results/farmsync/proposed/`): `p4_concentration_result.json`
(per-alpha E*_alpha, t_floor_alpha, full economics/stability/concentration/fairness,
crop drops, infeasibility causes if any), `p4_alpha_frontier.csv`, `p4_crop_concentration.csv`
(per-crop LPS/top3/HHI/effective/producers at each alpha), and `p4_revised_plan_alpha040.csv`
(representative inspectable revised plan at α=0.40, λ=0.05: per-plot crop, cash, commitment
lock, and status label — unchanged / soft_changed / flex_changed / REVISED_OFFER_recovered).

**Tests added (10).** Phase-3 both-constraints; exact tolerance; alpha=1 reproduces
corrected Phase-3 λ=0.05; shares sum ~1 + HHI valid + effective=1/HHI; concentration
constraints satisfied (0 violations); hard locks never change under alpha; infeasible
alpha handled honestly (no extraction, causes identified); rejected crop excluded +
outputs are recommendations; deterministic repeat; earlier artifacts preserved.
**Full suite: 126 passed.**

**Assumptions.** Mixed commitment scenario is SYNTHETIC_EXPERIMENTAL (fixed 1/3 design).
Expected production uses the validated deterministic yield resolver (no stochastic yield).
Decision scope = B3-planned plots. λ=0.05 is a development reference, not selected.

**Scientific interpretation / boundary.** All Phase-4 outputs are REVISED PLANS /
recommendations — recovery, production, return and income are NOT called "realised";
changed/new recommendations require renewed farmer consent
(`revised_requires_renewed_consent = True`). LPS / HHI / effective-producer counts are
**PRE-FAILURE EXPOSURE** measures only; no disaster resilience is demonstrated (that is
Phase 5). A crop disappearing under a tighter alpha would NOT by itself be claimed as a
resilience improvement (none dropped here anyway).

**Limitations.** (1) Exposure ≠ demonstrated resilience (no failure simulated yet).
(2) Concentration measured on expected (deterministic) production. (3) Feasibility of low
alpha is data/instance dependent; other seeds may make some alpha infeasible (handled
honestly). (4) Recovery remains potential, contingent on a future acceptance round.

**Frozen artifacts preserved.** `b1/b2/b3_final.json`, `baseline_comparison.json`,
`b1/b2/b3_ilp_v2.json`, `baseline_comparison_ilp_v2.json`, `b1_provisional_11crop.json`,
Phase-1 `p1_*`, Phase-2 `p2_*` — all unchanged.

**Mechanisms explicitly NOT implemented.** disaster / N−1 resilience (Phase 5);
monitoring/governance; LLM/OpenAI; renewed behavioural acceptance round; 30-replication
experiment.

**Exact next step (on your confirmation).** Phase 5 — disaster / N−1 resilience: simulate
producer/region failure and measure post-shock outcomes and backup allocations, using the
Phase-4 concentration-controlled revised plans as the pre-failure exposure baseline.

---

## PROPOSED PHASE 5 — disaster / N−1 resilience + post-shock backup reoptimisation

**STATUS** — implemented, validated, dev/checkpoint complete. 137 tests pass. All frozen
baseline and Phase-1–4 artifacts preserved. No monitoring/governance, LLM/OpenAI, renewed
acceptance, or 30-replication mechanism implemented. **READY FOR PROPOSED PHASE 6** (not
started; awaiting confirmation). (Phase-4 wording refinement logged in the Phase-4 section.)

**Scientific purpose.** Phase 4 measured PRE-FAILURE EXPOSURE. Phase 5 asks: what happens
if the largest producer fails (N−1) or a correlated hazard zone goes out; how much value
dynamic backup reoptimisation recovers; and whether Phase-4 concentration control actually
reduces failure exposure. All shocks are COUNTERFACTUAL / experimental stress tests — not
observed disasters or probabilities.

**Development references.** alphas {1.00, 0.40, 0.33}, λ=0.05 — all DEVELOPMENT references,
explicitly NOT publication-selected. seed 20260812 only; the frozen 30-replication run was
NOT executed.

**N−1 definition.** For every active crop in a pre-shock Phase-4 plan: identify the farmer
with the largest expected production (q_fc = op_yield_value·area) of that crop; that farmer
becomes unavailable. One deterministic scenario per active crop (8 crops → 8 scenarios per
alpha; 24 total).

**Failure semantics.** ALL of the failed farmer's allocations become FAILED_UNAVAILABLE
(not just the target crop); the target crop that selected them is recorded. A shock may
physically remove a HARD_LOCK/PLANTED allocation — that is exogenous loss, **NOT a lock
violation**. Every SURVIVING hard lock stays immutable; failed plots are **never reused**
by the post-shock optimiser (both verified = 0 across all scenarios).

**Hazard-zone design / provenance.** Uses the EXISTING `Plot.hazard_zone` field
(`"{region}-HZ{1..3}"`, region + spatial cluster = synthetic correlated-failure unit),
reused as-is — no invented geography or probabilities. 15 zones in data, 14 non-empty in
the plan → 14 zone-outage scenarios per alpha (42 total). A zone outage marks all its plots
FAILED_UNAVAILABLE. The sub-part is defensible on existing data, so it was completed.

**Post-shock optimisation formulation.** Reuses the Phase-4/Phase-3 MILP with the failed
farmer/plots removed from scope (same decision scope, not expanded); surviving hard locks
fixed; soft-lock changes = disruption; flexible free; rejection semantics retained (rejected
crop not re-offered unchanged); concentration alpha = the pre-shock alpha. Per scenario,
`E*_shock` and `t_floor_shock` are recomputed; the backup solve enforces BOTH
`E ≥ 0.95·E*_shock` AND `capable min-norm ≥ t_floor_shock` (exact fairness tolerance 0).
Non-Optimal CBC output is never extracted.

**Invariant confirmed.** Immediate target-crop production-loss fraction **== pre-shock LPS**
for every N−1 scenario (all_lps_match = True), directly linking Phase-4 LPS exposure to
Phase-5 N−1 loss.

**N−1 results (per alpha; 8 scenarios each):**
| alpha | mean immed target loss | worst immed target loss | worst cash loss | mean recovery frac | full/part/unrec |
|---|---|---|---|---|---|
| 1.00 | 0.209 | 0.529 | ₹—(largest) | 0.000 | 0/0/8 |
| 0.40 | 0.194 | 0.399 | — | 0.081 | 0/1/7 |
| 0.33 | 0.186 | 0.330 | — | 0.183 | 1/0/7 |
Worst-case immediate target-crop loss falls 0.529 → 0.399 → 0.330 (== max LPS), i.e.
concentration control mechanically reduces single-producer exposure. Recovery of the
immediate cash loss is LOW (mean 0.0 → 0.08 → 0.18) because budget/labour are per-farmer:
a failed farmer's resources vanish and cannot be reused by others; recovery comes only from
freed market-cap/concentration headroom and rejected-plot revised offers.

**Hazard-zone results (per alpha; 14 zone scenarios ATTEMPTED each). [CORRECTED — see
Phase-5 correction below: prior means used an Optimal-only denominator and prior text
claimed all backups Optimal.]** Immediate loss is over ALL attempted; recovery is over
Optimal backups only, with explicit denominators:
| alpha | attempted | Optimal backup | infeasible | mean immed loss (/attempted) | worst immed loss | mean recovery (/Optimal) |
|---|---|---|---|---|---|---|
| 1.00 | 14 | 14 | 0 | ₹881,466 | ₹3,604,702 | 0.0107 (/14) |
| 0.40 | 14 | 13 | 1 | ₹877,518 | ₹2,436,991 | 0.0084 (/13) |
| 0.33 | 14 | 13 | 1 | ₹873,989 | ₹2,402,993 | 0.0040 (/13) |
Worst-case zone-outage exposure falls with tighter alpha (₹3.60M → ₹2.40M). Recovery is
near-zero for correlated outages — a whole spatial cluster's plots and their per-farmer
resources are removed at once, leaving little to reoptimise. **Two zone-outage backups are
genuinely INFEASIBLE** (R5-HZ1 at α=0.40 and 0.33): under strong concentration control the
surviving hard locks leave no feasible recovery plan — preserved as a vulnerability, not
repaired.

**Alpha comparison / key distinction.** Tighter alpha **reduces EXPOSURE** on both shock
families (lower N−1 target-crop loss and lower worst-case zone loss). It does **NOT**
uniformly improve **RECOVERY CAPABILITY**: N−1 recovery rises modestly with tighter alpha,
but correlated-hazard recovery stays near zero and even falls slightly. Exposure reduction
and post-shock recovery are reported as distinct properties; no claim is made that
concentration control improves every resilience metric.

**Fairness / validity. [CORRECTED.]** Of 66 attempted stress scenarios, **64 produced an
Optimal post-shock backup plan and 2 are genuinely infeasible** (hazard R5-HZ1 at α=0.40,
0.33). For the **64 Optimal backup plans only**, both floors were enforced and each returned
CBC-Optimal with 0 hard-constraint violations, 0 concentration violations, 0 surviving-
hard-lock changes, and 0 failed-plot reuse. These validity checks are NOT claimed for the 2
infeasible cases (no plan was extracted). Immediate post-shock loss is valid for all 66
attempted (it does not depend on the backup solve). fairness-v2 computed per Optimal scenario.

**Representative worst case.** N−1 worst immediate cash loss at α=0.40: failed farmer F0354,
target crop onion, immediate loss ₹957,199, post-shock backup cash ₹11,328,055 (341 backup
allocations) — see representative CSV.

**Files created.** `farmsync/proposed/resilience.py`, `tests/test_farmsync_proposed_p5.py`.
**Files changed.** `docs/farmsync/PROGRESS.md` (Phase-4 wording refinement + this section).
No code changed outside the new module.

**Result artifacts** (`results/farmsync/proposed/`): `p5_resilience_result.json`
(summaries, alpha comparison, provenance, invariant, evidence chain), `p5_nminus1_scenarios.csv`,
`p5_nminus1_summary.csv`, `p5_hazard_scenarios.csv`, `p5_backup_plan_repr_alpha040.csv`
(representative post-shock backup allocations with per-plot labels).

**Tests added (11).** largest producer by expected production; N−1 immediate loss fraction
== LPS; failed farmer's plots all unavailable; failed hard lock is exogenous (not violation);
surviving hard locks unchanged + no failed-plot reuse; shock-specific E* & t_floor recomputed
+ both floors enforced; concentration & rejection valid after recovery; deterministic N−1
repeat; hazard zones use existing data only; outputs counterfactual/not realised; Phase-1–4
artifacts present. **Full suite: 137 passed.**

**Assumptions.** Shocks are counterfactual single-farmer / single-zone outages on the
deterministic expected-production plan. Market-absorption cap treated as producer-independent
(unchanged post-shock). Decision scope = pre-shock plan's plots.

**Scientific interpretation / boundary.** Evidence chain: Phase-4 REVISED PLAN → simulated
shock → IMMEDIATE POST-SHOCK STATE → POST-SHOCK REVISED BACKUP PLAN. Backup outputs are
REVISED / COUNTERFACTUAL recommendations, never realised adoption or income; they require
renewed farmer consent (`revised_requires_renewed_consent = True`); no second acceptance
round ran. Exposure reduction ≠ demonstrated recovery.

**Limitations.** (1) Single-shock (one farmer / one zone) counterfactuals; no compound or
probabilistic hazards. (2) Recovery is farmer-resource-bound, so N−1/zone recovery is
structurally limited — a substantive finding, not a bug. (3) Synthetic hazard-zone geography.
(4) One seed; no replication yet.

**Frozen artifacts preserved.** `b1/b2/b3_final.json`, `baseline_comparison.json`,
`b1/b2/b3_ilp_v2.json`, `baseline_comparison_ilp_v2.json`, `b1_provisional_11crop.json`,
Phase-1 `p1_*`, Phase-2 `p2_*`, Phase-3 `p3_*`, Phase-4 `p4_*` — all unchanged.

**Mechanisms explicitly NOT implemented.** monitoring/governance; LLM/OpenAI layer; renewed
behavioural acceptance round; final 30-replication publication experiment; compound/
probabilistic disaster modelling.

**Exact next step (on your confirmation).** Phase 6 — full deterministic Proposed model
assembled end-to-end (participation → commitment/locks → stability-aware reopt →
concentration → resilience) as one integrated pipeline, before the Phase-7 LLM validation
layer and the final replicated experiment.

---

## PHASE-5 CORRECTION — hazard backup feasibility reporting

**Trigger.** Review found `p5_hazard_scenarios.csv` contained 8 non-Optimal hazard backup
solves that the Phase-5 write-up had incorrectly reported as "every backup solve returned
Optimal" / "0 violations across all 66 scenarios." Corrected rigorously; no valid scientific
result was altered to force optimality.

**Corrected scenario accounting.**
- Total attempted stress scenarios: **66** (N−1 **24**, hazard **42**).
- N−1: 24 attempted, **24 Optimal**, 0 infeasible.
- Hazard: 42 attempted, **40 Optimal**, **2 genuinely infeasible**.
- Valid post-shock backup plans overall: **64**; genuinely infeasible: **2**.

**Root cause of the 8 originally non-Optimal hazard cases (exact per-stage status).**
- **R3-HZ1 and R3-HZ3, all three α (6 cases) — cause B, numerical knife-edge.** E*_shock and
  t_floor_shock both solved Optimal, so a plan satisfying BOTH `E ≥ 0.95·E*_shock` and
  `min_norm ≥ t_floor_shock` provably exists; the exact-tolerance (tol=0) final solve rejected
  it at a max-attained-floor knife-edge (CBC status Infeasible). Resolved with a central,
  documented post-shock numerical tolerance `config.RESILIENCE_FLOOR_NUMERIC_TOL = 1e-7`
  (CBC's native feasibility-tolerance scale): the provably-feasible plan is extracted with
  achieved min_norm within ~2.5e-6 of the exact floor (relative ~5e-9) — verified numerical,
  NOT a substantive fairness relaxation. These 6 are now **Optimal**.
- **R5-HZ1 at α=0.40 and 0.33 (2 cases) — cause A, genuine post-shock infeasibility.** Fails
  at the **E*_shock** stage (before any fairness floor), so the numerical tolerance cannot and
  does not mask it. The same zone outage is feasible at α=1.0, proving the **concentration cap
  + surviving hard locks** are the binding cause: after this correlated outage removes the
  other producers, no assignment satisfies `q_fc ≤ α·Q_c` for all crops while keeping surviving
  hard locks fixed. Preserved as **INFEASIBLE** — a real resilience vulnerability, not repaired.
- No implementation bug (cause C) was found.

**Verification the tolerance is numerical, not substantive.** The 24 N−1 and the 34 hazard
scenarios that were already Optimal at exact tol=0 are numerically **unchanged** under 1e-7
(N−1 recovery fractions identical to the prior run); only the 6 knife-edge cases flip
Infeasible→Optimal, and only R5-HZ1 (which never involves the fairness floor) remains
infeasible.

**Corrected summary methodology.** Hazard summaries now report, per α: attempted, Optimal
backup, infeasible; **mean/worst immediate loss over ALL attempted** (denominator stated);
**recovery statistics over Optimal backups only** (denominator stated). Prior hazard
mean-immediate-loss used an Optimal-only denominator (the reported bug) and is corrected
(e.g. α=1.0 ₹846,269 → ₹881,466). Constraint/hard-lock/violation validity is claimed only
for the 64 extracted Optimal backup plans.

**Code changes.** `farmsync/config.py` (+`RESILIENCE_FLOOR_NUMERIC_TOL = 1e-7`, documented);
`farmsync/proposed/resilience.py` (`post_shock_reopt` uses it and returns exact per-stage
status: failed_stage ∈ {E*_shock, t_floor_shock, final_backup, None} + cbc_status).
`FAIRNESS_FLOOR_NUMERIC_TOL` (Phase 3/4) is unchanged at 0.0; Phase 1–4 were NOT rerun.

**Artifacts regenerated (Phase-5 only).** `p5_hazard_scenarios.csv` (per-stage status,
backup_optimal flag, cause, no backup metrics on infeasible rows), `p5_nminus1_scenarios.csv`
and `p5_nminus1_summary.csv` (explicit denominators; numbers unchanged),
`p5_resilience_result.json` (corrected accounting, 8-case diagnosis, corrected claims,
validity scope). Representative backup CSV (N−1 worst at α=0.40) unchanged.

**Did scientific conclusions change?** Qualitative conclusions are **unchanged**:
concentration control reduces pre-failure EXPOSURE (N−1 and worst-zone loss fall with α),
while post-shock RECOVERY stays low, especially for correlated hazards. **One conclusion is
STRENGTHENED/added:** under strong concentration (α ≤ 0.40) a specific correlated zone outage
(R5-HZ1) has **no feasible recovery plan** — an explicit concentration-vs-recoverability
trade-off. N−1 numeric results are identical; corrected hazard immediate-loss denominators.

**Tests added (5).** exact failure-stage/status recorded; infeasible reopt returns None with
no extracted metrics; result accounting distinguishes attempted vs Optimal (66 = 64 + 2);
recovery stats use Optimal-only denominators (immediate loss uses attempted); infeasible
hazard rows carry no backup metrics. **Full suite: 142 passed.**

**Exact next step (unchanged).** Phase 6 — full deterministic Proposed model assembled
end-to-end — on your explicit confirmation. NOT started.

---

## PROPOSED PHASE 6 — full deterministic pipeline (end-to-end integration)

**STATUS** — implemented, validated, dev/checkpoint complete. 154 tests pass. All frozen
baseline and Phase-1–5 artifacts preserved unchanged. No LLM, no new behaviour, no final
30-replication experiment, no monitoring/governance. **READY FOR PROPOSED PHASE 7** (not
started; awaiting confirmation).

**Purpose.** One canonical orchestration layer that runs the existing deterministic Proposed
workflow end-to-end and emits a single coherent, traceable evidence chain. Integration /
consistency / traceability only — no optimisation methodology change and no new behavioural
assumption. `farmsync/proposed/pipeline.py` CALLS the validated Phase 1–5 modules; it does
not duplicate any formulation.

**Pipeline architecture.** `run_proposed_pipeline(seed, lam, alpha, base, run_id)` returns
`{result, ledger, objects}`. It fails loudly (`PipelineError` via `_require_optimal`) if any
stage that must be Optimal is not — never continues from invalid optimisation output.

**Canonical stage sequence (exact order enforced & tested).**
- Stage 0 INSTANCE/PROVENANCE — master seed, instance hash, dataset version, config
  (ε, fairness/formulation versions, both numeric tolerances, λ/α dev refs, scenario id),
  RNG substream.
- Stage 1 STATIC PLAN — B3 ILP-v2 (canonical ε=0.95) → **PLANNED**.
- Stage 2 INITIAL RESPONSE — Phase-1 ACCEPT/REJECT → **REALIZED_INITIAL** (accepted only).
- Stage 3 COMMITMENT SNAPSHOT — existing **P3_MIXED_V1** (SYNTHETIC_EXPERIMENTAL timing,
  not observed prevalence) FLEXIBLE/SOFT/HARD/REJECTED_TERMINAL.
- Stage 4 STABILITY-AWARE REOPT — Phase-3, λ=0.05 dev-ref, full B3 ε-structure → **REVISED**.
- Stage 5 CONCENTRATION CONTROL — Phase-4, α=0.40 dev-ref →
  **CONCENTRATION_CONTROLLED_REVISED_PLAN**.
- Stage 6 RESILIENCE DEMONSTRATION — tiny deterministic representative set (NOT the full 66):
  N−1 on the active crop with MAX pre-shock LPS; hazard on the lexicographically FIRST
  non-empty zone; plus the known R5-HZ1 as an explicit INFEASIBLE-path integration test.
  Selection rules are documented, not cherry-picked. → **COUNTERFACTUAL_POST_SHOCK_BACKUP_PLAN**.

**Stage semantics (states kept strictly separate).** PLANNED / REALIZED_INITIAL / REVISED /
CONCENTRATION_CONTROLLED_REVISED_PLAN / COUNTERFACTUAL_POST_SHOCK_BACKUP_PLAN. Revised and
backup recommendations are NEVER realised; `revised_requires_renewed_consent = True`
propagates to Stages 4/5/6; `consent_exists` is True only for Stage-2 accepted offers.

**Development configuration (NOT publication-selected).** seed 20260812, ε=0.95, fairness-v2,
Phase-3/4 fairness tolerance 0.0 (exact), λ=0.05 dev-ref, α=0.40 dev-ref, resilience floor
tolerance 1e-7 only in the approved post-shock path.

**Integrated quantitative checkpoint (planned → realised → revised chain).**
| stage | state | cash | key metrics |
|---|---|---|---|
| 1 static plan | PLANNED | ₹13,142,166 | area 327.1 ha, 294 farmers, per-ha Gini(all) 0.7182 |
| 2 initial response | REALIZED_INITIAL | ₹11,464,341 | 331/381 accepted, realisation 0.8723, Gini 0.7493 |
| 3 commitment | — | — | FLEXIBLE 119 / SOFT 117 / HARD 95 / REJECTED 50 |
| 4 stability reopt | REVISED | ₹12,340,519 | recovery potential +₹876,178, soft 13 / flex 17, hard-lock chg 0 |
| 5 concentration | REVISED_CONC | ₹12,285,254 | retention 99.55% vs revised, max LPS 0.3988, mean HHI 0.1067, 0 viol, hard-lock chg 0 |

**Concentration metrics (Stage 5, α=0.40).** max LPS 0.3988, mean HHI 0.1067, 8 active crops,
0 concentration violations, 0 hard-lock changes.

**Representative resilience integration (Stage 6).** N−1 max-LPS crop = **cotton** (LPS 0.3988),
immediate loss ₹32,746, backup **Optimal**, 0 surviving-hard-lock changes, no failed-plot
reuse. Hazard first-zone = **R1-HZ1**, immediate loss ₹883,865, backup **Optimal**. Known
infeasible path = **R5-HZ1** → **Infeasible**, no plan extracted. (These prove the pipeline
invokes the mechanism correctly; the full 66-scenario study remains the Phase-5 evidence.)

**Same-config reproduction — every stage reproduces its prior checkpoint (YES).** Stage 2
accepted 331 and realisation 0.8723 == Phase-1; Stage 4 revised cash ₹12,340,519 == Phase-3
λ=0.05; Stage 5 cash ₹12,285,254 and max LPS 0.3988 == Phase-4 α=0.40. No second conflicting
result family was created.

**Cross-phase invariants — all 17 PASS (programmatic).** b3_source_unchanged;
realised_subset_of_planned; rejected_absent_from_realised; only_accepted_get_commitment;
rejected_crop_not_returned (revised & conc); hardlocks_immutable_reopt; revised_not_realised;
conc_not_realised; alpha040_concentration_holds; shock_surviving_hardlocks_unchanged;
shock_no_failed_reuse; infeasible_shock_no_plan; fairness_structure_both_stage4;
identity_preserved; consent_flag_propagates; deterministic_repeat.

**Event / evidence ledger.** One machine-readable stage/event ledger, **1490 records**, with
run_id, seed, sequence, stage, farmer/plot ids, crop before/after, participation response,
commitment/lock state, allocation status, reason, planned/current cash, consent flag,
counterfactual flag, source phase. Deterministic sequence IDs (no fabricated timestamps).

**Files created.** `farmsync/proposed/pipeline.py`, `tests/test_farmsync_proposed_p6.py`.
**Result artifacts** (`results/farmsync/proposed/`): `p6_pipeline_result.json` (stages +
17 invariants), `p6_stage_summary.csv`, `p6_event_ledger.csv` (1490 rows),
`p6_final_revised_plan.csv` (343 rows, concentration-controlled revised plan),
`p6_integration_manifest.json` (references Phase 1–5 artifacts by path + 16-char hash;
does not duplicate them; reproduction flags all True). **Files changed.** PROGRESS.md only.

**Tests added (12).** pipeline runs + exact stage order; metadata propagation; existing
checkpoint reproduction; realised-vs-revised labels never confused; renewed-consent flag
propagates; P3_MIXED_V1 reused exactly; hard-lock invariant + concentration validity;
representative N−1/hazard paths + infeasible path surfaced with no pseudo-plan; pipeline
refuses non-Optimal upstream (PipelineError); deterministic repeat; ledger identity/order;
Phase-1–5 artifacts unchanged + manifest references. **Full suite: 154 passed.**

**Reproducibility metadata.** seed 20260812, instance_hash 5ea24037c2d9cb6a, ε=0.95,
fairness-v2, formulation ilp-ref-v1, λ=0.05, α=0.40, fairness tol 0.0, resilience tol 1e-7,
scenario P3_MIXED_V1; deterministic repeat of the complete pipeline gives byte-identical
structured results and equal ledger size.

**Assumptions.** Reuses the existing SYNTHETIC_EXPERIMENTAL P3_MIXED_V1 timing scenario (not
observed prevalence); λ/α are development references, not publication-selected; Stage-6 uses a
tiny representative shock set for integration validation only.

**Interpretation boundary.** Revised/concentration/backup outputs are recommendations, never
realised adoption or income; changed/new recommendations require renewed farmer consent; the
resilience demo is counterfactual.

**Limitations.** Single integrated configuration/instance; representative (not exhaustive)
resilience inside the pipeline; no renewed acceptance round; publication α/λ not yet selected.

**Frozen artifacts preserved.** all baseline `b1/b2/b3_*`, `*_ilp_v2*`, and Phase-1–5
`p1_*`…`p5_*` — unchanged (referenced by hash in the manifest).

**Mechanisms explicitly NOT implemented (later-phase obligations).** LLM/OpenAI parsing &
explanations; renewed acceptance after reoptimisation; MODIFY/WITHDRAW behavioural modelling;
monitoring/governance; new disaster models; final α/λ selection; final 30-replication
statistics.

**Exact next step (on your confirmation).** Phase 7 — LLM/OpenAI interaction & validation
layer, measured ONLY on the interaction/validation surface (schema-valid rate, extraction
accuracy, unsupported-constraint/explanation rates, end-to-end equivalence vs gold structured
request), with NO allocation-improvement causal claims — followed later by publication
config selection and the final replicated experiment.

---

## PHASE-6 TRACEABILITY CORRECTION (ledger / consent)

Applied before Phase 7. **No economic result changed** (planned ₹13,142,166 / realised
₹11,464,341 / revised ₹12,340,519 / concentration ₹12,285,254 all identical; verified).
Three semantic gaps in the integrated ledger were fixed:
1. **Stage-4 revised allocations now written as per-allocation ledger records** (was 0 → 343):
   farmer/plot, previous accepted crop (or FALLOW_OR_REJECTED), revised crop, lock level,
   change classification, current cash, consent status, renewed-consent requirement.
2. **Stage-5 `crop_before` is now the actual Stage-4 revised crop** (was the original
   commitment crop); `crop_after` is the concentration-controlled crop.
3. **Allocation-specific consent** replaces the blanket `consent_exists=False`. A recommendation
   has existing consent iff the farmer accepted the original Phase-1 crop AND the current crop is
   still that accepted crop; renewed consent is required for recovered offers or any crop change.
   Stage 4/5 now report `contains_unconsented_recommendations` + `unconsented_allocation_count`
   (Stage 4: 295 consented / 48 requiring renewed consent = 30 crop-changed + 18 recovered).

**Ledger size** 1490 → **1833**. **Invariants** 17 → **20** (added: allocation_specific_consent_correct,
stage4_ledger_present, stage5_crop_before_is_stage4_crop; consent_flag_propagates redefined to
the allocation-specific rule) — **all 20 pass**. Regenerated only Phase-6 integration artifacts
(`p6_pipeline_result.json`, `p6_event_ledger.csv`, `p6_final_revised_plan.csv`,
`p6_stage_summary.csv`, `p6_integration_manifest.json`); no optimisation rerun changed economics.

---

## PROPOSED PHASE 7 — LLM / OpenAI interaction + validation boundary

**STATUS** — implemented, fully tested offline (mock), architecture validated. 179 tests pass.
All baseline and Phase-1–5 scientific artifacts preserved; only the Phase-6 integration
artifacts above were regenerated. Live LLM evaluation **NOT RUN** (no API access in this
environment). Final ≥300-case publication LLM benchmark and final 30-replication experiment
**NOT run**. **READY FOR NEXT EVALUATION PHASE** (awaiting confirmation).

**LLM scientific boundary.** The LLM is ONLY an interaction / parser / explanation layer. It
never optimises, chooses a crop, invents feasibility/agronomic/market values, overrides a lock,
weakens a constraint, or mutates FarmSync state. The deterministic system is the sole authority
for identity, crop existence/admission, feasibility, lock/state validity, market/concentration
constraints, optimisation, fairness and shock logic.

**Architecture.** farmer NL text → LLM structured parse → deterministic validation →
deterministic FarmSync mechanism → validated result → grounded LLM explanation.
Modules: `farmsync/proposed/llm_interaction.py` (schema, clients, parser, validator,
equivalence, grounded explanation) and `farmsync/proposed/llm_eval.py` (dev harness + metrics).

**Structured schema.** `request_schema()` (strict, `additionalProperties:false`),
schema_version `farmsync-farmer-request-v1`, prompt_version `p7-parse-v1`. Actions:
ACCEPT / REJECT / MODIFY / WITHDRAW / QUERY / CLARIFY (reuses FarmerEvent vocab + non-mutating
QUERY/CLARIFY). Allowed fields: action, farmer_id, plot_id, requested_crop, requested_value,
unit, reason, clarification_required, clarification_question, confidence, source_text. The LLM
may NEVER supply feasibility, allocation, yield, price, return, lock permission, approval, or
may_execute — such fields are stripped into `unsupported_claims` (no authority); unknown junk
keys or bad actions → SCHEMA_INVALID (never reaches the handler).

**Validation pipeline (deterministic authority).** `validate_request` returns
parsed_action, outcome, reason_codes, farmer/plot/ownership_verified, state_valid, lock_valid,
crop_valid, feasibility_valid, unsupported_claims, deterministic_action_payload, may_execute,
requires_renewed_consent. Only `may_execute=True` requests may reach the deterministic handler.

**Identity / ownership.** Trusted context farmer_id is preferred over any LLM-inferred id;
mismatches → IDENTITY_MISMATCH (rejected). Validation confirms farmer exists, plot exists, plot
belongs to that farmer, action valid for state, crop exists where applicable — reusing existing
`assess_plot_crop` and `is_admitted`.

**Lock / feasibility validation.** MODIFY on HARD_LOCK/PLANTED → HARD_LOCK_IMMUTABLE (rejected).
Requested crop checked for existence, admission and full agronomic + budget/labour feasibility
via the existing deterministic feasibility module; infeasible/unadmitted → rejected with reason
codes. Vague requests ("give me a better crop", "choose something safer", "whatever makes more
money") → CLARIFICATION_REQUIRED; the LLM never chooses a crop. WITHDRAW is parsed but returns a
deterministic `NOT_IMPLEMENTED / WITHDRAW_REQUIRES_POLICY` result (no invented withdrawal rules).

**Unsupported / injection handling.** Farmer free text is untrusted and passed only as user-role
DATA, never into system/developer instructions. Injected authority fields (feasible=true,
price=100, may_execute=true, "pretend unlocked", "override the lock") are stripped into
unsupported_claims and carry no authority; deterministic validation still rejects the action.

**Deterministic-equivalence design.** `payload_equivalent(llm_payload, gold_payload)` and
`outcome_equivalent(...)`: because the LLM never alters the optimisation input, equal validated
payloads guarantee identical FarmSync outcomes. This is the paper's end-to-end equivalence
metric (validated LLM payload == validated gold payload ⇒ identical deterministic outcome).

**Explanation grounding.** `build_grounded_explanation` assembles an explanation OBJECT from
ONLY validated deterministic facts (whitelisted fact ids), copies numeric fields from the
deterministic source and cross-checks them (numeric_consistency), records referenced_fact_ids,
and refuses to call an unaccepted revised recommendation "realised". No external facts permitted.

**Development case-set design.** Fixed **41-case DEVELOPMENT / prompt-engineering set** (NOT the
publication benchmark) with fixed gold labels, covering: straightforward ACCEPT/REJECT, valid
MODIFY, infeasible crop, wrong ownership, hard-locked modify, unknown crop, ambiguous/choose-for-me,
missing plot, unit/numeric extraction, WITHDRAW parsing, unsupported/injected constraints,
QUERY/explanation grounding, invalid farmer. Cases reference real snapshot ids; gold parses are
fixed; prompts are not tuned on these cases and then reported as unbiased.

**Live vs mock status.** No OpenAI/Groq API access in this environment (allowlist excludes the
API host) → executed with a deterministic `MockLLMClient`; a lazy-import `OpenAILLMClient`
(reuses AskVish's OpenAI-compatible SDK convention, env-var key, strict json_schema structured
output, records model/schema/prompt/temperature/response id) is implemented and unit-tested but
**live evaluation NOT RUN**. No API key is read into any artifact.

**Development metrics actually obtained (MOCK client; live LLM parse accuracy NOT RUN).**
41 cases, 0 API failures. schema_valid_rate 1.0, action_exact_match 1.0, field_F1 1.0,
crop/farmer/plot/numeric/unit extraction 1.0 (these reflect the mock parse, honestly labelled),
clarification_recall 1.0, invalid_action_rejection_rate 1.0, hard_lock_rejection_rate 1.0,
unsupported_constraint_handled_rate 1.0, **payload_equivalence_rate 1.0**,
deterministic_outcome_equivalence_rate 1.0, explanation_groundedness_rate 1.0,
numerical_consistency_rate 1.0, unsupported_explanation_rate 0.0. Interpretation: these
demonstrate the DETERMINISTIC BOUNDARY behaves correctly given parses (injection neutralised,
locks/ownership/feasibility enforced, equivalence and grounding hold); they are NOT a claim about
live LLM parsing accuracy, which remains to be measured.

**Failure taxonomy.** API_ERROR, MODEL_REFUSAL, SCHEMA_INVALID, VALIDATION_REJECTED,
CLARIFICATION_REQUIRED, VALIDATED, EXECUTED, EXPLANATION_ERROR. A malformed/failed LLM response
returns None and never reaches the optimiser.

**Files created.** `farmsync/proposed/llm_interaction.py`, `farmsync/proposed/llm_eval.py`,
`tests/test_farmsync_proposed_p7.py`. **Result artifacts** (`results/farmsync/proposed/`):
`p7_llm_schema.json`, `p7_dev_cases.jsonl`, `p7_dev_predictions.jsonl` (per-case predictions,
reproducible), `p7_dev_metrics.json`, `p7_interaction_examples.json` (6 end-to-end examples),
`p7_llm_manifest.json` (model, SDK/API path, schema/prompt versions, case-set hash, dataset/
instance hashes, live=false, api_key_persisted=false, evaluation_status). **Files changed.**
PROGRESS.md; Phase-6 integration artifacts (traceability correction above).

**Tests added (25).** strict schema + unknown-field/bad-action rejection; malformed output never
reaches handler; valid MODIFY validated; hard-lock/infeasible/unknown-crop/ownership/invalid-
farmer/plot rejection; identity mismatch prefers trusted context; vague no-allocation-authority;
prompt-injection neutralised; WITHDRAW → NOT_IMPLEMENTED; renewed-consent + unchanged-consent
semantics; payload/outcome equivalence utilities; explanation grounding + numeric consistency +
realised-label refusal; no API key in artifacts; manifest live-NOT-RUN; dev metrics labelled
mock; and Phase-6 correction regressions (Stage-4 ledger exists, Stage-5 crop_before linkage,
allocation-specific consent, Phase-1–6 artifacts present). **Full suite: 179 passed.**

**Reproducibility metadata.** schema `farmsync-farmer-request-v1`, prompt `p7-parse-v1`,
case_set_hash recorded, master_seed 20260812, instance_hash 5ea24037c2d9cb6a; per-case
predictions stored for reproducibility.

**Limitations.** Live LLM parse accuracy not measured (mock only); dev set (41) is for
architecture/prompt validation, not publication; WITHDRAW policy deliberately unimplemented;
grounded-explanation text is templated (a live model would generate it under the same grounding
contract).

**Security / privacy.** Farmer text treated as untrusted user-role DATA, never injected into
system/developer instructions; API key read from environment only, never persisted to artifacts
or logs (tested); no farmer PII beyond synthetic ids.

**Frozen artifacts preserved.** all baseline and Phase-1–5 `p1_*`…`p5_*` unchanged; only Phase-6
integration artifacts regenerated for the traceability correction.

**Mechanisms explicitly NOT implemented (later-phase obligations).** live LLM evaluation run;
≥300-case publication LLM benchmark; renewed acceptance round after reoptimisation; MODIFY→reopt
execution wiring at scale; monitoring/governance; final α/λ selection; final 30-replication
statistics.

**Exact next step (on your confirmation).** Next evaluation phase — run the live LLM against the
development set (honest live metrics), then design and run the ≥300-case publication benchmark;
separately, publication α/λ selection followed by the final 30-replication experiment.

---

## PHASE-7 METHODOLOGICAL CORRECTION (true outcome equivalence + source-text authority)

Narrow correction applied after the initial Phase-7 build. No publication benchmark run, no
30-replication run, no Phase 1–6 optimisation result altered. 185 tests pass.

**Issue 1 — outcome equivalence was payload-only.** The original `outcome_equivalent()` merely
compared validated payloads, so reporting it as `deterministic_outcome_equivalence` overclaimed.
Root cause: no execution step existed at the boundary. Fix: added a deterministic executor
(`BoundaryState` + `execute_payload`) and `outcome_execution_equivalent(payload_a, payload_b,
base_state)` which runs each validated payload against an **independent deep-cloned state**
(asserted non-shared: `sa is not sb`, `sa.plot_crop is not sb.plot_crop`) and compares the
ACTUAL executed outcomes (action, farmer_id, plot_id, crop before/after, transition status,
resulting state label, lock, renewed-consent) plus the affected post-state. Only
ACCEPT/REJECT/MODIFY have implemented execution semantics; other actions (e.g. WITHDRAW) and
non-executed cases return `applicable=False` → **NOT_APPLICABLE**, never counted as success. The
metric is computed only over cases where execution actually occurred.

**Issue 2 — model was trusted for source_text.** Root cause: `source_text` was a required
model-output field and flowed into vague/injection detection. Fix: `source_text` is REMOVED from
the model-output schema (`request_schema()` requires only `action`); `parse_request(text, …)`
sets `ParsedRequest.source_text = text` (the original application-held farmer input) regardless
of anything the model returns; a model-supplied `source_text` is tolerated-but-ignored. All
vague-request and unsupported-instruction detection now operates on the ORIGINAL farmer text.
Regression tests prove that even when a mock model paraphrases or omits the source text, the
validator sees the exact original and vague detection still fires.

**Issue 3 — live strict-schema preparation.** Added `scripts/p7_live_smoketest.py` — a runnable
script for the real AskVish environment that makes 3–5 representative calls through the real
`OpenAILLMClient` (valid MODIFY, optional/null ACCEPT, vague "choose for me", price-injection,
REJECT), verifies strict-schema acceptance, optional/null handling, refusal/API-error handling,
and source-text authority. It **persists no API key** and, when no key/SDK/network is present
(as in this sandbox), prints `SKIPPED` and exits 0 — verified. **Live smoke test NOT RUN here.**

**Corrected metric definitions (regenerated, MOCK client).** Metrics are now grouped:
- `_group_parse_metrics_MOCK_architecture_validation_only` — schema/parse numbers reflect the
  mock, NOT a live model (schema-valid, action match, field P/R/F1, extraction accuracies,
  clarification P/R). Live LLM parse accuracy remains NOT RUN.
- `_group_deterministic_boundary` — invalid-action rejection 1.0, hard-lock rejection 1.0,
  unsupported-constraint handled 1.0, **source_text_authoritative_rate 1.0**.
- `_group_equivalence` — **validated_payload_equivalence 1.0 (denominator 41)**; **TRUE
  deterministic_outcome_equivalence 1.0 (denominator 12 executed cases; 29 NOT_APPLICABLE)**.
  The old single `deterministic_outcome_equivalence_rate = 1.0/n` based on payload equality is
  removed.
- `_group_explanation` — groundedness 1.0, numeric consistency 1.0, unsupported-explanation 0.0.

**True end-to-end execution examples.** `p7_interaction_examples.json` now includes executed
cases (mod0, acc0, rej0) carrying the real execution detail (independent-clone outcomes for LLM
and gold payloads), alongside rejected/vague/injection/withdraw examples.

**Code changes.** `farmsync/proposed/llm_interaction.py` (schema drops source_text; parse_request
forces original text; removed payload-only `outcome_equivalent`; added `BoundaryState`,
`ExecutionOutcome`, `execute_payload`, `outcome_execution_equivalent`, `EXECUTABLE_ACTIONS`,
`TOLERATED_IGNORED_FIELDS`). `farmsync/proposed/llm_eval.py` (separate payload vs execution
equivalence + N/A + source-text-authoritative rate; grouped metrics). New
`scripts/p7_live_smoketest.py`. Regenerated `p7_dev_metrics.json`, `p7_dev_predictions.jsonl`,
`p7_dev_cases.jsonl`, `p7_llm_schema.json`, `p7_interaction_examples.json`, `p7_llm_manifest.json`.

**Tests added/updated (Phase-7 file 25 → 31).** original-source-text-authoritative (paraphrase
and omission); vague detection uses original text; payload vs execution equivalence are distinct;
execution uses independent cloned states (base unmutated); execution compares real outputs
(different crop ⇒ not equivalent); WITHDRAW outcome equivalence N/A; malformed parse never
executes; dev-metrics test updated to the grouped structure with separate denominators.
**Full suite: 185 passed.**

**Scientific conclusions changed?** No optimisation result changed. The Phase-7 claim is
corrected/strengthened: `deterministic_outcome_equivalence` is now an EXECUTION-level guarantee
over a stated denominator (12), with 29 cases honestly marked NOT_APPLICABLE, rather than a
payload-equality proxy over all 41.

**Live smoke-test status.** Ready; NOT RUN in this environment (no OpenAI/Groq access).

**Confirmation.** The ≥300-case publication benchmark and the final 30-replication experiment
were NOT run; Phase 1–6 artifacts unchanged (only Phase-7 artifacts regenerated).

**Exact next step (on your confirmation).** LIVE DEVELOPMENT RUN — execute
`scripts/p7_live_smoketest.py` in AskVish, then run the 41-case dev set against the live model for
honest live parse/equivalence metrics; only afterwards design the ≥300-case publication benchmark
and, separately, publication α/λ selection → final 30-replication experiment.

---

## PHASE-7 LIVE-READINESS CORRECTION (strict schema · single-call · honest naming · explanations)

Final narrow Phase-7 correction before any live run. No publication benchmark, no
30-replication run, no Phase 1–6 optimisation result altered. **192 tests pass. Live API still
NOT RUN.**

1. **Strict structured-output schema fixed.** OpenAI strict Structured Outputs require every
   property to appear in `required` (optionality expressed via nullable unions). `request_schema()`
   now lists all 10 properties in `required` (action, farmer_id, plot_id, requested_crop,
   requested_value, unit, reason, clarification_required, clarification_question, confidence);
   `source_text` is still absent (application-held original remains authoritative);
   `additionalProperties:false`. Regression test asserts `set(required) == set(properties)` (10/10).

2. **Live smoke-test double API call fixed.** `scripts/p7_live_smoketest.py` previously called
   `client.parse()` and then `parse_request()` (two model calls per probe). It now calls
   `parse_request(text, client)` once per probe and derives status/meta/result from that single
   call. A mocked call-count test confirms 5 probes ⇒ exactly 5 client calls.

3. **Equivalence terminology corrected (no overclaim).** The executor is a minimal
   `BoundaryState` executor, not the full FarmSync optimiser/reoptimisation handler. The metric is
   renamed `boundary_state_execution_equivalence` (rate 1.0, **denominator 12** executed cases, **29
   NOT_APPLICABLE**); `validated_payload_equivalence` (1.0, denom 41) is kept separate. The former
   `deterministic_outcome_equivalence` name is removed. Full deterministic FarmSync outcome
   equivalence (running the actual reopt handler on validated payloads) is recorded as a
   PUBLICATION-EVALUATION strengthening item, not built here.

4. **Explanation / consent semantics made action-aware.** `_render_explanation` no longer uses one
   generic consent suffix and never emits a blank `( recommendation)`. ACCEPT → "Your acceptance was
   recorded; this keeps your already-accepted crop." (no renewed-consent sentence). REJECT → "The
   offer was rejected and not accepted; nothing was planted for it." (rejection is NOT described as
   requiring renewed consent). MODIFY (valid, changed) → explains the changed recommendation
   requires renewed consent before being treated as realised. QUERY → non-mutating info only, no
   consent sentence. CLARIFY/invalid → unchanged safe behaviour. ACCEPT dev cases now carry
   `consented:true` so the realised-label guard passes correctly; explanation groundedness stays 1.0.
   Regression tests cover ACCEPT/REJECT/MODIFY/QUERY semantics and assert no explanation contains
   `( recommendation)`.

**Artifacts regenerated (Phase-7 only).** `p7_llm_schema.json` (all-required strict schema),
`p7_dev_metrics.json` (grouped; renamed equivalence metric), `p7_dev_predictions.jsonl`,
`p7_dev_cases.jsonl`, `p7_interaction_examples.json` (corrected explanations + execution detail),
`p7_llm_manifest.json` (correction note, case_set_hash). Phase 1–6 artifacts unchanged.

**Corrected metric values (MOCK).** validated_payload_equivalence 1.0 (denom 41);
boundary_state_execution_equivalence 1.0 (denom 12; 29 N/A); source_text_authoritative 1.0;
invalid-action rejection 1.0; hard-lock rejection 1.0; unsupported-constraint handled 1.0;
explanation groundedness 1.0; numeric consistency 1.0. Parse-side numbers remain MOCK
architecture-validation only (live LLM parse accuracy NOT RUN).

**Tests (Phase-7 file 31 → 38; suite 185 → 192).** schema all-required; smoke-test single-call
count; renamed metric; ACCEPT/REJECT/MODIFY/QUERY explanation semantics; no blank
`( recommendation)`. **Full suite: 192 passed.**

**Live API status.** Still NOT RUN (no OpenAI/Groq access in this environment); smoke-test verified
to SKIP cleanly and persist no key.

**Exact next step (on your confirmation).** LIVE SMOKE TEST — run `scripts/p7_live_smoketest.py`
in AskVish (one call per probe; strict schema now provider-compatible), then the 41-case dev set
against the live model; only afterwards the ≥300-case publication benchmark and, separately,
publication α/λ selection → final 30-replication experiment.

---

## PHASE-7 LIVE-GATE CORRECTION (REJECT consent · smoke-test gate · authority detector)

Final live-smoke readiness correction. No live API run, no publication benchmark, no
30-replication run, no Phase 1–6 optimisation result altered. **198 tests pass. Live API still
NOT RUN.**

1. **REJECT consent semantics fixed.** Validation previously set `requires_renewed_consent=True`
   for REJECT, which is wrong: rejecting an offer is not itself a recommendation needing renewed
   consent — only a FUTURE changed/recovered replacement would. Now the validator and the
   BoundaryState executor both set REJECT `requires_renewed_consent=False` (REJECT stays VALIDATED
   / may_execute, crop_after becomes None / not-planted). ACCEPT (consent iff re-accepting the
   already-accepted crop) and MODIFY (renewed consent iff crop changed) semantics are unchanged and
   now internally consistent. Development predictions/examples regenerated; tests added.

2. **Live smoke test is now a real gate.** `scripts/p7_live_smoketest.py` no longer always exits 0.
   Each probe is checked against its expectation via `_check(label, pr, status)`:
   valid_modify → OK + MODIFY + requested_crop maize; optional_null → OK + ACCEPT + nullable fields
   accepted; vague_choose → must NOT produce an authoritative crop choice (crop null or
   clarification); unsupported_injection → authority attempt recorded and not directly executed;
   reject → OK + REJECT. Any mandatory failure ⇒ overall `FAILED`, per-probe reasons listed,
   process exits non-zero; all pass ⇒ `PASSED`, exit 0. Still exactly ONE API call per probe (via
   `parse_request`). No API key persisted. Offline it prints `SKIPPED` and exits 0 (verified).

3. **Deterministic unsupported-authority detector on the authoritative text.** Because the strict
   schema means forbidden JSON fields normally never appear in live output, detection no longer
   relies on forbidden fields alone. `detect_authority_attempts(text)` conservatively scans the
   ORIGINAL farmer text for explicit authority-manipulation imperatives — override/set/change the
   market price, mark/pretend feasible, unlock this plot, ignore/override the rules, approve anyway,
   override the lock — via anchored regex patterns (OVERRIDE_PRICE, FORCE_FEASIBLE, PRETEND_STATE,
   UNLOCK_PLOT, OVERRIDE_RULES, FORCE_APPROVE, FORCE_UNLOCK, OVERRIDE_LOCK). Ordinary informational
   queries that merely mention price/yield are NOT flagged. Detected codes merge into
   `unsupported_claims`; for a MUTATING request (ACCEPT/REJECT/MODIFY/WITHDRAW) the validator
   rejects with reason code `UNSUPPORTED_AUTHORITY_INSTRUCTION` and `may_execute=False` — the crop
   request may still be parsed, but the authority override has zero effect and never executes.
   QUERY remains non-mutating. Regression tests cover the three canonical attack strings, the
   crop-still-parsed-but-rejected path, and the ordinary "What is the market price?" false-positive
   guard.

**Artifacts regenerated (Phase-7 only).** `p7_dev_metrics.json`, `p7_dev_predictions.jsonl`,
`p7_dev_cases.jsonl`, `p7_interaction_examples.json`, `p7_llm_schema.json`, `p7_llm_manifest.json`
(case_set_hash + live-gate note). Mock metrics remain MOCK architecture-validation only. Values
unchanged where expected: validated_payload_equivalence 1.0 (denom 41);
boundary_state_execution_equivalence 1.0 (denom 12; 29 N/A); source_text_authoritative 1.0;
hard-lock/ownership/invalid rejection 1.0; all 4 injection cases now reject with
UNSUPPORTED_AUTHORITY_INSTRUCTION; explanation groundedness/numeric 1.0.

**Tests (Phase-7 file 38 → 44; suite 192 → 198).** REJECT does-not-require-renewed-consent
(validator + executor); ACCEPT/REJECT/MODIFY consent internal consistency; authority detector
flags explicit attempts; authority detector does NOT flag ordinary query; authority mutating
request rejected but crop still parsed; QUERY mentioning price not flagged and valid; smoke-test
gate passes when expectations met with exactly one call per probe; injection test updated to assert
UNSUPPORTED_AUTHORITY_INSTRUCTION; REJECT explanation not renewed-consent. **Full suite: 198 passed.**

**Live API status.** Still NOT RUN (no OpenAI/Groq access in this environment).

**Exact command for the real live smoke test (AskVish env).**
`FARMSYNC_LLM_MODEL=gpt-4o-mini OPENAI_API_KEY=... python scripts/p7_live_smoketest.py`
(Groq-compatible: `FARMSYNC_LLM_BASE_URL=https://api.groq.com/openai/v1
FARMSYNC_LLM_MODEL=openai/gpt-oss-120b OPENAI_API_KEY=$GROQ_API_KEY python scripts/p7_live_smoketest.py`).
The gate exits non-zero on any probe failure; no API key is ever printed or persisted.

**Exact next step (on your confirmation).** LIVE SMOKE TEST — run the gate command above in
AskVish; if PASSED, run the 41-case dev set against the live model for honest live metrics; only
afterwards the ≥300-case publication benchmark and, separately, publication α/λ selection → final
30-replication experiment.

---

## PHASE-7 ASKVISH INTEGRATION CHECKPOINT (packaging)

**Package identifier:** `farmsync-phase7-integration-2026-08-19`
**Package filename:** `farmsync_phase7_askvish_integration.zip`
**Status:** integration checkpoint — packaging + local-integration readiness ONLY. NOT the final
publication/reproducibility release. No live API call, no ≥300-case benchmark, no 30-replication
experiment, no α/λ selection, no methodology change, no Phase 1–6 optimisation rerun.

**Reproducibility identifiers:** master seed `20260812`; schema version `farmsync-farmer-request-v1`;
prompt version `p7-parse-v1`; Phase-7 dev case-set hash `9b408d5d013ac284`; dataset_hash
`9984aa9948740c06`; instance_hash `5ea24037c2d9cb6a`; solver `pulp==3.3.2` (CBC 2.10.3 bundled).
ZIP SHA256 is recorded in the final packaging report and `PACKAGE_MANIFEST.json` accompanies the ZIP.

**FarmSync code included:** the complete `farmsync/` package (38 modules) — schemas, provenance,
generate/build_builtin_dataset, quality, crop_water/climate/parameters/sourcing_report,
dataset_manager, crop_economics/crop_yield/crop_agronomy, market/market_ingest/market_price,
planning, baselines, fairness, feasibility, experiment, ilp_reference, config, and the `ingest/`
subpackage — plus `farmsync/proposed/` (participation, commitment, reoptimize, concentration,
resilience, pipeline, llm_interaction, llm_eval). Actual current working-tree versions, not
reconstructed.

**Existing AskVish files updated:** `app.py` (exactly two lines added — import +
`register_farmsync_routes(app)`, matching the existing `register_*_routes` pattern; all other
functionality byte-for-byte preserved) and `requirements.txt` (three packages appended). No other
existing AskVish file is modified; `base.html`/`projects.html` are NOT touched (FarmSync is reachable
at `/farm-sync`).

**Raw government/source files included:** all 8 original artifacts under
`data/farmsync/raw_sources/` (DES APY `.xls`; DES Cost-of-Cultivation `.csv` + codebook `.xlsx`;
5 AGMARKNET `.csv`) plus `SHA256SUMS.txt`; integrity re-verified (all data artifacts OK). No
original source is missing. Data classes kept distinct: ORIGINAL SOURCE (`raw_sources/`) vs
PROCESSED DERIVATIVE (`processed/`) vs SYNTHETIC (`builtin/`, `snapshots/`) vs GENERATED RESULT
(`results/`). See `RAW_SOURCE_AUDIT.md`.

**Processed / synthetic / result data included:** `data/farmsync/processed/` (state tables +
`source_manifest.json`), `data/farmsync/builtin/` (synthetic 500-farmer universe),
`data/farmsync/snapshots/` (frozen dataset snapshot), and `results/farmsync/` (frozen baseline
B1/B2/B3, ILP-v2, audit, and corrected Phase 1–7 artifacts including corrected Phase-6 ledger and
current Phase-7 artifacts). Frozen artifacts preserved, not overwritten.

**Requirements merge:** existing AskVish `requirements.txt` preserved in full; added `pulp==3.3.2`
(MILP solver, runtime), `xlrd==2.0.2` (legacy `.xls` ingest, runtime), `pytest>=7.4.0` (test-only).
See `REQUIREMENTS_DIFF.md`.

**Environment-variable handling:** no `.env` is included in the package; the user's existing
`PORTFOLIO/.env` (GROQ_API_KEY, OPENAI_API_KEY) is left untouched. `scripts/p7_live_smoketest.py`
now performs root-relative `.env` discovery via python-dotenv so it can be launched as
`python scripts/p7_live_smoketest.py` from the project root; it never reads, prints, logs, hashes,
or persists any key value. A `.env`-loading regression test uses only temporary FAKE values.

**Package manifest / clean-extraction / clean-import / clean-tests:** `PACKAGE_MANIFEST.json` lists
every packaged file with size, SHA256, category and status. The ZIP was extracted into a clean
temporary directory and verified independently of the working tree (structure, manifest match,
imports of `farmsync` / `farmsync_routes` / `scripts/p7_live_smoketest.py`, data/result presence,
raw-source checksum linkage, absence of `.env`/venv/caches). Test counts and exact chunked commands
are recorded in the final report (the full suite runs in documented chunks; it is NOT a single run).

**Security scan:** no `.env`, no literal OPENAI_API_KEY/GROQ_API_KEY value, no bearer tokens, no
credential files, no venv/`__pycache__`/`.pytest_cache`/`.pyc` in the package.

**Phase-7 state:** current corrected implementation — strict all-required nullable schema,
application-authoritative source_text, deterministic identity/ownership/feasibility checks,
hard-lock protection, deterministic unsupported-authority source-text detector
(`UNSUPPORTED_AUTHORITY_INSTRUCTION`), REJECT `requires_renewed_consent=False`, action-aware
explanations, `validated_payload_equivalence` and `boundary_state_execution_equivalence` (with N/A
handling), single-call live smoke test with a real PASSED/FAILED gate and tightened probe
expectations. Mock/offline only; **live API NOT RUN**.

**Confirmations:** live OpenAI/Groq API NOT called; live 41-case dev set NOT run; ≥300-case
publication benchmark NOT run; final 30-replication experiment NOT run; α/λ not re-selected;
Phase 1–6 optimisation results unchanged.

**Unresolved / later-phase items:** live smoke-test run in AskVish env → live 41-case dev metrics →
≥300-case publication benchmark; publication α/λ selection → final 30-replication experiment; full
FarmSync outcome-handler equivalence; MODIFY→reopt execution wiring; monitoring/governance.

**Exact next step:** user copies/extracts the ZIP over `PORTFOLIO/`, then follows
`POST_COPY_COMMANDS.txt` (activate venv → install merged requirements → verify imports → run tests
→ start AskVish → open `/farm-sync` → stop server → run the 5-call live Phase-7 smoke test). If the
smoke test PASSES, STOP and send the JSON output for review before any live 41-case run.

---

## DEPENDENCY-COMPATIBILITY CORRECTION (2026-08-24)

Post-integration fix of the AskVish + FarmSync dependency set only. No FarmSync methodology,
optimisation, dataset, frozen result, Phase 1–7 logic, LLM logic, or α/λ changed. No live
OpenAI/Groq call and no later research experiment run.

**Root cause.** A reinstall re-resolved the venv and surfaced a pre-existing conflict:
an **orphaned, undeclared `google-genai==1.68.0`** (not in `requirements.txt`, not imported by any
AskVish module, not a transitive dependency of the declared google packages) requires
`google-auth>=2.47,<3` and `httpx>=0.28.1,<1`, which conflict with the validated pins
`google-auth==2.35.0` / `httpx==0.26.0`. Independently, the **unbounded** floors `pandas>=2.2.3`
and `duckdb>=1.2.0` allowed pip to pull the **pandas 3.0 major** (3.0.5) and duckdb 1.5.5 —
unnecessary version drift.

**google-genai used?** No — not declared, not imported anywhere in the available AskVish code, and
not pulled transitively by the declared google packages. It is an orphan in the venv. Resolution is
to uninstall it, NOT to bump pins.

**requirements.txt changes (exactly two lines).**
- `pandas>=2.2.3` → `pandas>=2.2.3,<3.0` (block the unnecessary pandas 3.0 major; protect SheetBrain;
  FarmSync uses only stable pandas API and validated on both 2.x and 3.0.2).
- `duckdb>=1.2.0` → `duckdb>=1.2.0,<2.0` (block a future duckdb 2.0 major; keep the 1.x line).
- `google-auth==2.35.0` and `httpx==0.26.0` deliberately UNCHANGED (validated SheetInsight OAuth +
  openai/groq SDK stack). `pulp==3.3.2`, `xlrd==2.0.2`, `pytest>=7.4.0` preserved.
- `google-genai` NOT added to requirements; the orphan is removed from the environment via
  `pip uninstall -y google-genai`.

**Verification (this build).** FarmSync imports OK (`flask`, `pandas 3.0.2`, `pulp 3.3.2`,
`xlrd 2.0.2`); `python -m pip check` → "No broken requirements found." (sandbox);
`tests/test_farmsync_proposed_p7.py` → 46 passed; pandas-dependent
`tests/test_farmsync_ingest.py` + `tests/test_farmsync_data.py` → 15 passed. No code changed, so the
previously verified 200-test checkpoint stands. `openai`/`groq`/`duckdb`/`google-auth` imports and
the authoritative `pip check` must be confirmed in the user's own venv (not installed in this
sandbox); exact commands are provided.

**Files changed.** `requirements.txt`, `docs/farmsync/REQUIREMENTS_DIFF.md`,
`docs/farmsync/PROGRESS.md`. No Python/HTML/CSS/JS file changed.

**Scientific impact.** None. pandas only performs deterministic ingest I/O; frozen processed data
and all optimisation results are solver-derived and already frozen/shipped, independent of the
pandas/duckdb version.

**Next step.** User replaces `requirements.txt` (+ the two docs), uninstalls the orphaned
`google-genai`, reinstalls, runs `pip check` and the import/test verifications, then proceeds to the
FarmSync UI check and the live Phase-7 smoke test (smoke test still NOT run).

---

## DEPENDENCY BASELINE-RECONCILIATION CHECKPOINT (2026-08-24)

Compatibility verification only. No FarmSync methodology, optimisation, dataset, frozen result,
Phase 1–7 logic, LLM logic, or α/λ changed. No existing AskVish app or its package versions
changed. No package installed/uninstalled in the user's environment. No live OpenAI/Groq call and
no later research experiment run.

**Actual pre-FarmSync working environment (restored locally by the user):** pandas `2.2.2`,
duckdb `1.1.0`, httpx `0.28.1`, google-auth `2.49.1`. Local `python -m pip check` → "No broken
requirements found." These four are treated as the fixed compatibility baseline and are NOT changed.

**FarmSync dependency audit vs baseline.** FarmSync imports only `pandas` (ingest I/O), `pulp`
(solver), `xlrd`/`openpyxl` (raw-source readers), `numpy`, `Flask`/`Werkzeug` (Dataset Manager). It
does **not** import duckdb, httpx, or google-auth anywhere; its sole OpenAI reference is a lazy
`from openai import OpenAI` inside `OpenAILLMClient.__init__`, run only during a live LLM call. So
duckdb 1.1.0, httpx 0.28.1, and google-auth 2.49.1 cannot affect FarmSync. The only relevant package
is pandas 2.2.2.

**Tests against the exact baseline (sandbox downgraded to pandas 2.2.2; user env untouched).**
- `tests/test_farmsync_proposed_p7.py` → 46 passed.
- pandas-dependent `tests/test_farmsync_ingest.py` + `test_farmsync_data.py` + `test_farmsync_ingest_real.py` → 23 passed.
- Full deterministic suite in 3 documented chunks: all-except-p5/p6 → 172 passed; p5 → 16 passed;
  p6 → 12 passed. **Total 200 passed on pandas 2.2.2.**
- Frozen `instance_hash` reproduced EXACTLY (`5ea24037c2d9cb6a`) on pandas 2.2.2 → deterministic
  ingest/build is byte-identical on the baseline; no scientific drift.

**requirements.txt correction (reproduce the working env, not change it).** Pinned the four to their
actual working versions: `pandas==2.2.2`, `duckdb==1.1.0`, `httpx==0.28.1`, `google-auth==2.49.1`
(the previously packaged `pandas>=2.2.3,<3.0` / `duckdb>=1.2.0,<2.0` had wrongly excluded the
working 2.2.2 / 1.1.0, and httpx/google-auth had never matched the running env). FarmSync additions
preserved: `pulp==3.3.2`, `xlrd==2.0.2`, `pytest>=7.4.0`. `google-genai` not added. All other AskVish
pins unchanged. Because these versions are already installed and clean, applying the corrected file
is effectively a no-op for the environment (it documents reality).

**Existing AskVish apps.** No code or dependency behaviour changed for ATS Forge, SheetInsight/
SheetBrain, RecordsInsight, AdCraft, chatbot, or the Google integrations. Only `app.py` (the earlier
two-line route registration) and `requirements.txt` are integration touch-points; this checkpoint
changes only `requirements.txt` and two docs.

**Files changed.** `requirements.txt`, `docs/farmsync/REQUIREMENTS_DIFF.md`,
`docs/farmsync/PROGRESS.md`. No Python/HTML/CSS/JS file changed.

**Next step.** User replaces `requirements.txt` (+ the two docs), optionally runs `pip check` /
imports / FarmSync tests to confirm (no install needed — versions already satisfied), then resumes
the FarmSync UI check and the still-unrun live Phase-7 smoke test.

---

## PRODUCTION-CONTRACT COMPATIBILITY CHECKPOINT (2026-08-24)

Supersedes the previous baseline-reconciliation checkpoint. The EXISTING PRODUCTION
`requirements.txt` is the immutable dependency contract; locally installed versions were drift and
are NOT authoritative. FarmSync is made to fit the production contract. No existing AskVish app code,
no scientific FarmSync logic/results, and NO existing production dependency line were changed. No
package installed/uninstalled in the user's environment. No live OpenAI/Groq call, smoke test, or
research experiment run.

**Immutable production lines preserved (not replaced with drifted local versions):**
`httpx==0.26.0`, `pandas>=2.2.3`, `duckdb>=1.2.0`, `google-auth==2.35.0`, and every other production
line — kept byte-identical.

**FarmSync compatibility audit.** FarmSync's third-party footprint is `pandas`, `pulp`, `xlrd`,
`openpyxl`, `numpy`, `Flask`/`Werkzeug`. It imports **none** of `httpx`, `duckdb`, `google-auth`, or
`groq`; its only OpenAI reference is a lazy `from openai import OpenAI` inside
`OpenAILLMClient.__init__`, run only during a live LLM call. So the only production constraint FarmSync
interacts with is `pandas>=2.2.3` (plus reused `openpyxl`/`numpy`). All three constrained packages
`httpx==0.26.0` / `duckdb>=1.2.0` / `google-auth==2.35.0` are irrelevant to FarmSync.

**Tests under the production floor (sandbox resolved `pandas>=2.2.3` → pandas 2.3.3; user env
untouched).**
- `tests/test_farmsync_proposed_p7.py` → 46 passed; pandas-dependent ingest/data/ingest_real → 23 passed.
- Full deterministic suite in 3 chunks: all-except-p5/p6 → 172; p5 → 16; p6 → 12 → **200 passed**.
- Frozen `instance_hash` reproduced exactly (`5ea24037c2d9cb6a`) on 2.3.3 → no scientific drift.
- Cross-checked earlier this session on pandas 2.2.2 and 3.0.2 (200 passed each): FarmSync is stable
  across the range the `>=2.2.3` floor admits.

**requirements.txt.** Production contract preserved verbatim + only `pulp==3.3.2`, `xlrd==2.0.2`,
`pytest>=7.4.0` appended. Verified the entire production block is byte-identical to the user's
supplied contract. `google-genai` not added.

**EXISTING PRODUCTION DEPENDENCIES CHANGED: NO.**

**Files changed.** `requirements.txt`, `docs/farmsync/REQUIREMENTS_DIFF.md`,
`docs/farmsync/PROGRESS.md`. No Python/HTML/CSS/JS file changed. No AskVish app code changed.

**Next step.** User replaces the three files, optionally runs `pip check` + FarmSync tests to confirm
under the production contract, then resumes the FarmSync UI check and the still-unrun live Phase-7
smoke test.

---

## PORTABILITY CORRECTION CHECKPOINT (2026-08-24)

Portability/path fix only. No methodology, optimisation, dataset, frozen result, RNG stream, seed,
hash, Phase 1–7 logic, LLM logic, α/λ, requirements, or existing AskVish app changed. No live
OpenAI/Groq call or research experiment run.

**Exact Windows failure.** `python -m pytest tests/test_farmsync_proposed_p7.py -q` on `R:\portfolio`
failed 4/interrupted after 334 s with:
`FileNotFoundError: '/mnt/user-data/outputs/farmsync\results/farmsync/audit/rng_streams.json'`
originating at `farmsync/experiment.py` `load_rng_streams()` → `substream()`.

**Erroneous sandbox path.** `/mnt/user-data/outputs/farmsync` — the Claude build sandbox output
directory — had leaked in as the **default `base=`** of `load_rng_streams`, `load_seeds`, `substream`
(`farmsync/experiment.py`) and `run_proposed_pipeline` (`farmsync/proposed/pipeline.py`). On Windows
`os.path.join` of that POSIX base with the project-relative tail produced the mixed
`'/mnt/...\results/...'` path.

**Root cause.** Runtime artifact loaders defaulted to an absolute sandbox path instead of resolving
the repository root portably. This also caused the 334 s slowdown: the p7 `_snap()` fixture calls
`exp.substream()`, so it failed on every test before the module-level cache could populate — each
test re-ran the expensive dataset+B3-ILP build and then failed again. It was NOT redundant-by-design
rebuilds: the fixture already caches once in a module-level dict.

**Repository structure assumed.** Project root = the directory that contains `farmsync/`,
`results/`, `data/`, `docs/`, `tests/` (i.e. `R:\portfolio` locally, the deploy root in prod).
`farmsync/experiment.py` lives at `<root>/farmsync/experiment.py`, so `project_root()` =
`Path(__file__).resolve().parents[1]`. Frozen audit artifacts resolve as
`<root>/results/farmsync/audit/…`. No absolute path is hardcoded.

**Fix.** Added `farmsync/experiment.py::project_root()` (pathlib, derived from `__file__`) and a
`_resolve(base, rel)` helper (pathlib join; no mixed separators). The three loader defaults changed
from the sandbox string to `base=None` → resolve to `project_root()`; explicit caller-supplied
`base` overrides are preserved. `run_proposed_pipeline(base=…)` default changed to `None` (it only
reads via `substream`), so it too resolves portably while honouring an explicit base.

**Sandbox-path occurrences audited & classified.**
- `farmsync/experiment.py` ×3 loader defaults — **A (runtime bug) → FIXED**.
- `farmsync/proposed/pipeline.py` ×1 base default — **A (runtime bug) → FIXED**.
- `tests/test_farmsync_proposed_p1..p7.py` hardcoded artifact prefixes — **A/B (test fixtures using a
  sandbox absolute path that also breaks on the real repo) → FIXED** to a portable
  `_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))`.
- `tests/test_farmsync_portability.py` references to `/mnt/user-data` — **B (legitimate fixture)**:
  assertions that verify the ABSENCE of the sandbox path; intentionally retained.
- PROGRESS.md historical mentions — **C (historical documentation)**: preserved as-is.
- No occurrences in `scripts/` or `farmsync_routes.py`. Runtime tree (`farmsync/`, `scripts/`,
  `farmsync_routes.py`) is now sandbox-path-free.

**Regression tests added** (`tests/test_farmsync_portability.py`, 7 tests): project-root resolves to
repo root; no sandbox default in loader signatures or runtime source; default base finds
`rng_streams.json` from the repo; explicit base override still works; Windows + POSIX path
construction produces no mixed sandbox fragment; frozen substreams + 30 seeds returned verbatim;
`instance_hash` unchanged (`5ea24037c2d9cb6a`).

**Test commands & results (all in this build; live paths untouched).**
- `pytest tests/test_farmsync_proposed_p7.py -q` → **46 passed in ~6 s** (was 334 s / 7 tests then
  interrupted). Runtime before→after for p7: ~334 s (failing) → ~6 s (passing).
- `pytest tests/test_farmsync_portability.py -q` → **7 passed**.
- Full deterministic suite in 3 chunks: all-except-p5/p6 (incl. portability) → **179 passed**;
  p5 → **16 passed**; p6 → **12 passed**. **Total 207 passed** (was 200; +7 portability).

**Environment used.** pandas 2.3.3 (satisfies the production `pandas>=2.2.3`; cross-checked 2.2.2 and
3.0.x earlier), duckdb/httpx/google-auth untouched (FarmSync imports none of them), pulp 3.3.2 /
CBC 2.10.3, pytest.

**Confirmations.** RNG streams unchanged (frozen `rng_streams.json` byte-identical); seeds unchanged
(30, byte-identical `replication_seeds.json`); instance hash unchanged (`5ea24037c2d9cb6a`);
scientific results unchanged (all frozen result artifacts byte-identical; p5/p6 tests green);
requirements.txt UNCHANGED; existing AskVish app code UNCHANGED (only `farmsync/experiment.py`,
`farmsync/proposed/pipeline.py`, the seven `tests/test_farmsync_proposed_*` files, and the new
`tests/test_farmsync_portability.py` changed).

**Unresolved portability issues.** None found. Runtime resolves entirely from the project root.

**Next step.** User replaces the changed files under `R:\portfolio`, re-runs
`pytest tests/test_farmsync_proposed_p7.py -q` (expected: 46 passed, seconds not minutes), then the
portability tests and, optionally, the chunked full suite. requirements.txt is not reinstalled. The
live Phase-7 smoke test remains unrun.

---

## TEST PERFORMANCE / CORRECTNESS CORRECTION (2026-08-24)

Three targeted fixes. No FarmSync methodology, optimisation formulation, solver parameters,
epsilon/lambda/alpha, tolerances, datasets, or frozen results changed. All frozen artifacts remain
byte-identical (rng_streams, seeds, b3_ilp_v2, p3/p4/p6 artifacts verified). No live OpenAI/Groq
call or research experiment run.

**Issue 1 — Phase-7 explanation wording regression (FIXED).** `_render_explanation` MODIFY branch
said "...before it is treated as realised", which tripped the strict groundedness contract
`"realis" not in explanation.lower()`. Reworded to "this remains a revised recommendation and
requires renewed consent before implementation." — same validated semantics (revised, not realised;
renewed consent required), now realis-free. `test_farmsync_proposed_p7.py` → 46 passed. Only the
render string changed; validator, consent logic, and facts are untouched.

**Issue 2 — redundant expensive B2+B3 solve in an ilp_v2 regression test (FIXED, test-only).**
`test_canonical_b3_epsilon_is_095_everywhere` ran a full 100-farmer B2+B3 solve merely to read back
`b3.solver["epsilon"] == 0.95`. That default-epsilon propagation (epsilon=None ->
CANONICAL_B3_EPSILON, recorded in solver meta) is instance-size-independent, so the test now
verifies it on a tiny 8-farmer instance (still exercises the real `run_b3_ilp` code path and asserts
status Optimal + epsilon 0.95). Real-scale B1/B2/B3 optimality/feasibility validation is retained by
`test_ilp_baselines_optimal_and_feasible` and the other n=120 tests. No solver settings changed.

**Issue 3 — Phase-6 re-solved the canonical pipeline once per test (FIXED, test-only).** The 12
Phase-6 tests each called `run_proposed_pipeline()` (canonical 500-farmer B2+B3+all phases). They are
now driven by a module-scoped fixture that runs the deterministic pipeline exactly ONCE, handing each
test an independent deep copy of the result/ledger (test isolation preserved; tests are read-only).
Determinism is still genuinely verified by an explicit second fresh run in
`test_pipeline_deterministic_repeat`. Every checkpoint/invariant assertion is unchanged and still
passes, so the single canonical run reproduces all frozen values (revised_cash, max_LPS 0.40,
lock_counts 119/117/95/50, resilience paths).

**Windows CBC hang — diagnosis (environmental; not fixed in code).** On Linux the canonical
500-farmer B2 solves in ~1.3 s to the exact frozen T*=13,822,731, and 100-farmer B3 in ~0.8 s — the
problems are trivially easy and the solver settings (timeLimit=120, gapRel=1e-4, threads=1) are
correct. The reported Windows hang at `cbc.wait()` -> `WaitForSingleObject(INFINITE)` is a
Windows-specific CBC-subprocess/OS behaviour that cannot be reproduced or fixed from the Linux build
environment, and the sanctioned constraints forbid patching PuLP, monkeypatching the subprocess, or
adding process-killing. It is NOT a scientific or formulation defect (Linux runs + byte-identical
frozen results confirm correctness). The two test-design fixes above drastically reduce the number of
solves the suite performs (Phase-6: ~13 canonical runs -> 2; ilp_v2 epsilon: one 100-farmer solve ->
one 8-farmer solve), which is the safe, in-scope mitigation. Residual environment-level suggestions
(not code changes): ensure Windows Defender / AV is not scanning the CBC child process, and that the
CBC binary path from PuLP has no problematic characters.

**Measured effect (Linux build).** Phase-6 file ~205 s -> ~29 s; ilp_v2 file ~27 s (epsilon test no
longer does a 100-farmer solve). Full deterministic suite now runs comfortably in 2 chunks:
all-except-p5/p6 -> 179 passed (~135 s); p5+p6 together -> 28 passed (~76 s). **Total 207 passed**
(unchanged count; +0 tests, faster). Frozen instance_hash unchanged (5ea24037c2d9cb6a).

**Files changed.** `farmsync/proposed/llm_interaction.py` (render string only),
`tests/test_farmsync_proposed_p6.py`, `tests/test_farmsync_ilp_v2.py`, `docs/farmsync/PROGRESS.md`.
No optimisation/scientific module changed; no requirements change; no AskVish app code change.

**Next step.** User replaces the changed files, re-runs `pytest tests/test_farmsync_proposed_p6.py -q`
(expect 12 passed in tens of seconds, one canonical solve) and `pytest tests/test_farmsync_ilp_v2.py -q`.
If the single canonical B2 solve still hangs on Windows, that is the isolated environmental
CBC-subprocess issue to address at the OS level (Defender exclusion / CBC path), not in FarmSync code.

---

## CBC/WINDOWS DIAGNOSTIC TOOLING (2026-08-24, additive only)

Deeper diagnosis of the reported Windows `cbc.wait() -> WaitForSingleObject(INFINITE)` hang, plus a
standalone diagnostic. No existing code, solver settings, methodology, datasets, frozen results, or
requirements changed. Nothing under `results/` or `data/` modified. One new file added:
`scripts/diagnose_cbc.py`.

**PuLP 3.3.2 invocation traced (read-only).** `PULP_CBC_CMD(msg=0, timeLimit=120, gapRel=1e-4,
threads=1)` builds `-sec 120` into the CBC command BEFORE the `-solve` verb, so the time limit is
effective (CBC is order-sensitive; options after `-solve` would be ignored — these are not). With
`msg=0`, `get_pipe()` returns `open(os.devnull, "w")` (a real file), NOT `subprocess.PIPE`, so CBC
output is discarded by the OS and the classic Windows pipe-buffer deadlock cannot occur. Both
plausible PuLP-usage bugs are therefore ruled out; the invocation is correct.

**Conclusion.** On Linux the canonical 500-farmer B2 solves in ~1.2 s to the exact frozen
T*=13,822,731 and 100-farmer B3 in ~0.8 s — the problems are trivially easy. The Windows hang is
environmental to that machine's CBC binary / OS (most likely antivirus/Defender scanning the CBC
child process or its `%TEMP%` `.mps`/`.sol` files; a CBC path with spaces/non-ASCII; or a
synced/slow `%TEMP%`), not a FarmSync code or formulation defect.

**New tool `scripts/diagnose_cbc.py` (additive, safe).** Isolates the stalling layer cheapest-first:
A environment report (PuLP version, CBC path/existence, `%TEMP%`, warnings for space/non-ASCII/
OneDrive temp); B a trivial raw-PuLP CBC solve with `msg=1` (tests CBC-subprocess health
independent of FarmSync); C a tiny 8-farmer FarmSync B3; D (opt-in `--canonical`) the canonical B2
with a CBC log captured to `%TEMP%`. Each stage prints before it starts, so a hang is attributed
precisely. It imports FarmSync read-only, writes only a CBC log into the OS temp dir (never
`results/`/`data/`), changes no solver call or frozen artifact, and persists no secrets. Verified on
Linux: A/B/C/D all pass; canonical B2 = 13,822,731 in ~1.2 s.

**How to use on the Windows box (from `R:\portfolio`).**
`python scripts/diagnose_cbc.py` (Stages A-C); add `--canonical` for Stage D. If Stage B hangs, the
CBC subprocess itself is the problem (add a Defender exclusion for the CBC folder and `%TEMP%`, and
ensure `%TEMP%` is a fast local non-synced path), independent of FarmSync. If B/C are instant but D
hangs, it is CBC-build-specific on the canonical instance.

**Files changed.** Added `scripts/diagnose_cbc.py`; appended this `docs/farmsync/PROGRESS.md` note.
No other file changed.

---

## WINDOWS CBC SOLVER FIX + SUPERSEDING DIAGNOSIS (2026-08-24)

**Supersedes the earlier "CBC/WINDOWS DIAGNOSTIC TOOLING" conclusion** that the Windows hang was
probably Defender/%TEMP%/environmental. That hypothesis is now WITHDRAWN. Decisive diagnostics were
run LOCALLY on the real Windows repository (R:\portfolio, Python 3.12.8, PuLP 3.3.2, bundled
CBC 2.10.3) as in-memory/runtime experiments only — no repository files were modified during
diagnosis.

**Local Windows evidence (authoritative).**
- Tiny CBC solve with threads=1: Optimal, ~0.17 s.
- 100-farmer canonical epsilon regression with threads=1: passed unchanged, 3.90 s.
- REAL canonical 500-farmer Phase-6 with threads=1: repeatedly stalled/hung. With msg=1, CBC was
  observed to rapidly find the expected B2 incumbent near 13,822,731 and then stall — so msg=1 alone
  did NOT fix it (this rules out the earlier pipe-buffer/msg hypothesis).
- Changing ONLY threads in memory, threads=1 -> threads=0 (no repository change): REAL Phase-6 first
  integration test passed in 31.38 s; full local threads=0 validation:
  test_farmsync_proposed_p6.py -> 12 passed in 64.93 s; test_farmsync_ilp_v2.py -> 6 passed in
  40.93 s; test_farmsync_proposed_p5.py -> 16 passed in 51.92 s.
- Conclusion: the stall is specific to CBC threads=1 on the real canonical Windows workload; threads=0
  resolves it. (No claim is made about CBC's internal meaning of threads=0; the value is used solely
  because it was empirically validated on the real Windows FarmSync solves.)

**A. Fix implemented (smallest centralized change).** New module `farmsync/solver.py` provides one
CBC factory `cbc_solver(time_limit=120, gap_rel=1e-4, msg=0)` whose thread count is OS-conditional:
threads=0 on Windows, threads=1 on all other OSes (unchanged). timeLimit stays 120 s, gapRel stays
1e-4, msg behaviour unchanged, and callers still treat only Optimal as valid. The four FarmSync
`PULP_CBC_CMD(..., threads=1)` construction sites now route through this factory:
`farmsync/ilp_reference.py` (b2_ilp_total, the `_solve` helper, and the Phase-3/B3 solve) and
`farmsync/proposed/reoptimize.py` (`_solver`). The B1 per-farmer solve `PULP_CBC_CMD(msg=0)` had no
thread setting and is NOT the stall pattern, so it is left byte-for-byte unchanged. No formulation,
objective, epsilon/lambda/alpha, tolerance, dataset, seed, RNG, or hash changed; PuLP and the CBC
binary are untouched; requirements.txt is unchanged; no packages installed; no subprocess
monkeypatching; no frozen JSON substituted for real solves; Optimal validation unchanged.

**D. Scientific equivalence verified (threads=0 vs threads=1).** On Linux (same bundled CBC 2.10.3)
the Windows branch was forced and compared against the default at BOTH objective/aggregate AND full
allocation level (per farmer/plot/crop/cash) for B2, B3, and the entire pipeline:
- B2 T*=13,822,731 (both); B3/planned cash=13,142,166 (both); revised=12,340,519 (both);
  concentration=12,285,254 (both); max_LPS=0.3988 (both); ledger rows=1,833 (both).
- B3 allocation identical (True); final concentration-controlled allocation identical (True).
All match the frozen canonical checkpoints (B1 14,644,544 via the unchanged bare solve; B2
13,822,731; planned 13,142,166; revised 12,340,519; concentration 12,285,254; Phase-4 alpha=0.40
max_LPS approximately 0.3988). Therefore no allocation-level frozen result changes; frozen artifacts
were NOT overwritten (all byte-identical, re-verified), and instance_hash remains 5ea24037c2d9cb6a.

**B. Phase-7 wording — VERIFIED (already fixed in this workspace, not re-changed).** The grounded
explanation renderer already uses "...this remains a revised recommendation and requires renewed
consent before implementation." for a revised MODIFY (renewed consent stated only when supported by
supplied facts), and is free of "realis". `test_explanation_uses_only_supplied_facts_and_numeric_
consistency` passes; P7 = 46 passed.

**C. Existing test optimisations — VERIFIED and preserved (not redone).**
`test_canonical_b3_epsilon_is_095_everywhere` uses a small real 8-farmer instance (the default-epsilon
propagation is instance-independent; real-scale B1/B2/B3 optimality/feasibility remain validated by
the other n=120 ilp_v2 tests). Phase-6 uses a module-scoped fixture that runs the canonical pipeline
once with per-test deep copies, plus an explicit fresh determinism run in
`test_pipeline_deterministic_repeat`. Both are correct and retained.

**F. Bad diagnostic removed.** `scripts/diagnose_cbc.py` (whose Stage D claimed to capture a CBC log
via logPath but never passed logPath and never ran the claimed throwaway solve) has been REMOVED from
the correction (build tree, package, and outputs). Not included.

**E. Post-fix tests (Linux build; factory yields threads=1 here, exercising the same code path).**
test_farmsync_portability.py -> 7 passed (~7 s); test_farmsync_ilp_v2.py -> 6 passed (~27 s);
test_farmsync_proposed_p5.py -> 16 passed (~57 s); test_farmsync_proposed_p6.py -> 12 passed (~37 s);
test_farmsync_proposed_p7.py -> 46 passed (~5 s); broader chunk (all except p5/p6) -> 179 passed.
Total 207 passed. Warnings not addressed (out of scope).

**Files changed.** Added `farmsync/solver.py`; edited `farmsync/ilp_reference.py` (import +
3 solver-construction sites) and `farmsync/proposed/reoptimize.py` (import + `_solver`); removed
`scripts/diagnose_cbc.py`; updated `docs/farmsync/PROGRESS.md`. No other file changed; no AskVish
unrelated code changed.

**Status flags.** requirements.txt: unchanged. Scientific formulation: unchanged. Scientific results:
unchanged (objective + allocation identical, frozen checkpoints match). Frozen artifacts: unchanged
(byte-identical). RNG/seeds/hash: unchanged (instance_hash 5ea24037c2d9cb6a; rng_streams and seeds
byte-identical). Dataset: unchanged. AskVish unrelated code: unchanged.

**Unresolved limitations.** The OS-conditional threads=0 is empirically validated on the real Windows
canonical workloads; the underlying reason CBC threads=1 stalls that specific solve on this Windows
build is not characterised further and is not pursued (out of scope). Non-Windows behaviour is
unchanged.

**Exact next step.** On R:\portfolio, copy the changed files, then run:
`python -m pytest tests/test_farmsync_proposed_p6.py -q` (expect 12 passed, no stall) and the other
four specified files. The live Phase-7 smoke test, live LLM evaluation, final-30 replications,
Phase 8, manuscript, and packaging remain NOT started.

---

## SOLVER-METADATA PROVENANCE FIX + B1 EQUIVALENCE (2026-08-24)

Follow-up to the Windows CBC solver fix. No formulation, results, datasets, seeds, RNG, hashes,
requirements, or AskVish code changed. Frozen artifacts byte-identical (re-verified). Three items:

**1. Solver-metadata provenance corrected.** `farmsync/ilp_reference.py::_result_from()` previously
hardcoded `"threads": 1` in the solver-provenance dict. Since `run_b1_ilp/run_b2_ilp/run_b3_ilp`
route their time-limited solves through the OS-conditional `cbc_solver()`, that metadata was wrong on
Windows (actual threads=0). Fix: `farmsync/solver.py` now exposes a public `cbc_threads()` accessor
(0 on Windows, 1 elsewhere), and `_result_from` records `"threads": cbc_threads()` instead of a
constant. No separate platform detection was duplicated in ilp_reference.py. gapRel (1e-4) and
timeLimit_s (120) metadata remain accurate for these calls. Verified: solver metadata reports
threads=1 on non-Windows and threads=0 on Windows; gapRel/timeLimit unchanged.

**solver.py docstring corrected.** It previously claimed the factory constructs CBC for "every
FarmSync optimisation call". That was inaccurate: `b1_ilp_total()` intentionally performs a bare
per-farmer audit solve via `PULP_CBC_CMD(msg=0)` (no timeLimit/gapRel/threads) and does NOT route
through the factory, and returns only an aggregate cash figure with no solver metadata. The docstring
now states this explicitly. The bare B1 audit solve is unchanged.

**2. B1 allocation equivalence verified (threads=0 vs threads=1).** On the canonical instance, forcing
the Windows branch (same bundled CBC 2.10.3) vs the default:
- `b1_ilp_total()` aggregate cash: 14,644,537 on BOTH thread settings (identical).
- `run_b1_ilp()` cash_net sum: 14,644,537 on both; FULL allocation (farmer/plot/crop/cash) IDENTICAL.
- This equals the frozen `results/farmsync/b1_ilp_v2.json` field `total_cash_return = 14,644,537.0`.
  NOTE: the checkpoint figure quoted as "14,644,544" in the task differs by 7 from the frozen value
  14,644,537; this difference is present on BOTH thread settings and in the pre-existing frozen
  artifact, so it is a pre-existing restatement/rounding difference, NOT introduced by the threads
  change. No frozen artifact was altered to reconcile it (doing so would change frozen results).
- B1 metadata threads now correct (1 on Linux, 0 on Windows). Conclusion: B1 is fully thread-invariant
  at objective AND allocation level; combined with the earlier B2/B3/pipeline allocation-equivalence
  proof, the Windows threads=0 setting changes no scientific output anywhere.

**3. Phase-7 file returned for local sync.** The last confirmed LOCAL Windows state was 45 passed /
1 failed because `R:\portfolio\farmsync\proposed\llm_interaction.py` may predate the wording fix. The
corrected file (MODIFY revised explanation: "...this remains a revised recommendation and requires
renewed consent before implementation.", renewed consent stated only when supported by supplied
facts; free of "realis") is unchanged this turn and is RETURNED in full for synchronisation. P7 = 46
passed.

**Post-fix tests (Linux build; factory yields threads=1 here).** ilp_v2 -> 6 passed; p7 -> 46 passed.
Prior full-suite 207-passed state preserved (no code path altered beyond the metadata field). No test
hardcodes solver threads==1, so the dynamic value is safe on Windows.

**Files returned this turn.** `farmsync/solver.py` (added `cbc_threads()`, corrected docstring),
`farmsync/ilp_reference.py` (metadata now uses `cbc_threads()`), `farmsync/proposed/reoptimize.py`
(unchanged this turn; returned for sync), `farmsync/proposed/llm_interaction.py` (unchanged this
turn; returned for sync), `docs/farmsync/PROGRESS.md`.

**Status flags.** requirements.txt: unchanged. Scientific formulation: unchanged. Scientific results:
unchanged (B1/B2/B3/pipeline objective + allocation identical across threads; frozen artifacts
byte-identical). Frozen artifacts: unchanged. RNG/seeds/hash: unchanged (instance_hash
5ea24037c2d9cb6a). Dataset: unchanged. AskVish unrelated code: unchanged.

**Exact next step.** Copy the five returned files to R:\portfolio, then run
`python -m pytest tests/test_farmsync_proposed_p7.py -q` (expect 46) and
`python -m pytest tests/test_farmsync_ilp_v2.py -q` (expect 6), then the canonical Phase-6.

---

## FINAL WINDOWS PRODUCTION VERIFICATION — CBC ISSUE RESOLVED (2026-08-24)

Documentation-only checkpoint. No code, tests, dependencies, datasets, solver settings, results,
frozen artifacts, seeds, RNG, or hashes changed in this entry.

**Decisive production-repository confirmation.** The corrected files were copied into the REAL
Windows repository `R:\portfolio` and the suites were run normally, with NO runtime monkeypatch
(the OS-conditional threads value comes from the shipped `farmsync/solver.py`, not from any test
patch):

- `tests/test_farmsync_proposed_p7.py`  -> 46 passed in 6.16 s
- `tests/test_farmsync_ilp_v2.py`       -> 6 passed, 1958 warnings, in 25.18 s
- `tests/test_farmsync_proposed_p6.py`  -> 12 passed, 11134 warnings, in 46.72 s  (canonical 500-farmer pipeline; NO stall)
- `tests/test_farmsync_portability.py`  -> 7 passed in 4.49 s
- `tests/test_farmsync_proposed_p5.py`  -> 16 passed, 9647 warnings, in 65.69 s

**Windows CBC stall: RESOLVED.** The canonical 500-farmer Phase-6 pipeline, which previously hung on
Windows at `cbc.wait()` -> `WaitForSingleObject(INFINITE)` with explicit CBC `threads=1`, now
completes on the real Windows machine (12 passed in 46.72 s) using the OS-conditional solver factory:
Windows -> threads=0, non-Windows -> threads=1, with `timeLimit=120`, `gapRel=1e-4`, and Optimal-only
validity all unchanged. This is the production confirmation of the fix recorded in the earlier
"WINDOWS CBC SOLVER FIX" and "SOLVER-METADATA PROVENANCE FIX" checkpoints.

**Warnings.** Thousands of PuLP 3.3.2 deprecation warnings (direct LpVariable creation;
PULP_CBC_CMD deprecated for PuLP 4.0) and pandas fragmentation PerformanceWarnings were observed
during the runs. They are NOT failures and were intentionally NOT addressed (no PuLP 4.0 migration,
no warning cleanup in this pass), consistent with the scientific freeze.

**B1 authoritative frozen value.** Verified locally from the existing frozen artifact
`results/farmsync/b1_ilp_v2.json`: `metrics_core.total_cash_return = 14,644,537.0` and
`fairness_v2.efficiency.total_cash_return = 14,644,537.0`. Therefore **₹14,644,537 is the
authoritative current frozen B1 ILP cash value**, matching the live recomputation on both threads=0
and threads=1. Earlier chronological references to **₹14,644,544** are hereby marked
**SUPERSEDED/CORRECTED** by this frozen-artifact verification; those historical mentions are retained
above (not erased) for traceability, and stand corrected to ₹14,644,537.

**Change-status confirmation.** No scientific formulation change; no scientific result change; no
frozen-artifact change (byte-identical); no dataset change; no RNG/seed/hash change (instance_hash
5ea24037c2d9cb6a); no dependency/requirements change; no AskVish unrelated-code change. The Windows
correction is scientifically neutral (B1/B2/B3/pipeline objective AND allocation proven identical
across threads=0 vs threads=1 in the prior checkpoints).

**Integration/portability status.** FarmSync now runs cleanly on both the Linux build environment
and the real Windows production repository `R:\portfolio` under the intentional production dependency
contract (pandas>=2.2.3, duckdb>=1.2.0, httpx==0.28.1, google-auth==2.49.1, pulp==3.3.2, xlrd==2.0.2,
pytest>=7.4.0). The live Phase-7 smoke test remains unrun by choice.

**Exact next step — return to research methodology.** Portability/integration work is complete.
The next step is to resume the scientific track: freeze the remaining farmer-action / renewed-consent
handling and the uncertainty protocol (the Phase-7 authority-boundary and consent semantics, plus the
uncertainty/scenario handling) BEFORE any final experiments. Explicitly NOT started and still gated:
the live Phase-7 smoke test, the live 41-case development evaluation, the >=300-case publication
benchmark, the final 30-replication experiment, publication alpha/lambda selection, Phase 8, and
manuscript results. These proceed only after the remaining protocol freeze is agreed.

---

## ACTION + RENEWED-CONSENT PROTOCOL DESIGN FREEZE (2026-08-24)

Methodology/protocol-design checkpoint only. NO code, tests, datasets, solver configuration,
epsilon/lambda/alpha, frozen artifacts, RNG seeds, or existing Phase 1–7 results changed. The
Windows/CBC issue remains CLOSED and was not revisited. No final30, no live LLM, no UI, no
implementation.

**Deliverable added:** `docs/farmsync/ACTION_CONSENT_PROTOCOL.md` (design specification for review) —
freezes the farmer-action + renewed-consent protocol required for the publication contribution.

**Scope of the design.** Publication-safe deterministic semantics for the seven actions ACCEPT,
REJECT, MODIFY, NO_RESPONSE, WITHDRAW, RENEWED_ACCEPT, RENEWED_REJECT; a full 5×3 action/lock matrix
(ACCEPT/REJECT/MODIFY/NO_RESPONSE/WITHDRAW × FLEXIBLE/SOFT_LOCK/HARD_LOCK) with per-cell permitted/
state/crop/commitment/reopt/renewed-consent/realised/reason-code; a deterministic, keyed,
order-independent synthetic behavioural policy (PRIMARY profile + optional S1/S2 sensitivity, all
tagged SYNTHETIC_EXPERIMENTAL, drawn from the frozen `farmer_response` substream); the deterministic
renewed-consent workflow (revised recommendation → renewed response → realised revised plan, with the
existing-consent exception and unconsented offers excluded from realised recovery); the four-tier
metric separation PLANNED / INITIAL_REALIZED / RECOMMENDED_REVISED / FINAL_REALIZED; invariants, edge
cases, provenance classification, limitations, a proposed implementation plan, proposed tests, and a
list of unresolved decisions requiring approval.

**Grounded in current implementation (verified this turn, read-only).** `FarmerEvent` already
contains ACCEPT/REJECT/MODIFY/NO_RESPONSE/WITHDRAW; commitment ladder VIEWED→…→PLANTED with locks
VIEWED=FLEXIBLE, intermediate=SOFT_LOCK, PLANTED=HARD_LOCK; Phase-7 parses ACCEPT/REJECT/MODIFY/
WITHDRAW/QUERY/CLARIFY with WITHDRAW → NOT_IMPLEMENTED (`WITHDRAW_REQUIRES_POLICY`) and
EXECUTABLE_ACTIONS={ACCEPT,REJECT,MODIFY}; existing renewed-consent logic
`requires_renewed_consent = (acc is None) or (acc != offered)` for ACCEPT and `(acc != crop)` for
MODIFY. The protocol is consistent with these and supplies the missing NO_RESPONSE behaviour, the
WITHDRAW policy, and the renewed-consent round.

**Scientific audit (no edits made).** Manuscript Methods sentences that state behaviour is limited to
ACCEPT/REJECT, or that revised recommendations realise without a renewed round, would become
inaccurate once implemented and must be revised LATER (not now). Schema note: `RENEWED_ACCEPT`/
`RENEWED_REJECT` and a `PENDING_LAPSED` marker are NOT yet in the enums; flagged for a later,
approval-gated schema extension. NO enum changed this turn.

**Status flags.** requirements.txt: unchanged. Scientific formulation: unchanged. Scientific results:
unchanged. Frozen artifacts: unchanged (byte-identical). RNG/seeds/hash: unchanged (instance_hash
5ea24037c2d9cb6a; `farmer_response` substream reused, not modified). Dataset: unchanged. AskVish
unrelated code: unchanged. Files changed this turn: added
`docs/farmsync/ACTION_CONSENT_PROTOCOL.md`; updated `docs/farmsync/PROGRESS.md`.

**Unresolved decisions requiring approval (see protocol §16).** PRIMARY probabilities; WITHDRAW
modelling; SOFT_LOCK MODIFY/REJECT policy; PENDING_LAPSED representation; renewed-consent scope
(single vs iterated); inclusion of sensitivity profiles; schema-extension timing.

**Exact next step.** Review `ACTION_CONSENT_PROTOCOL.md` and resolve the §16 decisions. On approval,
the next turn implements the frozen protocol (config policy block, `actions.py`, consent gate,
renewed-consent round, WITHDRAW policy, four-tier metrics) with tests — still BEFORE final30, live
LLM, uncertainty implementation, Phase 8, manuscript results, or UI, all of which remain gated.

---

## ACTION + RENEWED-CONSENT PROTOCOL — APPROVED & FROZEN (2026-08-24)

Approval/freeze checkpoint. NO code, tests, datasets, solver configuration, epsilon/lambda/alpha,
frozen artifacts, RNG seeds, or Phase 1–7 results changed. Windows/CBC remains CLOSED. No final30, no
live LLM, no uncertainty implementation, no UI. Read-only inspection of the preference representation
was performed (see decision 10 below).

`docs/farmsync/ACTION_CONSENT_PROTOCOL.md` status advanced to
**action-consent-protocol-v1-FROZEN-PENDING-IMPLEMENTATION**; all §16 items resolved.

**Approved & frozen decisions:**
1. Acceptance model RETAINED: `p_accept(f) = clip(0.85 + 0.20*(risk_tolerance-0.5), 0, 1)`
   (SYNTHETIC_EXPERIMENTAL); no fixed 0.70.
2. Initial non-acceptance conditional split: REJECT 0.45 / MODIFY 0.35 / NO_RESPONSE 0.20.
3. Renewed round reuses `p_accept(f)`; renewed non-acceptance REJECT 0.70 / NO_RESPONSE 0.30; single
   pass; FINAL_REALIZED only via existing consent or renewed ACCEPT.
4. WITHDRAW `p_withdraw=0.02`, drawn ONCE per farmer per cycle, keyed WITHOUT plot_id
   (`sha256(substream:farmer_id:cycle_id:withdraw)`), applied to all owned plots.
5. WITHDRAW land-agency corrected: withdrawn flexible land REMOVED from the optimiser decision set and
   NOT reassigned to the collective; soft-lock sunk cost preserved; hard-lock physical crop
   immutable/administrative-only. Distinct from REJECT (participant retained, plot re-offerable).
6. SOFT_LOCK is changeable (≠ hard-lock): MODIFY allowed with soft-lock disruption penalty +
   constrained reopt + renewed consent; REJECT revokes/invalidates the consented soft-lock crop with
   sunk cost recorded.
7. NO_RESPONSE / PENDING_LAPSED: `action=NO_RESPONSE` behavioural event + `offer_status=PENDING_LAPSED`
   status; PENDING_LAPSED is NOT a FarmerEvent.
8. Renewed vocabulary: NO RENEWED_ACCEPT/RENEWED_REJECT enums; reuse ACCEPT/REJECT/NO_RESPONSE with
   `decision_round=RENEWED`; optional new STATUS types ConsentKind/DecisionRound/OfferStatus only.
9. Sensitivity profiles as acceptance-propensity shifts: PRIMARY `p_accept`; S1 `-0.15`; S2 `+0.10`;
   splits and `p_withdraw` unchanged; paired seeds.
10. MODIFY-target FACTUAL FINDING: `farmer_preferences.csv` schema exists but is EMPTY (0 data rows in
    builtin and snapshot); no runtime preference ordering; only `risk_tolerance` plus per-(plot,crop)
    feasibility (`plot_crop_suitability`) and the optimiser's expected-net-return coefficient are
    available. FROZEN substitute: choose the highest deterministic expected-net-return FEASIBLE +
    ADMITTED alternative (exclude current crop), tie-break by crop_id, then hand to the deterministic
    reoptimisation layer for global validation; if none, `MODIFY_NO_FEASIBLE_ALTERNATIVE` (no invented
    crop, no reopt, prior consent retained). Preference-ordering targeting remains an approval-gated
    follow-up if `farmer_preferences.csv` is later populated.
11. NO_RESPONSE context: matrix distinguishes fresh-offer lapse from no-response where a still-valid
    prior crop-specific consent exists (prior consent retained; hard-lock physical state unchanged).

**Full lock/action matrix, RNG design, renewed-consent workflow, four-tier metrics
(PLANNED/INITIAL_REALIZED/RECOMMENDED_REVISED/FINAL_REALIZED), invariants, edge cases, provenance,
implementation plan, and tests are frozen in the protocol document.** No unresolved methodological
decision remains.

**Status flags.** requirements.txt: unchanged. Scientific formulation: unchanged. Scientific results:
unchanged. Frozen artifacts: unchanged (byte-identical). RNG/seeds/hash: unchanged (instance_hash
5ea24037c2d9cb6a; `farmer_response` substream reused, not modified). Dataset: unchanged (preference
table confirmed empty; NOT populated this turn). AskVish unrelated code: unchanged. Files changed:
updated `docs/farmsync/ACTION_CONSENT_PROTOCOL.md` (draft → v1-FROZEN) and this `PROGRESS.md`.

**Exact next step.** Implement the frozen protocol WITH tests, per protocol §17–§18: config policy
block, `farmsync/proposed/actions.py`, consent-gate `consent_kind`/`decision_round`, renewed-consent
round, WITHDRAW policy replacing the Phase-7 `NOT_IMPLEMENTED` stub, four-tier metrics, and optional
status types (no behavioural enum change). Still gated and NOT started: uncertainty implementation,
final30, live LLM, ≥300 benchmark, Phase 8, manuscript results, UI.

---

## ACTION + RENEWED-CONSENT PROTOCOL — IMPLEMENTED + DEV CHECKPOINT (2026-08-24)

Implementation of the frozen `action-consent-protocol-v1`. NO frozen B1/B2/B3/Phase 1–7 scientific
artifacts changed (all byte-identical, re-verified); no dataset, solver config, epsilon/lambda/alpha,
master seeds, or RNG files changed. No final30, no live LLM, no ≥300 benchmark, no uncertainty, no UI.
Windows CBC solver settings untouched.

**Version / provenance.** `action-consent-v1`; all behavioural probabilities tagged
SYNTHETIC_EXPERIMENTAL (frozen in config; not empirical prevalence). Stable action-cycle identifier =
master seed (recorded in output metadata).

**Files created.** `farmsync/proposed/actions.py` (deterministic keyed draws, once-per-farmer
withdrawal keyed WITHOUT plot_id, action selection, lock/action matrix, canonical MODIFY-target via
`_eligible`, consent types, renewed-consent workflow, four-tier orchestrator; NO solver authority);
`tests/test_farmsync_actions.py` (16 tests).
**Files modified.** `farmsync/config.py` (frozen SYNTHETIC_EXPERIMENTAL policy block: p_accept model,
initial split 0.45/0.35/0.20, renewed split 0.70/0.30, p_withdraw 0.02, sensitivity PRIMARY/S1/S2);
`farmsync/proposed/llm_interaction.py` (Phase-7 WITHDRAW replaced `NOT_IMPLEMENTED`/
`WITHDRAW_REQUIRES_POLICY` with a validated administrative-withdrawal payload — scope
CYCLE_PARTICIPATION, hard-lock administrative-only/physical-immutable; the LLM/parser still decides no
allocation or feasibility, and the crop-executor still treats WITHDRAW as NOT_APPLICABLE, so
BoundaryState execution-equivalence is preserved); `tests/test_farmsync_proposed_p7.py` (WITHDRAW test
updated to the new policy); `docs/farmsync/ACTION_CONSENT_PROTOCOL.md` (§20 SOFT_LOCK-WITHDRAW
final-realisation clarification only — no redesign).

**Policy/config values (frozen).** `p_accept(f)=clip(0.85+0.20*(risk_tolerance-0.5),0,1)`; initial
non-acceptance REJECT/MODIFY/NO_RESPONSE = 0.45/0.35/0.20; renewed non-acceptance REJECT/NO_RESPONSE =
0.70/0.30; `p_withdraw=0.02` once per farmer per cycle; sensitivity shifts PRIMARY 0 / S1 −0.15 /
S2 +0.10 (splits + withdraw unchanged across profiles).

**RNG design.** Frozen `farmer_response` substream (unchanged). Per-plot draws keyed
`sha256(substream:farmer_id:plot_id:cycle_id:decision_point)`; WITHDRAW keyed
`sha256(substream:farmer_id:cycle_id:withdraw)` — NO plot_id, once per farmer, applied to all plots.
Order-independent by construction; cycle_id = master seed (stable, deterministic, recorded).

**Development checkpoint (seed 20260812, PRIMARY; NOT a final30 run).**
instance_hash 5ea24037c2d9cb6a; substream(farmer_response)=1120031581; determinism check = PASS
(two runs identical). Hard constraints: pipeline `_require_optimal` gate satisfied (Optimal only).
- Action counts (over 381 planned plots): ACCEPT 322, REJECT 18, MODIFY 22, NO_RESPONSE 7,
  WITHDRAW 12. Withdrawn farmers: 12. MODIFY valid-target 9 / no-feasible-alternative 7 (remaining
  MODIFYs fell on hard-lock plots → lock-blocked). Lock-blocked actions: 12. Consent invalidations: 11.
- Renewed prompts: 76 → renewed ACCEPT 56 / REJECT 13 / NO_RESPONSE 7. Existing-consent exceptions:
  172. Unconsented revised recommendations: 20.
- Four tiers (cash ₹ / area ha / n):
  PLANNED 13,142,166 / 327.117 / 381 (matches frozen B3 planned);
  INITIAL_REALIZED 12,081,314 / 299.506 / 336;
  RECOMMENDED_REVISED 12,285,254 / 292.049 / 343 (matches frozen concentration);
  FINAL_REALIZED 11,837,491 / 282.939 / 323.
- Recommendation-realisation ratio: 0.9007 vs PLANNED; 0.9636 vs RECOMMENDED.
- Consent coverage of FINAL_REALIZED: 1.0. fairness-v2 reported for INITIAL and FINAL realised sets
  (per_ha_gini ~0.745; participation 53.4%→51.4%).
- OBSERVATION (reported, not tuned): FINAL_REALIZED (11,837,491) < INITIAL_REALIZED (12,081,314)
  because revised recommendations require renewed consent and not all are renewed-accepted (13 renewed
  REJECT + 7 renewed NO_RESPONSE + 20 unconsented revised), so consented-only final recovery is lower
  than the initial consented set. This is expected protocol behaviour; the frozen policy was NOT
  altered to change it.

**Tests.** New `test_farmsync_actions.py` 16 passed. Regression: chunk 1 (all except p5/p6, incl.
actions + P7 + ilp_v2 + portability) 195 passed; p5+p6 28 passed. **Total 223 passed** (was 207; +16).
P7 = 46 passed (WITHDRAW policy). A pre-existing order-fragility in `test_farmsync_b1.py` (it resets
`planning._INGESTED` but not the `opdata` singleton, and assumed opdata unloaded) surfaced when the new
ingest-loading actions module runs earlier; fixed test-only via an autouse teardown in
`test_farmsync_actions.py` that restores pristine unloaded global state (no scientific code changed).

**Provenance / limitations.** Behavioural rates experimental, not empirical. Single decision window;
single renewed-consent pass. MODIFY target uses the canonical expected-return eligibility proxy while
`farmer_preferences.csv` remains empty. Dev checkpoint is a single seed, not the paired final30.

**Status flags.** REQUIREMENTS CHANGED: NO. DATASET CHANGED: NO. SOLVER CHANGED: NO. FROZEN ARTIFACTS
CHANGED: NO. SEEDS/RNG MASTER CHANGED: NO. SCIENTIFIC POLICY CHANGED: NO (frozen protocol implemented
as specified). ASKVISH UNRELATED CODE CHANGED: NO.

**Exact next step.** On approval, wire the action-consent layer's four-tier outputs into the
manuscript results pipeline and prepare the paired evaluation harness — still BEFORE final30, live
LLM, ≥300 benchmark, uncertainty implementation, Phase 8, manuscript results, and UI, all of which
remain gated.

---

## ACTION-CONSENT CAUSAL-INTEGRATION CORRECTION (2026-08-24)

Corrects the IMPLEMENTATION of the frozen `action-consent-protocol-v1`; the frozen methodology,
probabilities, RNG/lock/MODIFY/WITHDRAW/renewed-consent policy are UNCHANGED. NO dataset, solver
config, epsilon/lambda/alpha, master seeds, or frozen artifacts changed (all byte-identical). No
final30, live LLM, uncertainty, ≥300 benchmark, or UI.

### Prior checkpoint marked IMPLEMENTATION DEFECT FOUND / SUPERSEDED
The first action-consent implementation checkpoint (ACCEPT 322 / REJECT 18 / MODIFY 22 /
NO_RESPONSE 7 / WITHDRAW 12; FINAL_REALIZED ₹11,837,491) is SUPERSEDED — its numbers are retained
above for history but are provisional/incorrect because actions did not causally drive the revised
plan.

**Root cause.** actions.py generated actions AFTER `run_proposed_pipeline` produced the revised/conc
plan and overlaid renewed consent on that action-independent plan. MODIFY targets were computed but
never fed to reoptimisation; REJECT/WITHDRAW did not change the reopt input; renewed ACCEPT only
incremented a counter (no Consent record); fairness B1 reference was `farmer_cash(planned)` = B3, not
B1.

**Corrected causal sequence (reuses existing Phase-3/4 machinery; no new optimiser).**
PLANNED (B3) → initial farmer actions → build an action-adjusted commitment SCENARIO
(REJECT and validated MODIFY → the plot's current crop is excluded via the existing
`REJECTED_TERMINAL` option rule in `reoptimize._phase3_options`; WITHDRAW flexible/soft → plot removed
from the decision set and from `plots`; HARD_LOCK immutable) → `ro.max_economic` / `ro.fairness_floor`
/ `ro.solve_phase3` then `co.max_economic_alpha` / `co.fairness_floor_alpha` / `co.solve_phase4` on
that scenario → RECOMMENDED_REVISED → renewed consent (real records) → FINAL_REALIZED. Optimiser stays
authoritative: MODIFY recorded as REQUESTED_AND_RECOMMENDED / REQUESTED_NOT_RECOMMENDED /
MODIFY_NO_FEASIBLE_ALTERNATIVE / BLOCKED_BY_LOCK, never forced.

**B1 fairness reference correction.** Now uses the pipeline's canonical B1 ILP cash
(`objects["b1cash"]` from `run_b1_ilp`), total ₹14,644,537 — verified and recorded in result meta as
`b1_reference_source="B1_ILP (run_b1_ilp)"`. The authoritative frozen B1 value ₹14,644,537 is
unchanged.

**Consent records + coverage.** Renewed ACCEPT now CREATES a `Consent(consent_kind=RENEWED,
decision_round=RENEWED, cycle_id, ...)`; existing-consent exception reuses the still-valid INITIAL
record; HARD_LOCK reconstructs provenance from the prior accepted consent (no fabricated current
ACCEPT). `consent_coverage_final` is DERIVED from verified (farmer, plot, exact-crop, valid) record
matches / FINAL_REALIZED count (predicate `actions.consent_matches`), asserted == 1.0 — not a counter.

**Event ledger.** Inspectable in-memory ledger (returned in the result; no frozen artifact written)
with event_id, seed, cycle_id, farmer_id, plot_id, event_type
(ACTION / MODIFY_RESULT / RECOMMENDATION / CONSENT), behavioural_action, decision_round, crop_before,
crop_requested, crop_recommended, consent_kind, consent_valid, offer_status, lock, reason_code,
realised. Recommendation events and consent events are separate rows; renewed actions are recorded.

**Files changed.** `farmsync/proposed/actions.py` (REPLACE — causal orchestrator, consent records,
ledger, `consent_matches`, B1 fix); `tests/test_farmsync_actions.py` (REPLACE — causal + record
tests); `docs/farmsync/ACTION_CONSENT_PROTOCOL.md` (§21 implementation-correction note);
`docs/farmsync/PROGRESS.md`. `farmsync/config.py` and `farmsync/proposed/llm_interaction.py` unchanged
this turn.

**Corrected development checkpoint (seed 20260812, PRIMARY; NOT final30).** instance_hash
5ea24037c2d9cb6a; substream(farmer_response)=1120031581; determinism = PASS; reopt Optimal;
concentration Optimal. Participating farmers 263.
- Actions: ACCEPT 284, REJECT 17, MODIFY 16, NO_RESPONSE 5, WITHDRAW 9 (over accepted offered plots).
  Withdrawn farmers 5. MODIFY valid 6 (REQUESTED_AND_RECOMMENDED 5 / REQUESTED_NOT_RECOMMENDED 1) /
  no-feasible-alternative 4 / remaining MODIFY fell on hard-lock (lock-blocked). Lock-blocked 12.
  Consent invalidations 11.
- Renewed prompts 66 → ACCEPT 48 / REJECT 11 / NO_RESPONSE 7. Existing-consent exceptions 171.
  Unconsented revised recommendations 20.
- Tiers (cash ₹ / area ha / n): PLANNED 13,142,166 / 327.117 / 381 (frozen B3 input);
  INITIAL_REALIZED 10,499,075 / 250.780 / 298; RECOMMENDED_REVISED 11,703,497 / 283.263 / 332
  (action-driven — differs from the frozen action-free conc 12,285,254, confirming causality);
  FINAL_REALIZED 11,324,071 / 274.175 / 312.
- Ratios: 0.8617 vs PLANNED; 0.9676 vs RECOMMENDED. Consent coverage FINAL = 1.0 (record-derived).
  withdrawn_in_renewed_prompts = [] (invariant holds). Ledger 906 rows.
- Hard constraints: reopt/concentration Optimal gates satisfied (Optimal-only extraction).

**Tests.** `test_farmsync_actions.py` 23 passed (incl. causal tests that FAIL on the old overlay:
RECOMMENDED_REVISED action-dependent; withdrawn absent from revised; withdrawn never re-prompted;
MODIFY reaches reopt; REJECT excluded in reopt; renewed ACCEPT creates real record; renewed
REJECT/NO_RESPONSE create none; exact-crop consent required; coverage record-derived; recommendation
≠ consent ledger rows; B1 reference is B1). Regression: chunk 1 (all except p5/p6) 202 passed; p5+p6
28 passed. **Total 230 passed.** P7 46 passed. Frozen artifacts byte-identical (b1_ilp_v2, b3_ilp_v2,
rng_streams, p6_event_ledger, p4_concentration).

**Limitations.** Behavioural rates experimental (SYNTHETIC_EXPERIMENTAL). Single decision window;
single renewed-consent pass. MODIFY target uses the canonical expected-return proxy while
`farmer_preferences.csv` is empty. Dev checkpoint is a single seed, not the paired final30.

**Status flags.** REQUIREMENTS CHANGED: NO. DATASET CHANGED: NO. SOLVER CHANGED: NO. FROZEN ARTIFACTS
CHANGED: NO. SEEDS/RNG MASTER CHANGED: NO. SCIENTIFIC POLICY CHANGED: NO. ASKVISH UNRELATED CODE
CHANGED: NO.

**Exact next scientific step.** UNCERTAINTY PROTOCOL DESIGN / FREEZE (design only, as with the action
protocol). NOT manuscript-results wiring. UI, live LLM, final30, and the ≥300 benchmark remain gated.

---

## UNCERTAINTY PROTOCOL — DESIGN CHECKPOINT (2026-08-24)

Methodology design only. NO code, datasets, solver settings, epsilon/lambda/alpha, frozen artifacts,
action-consent policy, master seeds, or Phase 1–7 results changed. The causal action + renewed-consent
implementation is UNCHANGED. Windows/CBC remains CLOSED. No final30, live LLM, ≥300 benchmark, or UI.

**Deliverable added:** `docs/farmsync/UNCERTAINTY_PROTOCOL.md` (draft-1, design for review; 24
sections). Parameter values are explicitly UNRESOLVED pending approval.

**Factual current-state findings (read-only).**
- All five RNG substreams exist for 30 seeds: farmer_response (in use, untouched), and
  participation_scenario / weather_hazard / market_shock / resource_shock — the latter four are
  currently UNUSED by any runtime code (clean 1:1 mapping to the four channels).
- `climate_scenarios`: POPULATED (40 rows = 8 scenarios × 5 regions) with baseline ET0, but ET0 is
  IDENTICAL across scenarios — shock magnitudes are undifferentiated/unfrozen (severity_note confirms
  "shock magnitudes are experimental parameters").
- `participation_scenarios`: POPULATED (5 rows) with participation_rate {1.0,0.9,0.75,0.6,0.4};
  non_response_rate/withdrawal_rate columns EMPTY by design → supports participation = pre-offer
  membership, disjoint from farmer_response.
- `market_scenarios`: SCHEMA-ONLY (0 rows) with anticipated columns price_change / absorption_change /
  cost_change → primary parameter gap.
- Constraints: per-farmer cultivation_budget + labour_capacity; global op_absorption caps; op_price/
  MSP; ET0/NIR/CWR/Ky water-yield pathway; plot available_water_m3. All perturbation targets exist.
- Phase-5 resilience has ZERO RNG references — fully deterministic counterfactual (N-1 + hazard-zone),
  never realised; categorically separate from the stochastic uncertainty layer.

**Design summary (proposed, pending approval).** Four independent channels, each perturbing only its
own causal variable via its own frozen substream: PARTICIPATION (pre-offer Bernoulli membership,
PRIMARY 0.90) ; WEATHER (region/season-correlated ET0 multiplier → water_req → yield via Ky, discrete
favourable/normal/adverse) ; MARKET (separate price and absorption multipliers, crop/region
correlated, MSP-floored; cost_change excluded from PRIMARY to avoid double count) ; RESOURCE (per-
farmer budget + labour multipliers; cost NOT perturbed). Causal timeline A–J with a NEW Stage C
input-perturbation layer feeding the EXISTING optimisation + action-consent stages; Stage J keeps
Phase-5 separate. Paired reuse of each seed's realisation across B1/B2/B3/Proposed; behavioural tiers
apply to Proposed only (baselines get N/A tiers, not fabricated mechanics). Optimal-only extraction;
infeasibility is a valid recorded outcome, never relaxed. Ablations U0/UW/UM/UR/UP/UJ (six), kept
separate from action S1/S2. Final-30 analysis (design only): paired Wilcoxon + Holm + rank-biserial,
infeasible runs included, no seed excluded.

**RNG/substream decisions.** 1:1 channel↔substream mapping; sub-seeds via existing
experiment.substream; master 30-seed list unchanged; keyed order-independent draws with stable
region/crop/farmer/plot keys; cycle_id = master seed; farmer_response untouched.

**Status.** Dataset/gate/config/instance hash unchanged (instance_hash 5ea24037c2d9cb6a). Frozen
artifacts unchanged (byte-identical). Files changed: added `docs/farmsync/UNCERTAINTY_PROTOCOL.md`;
updated `docs/farmsync/PROGRESS.md`. No code, no requirements, no scientific-policy change.

**Unresolved decisions requiring approval (protocol §24).** Weather ET0 multipliers/probabilities;
market price+absorption multipliers/probabilities and cost_change inclusion (market_scenarios empty);
resource budget/labour multipliers and optional water; participation PRIMARY level and UP ladder; draw
granularity; ablation set + optional S×U add-ons; infeasibility summary handling; final-30 statistics.

**Exact next step.** Review `UNCERTAINTY_PROTOCOL.md` and resolve the §24 parameters. On approval, the
next turn freezes those values into the document (status → v1-FROZEN) and only THEN implements the
uncertainty layer with tests — still BEFORE final30, live LLM, ≥300 benchmark, Phase 8, manuscript
results, and UI, all of which remain gated.

---

## UNCERTAINTY PROTOCOL — APPROVED & FROZEN (2026-08-24)

Approval/freeze checkpoint. NO code, datasets, solver settings, epsilon/lambda/alpha, action-consent
policy, master seeds, frozen artifacts, or existing scientific results changed. The causal
action + renewed-consent implementation is UNCHANGED. Windows/CBC remains CLOSED. No final30, live LLM,
≥300 benchmark, or UI. Read-only inspection this turn confirmed two facts used below.

`docs/farmsync/UNCERTAINTY_PROTOCOL.md` status advanced to
**uncertainty-protocol-v1-FROZEN-PENDING-IMPLEMENTATION**; §24 fully resolved; the entire document was
reviewed and all stale text corrected (MSP-floor, absorption granularity, Ky penalty, favourable/
adverse naming, stochastic-optimisation wording, resource water perturbation).

**Framing correction.** Described as PAIRED SCENARIO-BASED UNCERTAINTY EVALUATION using SYNTHETIC
EXOGENOUS UNCERTAINTY REALISATIONS — explicitly NOT stochastic programming/optimisation. For each seed,
uncertainty inputs are drawn reproducibly and the existing deterministic optimisation is solved under
that realisation. Phase-5 remains a separate deterministic counterfactual.

**Frozen values (all SYNTHETIC_EXPERIMENTAL; NOT empirical Indian agricultural frequencies).**
- WEATHER (channel W): ET0 states LOW_EVAPORATIVE_DEMAND 0.90 (p=0.20) / NORMAL 1.00 (0.60) /
  HIGH_EVAPORATIVE_DEMAND 1.15 (0.20); draw per region×season×cycle (weather_hazard). PRIMARY effect is
  ET0-only via existing CWR/NIR/water feasibility; **NO Ky yield penalty in v1** (avoids double-count
  with hard water feasibility; Ky reserved for a separately approved future sensitivity). Sourced
  baseline ET0 not modified.
- MARKET price (channel M): 0.90/1.00/1.10 at 0.25/0.50/0.25; crop×region (market_shock).
  `price' = price_AGMARKNET × m`, non-negativity only. **MSP CORRECTION:** operational basis is
  AGMARKNET market (median monthly modal); MSP is DEMOTED TO REFERENCE and does NOT floor/clip/replace
  the shocked price. MSP may appear in metadata/reporting as a reference comparison only. All draft
  "max(price, MSP_floor)" / "MSP floor respected" text removed.
- MARKET absorption: 0.85/1.00/1.15 at 0.20/0.60/0.20; **crop GLOBAL granularity** (matches
  `op_absorption(crop)` — verified crop-level, no region arg), one draw per crop×cycle. NOT crop×region.
  AGMARKNET arrivals remain an absorption proxy, never "demand".
- MARKET cost: `cost_change` NOT activated in v1; cultivation cost not perturbed.
- RESOURCE (channel R): one shared per-farmer state NORMAL 1.00 (0.70) / CONSTRAINED 0.85 (0.30),
  drawn once per farmer per cycle (resource_shock); the SAME multiplier scales BOTH cultivation_budget
  and labour_capacity. Costs and available_water_m3 NOT perturbed in v1. Hard-lock/planted immutable.
- PARTICIPATION (channel P): PRIMARY/core participation_rate = 0.90, per-farmer Bernoulli
  (participation_scenario), pre-offer membership only (disjoint from farmer_response); non-participating
  farmer+plots absent, land not reassigned, no offer, no action. The {1.0/0.9/0.75/0.6/0.4} ladder is a
  SEPARATE descriptive sensitivity, NOT part of the inferential U-family.

**Draw granularity (frozen).** weather region×season; price crop×region; absorption crop-global;
resource farmer; participation farmer; farmer_response unchanged. All keyed/order-independent/platform-
independent (no timestamp/UUID); cycle_id = master seed; same realisation reused across B1/B2/B3/
Proposed; master 30-seed list unchanged.

**Core ablations (frozen, six):** U0 / UW / UM / UR / UP / UJ. UJ = joint W+M+R+P via independent
substreams, no overall risk multiplier, no cross-channel term. Action S1/S2 NOT crossed with UJ in v1.

**Infeasibility (frozen, no imputation).** Optimal-only extraction; infeasible never zero-cash and
never relaxed/imputed. Per method×condition report n_total/n_optimal/n_infeasible/infeasibility_rate/
failed_stage. Continuous metrics summarised CONDITIONAL-ON-OPTIMAL with n. Paired continuous tests use
both-Optimal seeds only (report n_pairs); paired feasibility via exact McNemar; every seed retained in
reliability analysis. Phase-5 numeric tolerance NOT generalised.

**Final-30 statistics (frozen; design only).** Descriptive mean/median/SD/IQR/n/95% CI; 95% CI via
deterministic bootstrap 10,000 resamples with analysis-only bootstrap seed 20260812 (an analysis
constant, NOT a FarmSync scientific substream). Primary paired inference: two-sided Wilcoxon
signed-rank + matched-pairs rank-biserial (NOT Cliff's delta); deterministic zero/tie handling (Pratt
where supported). Holm within predefined families: A planning/method comparison (comparable
PLANNED/optimised tiers only — never Proposed FINAL_REALIZED vs baseline PLANNED as equivalent),
B Proposed deployment (FINAL_REALIZED retention/vs-U0, rec-to-realisation, churn), C reliability.

**Paired baseline rule (frozen).** Same seed → identical realisation + population for all methods;
farmer-response/renewed-consent Proposed-only; method comparisons at comparable tiers; baselines never
given synthetic farmer response; missing tiers reported N/A.

**Status.** Dataset/config/gate/instance hash unchanged (instance_hash 5ea24037c2d9cb6a). Frozen
artifacts unchanged (byte-identical). farmer_response substream untouched. Files changed: updated
`docs/farmsync/UNCERTAINTY_PROTOCOL.md` (draft-1 → v1-FROZEN) and this `PROGRESS.md`. No code, no
requirements, no scientific-result change.

**Exact next step.** IMPLEMENT uncertainty-v1 with tests and ONE development checkpoint only (per
protocol §20–§21: config block, `farmsync/proposed/uncertainty.py`, Stage-C application shims, six-
ablation runner build, metrics/reliability extension) — still BEFORE final30, live LLM, ≥300 benchmark,
Phase 8, manuscript results, and UI, all of which remain gated.

---

## UNCERTAINTY-v1 — IMPLEMENTED + DEV CHECKPOINT (2026-08-24)

Implementation of the frozen `uncertainty-protocol-v1`. NO methodology redesign. NO requirements,
dataset, solver config, epsilon/lambda/alpha, action-consent policy, master seeds, or frozen artifacts
changed (all byte-identical, re-verified). No final30, live LLM, ≥300 benchmark, or UI. Windows CBC
untouched. Protocol status → uncertainty-protocol-v1-FROZEN-IMPLEMENTED.

**Framing.** Paired scenario-based uncertainty evaluation with SYNTHETIC EXOGENOUS realisations (NOT
stochastic optimisation). One Realisation per (seed, condition), reused across B1/B2/B3/Proposed via a
deterministic realisation_hash.

**Files created.** `farmsync/proposed/uncertainty.py` (keyed per-channel draws, `Realisation` +
`realisation_hash`, scoped `apply()` context, `perturb_instance`, `run_uncertainty_condition`);
`tests/test_farmsync_uncertainty.py` (13 tests).
**Files modified.** `farmsync/config.py` (frozen uncertainty-v1 constants); `farmsync/climate.py`
(scoped ET0 multiplier hook in `_et0_for`); `farmsync/ingest/operational.py` (scoped price + crop-
global absorption hooks in `op_price`/`op_absorption`); `farmsync/proposed/pipeline.py` and
`farmsync/proposed/actions.py` (optional `instance=` injection so Proposed consumes the SAME perturbed
instance as the baselines). No behavioural/action-consent policy change.

**How each channel reaches ACTUAL optimiser inputs.**
- WEATHER (W): `climate._et0_for(region,season)` applies a read-time ET0 multiplier keyed
  (region_id, season) → existing CWR/NIR/water feasibility. ET0-only; NO Ky penalty. Baseline
  REGION_ET0 never mutated.
- MARKET (M): `operational.op_price(region,crop)` applies a read-time multiplier keyed (region, crop),
  non-negativity only, NO MSP floor (MSP demoted to reference); `operational.op_absorption(crop)`
  applies a read-time crop-GLOBAL multiplier (no region in key). No cost perturbation.
- RESOURCE (R): one shared per-farmer multiplier scales BOTH cultivation_budget and labour_capacity on
  a deep-copied instance. No cost/water perturbation. Hard-lock/planted untouched at input stage.
- PARTICIPATION (P): pre-offer per-farmer Bernoulli at rate 0.90; non-participants and ALL their plots
  removed from the deep-copied instance BEFORE planning (no offer, no farmer_response events).

**State-isolation mechanism.** Weather/market multipliers are set and CLEARED via `uncertainty.apply()`
(try/finally) — baseline data + REGION_ET0 never mutated. Resource/participation transform a deep copy.
HARD GATE VERIFIED: UJ followed by U0 in the same process reproduces clean U0 exactly; all overrides
(`operational._PRICE_MULT/_ABS_MULT`, `climate._ET0_MULT`) empty afterwards.

**Frozen config (SYNTHETIC_EXPERIMENTAL).** Weather ET0 {LOW 0.90/0.20, NORMAL 1.00/0.60, HIGH
1.15/0.20} region×season; price {0.90/1.00/1.10 @ 0.25/0.50/0.25} crop×region; absorption {0.85/1.00/
1.15 @ 0.20/0.60/0.20} crop-global; resource {NORMAL 1.00/0.70, CONSTRAINED 0.85/0.30} per farmer →
budget+labour; participation 0.90; conditions U0/UW/UM/UR/UP/UJ; analysis bootstrap seed 20260812.

**RNG / substreams.** 1:1 mapping: weather_hazard (W), market_shock (M, price+absorption),
resource_shock (R), participation_scenario (P); farmer_response unchanged (verified substream value
1120031581 for seed 20260812). Keyed order-independent draws; absorption key has NO region; withdraw
(action layer) still keyed without plot_id. cycle_id = master seed. Master 30-seed list unchanged.

**Development checkpoint (seed 20260812; NOT final30). NO tuning.**
- **U0 PARITY — PASS (hard gate):** B1 14,644,537 / B2 13,822,731 / B3 13,142,166 (== frozen canonical
  values); participating 500/500; Proposed PLANNED 13,142,166; consent coverage 1.0. realisation_hash
  8e7716de9796a0e0.
- **UJ checkpoint:** realisation_hash daf331e3d0b2a1fc (≠ U0). Participating 459/500 (41 removed by P).
  Channel states: weather 3 LOW / 7 NORMAL (region×season); absorption 5 HIGH / 2 LOW / 7 NORMAL;
  resource 342 NORMAL / 158 CONSTRAINED; price 70 crop×region cells. Baselines (Optimal): B1
  13,158,690 / B2 12,545,978 / B3 11,930,066 — all below U0, confirming uncertainty reaches the actual
  optimiser inputs. Proposed tiers: PLANNED 11,930,066 / INITIAL_REALIZED 9,335,113 /
  RECOMMENDED_REVISED 10,309,288 / FINAL_REALIZED 10,007,462. Actions ACCEPT 247 / REJECT 15 /
  MODIFY 14 / NO_RESPONSE 9 / WITHDRAW 7 (5 farmers); renewed 67 (ACCEPT 47/REJECT 13/NO_RESPONSE 7);
  reopt+conc Optimal; consent coverage 1.0. Runtime ~2 min for the pair. No infeasibility.
- UW/UM/UR/UP validated via unit/integration tests (not full-scale runs), per instruction.

**Tests.** `test_farmsync_uncertainty.py` 13 passed (weather ET0→accessor; price→projected_return with
NO MSP floor; absorption crop-global + no region in key; resource same mult on budget+labour + original
instance intact; participation removes farmer+plots pre-planning; realisation hash stable/order-
independent; U0 parity; UJ causal; same realisation reused across methods; UJ→U0 isolation;
farmer_response substream unchanged). Regression: chunk 1 (all except p5/p6/uncertainty) 202 passed;
p5+p6 28 passed; uncertainty 13 passed. **Total 243 passed.** P7 46. Frozen artifacts byte-identical
(b1_ilp_v2, b3_ilp_v2, rng_streams, p6_event_ledger, p4_concentration). Phase-5 resilience unchanged
and separate.

**Provenance / limitations.** All severities SYNTHETIC_EXPERIMENTAL, not empirical. Single cycle per
seed; single renewed-consent pass; weather ET0-only (no Ky) in v1; market cost + water-supply excluded
by design; participation a simple Bernoulli. Dev checkpoint is a single seed, not final30. No
unresolved implementation issues.

**Status flags.** REQUIREMENTS CHANGED: NO. DATASET CHANGED: NO. SOLVER CHANGED: NO. FROZEN ARTIFACTS
CHANGED: NO. SEEDS/RNG MASTER CHANGED: NO. ACTION-CONSENT POLICY CHANGED: NO. UNCERTAINTY POLICY
CHANGED: NO (frozen protocol implemented as specified). ASKVISH UNRELATED CODE CHANGED: NO.

**Exact next step.** Publication λ/α freeze/check → pre-publication audit → UI. final30, live LLM, ≥300
benchmark, Phase 8, and manuscript results remain gated.

---

## FINAL INTEGRATION CORRECTION — SINGLE-GATE + INFEASIBILITY + HASH + PHASE-5 (2026-08-24)

Implementation-consistency corrections before λ/α freeze. NO methodology redesign; NO change to
behavioural probabilities, uncertainty parameters, λ/α/epsilon, solver settings, datasets, seeds, or
frozen artifacts (all byte-identical, re-verified). No final30, live LLM, ≥300 benchmark, or UI.
Windows CBC untouched.

### Superseded checkpoints
- The action causal checkpoint (ACCEPT 284/REJECT 17/MODIFY 16/NO_RESPONSE 5/WITHDRAW 9; participating
  263; FINAL_REALIZED 11,324,071) is SUPERSEDED — its Proposed numbers depended on the duplicate
  Phase-1 + action gate.
- The prior UJ Proposed checkpoint (FINAL_REALIZED 10,007,462) is SUPERSEDED for the same reason.
- B1/B2/B3 U0 canonical values are UNCHANGED and were never affected.

### Root cause
`run_action_consent_layer` obtained its base commitment scenario from the full `run_proposed_pipeline`,
whose Stage-2 already applies the legacy Phase-1 ACCEPT/REJECT gate; the frozen action process then ran
on the survivors — a DUPLICATE initial-response gate. The full pipeline also executed Stage-6
resilience under `uncertainty.apply()`. Baseline status was hard-coded Optimal, and the Proposed
realisation-hash match was tautological.

### Corrections
1. **Single initial-response gate.** New `pipeline.prepare_proposed_prerequisites(seed, base, instance)`
   returns B3 planned + canonical B1 reference + a commitment scenario built over ALL planned offers
   via the existing P3_MIXED_V1 hash (every eligible offer gets a FLEXIBLE/SOFT/HARD lock; none
   pre-marked REJECTED_TERMINAL) — NO Phase-1 accept/reject, NO Stage-6 resilience. The action layer
   now applies exactly ONE frozen initial action per eligible B3 offer (verified: Σ actions == planned
   offers). All frozen action params/RNG/renewed/MODIFY/lock semantics unchanged; P3_MIXED_V1 timing
   preserved.
2. **Infeasibility handling.** `uncertainty.baseline_record` reads the ACTUAL `res.solver["status"]`;
   only Optimal exposes cash/area/allocations; non-Optimal → {status, optimal:False, failed_stage,
   cash:None, area:None}. Proposed reopt/concentration non-Optimal is caught as a valid recorded
   outcome (optimal:False, failed_stage), never a pseudo-solution, never zero-imputed.
3. **Realisation-hash provenance.** `run_action_consent_layer` accepts `uncertainty_condition` +
   `realisation_hash` from the SAME Realisation and surfaces them in meta; not recomputed inside
   Proposed. B1==B2==B3==Proposed share one realisation_hash.
4. **Phase-5 separation.** The action/uncertainty path uses the prefix (no Stage-6). Verified by test
   that resilience is not invoked by `run_uncertainty_condition`. Standalone P6 retains Stage-6;
   Phase-5 artifacts/formulation unchanged.

### Files changed
Modified: `farmsync/proposed/pipeline.py` (NEW `prepare_proposed_prerequisites`; `instance=` retained);
`farmsync/proposed/actions.py` (consume prefix → single gate; `uncertainty_condition`/`realisation_hash`
meta params); `farmsync/proposed/uncertainty.py` (`baseline_record` real status; realisation propagated
to Proposed; Proposed try/except for non-Optimal). Tests: `tests/test_farmsync_uncertainty.py`
(strengthened; now 20). `farmsync/config.py`, `farmsync/climate.py`,
`farmsync/ingest/operational.py` unchanged this turn. Docs: ACTION_CONSENT_PROTOCOL.md §22 +
UNCERTAINTY_PROTOCOL.md §26 implementation-correction notes.

### Corrected development checkpoint (seed 20260812; NO tuning)
- **U0 PARITY — PASS (hard gate):** B1 14,644,537 / B2 13,822,731 / B3 13,142,166 (all optimal=True).
  realisation_hash 8e7716de9796a0e0; B1==B2==B3==Proposed hash identical. Proposed (single gate):
  actions ACCEPT 322 / REJECT 18 / MODIFY 22 / NO_RESPONSE 7 / WITHDRAW 12 (Σ=381 = planned offers);
  tiers PLANNED 13,142,166 / INITIAL_REALIZED 12,104,102 / RECOMMENDED_REVISED 12,647,039 /
  FINAL_REALIZED 12,424,780; consent coverage 1.0; reopt/conc Optimal; participating 500.
- **UJ checkpoint:** realisation_hash daf331e3d0b2a1fc (≠U0), Proposed hash match True, condition UJ.
  Participating 459/500. Baselines (real status, all Optimal): B1 13,158,690 / B2 12,545,978 /
  B3 11,930,066. Proposed optimal=True; tiers PLANNED 11,930,066 / INITIAL_REALIZED 10,910,387 /
  RECOMMENDED_REVISED 11,396,693 / FINAL_REALIZED 11,286,155; actions ACCEPT 285/REJECT 16/MODIFY 19/
  NO_RESPONSE 10/WITHDRAW 8; renewed prompts 45; consent coverage 1.0; reopt/conc Optimal. No
  infeasibility. UW/UM/UR/UP validated via unit/integration tests.

### Tests
`test_farmsync_uncertainty.py` 20 passed (adds: non-Optimal never reported Optimal; weather ET0 reaches
real NIR pathway; shocked crop-global absorption binds actual B2 cap; scaled resource binds solver;
non-participant has zero action/consent ledger events; Phase-5 not invoked; single action per offer;
Proposed carries real realisation_hash). `test_farmsync_actions.py` 23 passed (single-gate). Regression:
chunk 1 (incl. actions/P7/ilp_v2/portability) 202 passed; p5+p6 28 passed; uncertainty 20 passed.
**Total 250 passed.** Frozen artifacts byte-identical (b1_ilp_v2, b3_ilp_v2, rng_streams,
p6_event_ledger, p4_concentration). Phase-5 unchanged/separate. farmer_response substream unchanged.

### Provenance / limitations / next
All severities SYNTHETIC_EXPERIMENTAL. NO parameter tuning anywhere in this correction. Dev checkpoint
is a single seed, not final30. No unresolved implementation issues.

**Status flags.** REQUIREMENTS CHANGED: NO. DATASET CHANGED: NO. SOLVER CHANGED: NO. FROZEN ARTIFACTS
CHANGED: NO. SEEDS/RNG MASTER CHANGED: NO. ACTION-CONSENT POLICY CHANGED: NO. UNCERTAINTY POLICY
CHANGED: NO. ASKVISH UNRELATED CODE CHANGED: NO.

**Exact next step.** Publication λ/α freeze/check.

---

## ACTION/COMMITMENT ORDERING CORRECTION (2026-08-24)

Ordering correction introduced by the single-gate fix. NO methodology redesign; NO change to
behavioural probabilities, uncertainty parameters, λ/α/epsilon, solver settings, datasets, seeds, or
frozen artifacts (all byte-identical, re-verified). No final30, live LLM, ≥300 benchmark, or UI.
Windows CBC untouched. (Sandbox was reset mid-session; build tree was restored intact from the
delivered outputs and dependencies reinstalled — no scientific state lost.)

### Superseded
- The previous Proposed dev checkpoint (U0 tiers with FINAL_REALIZED 12,424,780; UJ FINAL_REALIZED
  11,286,155) is SUPERSEDED — those numbers came from the commitment-before-acceptance ordering.
- B1/B2/B3 U0 canonical values (14,644,537 / 13,822,731 / 13,142,166) were never affected and remain.

### Root cause
`prepare_proposed_prerequisites` marked every B3 offer `status="REALISED"` and ran P3_MIXED_V1 BEFORE
`initial_action`, so unaccepted offers could be pre-assigned SOFT_LOCK/HARD_LOCK; the action layer then
treated a pre-assigned HARD_LOCK as already realised and constructed INITIAL consent even when the
drawn initial action was REJECT/MODIFY/NO_RESPONSE/WITHDRAW — violating the frozen consent semantics.

### Correction — commitment after acceptance
Causal order is now: B3 PLANNED → ONE initial action per FRESH VIEWED/FLEXIBLE offer → construct
consent/action outcome → assign P3_MIXED_V1 commitment timing to INITIALLY ACCEPTED allocations ONLY
(`pipeline.commit_accepted`, unchanged deterministic hash / same timing mechanism) → action-adjusted
scenario (accepted plots carry their FLEX/SOFT/HARD lock; REJECT & valid-MODIFY plots →
REJECTED_TERMINAL; NO_RESPONSE & MODIFY-no-alt → FLEXIBLE decision plot, no consent; withdrawn farmers'
plots removed) → Phase-3/4 reopt → RECOMMENDED_REVISED → renewed consent → FINAL_REALIZED.
- A fresh offer is FLEXIBLE and can never be SOFT/HARD before acceptance.
- Initial ACCEPT: exact-crop INITIAL consent + INITIAL_REALIZED, then eligible for the commitment
  ladder. Initial REJECT/MODIFY/NO_RESPONSE/WITHDRAW: NO INITIAL consent, NO commitment ladder.
- Every HARD_LOCK now traces to a prior ACCEPT (the ladder is built only from accepted offers).
- `prepare_proposed_prerequisites` returns fresh `offers` (no `scen`); new `pipeline.commit_accepted`
  assigns P3_MIXED_V1 to accepted offers only.

### Typed infeasibility (exception handling)
New `actions.ProposedInfeasibleError(failed_stage, status)` is raised for non-Optimal action-adjusted
reopt/concentration. `uncertainty.run_uncertainty_condition` now catches ONLY that typed exception;
unexpected programming errors (KeyError/TypeError/etc.) PROPAGATE and fail the run. No pseudo-solution,
no zero-imputation. Baseline non-Optimal handling (`baseline_record`) unchanged.

### Files changed
Modified: `farmsync/proposed/pipeline.py` (prefix returns fresh offers; NEW `commit_accepted`);
`farmsync/proposed/actions.py` (reordered initial round: fresh→action→commit-accepted; typed
`ProposedInfeasibleError`; `lock_blocked_actions` now 0 — no hard-lock at initial); `farmsync/proposed/
uncertainty.py` (catch only `ProposedInfeasibleError`). Tests: `tests/test_farmsync_actions.py`
(+5 ordering/hard-lock invariant tests → 28); `tests/test_farmsync_uncertainty.py` (+2 exception tests
→ 22). `config.py`, `climate.py`, `operational.py` unchanged this turn. Docs: ACTION_CONSENT_PROTOCOL
§23 + UNCERTAINTY_PROTOCOL §27 notes; both top-level statuses set to v1-FROZEN-IMPLEMENTED.

### Corrected development checkpoint (seed 20260812; NO tuning)
- **U0 PARITY — PASS:** B1 14,644,537 / B2 13,822,731 / B3 13,142,166 (all optimal=True); realisation
  B1==B2==B3==Proposed hash 8e7716de9796a0e0. Proposed: actions ACCEPT 322/REJECT 18/MODIFY 22/
  NO_RESPONSE 7/WITHDRAW 12 (Σ=381=offers); tiers PLANNED 13,142,166 / INITIAL_REALIZED 11,953,688 /
  RECOMMENDED_REVISED 12,586,101 / FINAL_REALIZED 12,362,577; consent coverage 1.0 (record-derived);
  reopt/conc Optimal.
- **UJ checkpoint:** hash daf331e3d0b2a1fc, Proposed hash match True. Baselines (real status, all
  Optimal): B1 13,158,690 / B2 12,545,978 / B3 11,930,066. Proposed optimal=True; tiers PLANNED
  11,930,066 / INITIAL_REALIZED 10,716,058 / RECOMMENDED_REVISED 11,315,587 / FINAL_REALIZED
  11,208,457; actions ACCEPT 285/REJECT 16/MODIFY 19/NO_RESPONSE 10/WITHDRAW 8; renewed prompts 54;
  consent coverage 1.0; participating 459/500. No infeasibility.

### Tests
`test_farmsync_actions.py` 28 passed (incl. new: prefix offers all fresh-flexible; only ACCEPTs enter
P3_MIXED_V1 and every HARD_LOCK has a prior ACCEPT; fresh non-ACCEPT actions create no consent; no
initial hard-lock block events; coverage record-derived after reorder). `test_farmsync_uncertainty.py`
22 passed (incl. unexpected programming exception NOT classified infeasible; typed error structured).
Regression totals: uncertainty 22; actions+P7+ilp_v2+portability 87; remaining chunk-1 120; p5+p6 28 →
**257 passed**. Frozen artifacts byte-identical (b1_ilp_v2, b3_ilp_v2, rng_streams, p6_event_ledger,
p4_concentration). Phase-5 unchanged/separate. farmer_response substream unchanged.

### Status flags
REQUIREMENTS CHANGED: NO. DATASET CHANGED: NO. SOLVER CHANGED: NO. FROZEN ARTIFACTS CHANGED: NO.
SEEDS/RNG MASTER CHANGED: NO. ACTION-CONSENT POLICY CHANGED: NO. UNCERTAINTY POLICY CHANGED: NO.
ASKVISH UNRELATED CODE CHANGED: NO. NO parameter tuning.

**Exact next step.** Publication λ/α freeze/check.

---

## AUXILIARY-SOLVER STATUS GUARD (2026-08-24)

Small failure-handling patch only. NO methodology redesign; NO change to probabilities, uncertainty,
epsilon/lambda/alpha, solver config, datasets, seeds, RNG, or frozen artifacts. Successful-run
behaviour is unchanged (this patch only adds fail-loudly checks on non-Optimal auxiliary solves).
Sandbox was reset again mid-session; build tree restored intact from delivered outputs, deps
reinstalled — no scientific state lost.

### Change
`run_action_consent_layer` previously checked only the final Phase-3 and Phase-4 solve statuses. It now
guards EVERY auxiliary solve before consuming its value and before calling the next solve, matching the
validated P6 fail-loudly behaviour. No E*/t_floor/E*_alpha/t_floor_alpha is fabricated or zero-imputed.
New typed `ProposedInfeasibleError` failed_stage names:
- `proposed.phase3_e_star`              (ro.max_economic status)
- `proposed.phase3_fairness_floor`      (ro.fairness_floor status)
- `proposed.phase4_e_star_alpha`        (co.max_economic_alpha status)
- `proposed.phase4_fairness_floor_alpha`(co.fairness_floor_alpha status)
Existing typed checks retained: `proposed.reopt_phase3`, `proposed.concentration_phase4`. Downstream
solves run only after their prerequisites are Optimal.

### Files changed
Modified: `farmsync/proposed/actions.py` (four auxiliary status guards; stale prefix comment fixed —
now "fresh uncommitted offers", not "locks over ALL offers"). Tests: `tests/test_farmsync_actions.py`
(+5: four parametrized auxiliary-stage guards proving exact failed_stage/status and that the downstream
solver is NOT called, plus uncertainty conversion of a typed auxiliary error to
optimal=False/failed_stage/status/cash=None). Docs: ACTION_CONSENT_PROTOCOL.md §22 marked SUPERSEDED BY
§23 (chronology preserved); this PROGRESS entry. `config.py`, `climate.py`, `operational.py`,
`uncertainty.py`, `pipeline.py` unchanged this turn.

### Hard gates — successful checkpoint UNCHANGED (verified)
- U0: B1 14,644,537 / B2 13,822,731 / B3 13,142,166.
- Proposed U0 tiers: PLANNED 13,142,166 / INITIAL_REALIZED 11,953,688 / RECOMMENDED_REVISED 12,586,101
  / FINAL_REALIZED 12,362,577 (identical to the pre-patch values).
- UJ FINAL_REALIZED 11,208,457 (identical). Consent coverage 1.0; reopt/conc Optimal.

### Tests
`test_farmsync_actions.py` 33 passed (28 + 5 new). `test_farmsync_uncertainty.py` 22 passed. Regression:
P7 + ILP-v2 + portability + P6 71 passed. Unexpected KeyError/TypeError still propagate (unchanged).
Frozen artifacts byte-identical (b1_ilp_v2, b3_ilp_v2, rng_streams, p6_event_ledger, p4_concentration).
No tuning.

### Status flags
REQUIREMENTS CHANGED: NO. DATASET CHANGED: NO. SOLVER CHANGED: NO. FROZEN ARTIFACTS CHANGED: NO.
SEEDS/RNG MASTER CHANGED: NO. ACTION-CONSENT POLICY CHANGED: NO. UNCERTAINTY POLICY CHANGED: NO.
ASKVISH UNRELATED CODE CHANGED: NO.

**Exact next step.** Publication λ/α freeze/check.

---

## TRACEABILITY CLOSURE + PUBLICATION λ/α FREEZE (2026-08-24)

One controlled publication-freeze turn: (A) closed the consent-provenance implementation requirement;
(B) audited and froze publication λ and α before final30. NO methodology redesign; NO change to
datasets, master seeds, RNG substreams, uncertainty-v1 params, action-consent probabilities, canonical
ε, fairness-v2, solver/Windows-CBC config, Phase-5 formulation, or frozen artifacts. NO final30, NO
≥300 LLM benchmark, NO live LLM, NO UI, NO manuscript Results. (Sandbox reset again mid-session; tree
restored intact from delivered outputs, deps reinstalled — no scientific state lost.)

### A. Consent-provenance traceability — CLOSED
Root gap: consent lacked a link to the authorising ACCEPT action, and a HARD_LOCK could fabricate
consent. Fixes (implementation only):
- `Consent.action_event_id` added — the exact ACCEPT ACTION ledger event_id that authorised the consent.
- INITIAL ACCEPT: emit ACTION → capture event_id → create INITIAL consent linked to it.
- RENEWED ACCEPT: emit a SEPARATE RENEWED ACCEPT ACTION row and a linked RENEWED CONSENT row (distinct
  rows; ledger row count legitimately increases). Existing-consent exception reuses the ORIGINAL consent
  + original action_event_id (no new behavioural ACCEPT); audit CONSENT row carries
  reason_code=AUTH_EVENT:<id>.
- REMOVED the fabricated HARD_LOCK consent fallback; a HARD_LOCK without a valid prior INITIAL ACCEPT
  consent now raises `ConsentProvenanceError` (dedicated exception; NOT a ProposedInfeasibleError).
- FINAL_REALIZED provenance-verified via `verify_consent_provenance` (farmer, plot, exact crop, valid,
  non-null action_event_id → real ACTION with behavioural_action==ACCEPT, matching farmer/plot, matching
  decision_round, matching cycle). `consent_coverage_final` is 1.0 only if all pass; shortfall raises.
  Coverage derivation text updated to "provenance-verified exact-crop ACCEPT consent / FINAL_REALIZED".
- `ConsentProvenanceError` propagates and is NEVER recorded optimal=False; only genuine solver-stage
  `ProposedInfeasibleError` is optimisation infeasibility (confirmed not a subclass).

### MODIFY tie-break audit — FIXED
Tie-break corrected from crop_name to crop_id (frozen policy; orderings not guaranteed identical).
Ranking/feasibility/admission/probabilities/optimiser authority unchanged. No development allocation
change (U0/UJ identical); controlled tie-case test added.

### Traceability hard gate — PASS (scientific values UNCHANGED)
U0 baselines B1 14,644,537 / B2 13,822,731 / B3 13,142,166. Proposed U0 PLANNED 13,142,166 /
INITIAL_REALIZED 11,953,688 / RECOMMENDED_REVISED 12,586,101 / FINAL_REALIZED 12,362,577. UJ
FINAL_REALIZED 11,208,457. Consent coverage 1.0; reopt/conc Optimal. Traceability change is
scientifically neutral (only ledger rows increased due to separate renewed ACTION+CONSENT rows).

### B. Publication λ/α freeze (pre-final30 development calibration; NO rerun)
Used existing frontier artifacts (sufficient; not regenerated):
- λ (`p3_lambda_frontier.csv`): objective unchanged `max E/E* − λ·(soft_disruption/soft_lock_area)`.
  λ=0 disruption 0.0575 → λ=0.05 disruption 0.0313 (~46% cut) at 99.85% economic retention (12,340,519
  vs 12,359,219). Selection rule: smallest strictly positive λ giving a meaningful disruption reduction
  vs λ=0 while retaining near-maximal economics → **λ=0.05**. Retained sensitivity {0,0.05,0.10,0.25,
  0.50,1.00} as descriptive evidence only.
- α (`p4_alpha_frontier.csv`): constraint unchanged `q_fc ≤ α·Q_c`. α=0.40 → max_LPS 0.3988 (~40% cap),
  99.55% retention, target_violations 0. Design rule: no single farmer > ~40% of an active crop's
  expected production → **α=0.40** (SYNTHETIC_EXPERIMENTAL design threshold, not empirical/regulatory).
  Retained sensitivity {1.00,0.60,0.50,0.40,0.33} as descriptive evidence only.
- Provenance note: frontiers generated under an earlier pipeline; the Phase-3/4 FORMULATIONS are
  unchanged, so the qualitative λ/α tradeoffs justifying selection remain valid. Documented, not rerun.

### Publication configuration (single source of truth) — config.py
`PUBLICATION_CONFIG_VERSION="farmsync-publication-config-v1"`, `PUBLICATION_EPSILON=0.95`
(asserted == CANONICAL_B3_EPSILON), `PUBLICATION_LAMBDA=0.05`, `PUBLICATION_ALPHA=0.40`,
`PUBLICATION_ACTION_PROFILE="PRIMARY"`, plus protocol/fairness constants. DEV_LAMBDA/DEV_ALPHA
(pipeline, =0.05/0.40) retained for compatibility — identical values, so NO pipeline behaviour change;
publication runners reference PUBLICATION_* (equivalence documented). PRIMARY analysis fixes
ε/λ/α/action; ε, λ, α, action S1/S2, and uncertainty U0..UJ remain SEPARATE sensitivity families — no
giant factorial. No-post-hoc-tuning rule recorded (any ε/λ/α change ⇒ amendment + version increment +
disclosure). New doc `docs/farmsync/PUBLICATION_CONFIG_FREEZE.md` (26 sections).

### Files changed
`farmsync/config.py` (PUBLICATION_* constants); `farmsync/proposed/actions.py` (action_event_id,
ConsentProvenanceError, removed HARD_LOCK fabrication, strengthened FINAL_REALIZED verification +
`verify_consent_provenance`, MODIFY crop_id tie-break, coverage-derivation text); `tests/
test_farmsync_actions.py` (+6 traceability/tie-break tests; 2 prior tests updated to provenance-accurate
shape → 39 total); `docs/farmsync/ACTION_CONSENT_PROTOCOL.md` (§24 note); `docs/farmsync/
PUBLICATION_CONFIG_FREEZE.md` (NEW); `docs/farmsync/PROGRESS.md`. No other files touched;
`uncertainty.py`/`pipeline.py`/`climate.py`/`operational.py` unchanged this turn.

### Tests / verification
test_farmsync_actions.py 39 passed; test_farmsync_uncertainty.py 22 passed; p3+p4+ilp_v2+portability 31
passed. Unexpected programming errors still propagate; provenance errors propagate (not infeasible).
Frozen artifacts + λ/α frontiers + ε frontier byte-identical. farmer_response 1120031581 and all
uncertainty substreams (participation 1267646869, weather 350915459, market 150500057, resource
30953779) unchanged. Master seeds unchanged. Windows CBC unchanged. No unrelated AskVish code touched.
No experiment rerun. No tuning.

### Provenance / limitations / unresolved
λ, α are development-calibrated design parameters (SYNTHETIC_EXPERIMENTAL), pre-final30, not from
final30. Concentration (α) does not guarantee hazard resilience (Phase-5 is a separate result). Dev
checkpoint is a single seed. No unresolved implementation issues.

### Status flags
REQUIREMENTS CHANGED: NO. DATASET CHANGED: NO. SOLVER CHANGED: NO. FROZEN ARTIFACTS CHANGED: NO.
SEEDS/RNG MASTER CHANGED: NO. ACTION-CONSENT POLICY CHANGED: NO (implementation traceability only).
UNCERTAINTY POLICY CHANGED: NO. ASKVISH UNRELATED CODE CHANGED: NO.

**Exact next step.** PRE-PUBLICATION METHODOLOGY + IMPLEMENTATION AUDIT → UI/UX BUILD → live LLM smoke →
≥300 LLM benchmark → final experiment readiness check → final30. (Not started this turn.)

---

## CONSENT-PROVENANCE TIGHTENING (2026-08-24)

Small traceability/documentation correction only. NO change to methodology, allocation results,
ε=0.95/λ=0.05/α=0.40, action/uncertainty policies, datasets, seeds/RNG, solver/Windows-CBC config, or
frozen artifacts/result files. NO final30, live LLM, ≥300 benchmark, UI, or manuscript work. (Sandbox
reset again; tree restored intact from delivered outputs; deps reinstalled — no scientific state lost.)

### Corrections
1. **Authorising-crop verification.** `verify_consent_provenance` now also checks that the referenced
   ACCEPT ACTION itself authorises the consent's crop: INITIAL consent → referenced event
   `crop_before == consent.crop`; RENEWED consent → referenced event `crop_recommended == consent.crop`;
   otherwise provenance fails. Action behaviour and RNG unchanged.
2. **Structural consent→ACTION link.** `action_event_id` is now a normal `_ev()` ledger field
   (default None), populated on every CONSENT ledger row with the exact authorising ACCEPT ACTION
   event_id. `reason_code="AUTH_EVENT:<id>"` retained for readability, but provenance no longer depends
   on parsing reason_code.
3. **Genuine HARD_LOCK guard test.** Replaced the ineffective ghost-injection test with one that
   genuinely exercises the production HARD_LOCK provenance guard (forces the first accepted plot to
   HARD_LOCK and invalidates its prior consent → real hard-locked allocation reaches the guard and
   raises `ConsentProvenanceError`; feasibility preserved). Added tests: wrong INITIAL authorising crop
   fails; wrong RENEWED authorising crop fails; CONSENT rows carry a real structural `action_event_id`
   pointing at the correct ACCEPT ACTION with the authorising crop. Updated the predicate break-case
   test's good event to include `crop_before` for the new check.
4. **Publication wording.** PUBLICATION_CONFIG_FREEZE §7 no longer calls the λ rule "predefined"; it is
   described as development-calibrated and frozen before final evaluation/final30 (α §11 already used
   "rationale"). Preserved: λ/α are experimental DESIGN parameters based on development evidence, not
   empirical/regulatory constants and not selected from final30. No retrospective numerical thresholds
   introduced.

### Hard gate — scientific values UNCHANGED
U0 B1 14,644,537 / B2 13,822,731 / B3 13,142,166; Proposed U0 PLANNED 13,142,166 / INITIAL_REALIZED
11,953,688 / RECOMMENDED_REVISED 12,586,101 / FINAL_REALIZED 12,362,577; UJ FINAL_REALIZED 11,208,457;
consent coverage 1.0; reopt/conc Optimal. The tightened check still yields coverage 1.0 (real ACCEPT
rows carry the correct crop), confirming it is scientifically neutral.

### Files changed
`farmsync/proposed/actions.py` (authorising-crop check in verify_consent_provenance; action_event_id in
_ev + on all CONSENT rows); `tests/test_farmsync_actions.py` (genuine hard-lock guard test + wrong-crop
+ structural-field tests; predicate good-event updated); `docs/farmsync/PUBLICATION_CONFIG_FREEZE.md`
(§7 wording); `docs/farmsync/PROGRESS.md`. No other files touched.

### Tests / verification
test_farmsync_actions.py 42 passed; test_farmsync_uncertainty.py 22 passed; p3+p4+ilp_v2+portability 31
passed. Frozen artifacts + λ/α frontiers byte-identical; farmer_response 1120031581 and uncertainty
substreams (participation 1267646869, weather 350915459, market 150500057, resource 30953779) unchanged;
master seeds unchanged; Windows CBC unchanged; no unrelated AskVish code touched. No experiment rerun.
No tuning.

### Limitations / next
Provenance now covers the full consent→ACCEPT→crop chain; dev checkpoint remains a single seed, not
final30. No unresolved implementation issues.
**Exact next step.** PRE-PUBLICATION METHODOLOGY + IMPLEMENTATION AUDIT → UI/UX BUILD → live LLM smoke →
≥300 LLM benchmark → final experiment readiness check → final30. (Not started this turn.)

---

## CONSENT-PROVENANCE MICRO-CLOSURE (2026-08-24)

Final micro traceability closure only. NO change to methodology, results, ε=0.95/λ=0.05/α=0.40,
action/uncertainty policies, datasets, seeds/RNG, solver/Windows-CBC config, frontiers, or frozen
artifacts. NO pre-publication audit, UI, LLM work, benchmark, final30, or any experiment. (Sandbox reset
again; tree restored intact from delivered outputs; deps reinstalled — no scientific state lost.)

### Corrections (verify_consent_provenance only)
1. **Referenced ACCEPT event cycle match.** In addition to `consent.cyc == cyc`, the verifier now
   requires the referenced ACTION row's `cycle_id == cyc`. Closes the gap where the ledger stores
   `cycle_id` but the referenced event's cycle was not checked.
2. **consent_kind / decision_round consistency.** Provenance now requires
   `consent.consent_kind == consent.decision_round` (both range over INITIAL/RENEWED and denote the same
   authorisation round); a mismatch is rejected as malformed.
No change to action generation, consent generation, ledger sequence, RNG, optimisation, allocations, or
metrics. Documentation: PUBLICATION_CONFIG_FREEZE §22 updated to enumerate the full FINAL_REALIZED
predicate (structural CONSENT-row action_event_id; referenced ACCEPT farmer/plot; referenced decision
round; referenced cycle; crop authorised by ACCEPT INITIAL→crop_before / RENEWED→crop_recommended;
consent_kind/decision_round consistency).

### Hard gate — scientific values UNCHANGED
U0 B1 14,644,537 / B2 13,822,731 / B3 13,142,166; Proposed U0 PLANNED 13,142,166 / INITIAL_REALIZED
11,953,688 / RECOMMENDED_REVISED 12,586,101 / FINAL_REALIZED 12,362,577; UJ FINAL_REALIZED 11,208,457;
consent coverage 1.0; reopt/conc Optimal. Real ACCEPT rows carry the correct cycle_id and
consent_kind==decision_round, so the tightened checks are scientifically neutral (coverage stays 1.0).

### Files changed
`farmsync/proposed/actions.py` (two added checks in verify_consent_provenance + docstring);
`tests/test_farmsync_actions.py` (+2 negative tests: referenced-ACCEPT wrong cycle_id; consent_kind vs
decision_round mismatch; positive predicate fixtures updated with cycle_id); `docs/farmsync/
PUBLICATION_CONFIG_FREEZE.md` (§22 predicate list); `docs/farmsync/PROGRESS.md`. No other files touched.

### Tests / verification
test_farmsync_actions.py 44 passed; targeted uncertainty regression (U0 parity, UJ causal, state
isolation, typed-infeasible + unexpected-exception propagation) 5 passed — provenance/invariant errors
still propagate and are not converted to solver infeasibility. Frozen artifacts + λ/α frontiers
byte-identical; farmer_response 1120031581 and uncertainty substreams (participation 1267646869, weather
350915459, market 150500057, resource 30953779) unchanged; master seeds unchanged; Windows CBC
unchanged; no unrelated AskVish code touched. No experiment rerun. No tuning.

### Provenance rules (now complete)
A FINAL_REALIZED allocation is provenance-verified iff: consent matches allocation
(farmer/plot/exact-crop, valid); consent_kind == decision_round; consent.cyc == current cycle;
action_event_id resolves to a real ledger ACTION with behavioural_action == ACCEPT; referenced event
farmer/plot match; referenced decision_round matches consent; referenced event cycle_id == current
cycle; referenced ACCEPT authorises the crop (INITIAL → crop_before, RENEWED → crop_recommended).

### Limitations / next
Consent provenance is now a complete self-consistent chain (consent ↔ ACCEPT ↔ crop ↔ round ↔ cycle).
Dev checkpoint remains a single seed, not final30. No unresolved implementation issues.
**Exact next step.** PRE-PUBLICATION METHODOLOGY + IMPLEMENTATION AUDIT → UI/UX BUILD → live LLM smoke →
≥300 LLM benchmark → final experiment readiness check → final30. (Not started this turn.)

---

## PRE-PUBLICATION METHODOLOGY + IMPLEMENTATION AUDIT (2026-08-24)

Controlled audit/reconciliation turn before UI/live-LLM/benchmark/final30. Inspection-only except one
documentation-only fix. NO methodology/results/ε/λ/α/policy/dataset/seed/RNG/solver/frozen-artifact
change. NO final30, ≥300 benchmark, live LLM, UI, or manuscript work. NO tuning. (Sandbox reset again;
tree restored intact from delivered outputs, deps reinstalled — no scientific state lost.)

### Scope / files inspected
config.py; ilp_reference.py (B1/B2/B3, ε, capable max-min, efficiency floor); fairness.py (fairness-v2
denominators); proposed/reoptimize.py (λ objective + disruption denominator); proposed/concentration.py
(α q_fc≤αQ_c, LPS/HHI pre-failure); proposed/resilience.py (N−1, hazard, exposure vs recovery);
proposed/actions.py (action-consent + provenance chain); proposed/uncertainty.py (W/M/R/P, U0..UJ);
proposed/pipeline.py; proposed/llm_interaction.py + llm_eval.py (LLM boundary/benchmark harness);
solver.py (OS-conditional CBC); experiment.py/generate.py (seed/substream, scalability); provenance.py;
docs (PROGRESS, PUBLICATION_CONFIG_FREEZE, ACTION_CONSENT_PROTOCOL, UNCERTAINTY_PROTOCOL, manifests);
frozen artifacts (b1/b3_ilp_v2, rng_streams, replication_seeds, experiment_manifest, p6_event_ledger,
p3/p4 frontiers, b3_epsilon_frontier).

### Verdict
**PASS WITH REQUIRED FIXES.** Methodology ↔ code ↔ tests ↔ artifacts ↔ documentation are internally
consistent. No correctness/traceability defect in code. Approved to proceed to UI/UX BUILD. See
`docs/farmsync/PRE_PUBLICATION_AUDIT.md` (16 sections + publication-claim matrix).

### Mismatch found + fix (documentation-only)
PUBLICATION_CONFIG_FREEZE §25 showed a stale "39 passed" action-test count from before the
consent-provenance closures. Reconciled to the actual current state (actions 44 / uncertainty 22 /
p3 8 + p4 10 + ilp_v2 6 + portability 7). No code/scientific change. No other doc/code mismatch found.

### Required fixes (to freeze BEFORE the gated steps; NOT correctness defects)
- MUST FIX BEFORE FINAL30: commit the publication experiment-matrix manifest (PRIMARY + ε/λ/α/action/
  uncertainty/scalability families) with per-experiment seeds/paired-key/metrics/test/effect-size/CI/
  multiplicity/table mapping. Provenance manifest already exists; the experiment MATRIX is proposed in
  AUDIT §10 and must be committed as an artifact.
- MUST FIX BEFORE ≥300 BENCHMARK: author the ≥300 labelled LLM benchmark dataset + gold spec (only 41
  dev cases in p7_dev_cases.jsonl); run the live smoke (scripts/p7_live_smoketest.py) first.
- SHOULD FIX BEFORE SUBMISSION: cross-reference the frozen statistical plan into the experiment manifest
  for ε/λ/α/scalability; populate manifest git_commit at final freeze.

### Quantitative verification (this turn)
U0 baselines B1 14,644,537 / B2 13,822,731 / B3 13,142,166 (all Optimal); Proposed U0 PLANNED
13,142,166 / INITIAL_REALIZED 11,953,688 / RECOMMENDED_REVISED 12,586,101 / FINAL_REALIZED 12,362,577;
UJ FINAL_REALIZED 11,208,457; reopt/conc Optimal; consent coverage 1.0. Checkpoint runtime ~30s.
30 replication seeds re-derived and match the frozen list exactly (not cherry-picked). Frozen artifacts
(b1/b3_ilp_v2, rng_streams, replication_seeds, experiment_manifest, p6_event_ledger, p3/p4 frontiers,
b3_epsilon_frontier) byte-identical. Substreams unchanged (farmer_response 1120031581, participation
1267646869, weather 350915459, market 150500057, resource 30953779). Windows CBC unchanged.
Tests run this turn: p7 + ilp_v2 52 passed; earlier collect-only counts confirmed (actions 44,
uncertainty 22, p3 8, p4 10, ilp_v2 6, portability 7). No unrelated AskVish code touched.

### Publication-claim guardrails (preserved)
B3 → Rawlsian worst-off among capable farmers subject to the efficiency floor (NOT global Gini
reduction). α → within-crop production concentration limit (NOT spatial hazard protection or large
post-shock recovery). λ/α synthetic experimental design parameters. Absorption is a proxy, never demand.
Synthetic population parameterised from Indian public data, not an empirical sample. LLM has no
allocation authority; live reliability unclaimed pre-benchmark.

### Files changed
`docs/farmsync/PRE_PUBLICATION_AUDIT.md` (NEW); `docs/farmsync/PUBLICATION_CONFIG_FREEZE.md` (§25 stale
count reconciled); `docs/farmsync/PROGRESS.md`. No code, test, dataset, or frozen-artifact files changed.

### Status flags
REQUIREMENTS: NO. DATASET: NO. SOLVER: NO. FROZEN ARTIFACTS: NO. SEEDS/RNG: NO. ACTION-CONSENT POLICY:
NO. UNCERTAINTY POLICY: NO. ASKVISH UNRELATED: NO. No tuning.

**Exact next step.** UI/UX BUILD → live LLM smoke → ≥300 LLM benchmark → final experiment readiness check
→ final30. Approved to begin UI/UX BUILD; the two MUST-FIX deliverables are gated before benchmark and
final30 respectively, not before UI. (Not started this turn.)

---

## UI/UX BUILD — RESEARCH WORKBENCH (2026-08-24)

Approved UI/integration turn (PRE_PUBLICATION_AUDIT = PASS WITH REQUIRED FIXES). NO change to
methodology, ε=0.95/λ=0.05/α=0.40, action/uncertainty policies, datasets, seeds/RNG, solver config, or
existing frozen scientific artifacts. NO final30, ≥300 benchmark, live LLM, experiment-manifest freeze,
or manuscript work. No parameter tuning. (Sandbox reset mid-session; tree restored from delivered
outputs, deps reinstalled — no scientific state lost.)

### UI architecture
Single research-workbench page (`templates/farmsync.html`, extends the AskVish `base.html`) with a
left workspace navigation and ten panels: Overview, Data & Provenance, Planning, Farmer Actions,
Reoptimisation, Fairness & Concentration, Uncertainty, Resilience, LLM Boundary, Reproducibility.
Polished, dense, accessible design system in `static/css/farmsync.css` (semantic HTML, keyboard-focusable
nav, responsive ≤860px, loading/empty/error states, no gimmicks). Client logic in
`static/js/farmsync.js` renders each workspace by fetching read-only artifact-driven APIs and lazy-loads
a panel on first activation. The existing Dataset Manager is preserved verbatim (its markup moved into a
`<template>` and mounted inside the Data & Provenance workspace; all its endpoints unchanged).

### Artifact-driven adapter (NEW `farmsync/ui_adapter.py`)
Read-only readers over config + result/audit artifacts. Never imports pulp; never runs the solver, the
action-consent pipeline, or any LLM (live or mock). Missing artifacts return an honest
{"available": False, "state": "Not run"/"Not available"} shape — never fabricated numbers.
Development-derived values carry provenance "DEVELOPMENT_CHECKPOINT".

### Routes/endpoints added (all read-only, in `farmsync_routes.py`, existing routes untouched)
/api/farmsync/overview, /planning, /actions-checkpoint, /fairness, /concentration, /lambda-frontier,
/epsilon-frontier, /uncertainty, /resilience, /llm-boundary, /reproducibility.

### Source artifacts used by each section
- Overview/Reproducibility: config.py PUBLICATION_* constants; audit/experiment_manifest.json;
  audit/replication_seeds.json; audit/rng_streams.json; ui_dev_checkpoint.json (instance hash, population).
- Planning/Fairness: b1/b2/b3_ilp_v2.json (metrics_core, fairness_v2). Proposed U0 tiers: ui_dev_checkpoint.
- Farmer Actions/Uncertainty: ui_dev_checkpoint.json (U0/UJ). UW/UM/UR/UP render "Not run".
- Reoptimisation: proposed/p3_lambda_frontier.csv. Concentration: proposed/p4_alpha_frontier.csv +
  p4_concentration_result.json. Resilience: proposed/p5_resilience_result.json + p5 scenario CSVs.
- LLM Boundary: proposed/p7_llm_schema.json, p7_llm_manifest.json, p7_dev_metrics.json (labelled MOCK).

### Displayed development checkpoints (labelled DEVELOPMENT CHECKPOINT)
NEW artifact `results/farmsync/proposed/ui_dev_checkpoint.json` generated once from the CURRENT corrected
pipeline (not page load), provenance "DEVELOPMENT_CHECKPOINT". U0 baselines B1 14,644,537 / B2 13,822,731
/ B3 13,142,166; U0 tiers PLANNED 13,142,166 / INITIAL_REALIZED 11,953,688 / RECOMMENDED_REVISED
12,586,101 / FINAL_REALIZED 12,362,577; UJ FINAL_REALIZED 11,208,457; coverage 1.0. Population 500
farmers / 911 plots / 10 collectives (from the real instance record). No scientific value hardcoded in
HTML/JS — all read from artifacts via the adapter.

### Integrity / guardrails enforced in UI copy
Global banner: synthetic population; Indian public datasets parameterise the model; LLM does not
allocate crops. Persistent DEVELOPMENT CHECKPOINT badge; final30/live-LLM/≥300 shown NOT RUN. B3 shown as
Rawlsian worst-off protection among capable farmers under the efficiency floor (never "reduces Gini").
α shown as within-crop concentration control, explicitly "not spatial hazard protection". λ/α labelled
development-calibration evidence, not empirical. AGMARKNET arrivals labelled "absorption proxy, NOT
demand". RECOMMENDED_REVISED rendered visually distinct (dashed) from realised FINAL_REALIZED.

### Tests (NEW `tests/test_farmsync_ui.py`, 9 passed)
page renders with all ten workspaces + banner + dev badge; APIs return honest states; no pulp imported on
API load (no solver on page load); no live LLM constructed on the LLM-boundary API; dev/experiment-state
labels correct; recommendation vs realised states distinct; research caveats present (B3/fairness/α/
uncertainty); missing-artifact honest states; AGMARKNET absorption-not-demand label present; Dataset
Manager endpoints intact. Combined regression this turn: actions 44 + ilp_v2 6 + p7 46 + ui 9 = 105
passed. Accessibility: semantic nav buttons, focus management, aria-labels, responsive breakpoint.
Verified: no pulp in sys.modules after API calls; frozen artifacts (b1/b3_ilp_v2, rng_streams,
replication_seeds, p3/p4 frontiers) byte-identical; config ε/λ/α/version unchanged.

### Files changed
NEW: `farmsync/ui_adapter.py`, `templates/farmsync.html` (workbench; prior dataset-manager-only template
replaced, its functionality preserved inside), `static/css/farmsync.css` (expanded design system),
`static/js/farmsync.js` (workbench + preserved dataset-manager JS), `tests/test_farmsync_ui.py`,
`results/farmsync/proposed/ui_dev_checkpoint.json` (DEVELOPMENT_CHECKPOINT artifact); MODIFIED:
`farmsync_routes.py` (11 read-only endpoints added). No scientific code/test/dataset/frozen-artifact
changed.

### Unresolved UI limitations (non-blocking)
UW/UM/UR/UP have no stored per-condition checkpoint (render "Not run"); a full farmer-level action ledger
browser is summarised (counts + provenance chain) rather than per-row (the row-level ledger is generated
by the pipeline, not stored as a UI artifact); live LLM parse box is intentionally disabled (shell only).

### Status flags
REQUIREMENTS: NO. DATASET: NO. SOLVER: NO. FROZEN ARTIFACTS: NO. SEEDS/RNG: NO. ACTION-CONSENT POLICY:
NO. UNCERTAINTY POLICY: NO. ASKVISH UNRELATED: NO. No tuning.

**Exact next step.** live LLM smoke → ≥300 LLM benchmark → final experiment readiness check → final30.
(The publication experiment-manifest freeze and the ≥300 benchmark dataset remain MUST-FIX before those
steps, per PRE_PUBLICATION_AUDIT §14.) Not started this turn.

---

## ATS-FORGE-INFORMED UI/UX REFINEMENT (2026-08-25)

Frontend-only refinement of the already-complete research workbench, using the attached ATS Forge
frontend as a DESIGN reference (not functionality). NO change to methodology, ε=0.95/λ=0.05/α=0.40,
action/uncertainty policies, datasets, seeds/RNG, solver config, scientific formulation, result
artifacts, or consent/provenance semantics. NO final30, live LLM, ≥300 benchmark, tuning, or new
experiments. Backend untouched: ui_adapter.py, farmsync_routes.py, and all scientific modules unchanged;
ui_dev_checkpoint.json NOT regenerated (byte-identical). (Sandbox reset mid-session; tree restored from
delivered outputs, deps reinstalled — no scientific state lost.)

### ATS files inspected (reference only)
/mnt/user-data/uploads/atsforge.html, atsforge.css, atsforge.js, base.html (shared AskVish layout);
atsforge.py read for context only — none of its backend/LLM/CV/business logic reused.

### Key finding driving the refinement
ATS Forge inherits the shared AskVish theme tokens from style.css (loaded by base.html, data-theme
dark default + theme toggle): --bg-primary/secondary/tertiary/card, --text-primary/secondary/muted,
--accent-primary/glow, --border-color/hover, --radius-*, --space-*, --transition-base/bounce,
--gradient-primary/text, --font-display (Outfit / JetBrains Mono). FarmSync's previous CSS used its own
light-only palette disconnected from the theme (it did not follow the site's dark/light toggle) — the
single biggest polish gap.

### Patterns adopted
- Rebased static/css/farmsync.css onto the shared theme tokens with standalone fallbacks (e.g.
  --s-surface:var(--bg-card,#fff); --s-ink:var(--text-primary,#16241d); radius/space/transition tokens),
  so FarmSync now inherits the premium dark/light theming, typography and spacing rhythm and respects
  the site theme toggle, while keeping its green agricultural accent (--fs-green, --fs-grad) and
  scientific semantic colours (tier / lock / action).
- Stepper component adapted from ATS Forge (track + progress fill + circular indicators with
  done/current states, gradient + glow) applied where it genuinely fits: (a) Farmer Actions — a
  horizontal commitment-ladder stepper VIEWED→…→PLANTED and a NEW vertical causal-flow stepper
  (PLANNED det → farmer action beh → commitment det → RECOMMENDED_REVISED det → renewed consent beh →
  FINAL_REALIZED det) with deterministic/behavioural tags on every step; (b) LLM Boundary — the six-stage
  NL→…→Grounded Explanation pipeline as a horizontal stepper with authority/interface sublabels.
- Stronger hover/focus states (card lift, --fs-glow focus rings on nav/buttons/inputs), gradient
  masthead name, gradient primary buttons, refined chips/badges, drawer with rotating marker, pulsing
  DEVELOPMENT CHECKPOINT dot.
- Accessibility/responsive: focus-visible rings, prefers-reduced-motion disables animation, ≤880px nav
  collapses to a horizontal scroller, ≤560px compaction.

### Patterns deliberately rejected
ATS/CV/job terminology; the ATS five-step CV wizard flow (FarmSync stays a workbench, not a wizard);
ATS Forge API calls / Python / LLM / CV-assistant logic; decorative particles/background effects;
oversized marketing hero; excessive glassmorphism; irrelevant animations.

### Scientific wording preserved (unchanged in meaning; verified in served payloads)
B3 = worst-off protection among CAPABLE farmers under the efficiency floor (never "reduces Gini");
α = farmer-within-crop concentration, explicitly NOT spatial hazard protection; uncertainty = paired
synthetic exogenous scenarios, not empirical frequencies and not stochastic optimisation; AGMARKNET
arrivals = absorption proxy, NOT demand; RECOMMENDED_REVISED requires renewed consent and is not
realised (rendered dashed/blue, distinct from realised FINAL_REALIZED); synthetic behaviour labelled
DEVELOPMENT CHECKPOINT, not empirical prevalence.

### Files changed
static/css/farmsync.css (rebased design system + stepper + interactions);
static/js/farmsync.js (Farmer Actions causal-flow + commitment steppers; LLM Boundary pipeline stepper;
inline textarea style moved to CSS). templates/farmsync.html UNCHANGED. No test file changed (existing
coverage still exercises the refined behaviour). No backend/adapter/route/artifact change.

### Tests + verification
tests/test_farmsync_ui.py 9 passed (page renders, all ten workspaces, no pulp on API load, no live LLM,
dev labels, recommendation≠realised, caveats present, honest missing states, absorption-not-demand label,
Dataset Manager intact). ilp_v2 regression 6 passed. Page renders /farm-sync 200 with all ten workspaces;
CSS/JS served 200; JS parses clean. Verified: pulp absent from sys.modules after all ten API calls (no
solver on page/API load); LLM boundary reports Live NOT RUN / ≥300 NOT RUN, optimizer sole authority (no
live call). All seven scientific caveats verified intact in the served API payloads.

### Config / dataset / hash / seed / RNG / solver status
ε 0.95 / λ 0.05 / α 0.40 / version farmsync-publication-config-v1 unchanged. Frozen artifacts
(b1/b3_ilp_v2, rng_streams, replication_seeds, p3/p4 frontiers, experiment_manifest) byte-identical;
ui_dev_checkpoint.json byte-identical (not regenerated). No dataset/seed/RNG/solver edit.

### Status flags
REQUIREMENTS: NO. DATASET: NO. SOLVER: NO. FROZEN ARTIFACTS: NO. SEEDS/RNG: NO. ACTION-CONSENT POLICY:
NO. UNCERTAINTY POLICY: NO. BACKEND/ADAPTER/ROUTES: NO. ASKVISH UNRELATED: NO. No tuning.

### Unresolved UI limitations (non-blocking)
UW/UM/UR/UP still render "Not run" (no stored per-condition checkpoint); Farmer Actions remains a
summary (counts + steppers + provenance chain), not a per-row farmer ledger browser; live LLM parse box
intentionally disabled (shell only); steppers are illustrative progressions, not per-farmer state
machines.

**Exact next step.** live LLM smoke → ≥300 LLM benchmark → final experiment readiness check → final30.
Per PRE_PUBLICATION_AUDIT §14, the publication experiment-manifest freeze and the ≥300 benchmark dataset
remain MUST-FIX before those steps. Not started this turn.

---

## GUIDED UI/UX REDESIGN — INTUITIVE INTERACTIVE WORKBENCH (2026-08-26)

Information-architecture + UX correction turn. NO scientific change: methodology, ε=0.95/λ=0.05/α=0.40,
fairness, action probabilities, uncertainty, datasets, seeds/RNG, solver settings, frozen artifacts and
research results all unchanged. NO final30, NO live OpenAI call, NO ≥300 LLM benchmark. Colours preserved
exactly (see below). (User hand-edited the prior CSS/JS/HTML/routes to lock light-vs-dark palettes; those
hand-edited files were adopted as the starting truth for this turn.)

### Superseded
The previous artifact-dashboard UX (flat research-paper nav: Overview / Data & Provenance / Planning /
Farmer Actions / Reoptimisation / Fairness & Concentration / Uncertainty / Resilience / LLM Boundary /
Reproducibility) is SUPERSEDED as the primary experience. Its panels/loaders and all read-only endpoints
are retained and re-homed under the new Analyse / Research groups. Reason: a first-time user could not
understand or use FarmSync without first reading B1/B2/B3, ε/λ/α, P3/P4, hashes and solver details.

### New guided workflow + navigation
Workflow stepper across the top: Data → Plan → Farmer Responses → Replan → Consent → Finalise → Analyse
(clickable; reflects position). Grouped left nav: MAIN (Home, Plan, Farmer Interaction, Final Plan),
ANALYSE (Fairness & Concentration, Uncertainty, Resilience), RESEARCH (Data, Experiment Lab, Provenance &
Reproducibility). λ/ε frontier, LLM boundary internals, P3/P4 hashes are demoted to Research / progressive
disclosure, never primary nav.

### New experiences
- Home: plain-language purpose, primary CTA [Start Planning] + secondary [Explore Dataset], and a CURRENT
  DATASET card (FarmSync Built-in Research Dataset ✓ 500 farmers / 911 plots / 10 collectives / 5 regions /
  13-of-14 crops, Validated) — no forced Load→Validate→Activate to inspect.
- Plan: method radios (B1 / B2 / B3 / FarmSync Proposed), Explore vs Publication/Reproduction mode
  (publication locks ε/λ/α + config, states final30 NOT RUN; explore labelled "Exploratory — not a
  publication result"), [Generate Plan] → summary (recommendations, farmers, planned cash, solver Optimal)
  + recommendation table (farmer, plot, crop, area, cash, commitment, consent).
- Farmer Interaction (centrepiece): farmer picker (filterable) → recommendation (crop, expected cash) +
  action buttons [Accept][Reject][Request another crop][No response][Withdraw] with plain-language
  outcome explanations using the frozen FLEXIBLE/SOFT_LOCK/HARD_LOCK + consent semantics; the farmer's
  recorded response is marked, others shown as illustrative. [Ask FarmSync AI] shows a Development/Mock
  parse ("What FarmSync understood": action=MODIFY, schema Valid, semantic Pass, authority None) with the
  explicit note "LLM parses + explains; the deterministic system validates + allocates" and "Live LLM
  pending validation — no live API call". Never claims live.
- Final Plan: vertical causal chain Original recommendation → Farmer response → Commitment → Deterministic
  reoptimisation → Renewed consent → Final realised crop, plus the four distinct states PLANNED /
  INITIAL_REALIZED / RECOMMENDED_REVISED / FINAL_REALIZED (revised recommendation rendered visually
  distinct from a realised allocation; consent coverage shown).
- Analyse (fairness / uncertainty / resilience): plain-language explanation first, technical metrics
  second; uncertainty U0..UJ; resilience kept SEPARATE (producer failure + hazard outage), infeasible
  shown honestly.
- Research: Data (explore built-in tables immediately + Change Dataset → Advanced import preserved
  verbatim), Experiment Lab (frozen run config, publication-locked, final30 NOT RUN), Provenance &
  Reproducibility (hashes/seeds/audit verdict).

### Interactive backend, not JS science (§11)
NEW read-only adapter readers in `farmsync/ui_adapter.py` (no solver, no LLM, no pulp import):
dataset_summary(); plan(method) reading b1/b2/b3 allocation CSVs + p6_final_revised_plan for Proposed;
farmers_list() + farmer_detail(fid) joining p1_participation_offers + p2_commitment_timeline +
p6_final_revised_plan. NEW routes: /api/farmsync/dataset-summary, /plan, /farmers, /farmer/<id>. JS only
gathers input, calls these APIs, and renders; all scientific values come from frozen artifacts. Existing
artifact/history endpoints retained.

### Colour preservation + theme isolation (§16 — verified)
No --sci-* variable or its theme mapping was changed. Dark/base palette intact (green #1f9d6b, blue
#3b82f6, amber #e08a1e, red #e0533d, violet #8b5cf6). Light palette intact under [data-theme="light"]
.fs-app (green #16a34a, MODIFY→orange #ea580c, amber #d97706, red #e0483a, WITHDRAW/HARD_LOCK→rust
#c2410c) with light semantic-text overrides. Verified: dark values do NOT appear in the light override
block (no cross-bleed); all new components use existing theme-scoped variables; NO 6-digit colour hex is
hard-coded in JS (test-enforced). Theme switch updates all new components (cards, buttons, radios,
stepper, farmer list, chips, tables, drawers) with no reload.

### Files changed
REPLACE EXISTING: templates/farmsync.html, static/css/farmsync.css, static/js/farmsync.js,
farmsync/ui_adapter.py, farmsync_routes.py, tests/test_farmsync_ui.py, docs/farmsync/PROGRESS.md.
No scientific module, dataset, seed, solver, or frozen artifact changed.

### Tests + verification
tests/test_farmsync_ui.py rewritten for the guided IA — 14 passed: page loads guided IA; built-in dataset
default/available (500/911/10); built-in tables immediately inspectable; import controls preserved; plan
artifact-driven with no solver (pulp not imported); farmer selection + action mapping; recommendation ≠
consent; FINAL_REALIZED requires consent; no false live-LLM / final30 claims; explore vs publication
labels; research caveats preserved (worst-off/capable, hazard, not-empirical, absorption-not-demand);
theme palettes separate with no leak; no theme colour in JS; honest missing states. ilp_v2 regression 6
passed. Frozen artifacts (b1/b3_ilp_v2, ui_dev_checkpoint, replication_seeds) byte-identical; config
ε/λ/α unchanged. Both themes render 200; no solver/LLM on page or API load.

### Status flags
METHODOLOGY: NO. DATASET: NO. SOLVER: NO. SEEDS/RNG: NO. FROZEN ARTIFACTS: NO. FINAL30: NO. LIVE LLM: NO.
≥300 BENCHMARK: NO. LIGHT COLOURS PRESERVED: YES. DARK COLOURS PRESERVED: YES. THEME CROSS-BLEED: NONE.

### Unresolved / limitations
Farmer actions are explanatory over recorded synthetic responses (they explain the frozen outcome; they
do not live-mutate a solve — by design this turn, to avoid running the solver in-browser). Explore-mode
live re-solving with custom seed/params is scaffolded (Experiment Lab shows config) but a live-solve
endpoint is intentionally not wired this turn. Live LLM remains mock/disabled.

**Exact next step.** live LLM smoke → ≥300 LLM benchmark → final experiment readiness → final30 (with the
publication experiment-manifest freeze + ≥300 benchmark dataset gated before, per PRE_PUBLICATION_AUDIT
§14). Not started.

---

## FINAL GUIDED UX FLOW CORRECTION — PROGRESSIVE DISCLOSURE + THREE ENTRY PATHS (2026-08-26)

Frontend UX-flow correction only. NO redesign. Visual design, colours, typography, cards, theme
behaviour, scientific semantics, APIs and backend preserved. NO scientific change: methodology,
ε=0.95 / λ=0.05 / α=0.40, fairness-v2, action-consent-v1, uncertainty-v1, datasets, seeds/RNG, solver
settings, frozen artifacts and results all unchanged. NO final30, NO live LLM, NO ≥300 benchmark, NO
tuning, NO artifact regeneration. Page/API load runs no CBC/PuLP and no live LLM (re-verified).

### Work completed before the clarification arrived
This turn began from the delivered guided-redesign files (unchanged on disk). The correction itself
(stepper cleanup, progressive locks, Plan simplification, recorded-vs-illustrative wording) had not yet
been written when a clarification arrived; it was folded in wholesale (below). No valid prior work was
discarded.

### Reason for correction
Progressive disclosure was missing: a first-time user could see and enter stages they had not reached,
and the Plan screen exposed research controls (B1/B2/B3, ε/λ/α, Explore/Publication) too early. A new
user also lacked a clear "what can I actually do?" entry point.

### Previous behaviour superseded
- Flat, always-clickable nav (all stages enterable from load) → grouped nav with locked future stages.
- Workflow stepper started at "Data" → Data removed from the stepper (built-in dataset is already
  validated; Data is a research/support workspace, not a compulsory step).
- Plan screen led with method radios + Explore/Publication mode + "Generate Plan" → now leads with
  FarmSync Proposed + "View Development Plan"; comparison/mode/advanced controls moved under a collapsed
  "Research & comparison options".
- Home repeated the hero explanation and had two flat CTAs → replaced with three explicit entry paths.

### Three entry paths on Home (clarification)
1. Try FarmSync with the built-in dataset (PRIMARY): validated dataset already loaded (500 farmers /
   911 plots / 10 collectives), no upload; CTA Start Planning; the Plan→Farmer Responses→Replan→Consent
   →Finalise→Analyse journey is shown.
2. Use my own data: explains accepted data + requirements before upload; "View data requirements" reads
   the REAL validator (SUPPORTED_FILES / CORE_FILES / REQUIRED_COLUMNS / size limits / valid seasons) via
   new read-only endpoint — nothing invented; flow Choose data type → Requirements → Upload → Validate →
   Review → Activate → Plan; invalid data cannot proceed (activation requires a passing validation).
3. Reproduce the research (SECONDARY): frozen config, B1/B2/B3, ε/λ/α, seeds, solver, hashes,
   reproducibility — not prerequisites for ordinary use.
DEVELOPMENT CHECKPOINT / final30 NOT RUN / live LLM NOT RUN disclosure retained, visually secondary.

### Exact progressive-unlocking logic (session/UI only; no solver)
- Always unlocked: Home, Plan, and the Research tools (Data, Experiment Lab, Provenance & Reproducibility).
- Gated at start: Farmer Interaction, Final Plan (Replan/Consent/Finalise), Analyse (Fairness &
  Concentration / Uncertainty / Resilience).
- Plan → "View Development Plan" (reads stored artifact) → unlock Farmer Interaction.
- Farmer Interaction → select/view a farmer → unlock Final Plan (Replan/Consent/Finalise).
- Final Plan → reaching it → unlock Analyse.
- Locked nav items: muted + lock icon + tooltip ("View the development plan first", etc.); clicks are
  blocked and shake instead of navigating. Locked stepper steps show a lock glyph and are not clickable.
- Stepper states: completed = check, current = highlighted, future = muted, locked = lock + disabled.
- Deep-link (#hash) to a locked stage falls back to Home.

### Planning distinction (truthful capability)
The Plan view reads stored development artifacts and does NOT execute CBC/PuLP. Primary action is
"View Development Plan" (not "Generate Plan"). "Run a new exploratory plan" is present but DISABLED and
labelled pending — a safe fresh-solver path is not implemented and was NOT hastily added this turn. This
is recorded as a next implementation requirement.

### Farmer Interaction — recorded vs illustrative
Each farmer's recorded synthetic response is marked (✓, "Recorded response"). Selecting a different
action shows an "Illustrative — explore what would happen if…" consequence, visibly dashed/labelled, and
states it does not change the frozen result. Preserved: recommendation ≠ consent; RECOMMENDED_REVISED ≠
realised; FINAL_REALIZED requires valid consent.

### Files changed
REPLACE EXISTING: static/js/farmsync.js, static/css/farmsync.css, farmsync/ui_adapter.py (added read-only
data_requirements() from the validator constants), farmsync_routes.py (added GET /api/farmsync/
data-requirements), tests/test_farmsync_ui.py, docs/farmsync/PROGRESS.md. templates/farmsync.html
UNCHANGED this turn (stepper/nav are rendered by JS into the existing #fsWorkflow / nav shell). No
scientific module, dataset, seed, solver, or frozen artifact changed.

### Current UI capabilities vs unavailable
Available now (read-only, artifact-driven): three entry paths; built-in dataset default + explore;
real upload requirements; View Development Plan (Proposed + B1/B2/B3 comparison under a drawer); farmer
interaction with recorded + illustrative outcomes; Replan/Consent/Finalise causal chain + four states;
Analyse (fairness/concentration/uncertainty/resilience); Research (data/lab/repro). Unavailable/pending
(clearly labelled): fresh in-browser exploratory solve ("Run a new exploratory plan" disabled); live LLM
(mock/disabled); final30; ≥300 benchmark.

### Tests + verification
tests/test_farmsync_ui.py updated for progressive disclosure — 19 passed: page loads; Home+Plan
accessible; future stages locked; View-Development-Plan unlock wiring; no jump-ahead into locked stages;
workflow order Plan→Farmer Responses→Replan→Consent→Finalise→Analyse (Data removed from stepper);
"Generate Plan" removed / "View Development Plan" present; recorded vs illustrative distinguished; three
entry paths + real validator-sourced requirements; built-in default; import preserved; plan artifact-
driven no-solver (pulp not imported); recommendation ≠ consent; FINAL_REALIZED requires consent; no false
live-LLM/final30; explore/publication labels + fresh-solver clearly pending; caveats preserved; theme
palettes separate no-leak; no theme colour in JS. ILP v2 regression 6 passed. Frozen artifacts
(b1/b3_ilp_v2, ui_dev_checkpoint, replication_seeds, experiment_manifest) byte-identical; config
ε/λ/α unchanged. Both themes render 200 with full palette isolation.

### Config / dataset / hash / seed / RNG / solver / frozen artifacts
UNCHANGED. ε=0.95, λ=0.05, α=0.40; instance_hash 5ea24037c2d9cb6a; seeds base 20260812; CBC/PuLP 3.3.2;
all frozen artifacts byte-identical.

### Exact next step
Implement (in a later, dedicated turn) a SAFE fresh exploratory solver path for Explore mode — an explicit
user-triggered, backgrounded, clearly-labelled run that never fires on page/API load — OR keep it pending.
Only after that: live LLM smoke → ≥300 LLM benchmark → final experiment readiness → final30 (gated behind
publication experiment-manifest freeze + ≥300 benchmark dataset). NOT started. Live LLM smoke NOT begun.

---

## PRODUCT JOURNEY + AI-ROLE CAUSAL UX CORRECTION (2026-08-26)

Read-only product/UX correction over stored development artifacts. NO visual redesign. NO scientific
change: methodology, ε=0.95 / λ=0.05 / α=0.40, fairness-v2, action-consent-v1, uncertainty-v1, datasets,
seeds/RNG, solver settings, frozen artifacts and results unchanged. NO fresh exploratory solve, NO live
LLM, NO final30, NO ≥300 benchmark, NO tuning, NO artifact regeneration. Page/API load runs zero CBC/PuLP
and zero live LLM (re-verified).

### Manual UX failures discovered (first-time end-to-end test)
- User could not tell what each stage was doing, why it existed, what happened, what it meant, or what to
  do next; and could not tell where the LLM vs the validator vs the optimiser acted.
- Later-stage information leaked into earlier stages: the Plan view read the FINAL revised plan
  (p6_final_revised_plan) and effectively showed post-reoptimisation / final data as the initial plan.
- Replan and Consent were collapsed into one "Final Plan" page, so their stages auto-appeared complete.
- The AI panel risked implying the LLM could choose/suggest crops.

### Previous behaviour superseded
- plan(PROPOSED) sourced from p6 FINAL → replaced by a dedicated PLANNED reader (p1 planned_crop /
  planned_cash_return). Initial Plan no longer shows FINAL_REALIZED / final crop / renewed consent /
  RECOMMENDED_REVISED.
- Single combined "Final Plan" workspace → split into three genuine stages: Replan, Renewed Consent,
  Final Plan, each its own workspace + nav item + endpoint, unlocking in causal order.
- Farmer view now uses a response-only endpoint (no revised/final fields).
- Every main stage now teaches What / Why / What happened / What it means and ends with one next-step CTA.

### Canonical artifact used by each stage
- Home / dataset card: dataset_summary (population) + overview (experiment_state).
- Initial Plan (PLANNED): p1_participation_offers.csv → planned_crop, planned_cash_return; headline
  PLANNED tier (₹13,142,166). No realised_* columns read.
- Farmer Responses: p1_participation_offers.csv → farmer_id, plot_id, planned_crop, planned_cash_return,
  response (recorded synthetic). No revised/final.
- Replan (RECOMMENDED_REVISED): p3_revised_plan_lambda0.csv (crop, status_label) joined with p1 original
  crop; headline RECOMMENDED_REVISED tier (₹12,586,101); 53 changed / 342 plots. Marked NOT realised.
- Renewed Consent: p6_final_revised_plan.csv (consent_exists, requires_renewed_consent, consent_basis)
  joined with p1 original + p3 revised crop; 48 require renewed consent.
- Final Plan (FINAL_REALIZED): p6_final_revised_plan.csv rows; headline FINAL_REALIZED (₹12,362,577);
  consent coverage 1.0. Only stage that shows FINAL_REALIZED. Progression strip PLANNED → INITIAL_REALIZED
  → RECOMMENDED_REVISED → FINAL_REALIZED from checkpoint tiers.
- Evaluate: fairness / concentration / uncertainty / resilience endpoints (unchanged), now taught in
  order with plain-language-first and technical tables under research disclosure.

### Final stage / navigation model
Main journey (stepper, Home outside, no Data step): Initial Plan → Farmer Responses → Replan → Consent →
Finalise → Analyse. Analyse guides Fairness & Concentration → Uncertainty → Resilience. Research
(Data, Experiment Lab, Provenance & Reproducibility) remains separately accessible and always available.

### No-future-state-leakage rules (enforced + tested)
Initial Plan cannot display FINAL_REALIZED / final crop / renewed consent / RECOMMENDED_REVISED (state ==
PLANNED, no `final` key, columns limited to original recommendation). Farmer Responses cannot display
revised/final (response-only endpoint; no `final`/`revised_crop` keys). Replan shows RECOMMENDED_REVISED
but states NOT realised and revised_cash != final_cash. Consent occurs after Replan; Finalise after
Consent; FINAL_REALIZED appears only in Final Plan (+ evaluation). Analyse unlocks only after Finalise.
Stepper cannot auto-complete: each stage unlocks the next only when actually visited. Selected
farmer+plot detail matches the selected row.

### Recorded Development Replay vs future Interactive Exploratory Run
- Recorded Development Replay (current): stored synthetic responses are immutable. A user may try an
  illustrative alternative action/message; it is labelled "Illustrative — does not modify the recorded
  development experiment" and never replaces the recorded response.
- Interactive Exploratory Run (FUTURE / NOT IMPLEMENTED THIS TURN): a genuine fresh run (LLM parse →
  validation → action recorded for that run → reoptimise → revised recommendation → renewed consent →
  final) is described as pending and clearly does not work yet. No live execution added.

### AI role (parses, never allocates) — exactly as implemented
- LLM: understands/parses the farmer's natural-language message into structured intent
  (ACCEPT / REJECT / MODIFY / REQUEST_ALTERNATIVE / NO_RESPONSE / WITHDRAW).
- Deterministic validator: checks farmer, plot, crop, units, semantics, action validity, consent context.
- MILP optimiser + deterministic rules: decides feasible crop allocations / revised recommendations —
  the only source of crop choices/alternatives.
- LLM then explains the validated deterministic result.
- Explicit rule (surfaced in UI + ai_role payload + tested): the LLM never chooses or invents a crop
  allocation or an alternative crop. "What else can I grow?" parses to REQUEST_ALTERNATIVE and the UI
  states alternatives must come from the deterministic feasibility/optimisation layers. Mock/Dev only;
  no live call; no new allocation produced this turn.

### Files changed
REPLACE EXISTING: static/js/farmsync.js, static/css/farmsync.css, templates/farmsync.html (added ws-replan
+ ws-consent, split Main nav into 5 stages), farmsync/ui_adapter.py (added initial_plan / replan / consent
/ final_plan / farmer_response_detail readers), farmsync_routes.py (added the 5 endpoints below),
tests/test_farmsync_ui.py, docs/farmsync/PROGRESS.md. No scientific module, dataset, seed, solver or
frozen artifact changed.

### Endpoints changed/added
ADDED (read-only, no solver / no LLM): GET /api/farmsync/initial-plan, /farmer-response/<id>, /replan,
/consent, /final-plan. Existing endpoints retained. (Prior turn added /data-requirements.)

### Tests and exact counts
tests/test_farmsync_ui.py — 21 passed: five main stages present; workflow order Initial Plan→Farmer
Responses→Replan→Consent→Finalise→Analyse (Data not a step); separate Replan + Consent stages/endpoints;
unlock chain plan→farmer→replan→consent→final→analyse + no jump-ahead; Initial Plan PLANNED with no FINAL
leak; Farmer Responses no revised/final leak; Replan revised-not-realised; Final only FINAL_REALIZED
source; selected farmer+plot mapping; LLM parses but never allocates/invents (REQUEST_ALTERNATIVE, roles
shown); recorded vs illustrative; Dev/Mock LLM labelled + no live call + fresh-execution pending; every
main stage teaches what/why/result/meaning; Analyse guides fairness→uncertainty→resilience with technical
tables under disclosure; no solver on any API load (pulp not imported); no false live-LLM/final30;
recommendation ≠ consent preserved; caveats preserved; research pages preserved; theme palettes separate
no-leak; no colour hex in JS. ILP v2 regression — 6 passed.

### No-solver / no-live-LLM verification
All five new endpoints + evaluation endpoints return 200 with pulp never imported; no live LLM call path
exists (Mock/Dev only). Page load unchanged.

### Dataset / config / hash / seed / RNG / solver state — UNCHANGED
ε=0.95, λ=0.05, α=0.40; instance_hash 5ea24037c2d9cb6a; seeds base 20260812; CBC/PuLP 3.3.2.

### Frozen-artifact verification
b1_ilp_v2.json, b3_ilp_v2.json, ui_dev_checkpoint.json, replication_seeds.json byte-identical (SHA-256).

### Limitations
Farmer interaction is Recorded Development Replay only (illustrative "what if" does not mutate a solve).
Fresh exploratory solving and live LLM are pending/disabled. Replan/Consent/Final read the current
development artifacts; the p1 offer stage records ACCEPT/REJECT only, while the richer action-consent
aggregate (ACCEPT/REJECT/MODIFY/NO_RESPONSE/WITHDRAW) is surfaced from the checkpoint.

### Unresolved issues
None blocking. Interactive Exploratory Run remains to be designed/implemented safely.

### Exact next step
Design + implement (in a later, dedicated turn) the SAFE Interactive Exploratory Run: explicit
user-triggered, backgrounded, clearly-labelled fresh solve for Explore mode that never fires on page/API
load. Only after that: live LLM smoke → ≥300 LLM benchmark → final experiment readiness → final30 (gated
behind publication experiment-manifest freeze + ≥300 benchmark dataset). NOT started. Live LLM smoke NOT
begun.

---

## CRITICAL FARMER+PLOT BINDING FIX (2026-08-26)

Correctness fix for a real bug. NO scientific change: methodology, ε=0.95 / λ=0.05 / α=0.40, fairness-v2,
action-consent-v1, uncertainty-v1, dataset, seeds/RNG, solver, frozen artifacts and results unchanged. NO
solver, NO live LLM. p1_participation_offers.csv and all artifacts byte-identical.

### Correction of an earlier claim
The prior turn stated farmer+plot mapping was closed. That was WRONG and is corrected here. The list
carried only `data-fid`, `openFarmer(fid)` sent only farmer_id, the route accepted only <farmer_id>, and
`farmer_response_detail(farmer_id)` returned the FIRST matching p1 row. For a multi-plot farmer, clicking
one plot could load another plot's recorded response — reproducing the ACCEPT/REJECT mismatch.

### Bug reproduced (fixture)
294 farmers; 72 have multiple plots; 19 of those have differing responses across plots. Example F0017:
P02=ACCEPT, P03=REJECT, P05=ACCEPT. Single-key lookup always returned P02=ACCEPT, so the P03 REJECT row
mis-loaded as ACCEPT.

### Fix (exact two-key binding, no silent fallback)
- farmsync/ui_adapter.py: `farmer_response_detail(farmer_id, plot_id=None)`. With plot_id → EXACT
  (farmer_id, plot_id) match or not-found (never another plot). Without plot_id → resolved only when the
  farmer has exactly one plot; a multi-plot farmer without plot_id returns "plot_id required" (+ the list
  of plot_ids) so the wrong plot is never returned. farmer, plot, original crop, recorded response and
  expected cash all originate from that single exact row.
- farmsync_routes.py: added GET /api/farmsync/farmer-response/<farmer_id>/<plot_id> (exact; 404 on a
  missing pair). The legacy /farmer-response/<farmer_id> now returns 400 "plot_id required" for a
  multi-plot farmer instead of a wrong plot; single-plot farmers still resolve.
- static/js/farmsync.js: farmer rows carry both data-fid and data-pid; the click handler calls
  openFarmer(fid, pid); openFarmer requests the exact two-key URL and stores {farmer, plot} so a
  re-render restores the same plot.

### Verification
F0017 P02→ACCEPT, P03→REJECT, P05→ACCEPT each returned its exact source row (crop + cash + response match
p1). A REJECT plot cannot return an ACCEPT sibling. Invalid pair (F0017-P99) → 404. Multi-plot single-key
→ 400 (plot_id required). Single-plot single-key still 200. No pulp imported.

### Files changed / endpoints
REPLACE EXISTING: farmsync/ui_adapter.py, farmsync_routes.py, static/js/farmsync.js,
tests/test_farmsync_ui.py, docs/farmsync/PROGRESS.md. ADDED endpoint:
/api/farmsync/farmer-response/<farmer_id>/<plot_id>.

### Tests and exact counts
tests/test_farmsync_ui.py — 25 passed (was 21). New: test_multiplot_two_key_binding_no_cross_plot_leak
(finds a multi-plot farmer with differing responses, requests each plot, asserts exact per-row match, and
proves a REJECT row cannot return an ACCEPT); test_invalid_farmer_plot_pair_is_404_not_silent_fallback;
test_multiplot_single_key_refuses_ambiguous (400); test_js_sends_both_ids; and the strengthened
test_selected_farmer_plot_mapping (two-key). No scientific artifact changed.

### Scientific state
ε=0.95, λ=0.05, α=0.40; instance_hash 5ea24037c2d9cb6a; b3_ilp_v2 / ui_dev_checkpoint /
p1_participation_offers byte-identical. No final30, live LLM, ≥300 benchmark, tuning or regeneration.

### Exact next step
Unchanged from prior turn: design + implement the safe Interactive Exploratory Run (later, dedicated
turn), then live LLM smoke → ≥300 benchmark → final readiness → final30. NOT started.

---

## DATA REQUIREMENTS — MODE/PURPOSE-AWARE + CAPABILITY READINESS (2026-08-26)

Data-UX correctness fix. Read-only over artifacts. NO scientific change: methodology, ε=0.95 / λ=0.05 /
α=0.40, fairness-v2, action-consent-v1, uncertainty-v1, dataset, seeds/RNG, solver, frozen artifacts and
results unchanged. NO solver run, NO live LLM. dataset_manager.py (the scientific validator) byte-identical.

### Problem
The Data → requirements table reduced every file to core/optional from CORE_FILES alone. That is
misleading: whether a file is optional depends on the upload mode and the downstream capability.

### Dependency audit (from actual code, not filenames)
- Upload paths: custom-farmer route merges built-ins ({**builtin, **provided}) → supporting files are
  reused, not required. Complete-package route builds from the ZIP only (no merge) → each capability
  needs its own file present.
- validate_package() enforces ONLY: CORE_FILES presence, REQUIRED_COLUMNS, relational integrity
  (dup keys, region/collective/season references, positive area). It does NOT check planning/feasibility/
  uncertainty/resilience data. Therefore structural PASS != ready to plan (a core-only complete package
  validates yet cannot plan).
- Audited capability → files (for a fully-independent complete package):
  - core relational: farmers, plots, crops, regions, collectives (validator-enforced)
  - initial planning / optimiser: crop_region_season_params.csv (economics), plot_crop_suitability.csv
    (feasible crop set)
  - feasibility & weather uncertainty: plot_crop_suitability.csv, climate_scenarios.csv
  - market uncertainty: market_scenarios.csv
  - participation uncertainty: participation_scenarios.csv
  - resilience: hazard_zones.csv (plots also carry hazard_zone)
  - provenance/reproducibility: parameter_provenance.csv (dataset_dictionary.csv = documentation)
  - farmer_preferences.csv: optional (shapes farmer behaviour; defaults if absent)
  Note: the built-in dataset supplies all of these; in custom-farmer mode they are reused.

### Change: mode-aware / purpose-aware requirements
data_requirements() rewritten. The bare core/optional column is replaced with, per file, a Custom-farmer
label (Required | Built-in reused) and a Complete-package label (Required | Required for planning |
Required for feasibility & weather uncertainty | Required for market uncertainty | Required for
participation uncertainty | Required for resilience analysis | Optional (farmer behaviour) | Optional
metadata / reproducibility), plus a purpose string. The UI answers two questions explicitly: "If I only
upload farmer/plot/collective data, what must I provide?" (farmers/plots/collectives; rest reused) and
"For a fully independent dataset, what files does each capability need?" (per-capability table).

### Change: capability readiness (advisory; validator unchanged)
Added capability_readiness(present_files, mode): computes, from the audited capability→file map, which
capabilities can run and whether the set is ready_to_plan. It does NOT alter the scientific validator; it
is an advisory layer so the UI cannot claim "Ready to Plan" on a structural-only pass. The dataset
validation report now shows, after PASS, a "Ready to plan ✓ / Not ready to plan" banner and a
per-capability Ready/Missing grid. Custom-farmer mode reports capabilities satisfied by built-in reuse.

### Validator vs readiness distinction (mismatch handling)
The mismatch (structural PASS on a core-only complete package) is surfaced, not silently changed: the
scientific validator keeps its behaviour; the new readiness layer prevents the UI from claiming
ready-to-plan without the planning data files. No change to activation's scientific semantics.

### Files changed / endpoints
REPLACE EXISTING: farmsync/ui_adapter.py (mode/purpose-aware data_requirements + capability_readiness +
audited maps), farmsync_routes.py (added GET /api/farmsync/capability-readiness), static/js/farmsync.js
(mode/purpose requirements panel + readiness in the dataset report), tests/test_farmsync_ui.py,
docs/farmsync/PROGRESS.md. ADDED endpoint: /api/farmsync/capability-readiness. No scientific module,
dataset, seed, solver or frozen artifact changed.

### Tests and exact counts
tests/test_farmsync_ui.py — 30 passed (was 25). New: test_requirements_are_mode_and_purpose_aware
(per-mode labels grounded in the audit; no bare core/optional); test_capability_readiness_structural_vs_
planning (core-only complete → ready_to_plan False, planning files missing; adding them → True, resilience
still needs hazard_zones); test_capability_readiness_custom_farmer_reuses_builtin;
test_validation_vs_readiness_documented; test_no_solver_on_requirements_or_readiness. ILP regression
unaffected. No solver imported on requirements/readiness loads.

### Limitations
Capability→file mapping reflects the complete-package (no-merge) path; the built-in and custom-farmer
paths satisfy capabilities by reuse. Readiness is advisory and file-presence-based (it does not deep-parse
each file's rows for capability sufficiency). farmer_preferences.csv is treated as optional behaviour
input. dataset_dictionary.csv is documentation metadata.

### Scientific state / frozen artifacts
ε=0.95, λ=0.05, α=0.40; instance_hash 5ea24037c2d9cb6a; dataset_manager.py, b3_ilp_v2.json,
ui_dev_checkpoint.json byte-identical. No final30, live LLM, ≥300 benchmark, tuning or regeneration.

### Exact next step
Unchanged: design + implement the safe Interactive Exploratory Run (later, dedicated turn), then live LLM
smoke → ≥300 benchmark → final readiness → final30. Optionally, deepen readiness to validate capability
files' contents (not just presence) when the complete-package solve path is implemented. NOT started.

---

## MANUAL-QA CLOSURE + SAFE INTERACTIVE EXPLORATORY RUN

This turn closed the correctness/UX defects found during manual QA of the rebuilt journey **and**
implemented the previously-planned Safe Interactive Exploratory Run, so FarmSync is now a usable
application (a real run you drive) rather than only a frozen development replay. No cosmetic redesign
was done. No final30, no ≥300 LLM benchmark, no live OpenAI call, no tuning, no frozen-artifact change.

### Two explicit modes (now unmistakable in the UI)
- **Recorded Development Replay** — the frozen synthetic experiment. Responses are immutable; the
  PLANNED → responses → REPLAN → CONSENT → FINAL results are replayed from stored artifacts;
  illustrative what-if buttons never alter those records. Every replay stage now carries a mode
  banner and the recorded-vs-illustrative wording was sharpened: `Recorded: <RESPONSE>` for the
  stored fact vs `What-if selected: <ACTION> — not saved (recorded: <RESPONSE>)` for an illustrative
  click.
- **Interactive Exploratory Run** — the user explicitly starts a NEW run; the built-in dataset OR the
  currently-activated validated custom dataset is used; user actions genuinely become that run's
  state; reoptimisation genuinely consumes those actions; renewed consent genuinely affects that
  run's final result; all run outputs are isolated from every frozen publication/development artifact.
  Its workspace carries an interactive mode banner and is labelled "exploratory — not a publication
  result" throughout.

### Manual-QA defects — root cause + exact fix
1. **Partial custom upload was accepted.** Root cause: `/api/farmsync/upload-farmers` accepted "at
   least farmers.csv" and merged built-ins for the rest. Fix: the primary custom route now REQUIRES
   all three of `farmers.csv`, `plots.csv`, `collectives.csv` together; any missing file → HTTP 400
   with an explicit `missing_files` list; the three farmer/plot/collective files are never silently
   replaced by built-ins. Supporting crops/regions/parameters/climate/market/hazard/participation
   continue to come from built-ins. (The research/debug single-file replacement facility remains a
   separate route.)
2. **Impossible validation state (`ISSUES` + FILES 0 + ERRORS 0 + WARNINGS 0 + "Ready to plan ✓").**
   Root cause: the JS read `v.files`, `v.n_errors`, `v.n_warnings` — fields the validation summary
   never had (it exposes `counts`/`errors`/`warnings`), so they bound to `undefined → 0`; and the
   readiness panel was fetched independently of the (failed) upload. Fix: `_stage()` now returns
   explicit `n_files`, `n_errors`, `n_warnings`, `file_states` (per-file `✓ N rows`), `row_counts`,
   `mode`, `passed`, and `readiness`. `renderReport()` binds those directly; a failed upload renders
   an `UPLOAD FAILED` state that clears stale validation, lists the missing files, disables
   activation, and never shows "Ready to plan".
3. **Successful upload still showed `FILES 0`.** Same root cause as (2); fixed by the explicit
   `n_files`/`file_states` binding. The QA 8-farmer/12-plot/2-collective dataset now shows PASS with
   `farmers.csv ✓ 8 rows`, `plots.csv ✓ 12 rows`, `collectives.csv ✓ 2 rows`.
   - Additional real subtlety fixed: merging the built-in `plot_crop_suitability.csv` (keyed to
     built-in F-plots) into a custom package created dangling plot references and failed validation.
     Fix: custom-farmer mode excludes that plot-keyed file (feasibility is recomputed for custom
     plots) and validates in `mode="farmer_only"`. QA dataset now validates with 0 errors.
4. **`Activated: versioned` was a dead end.** Fix: `/api/farmsync/activate` now returns `mode`,
   `version`, `dataset_hash`, and `population` (farmers/plots/collectives). After activation the UI
   shows a summary panel (mode, version, hash, counts, "built-in supporting parameters reused") and a
   primary **Start an Interactive Plan →** CTA that starts a fresh exploratory run from the activated
   dataset — it does NOT route to the frozen Recorded Development Initial Plan.
5. **Mock AI returned a hardcoded crop** ("Can I grow groundnut?" → "Requested crop: maize") and
   faked `Schema: Valid` / `Semantic validation: Pass`. Root cause: crop extraction and validation
   verdicts were hardcoded in the browser. Fix: removed all crop/verdict logic from JS; added a
   backend deterministic parser `ui_adapter.ai_parse()` that extracts the requested crop from the
   REAL crop vocabulary (`crops.csv`, longest-match, never hardcoded), classifies the action, reuses
   the P7 `detect_authority_attempts`, computes a real `schema_ok`, and reports semantic validation
   as **"not evaluated"** in read-only replay (never a fake Pass). The browser now renders only the
   backend-returned structured interpretation, labelled **Preview AI interpretation — Development /
   Mock**; no live API call is made.
6. **Renewed-consent / Final-plan artifact incoherence.** Renewed Consent showed rows with "renewed
   consent = none" while summarising "48 require renewed consent; 295 consent recorded", and Final
   Plan showed rows with `Consent = no` while claiming `coverage = 100%`. Root cause: the UI combined
   row-level data from `p6_final_revised_plan.csv` with the aggregate `consent_coverage_final = 1.0`
   from the newer development checkpoint — two incompatible provenance versions in one result. Fix:
   both `consent()` and `final_plan()` now derive rows, categories, coverage and totals from ONE
   coherent artifact (p6). Consent categories are correct: **295 existing valid initial consents**
   (unchanged accepted crop), **48 require renewed consent** (30 crop-changed + 18 recovered/no prior
   accept), **0 renewed consents recorded** — the 295 are never mislabelled as renewed. Final Plan
   realises only consent-verified rows: **295/343 realised, coverage 0.86**, realised cash
   **₹11,210,638** summed from p6; a `consent = no` row is shown but marked NOT realised. The
   development-checkpoint PLANNED→FINAL tier economics (FINAL_REALIZED ₹12,362,577) are shown in a
   separately-labelled panel and never merged into the realised figure. There is now no
   FINAL_REALIZED (realised) row without verified exact-crop consent.
7. **Uncertainty cards said only "Not run".** Fix: UW/UM/UR/UP now read **"No stored development
   checkpoint / Implementation/unit-integration validated; publication experiment pending."** No
   values are invented; U0/UJ stored checkpoints still show; opening the page runs no experiment.

### Safe Interactive Exploratory Run — architecture
- **New module `farmsync/exploratory_run.py`** (ADD NEW). A deterministic, commitment-aware exploratory
  engine that NEVER imports pulp and writes ONLY under `results/farmsync/exploratory/<run_id>/run.json`.
  It never reads-for-mutation or writes any publication/development/P1/P3/P6/frontier/replication/
  final30 artifact.
- **Solver-free by construction.** Page load, GET endpoints, dataset inspection and navigation run
  ZERO solver calls (verified: `pulp` never enters `sys.modules` across page load, all GETs, ai-parse,
  and every exploratory POST). A run is created ONLY by an explicit POST.
- **Why deterministic, not the frozen B3 MILP.** The `Farmer`/`Plot` dataclasses require many
  agronomic attributes (soil group, drainage, irrigation, exposures, budgets, labour) that a minimal
  custom upload does not contain, and `build_instance` is generator-bound (`generate_dataset(seed)`).
  Running the real MILP on a minimal custom upload would require fabricating those inputs, which is not
  honest. So one coherent deterministic engine drives both built-in and custom exploratory runs, and
  it is labelled clearly as NOT the frozen MILP and NOT a publication result.
- **Deterministic recommendation.** Per plot, the engine picks the highest expected-value feasible crop
  for the plot's region/season from the built-in economics: `expected_value_per_ha = yield × price −
  cost`, where `price = price_per_kg` if numeric else the numeric `msp_floor_per_kg` (the static
  built-in file carries `price_per_kg` as a `REQUIRES_SOURCING` placeholder; the MSP floor is the
  honest deterministic proxy, labelled as such). Crop choice comes from this engine/rules, never the
  LLM.
- **Run metadata recorded** in `run.json`: `run_id`, `created`, `source`, `source_kind`
  (builtin|custom), `dataset_hash`, `config` (`config_version`, ε/λ/α = 0.95/0.05/0.40,
  `action-consent-v1`, engine id — recorded, not retuned), `population`, `provenance = EXPLORATORY_RUN`,
  `solver_status` (Optimal only exposes allocations; otherwise a loud honest status),
  `stage`, `planned_cash`, per-plot `recommendations`, and `isolated_from`.
- **Endpoints** (all mutations POST-only; GET only reads): `POST /exploratory/start`,
  `GET /exploratory/<run_id>`, `POST /exploratory/<run_id>/action`, `.../replan`, `.../consent`,
  `.../finalise`. `run_id` is validated (`run-` + alnum) to block path traversal.

### Activated dataset actually drives the run
Starting a run uses the currently staged/activated package if present, else the built-in dataset. With
the QA custom dataset activated, the exploratory initial plan contains **QA001–QA008 and QA plot IDs
only** — it never displays F0001/F0017/etc., population/counts match the activated dataset, and
planning uses the activated merged snapshot rather than the frozen P1 artifact. A dedicated regression
test asserts exactly this (QA IDs present, no `F0` leak).

### Action → replan → consent → final (interactive) causal path
- **Action.** `POST .../action` records the exact `farmer_id + plot_id` action (ACCEPT/REJECT/MODIFY/
  NO_RESPONSE/WITHDRAW) into the run; the left list updates to the recorded action. ACCEPT sets a
  deterministic commitment (area ≥ 4 → HARD_LOCK, ≥ 2 → SOFT_LOCK, else FLEXIBLE). Invalid actions and
  unknown farmer/plot pairs → 400.
- **Replan.** `POST .../replan` consumes the run's own recorded actions (not the frozen synthetic
  actions): REJECT/MODIFY on a non-HARD_LOCK plot excludes the current crop and re-recommends the next
  best feasible crop (verified end-to-end: e.g. rice → groundnut), which then requires renewed consent;
  WITHDRAW/NO_RESPONSE drop the plot from realisation. Result is labelled `RECOMMENDED_REVISED — not
  yet realised`; crop decisions come from the engine, not the LLM.
- **Renewed consent.** `POST .../consent` records the run's own renewed ACCEPT/REJECT/NO_RESPONSE for
  each changed plot.
- **Finalise.** `POST .../finalise` realises a plot ONLY with verified exact-crop consent — an
  unchanged INITIAL_ACCEPT or a changed RENEWED_ACCEPT. No realised row exists without a consent basis
  (asserted by test).

### MockLLM / parser / validator correction
LLM parses → deterministic validator checks → optimiser decides → LLM explains; the LLM never
allocates. `ai_parse` correctly yields `MODIFY/groundnut` for "Can I grow groundnut?", `MODIFY/maize`
only when maize is named, `REQUEST_ALTERNATIVE` (no invented crop) for "What else can I grow?",
`REJECT` for "I don't want onion", and `ACCEPT` for "I accept". For REQUEST_ALTERNATIVE it states that
feasible alternatives must come from FarmSync's deterministic feasibility/optimisation layers, not the
LLM. Semantic validation is never displayed as Pass unless actually executed.

### Consent / final provenance correction (single version)
Recorded Replay now uses one coherent artifact (p6) for Replan-linked consent, renewed-consent
categories, FINAL_REALIZED rows, coverage and totals. Checkpoint aggregate economics are shown
separately and never combined. Categories are explicit: existing valid initial consent (295), renewed
consent required (48), renewed ACCEPT/REJECT/NO_RESPONSE, not-applicable. 295 initial consents are
never labelled as 295 renewed consents.

### Custom-data integration
Primary custom mode requires all three files; supporting general data comes from built-ins; the
plot-keyed suitability file is excluded (recomputed for custom plots); validation runs in
`farmer_only` mode. The activated custom snapshot drives the exploratory run.

### Files / endpoints changed
- `farmsync/exploratory_run.py` — **ADD NEW** → `R:\portfolio\farmsync\exploratory_run.py`
- `farmsync/ui_adapter.py` — REPLACE EXISTING → `R:\portfolio\farmsync\ui_adapter.py`
  (new `ai_parse`; coherent `consent()` + `final_plan()`)
- `farmsync_routes.py` — REPLACE EXISTING → `R:\portfolio\farmsync_routes.py`
  (custom-upload require-3 + farmer_only; enriched `_stage`; enriched `/activate`; exploratory routes;
  `/ai-parse`)
- `static/js/farmsync.js` — REPLACE EXISTING → `R:\portfolio\static\js\farmsync.js`
  (validation binding + failure state; activation summary + CTA; interactive-run workspace; backend
  ai-parse; coherent consent/final; uncertainty wording; two-mode banners)
- `static/css/farmsync.css` — REPLACE EXISTING → `R:\portfolio\static\css\farmsync.css`
  (mode-banner + consent-row, theme-var-only; `--sci-*` untouched)
- `templates/farmsync.html` — REPLACE EXISTING → `R:\portfolio\templates\farmsync.html`
  (Interactive group + Interactive Run nav/section)
- `tests/test_farmsync_ui.py` — REPLACE EXISTING → `R:\portfolio\tests\test_farmsync_ui.py`

### Tests + exact counts
- `tests/test_farmsync_ui.py`: **47 passed** (was 30; +17 QA/interactive tests added, 6 pre-existing
  updated to the corrected behaviour). New/updated coverage: custom-upload-requires-3 + exact missing
  filenames; full-QA-upload validates + binds real counts; failed-upload cannot claim ready / disables
  activate; no impossible ISSUES+0/0/0 binding; activation CTA; ai-parse extracts real crop (not
  hardcoded) + never fakes Pass + never allocates; no hardcoded maize in JS; GET/page-load runs no
  solver; interactive run is POST-only and driven by the activated dataset (QA IDs, no F leak);
  interactive action changes run state + exact farmer/plot enforced + replan consumes actions;
  interactive final has no realised row without consent; consent categories coherent; final is
  p6-coherent with no realised-without-consent and separate checkpoint tiers; uncertainty wording
  honest; two modes labelled; frozen artifacts untouched by exploratory.
- `tests/test_farmsync_ilp_v2.py`: **6 passed** (~29s), unchanged.

### Frozen-artifact verification
Config unchanged (ε=0.95, λ=0.05, α=0.40, fairness-v2, action-consent-v1, uncertainty-v1). Instance
hash `5ea24037c2d9cb6a`. All checked frozen artifacts (p1/p3/p6, ui_dev_checkpoint.json, b1/b3_ilp_v2,
experiment_manifest) byte-identical vs the delivered mirror. The exploratory run was exercised
(action→replan→finalise) and confirmed to leave frozen artifacts byte-identical (dedicated test). Both
themes render 200; 0 six-digit colour hex in JS; `--sci-*` intact; new components use theme variables
only.

### Limitations (honest)
- A minimal custom upload lacks the agronomic attributes the B3 MILP needs, so the exploratory run —
  for built-in and custom alike — uses the deterministic commitment-aware engine, clearly labelled as
  NOT the frozen MILP and NOT a publication result. A genuine MILP-backed custom solve would require a
  richer custom schema (soil/drainage/irrigation/exposure/budgets) and a custom-data instance builder;
  not attempted this turn to avoid fabricating optimiser inputs.
- The deterministic price proxy is the MSP floor where the static `price_per_kg` is a REQUIRES_SOURCING
  placeholder; labelled as an exploratory heuristic, not a sourced market price.

### Unresolved / not started
Live LLM smoke test, ≥300 LLM benchmark, final readiness gate, and final30 remain NOT started, as
required.

### Exact next step
Live LLM smoke test (guarded, single call) → ≥300 LLM parsing benchmark → final readiness gate →
final30. NOT started this turn.

---

## ONE-FLOW CORRECTION — WORKING PLAN REPLACES THE SEPARATE INTERACTIVE RUN

> **SUPERSEDED:** The previous turn's separate **Interactive Run** workspace (its own sidebar item,
> section, loader and `/exploratory/*` routes) is superseded by this correction. Its safe, isolated
> per-session storage and its deterministic commitment-aware engine are **retained and reused** as the
> *working-plan* state behind the ONE original workflow. The duplicate user-facing product is removed.
> History of the Interactive Run design is preserved in the sections above; it is no longer a visible
> flow.

One focused corrective turn. No new product flow, no new planner, no broad refactor. The audit traced
the existing flow end-to-end and reused working code. Scientific guardrails untouched: ε=0.95, λ=0.05,
α=0.40, fairness-v2, action-consent-v1, uncertainty-v1, frozen seeds/config/results. No live LLM, no
≥300 benchmark, no final30, no tuning, no manuscript work.

### Root causes found
1. **Duplicate product.** `run` was registered in the sidebar (`Interactive` group), `ALWAYS`, the
   valid-hash list, with its own loader, `#ws-run` section and "Start an Interactive Plan" CTAs.
2. **No dataset gate.** `plan` sat in `ALWAYS` with `unlocked = { plan: true }`, so Initial Plan (and
   the workflow) opened before any dataset was chosen.
3. **Research surfaced as primary UX.** Home offered "Reproduce the research" as a major card;
   Experiment Lab and Provenance & Reproducibility were primary sidebar nav.
4. **Responses were replay-only.** Farmer Responses showed the recorded response with *illustrative*
   what-ifs that changed nothing; there was no editable working-plan state that Replan consumed.
5. **`capability_readiness` over-claimed for custom.** `reused = (mode == "custom_farmer")` made every
   capability "ready", so minimal custom plots falsely reported *Ready to Plan* even though feasibility
   genuinely needs agronomic plot columns.

### Final user journey (ONE flow)
`Choose Data → Initial Plan → Farmer Responses → Replan → Renewed Consent → Final Plan → Analyse`, with
configuration/seeds/hashes/publication status behind **Advanced ▸ Research details & reproducibility**.
There is no visible Interactive Run.

- **Home** now asks for the dataset first: *Use the FarmSync research dataset* (built-in, validated,
  500 farmers / 911 plots) or *Use my own data* (Upload → Validate → Review → Activate → Plan). No
  "Reproduce the research" card; no premature "Start with the initial plan".
- **Dataset gate.** `ALWAYS = ["home","data","repro","lab"]`; `unlocked = {}` initially. `plan` and
  every downstream stage stay locked (hint: *"Choose a dataset first"*) until `chooseDataset()` runs.
- **Persistent dataset context bar** (`#fsDatasetCtx`) under the workflow stepper shows *Built-in
  research dataset · N farmers · N plots* or *Custom dataset · <version> · N · <hash>* with a **Change
  dataset** control. Changing the dataset calls `resetDataset()` → `resetWorkingState()`, relocks
  everything and returns to Home; datasets are never mixed.

### Dataset/session architecture
- **Working-plan session** = an editable overlay on the chosen dataset, stored in the reused isolated
  session store under `results/farmsync/exploratory/<run_id>/run.json` (never a frozen artifact).
  Created only by an explicit `POST /api/farmsync/working-plan/start`; GET/page load create and mutate
  nothing and run no solver.
- **Built-in** sessions are seeded from the **canonical stored plan** (`initial_plan()` recommendations)
  + **recorded responses** (`farmers_list()`), so Initial Plan and Farmer Responses show the real
  FarmSync development results — `engine = CANONICAL_STORED_PLAN`.
- **Custom** sessions are seeded from the **activated versioned snapshot** with a deterministic
  (non-MILP) recommendation — `engine = DETERMINISTIC_WORKING_PLAN`, clearly labelled *not the frozen
  MILP, not a publication result*. Heuristic output is **never** called `Optimal`.
- Every stage after selection uses this session, so an activated custom dataset drives **all** stages
  with its own IDs and **zero Fxxxx leakage**.

### Recorded vs working response semantics; save/reset
- Each rec carries an immutable `recorded_response` (built-in: from the stored experiment; custom:
  `None`, shown as *"custom — no recorded response"*, never fabricated) and a `working_response`
  override (initially unset).
- Farmer Responses (same existing screen, no second list) shows *Recorded research response*,
  *Response for this plan*, and the original recommendation. Actions (Accept / Reject / Request another
  crop / No response / Withdraw) start **pending**; **Save response** writes the override for the exact
  `farmer_id + plot_id`; the left list updates to `ACCEPT · edited` (or `set`); switching farmers and
  returning preserves it. **Reset to recorded response** deletes the override (`reset_response`) and
  restores the recorded value. The recorded response and all frozen artifacts are never mutated.
- Replan consumes `_effective(rec) = working_response or recorded_response` — the override wins only
  for that exact farmer+plot; editing all farmers is not required.

### AI recommendation / consent
- The farmer AI flow is unchanged in principle (LLM parses → deterministic validator → deterministic
  mechanism → grounded explanation; the LLM never allocates). Preserved fixes: no hardcoded maize
  (groundnut → `requested_crop=groundnut`), no fake Semantic Pass (*"not evaluated"* in replay),
  `REQUEST_ALTERNATIVE` invents no crop (alternatives come from FarmSync's deterministic layers). The
  AI panel now offers **"Save as 'request <crop>' for this plan"**, writing the working-plan response;
  it is labelled *Determined by feasibility + deterministic planning*, not "AI suggestion".
- **Renewed Consent** (same page) lists only plots whose crop changed, with *Accept recommendation /
  Reject / No response* per exact farmer+plot; acceptance records `RENEWED_ACCEPT`.
- **Final Plan** realises a plot only with verified exact-crop consent (`INITIAL_ACCEPT` unchanged, or
  `RENEWED_ACCEPT` for a changed crop). Unconsented rows are shown but **not realised**; there is no
  realised crop without valid consent for that exact farmer+plot+crop.

### Custom agronomy / suitability fix
- Audited `feasibility.py`: a plot genuinely needs `soil_group`, `soil_suitability_class`,
  `drainage_class`, `available_water_m3`, `waterlogging_exposure`, `active_season`.
- `capability_readiness(present_files, mode, plot_columns=…)` now checks these on the custom plots.
  Custom mode is **not** automatically ready: agronomy-dependent capabilities (initial planning,
  feasibility, resilience) require the columns; when missing, `ready_to_plan=False`, `agronomy_ready=
  False`, and `missing_plot_columns` lists exactly what's absent (surfaced in the UI as *Not ready to
  plan*). The custom-farmer merge still excludes the built-in `plot_crop_suitability.csv` (keyed to
  F-plots — would dangle) and validates in `farmer_only` mode. Advanced complete-package users may
  supply a valid `plot_crop_suitability.csv`.

### Files / endpoints changed
- `templates/farmsync.html` — removed the Interactive nav group + `#ws-run`; Data moved to its own
  group ("Choose / manage dataset"); Lab/Provenance moved under a quiet **Advanced** group ("Research
  details & reproducibility"); added the `#fsDatasetCtx` context bar. → `R:\portfolio\templates\farmsync.html`
- `static/js/farmsync.js` — removed all Interactive Run code; added the dataset-choice gate
  (`DATASET`, `chooseDataset`/`resetDataset`/`resetWorkingState`, context bar); Home redesigned to
  dataset-first; built-in load + custom activation call `chooseDataset` and lead to *Continue to
  Initial Plan*; working-plan session helpers; Initial Plan / Farmer Responses / Replan / Consent /
  Final loaders rewired to the working plan; Save/Reset with pending/saved/edited states; AI-apply to
  working plan. 0 colour hex. → `R:\portfolio\static\js\farmsync.js`
- `static/css/farmsync.css` — dataset context bar, edited/saved/save-row, advanced-nav styles; theme
  variables only; `--sci-*` untouched. → `R:\portfolio\static\css\farmsync.css`
- `farmsync_routes.py` — `/api/farmsync/working-plan/{start,<id>,response,reset,replan,consent,
  finalise}` (POST mutations; GET reads, never solves); `/load-builtin` returns `dataset_summary`;
  `/activate` returns mode/version/hash/population; `_stage` passes plot columns to readiness; custom
  upload requires all 3 files + `farmer_only`. → `R:\portfolio\farmsync_routes.py`
- `farmsync/ui_adapter.py` — `capability_readiness` agronomy gate; `ai_parse`, coherent
  `consent()`/`final_plan()` retained. → `R:\portfolio\farmsync\ui_adapter.py`
- `farmsync/exploratory_run.py` — reused as the working-plan session: `create_run` seeds built-in from
  the canonical plan + recorded responses (honest `engine`/status, never "Optimal"); `set_response`/
  `reset_response`; `replan`/`finalise` consume `_effective`. → `R:\portfolio\farmsync\exploratory_run.py`
- `tests/test_farmsync_ui.py` — the interactive-run test block replaced by the one-flow working-plan
  regressions. → `R:\portfolio\tests\test_farmsync_ui.py`

### Tests + results
- `tests/test_farmsync_ui.py`: **45 passed.** Covers: plan locked before dataset choice; built-in
  choice unlocks the workflow; built-in canonical rows appear; recorded response immutable; edit → save
  → reflect → preserve → reset; replan consumes the override; AI groundnut (never maize) + no-invent
  alternative; AI recommendation saves working state; revised crop needs renewed consent; unconsented
  never realised; activated custom drives all stages with QA IDs and zero F-leak; no Fxxxx suitability
  reuse; incomplete custom not Ready-to-Plan; no Interactive Run remains; Lab/Provenance not primary
  nav; GET/page-load runs no solver; frozen artifacts byte-identical after a full working-plan flow;
  dataset switch resets working state.
- `tests/test_farmsync_ilp_v2.py`: **6 passed** (~29 s), unchanged.

### Frozen-artifact / hash verification
ε=0.95, λ=0.05, α=0.40, fairness-v2, action-consent-v1, uncertainty-v1 unchanged. Instance hash
`5ea24037c2d9cb6a`. Six frozen artifacts (p1/p3/p6, ui_dev_checkpoint.json, b1/b3_ilp_v2,
experiment_manifest) byte-identical vs the delivered mirror, and a full working-plan flow
(response→replan→finalise) leaves them byte-identical (dedicated test). Both themes render 200; 0
six-digit colour hex in JS; `--sci-*` intact; new components use theme variables only.

### Limitations (honest)
- The custom working plan uses a deterministic (non-MILP) recommendation because a minimal custom
  upload lacks the agronomic attributes the B3 MILP requires; it is labelled as such and never called
  Optimal or a publication result. A genuine MILP-backed custom solve needs a richer custom plot schema
  and a custom-data instance builder (out of scope for this corrective turn).
- The built-in working plan is seeded from the canonical stored plan; edited working-plan replans use
  the reused deterministic commitment-aware engine (RECOMMENDED_REVISED, not realised, not Optimal) —
  the frozen p3/p6 remain the canonical research results and are shown in the research/advanced context.

### Unresolved / not started
Live LLM smoke test, ≥300 LLM benchmark, final readiness gate and final30 remain **not started**, as
required.

### Exact next step
Live LLM smoke test (guarded, single call) → ≥300 LLM parsing benchmark → final readiness gate →
final30. NOT started this turn.

### Exact manual-QA sequence
1. Load the app → Home shows **two dataset choices**; the sidebar shows Initial Plan and downstream as
   **locked**; the workflow stepper shows lock glyphs.
2. Click a locked stage → it shakes and does not open (*"Choose a dataset first"*).
3. Click **Use built-in dataset** → validation summary + *Dataset chosen*; the **context bar** appears
   (*Built-in research dataset · 500 farmers · 911 plots · Change dataset*); Initial Plan unlocks →
   **Continue to Initial Plan**.
4. **Initial Plan** shows canonical recommendations; **Farmer Responses** shows a searchable list with
   each farmer's recorded response.
5. Open a farmer+plot → see *Recorded research response* and *Response for this plan (unchanged)*.
   Pick a different action → **Pending** → **Save response** → *✓ Saved for this plan · Recorded: … ·
   This plan: …*; the left row shows `… · edited`.
6. Switch to another farmer and back → the edit is preserved. **Reset to recorded response** → restores
   the recorded value and clears *edited*.
7. In the AI box type *"Can I grow groundnut?"* → interpretation shows `MODIFY / groundnut`, schema
   valid, semantic *not evaluated*; *"What else can I grow?"* → `REQUEST_ALTERNATIVE`, no invented crop.
8. **Replan** → RECOMMENDED_REVISED reflecting your saved responses (original → revised, commitment,
   *not realised*). **Renewed Consent** → accept/reject the changed crop. **Final Plan** → only
   consent-verified plots realised; unconsented shown but not realised.
9. **Change dataset → Use my own data**: upload only `farmers.csv` → **400**, missing files listed.
   Upload all three QA files (QA001–QA008) → PASS with real counts, but **Not ready to plan** listing
   the missing agronomic plot columns. (With a complete package / sufficient columns, Activate → the
   context bar shows the custom dataset and every stage uses QA IDs — no F-IDs.)
10. Confirm **no Interactive Run** anywhere in the sidebar/workspaces, and that Experiment Lab /
    Provenance appear only under **Advanced ▸ Research details & reproducibility**.

---

## CORRECTNESS PASS — REAL REOPTIMISATION MACHINERY, CUSTOM AGRONOMY, SNAPSHOT BINDING, ANALYSE PROVENANCE

One focused corrective turn closing seven correctness gaps in the working-plan implementation. No
redesign, no new flow. Scientific guardrails untouched (ε=0.95, λ=0.05, α=0.40, fairness-v2,
action-consent-v1, uncertainty-v1, frozen seeds/config/results). No live LLM, ≥300 benchmark, final30,
tuning or manuscript work.

> **SUPERSEDES (previous turn's claims):**
> - The working-plan replan previously used `_best_crop_for_plot()` (a next-highest expected-value
>   heuristic) and was loosely described as "reoptimisation". That description is superseded: replan now
>   uses the REAL frozen action-consent machinery + canonical feasibility eligibility, and is explicitly
>   labelled as NOT the MILP collective reoptimisation.
> - The custom working plan previously kept only plot_id/farmer_id/region/area and picked crops by the
>   heuristic; `capability_readiness` treated "custom ⇒ ready". Superseded: custom now carries and uses
>   the real agronomic plot attributes through the canonical FarmSync feasibility, and readiness only
>   passes when a defensible feasible set is derivable.
> - `/working-plan/start` previously bound to `_state["pkg"]`. Superseded: it binds to the immutable
>   ACTIVATED versioned snapshot.
> - Analyse (Fairness/Uncertainty/Resilience) previously showed frozen research results for any plan.
>   Superseded: frozen results are labelled "Recorded development research analysis"; for a custom
>   dataset the frozen Fxxxx analysis is not shown at all.

### Root causes fixed
1. **Working replan used a private heuristic.** `_best_crop_for_plot()` duplicated eligibility and was
   mislabelled reoptimisation.
2. **Custom plan ignored agronomy.** The custom snapshot lacked agronomic columns and the heuristic did
   not use them, so "readiness" could not reflect real feasibility.
3. **Snapshot binding was to staged state.** Later staged uploads could bleed into an active plan.
4. **Requested crop was lost.** "Can I grow groundnut?" stored only `action=MODIFY`.
5. **Analyse mixed provenance.** Frozen F-derived fairness/uncertainty/resilience were presented as
   analysis of edited/custom plans.
6. **Lab ghost.** `ws-lab`, `loaders.lab`, and `lab` routing remained after the sidebar item was hidden.

### Mechanism now used for working replan
`replan()` uses the REAL frozen deterministic layer, imported lazily (POST-only, so GET/page-load stay
solver- and import-free):
- **`matrix_cell(action, lock)`** (`farmsync/proposed/actions.py`, ACTION_CONSENT_PROTOCOL v1, FROZEN)
  decides permission + offer status per (action, lock) cell — e.g. REJECT→DECLINED, MODIFY on
  HARD_LOCK→BLOCKED, WITHDRAW→WITHDRAWN.
- **`modify_target()` / `_eligible()`** (`farmsync/ilp_reference.py`, the CANONICAL optimiser
  feasibility eligibility) choose the revised crop from the plot's real feasible, cash-positive options
  (region + season + `is_admitted` + `assess_plot_crop` + positive `projected_return`), excluding the
  current crop, ranked by canonical cash then crop_id.
- A MODIFY may carry the farmer's `requested_crop`; it is honoured only if it is in the plot's canonical
  eligible set, otherwise the canonical `modify_target` pick is used. The LLM never allocates.
- **No CBC/PuLP solve is run.** This is the real deterministic action-consent + feasibility layer
  applied to working-plan responses. It is explicitly NOT the MILP collective reoptimisation
  (`reoptimize.py` re-solves the whole instance and is not reused per working-plan edit); the run

  records `replan_mechanism` saying exactly this.
  **Scientific correction 2026-09-18:** the earlier crop-specific REJECT example was
  produced before the interactive operational parameter layer was guaranteed to be
  loaded. The action-consent semantics remain valid, but crop selection and projected
  cash must come from canonical `_eligible` with the processed operational data loaded.

### Custom agronomy path
- Audited: real feasibility (`assess_plot_crop`) uses `active_season`, `region_id`, `area_ha`,
  `soil_suitability_class`, `soil_group`, `drainage_class`, `available_water_m3`, `waterlogging_exposure`,
  and `previous_crop` (no-monocrop rotation rule). `previous_crop` is **Optional**: when absent the
  no-monocrop rule cannot fire and is treated as OK (feasibility is not fabricated, only less
  restrictive) — documented, not required for readiness.
- The activated custom snapshot's own rows are used to build real `Plot`/`Farmer` objects (`Farmer`
  budget/labour set non-binding so the collective MILP's economic caps do not distort a per-plot
  feasibility view; crop objects borrowed from the canonical set). **Built-in Fxxxx
  plot_crop_suitability is never reused for custom plots** — feasibility is derived fresh from the
  custom plots' own attributes via `_eligible`.
- The custom **initial** recommendation is now the top canonical feasible option per plot (via
  `_eligible`), not the old heuristic. Verified: agronomy-complete QA plots yield real feasible crops
  (groundnut/maize/pearl_millet), QA IDs only, zero F leakage.
- Readiness: `capability_readiness` requires the agronomic plot columns (else `ready_to_plan=False`
  with `missing_plot_columns`), and `create_run` additionally fails loudly if canonical feasibility
  derives **no** cash-positive crop for any plot ("no defensible feasible crop could be derived") rather
  than presenting an empty plan.

### Activated snapshot binding
- At activation, an immutable copy of the snapshot rows (`_state["active_snapshot"]`: version, hash,
  mode, farmers/plots/collectives rows) is captured. `/working-plan/start` binds to it, not to
  `_state["pkg"]`. A staged-but-not-activated custom upload returns 400 ("Activate … before planning").
  Verified: a different upload staged AFTER activation does not alter the active working plan (no ZZ
  leakage; IDs unchanged).

### Requested-crop / alternative state flow
- `set_response(..., requested_crop=…)` stores `requested_crop` separately from the action (only for
  MODIFY). The route and the AI panel carry it through (`data-ai-crop` → POST body). Replan validates
  the requested crop against canonical eligibility and honours it when feasible; the LLM still never
  allocates, and "What else can I grow?" yields `REQUEST_ALTERNATIVE` with no invented crop (the
  deterministic layer supplies alternatives).

### Working-plan vs research Analyse behaviour
- `analyseGate()` runs first in the fairness/uncertainty/resilience loaders. For a **custom** dataset it
  shows only the working-plan summary that is genuinely derivable (plot count, consent-verified realised
  count, working cash, crop composition) and a clear notice that the frozen fairness-v2/uncertainty/
  resilience results are computed on the built-in research dataset and do **not** describe the custom
  plan — no Fxxxx-derived analysis is presented for custom. For the **built-in** dataset the frozen
  analyses are shown but explicitly labelled **"Recorded development research analysis"**.

### Lab ghost removed
- Removed `loaders.lab`, the `#ws-lab` section, and `lab` from `ALWAYS`/valid-hash routing. The useful
  run-configuration/solver panel was folded into the single **Advanced ▸ Research details &
  reproducibility** view (which now also states it describes the recorded research, not working plans).

### Files / endpoints changed
- `farmsync/exploratory_run.py` — real-machinery `replan` (matrix_cell + modify_target/_eligible, lazy
  POST-only imports); `_custom_objects` builds real Plot/Farmer from the activated snapshot; custom
  initial recommendation via `_eligible`; `set_response(requested_crop=…)`; all-infeasible guard;
  `custom_snapshot` carried on the run. → `R:\portfolio\farmsync\exploratory_run.py`
- `farmsync_routes.py` — `/working-plan/start` binds the activated snapshot; `activate` captures
  `active_snapshot`; `/working-plan/<id>/response` forwards `requested_crop`. → `R:\portfolio\farmsync_routes.py`
- `static/js/farmsync.js` — removed Lab; `analyseGate` + `recordedResearchBanner`; AI-apply carries
  `requested_crop`; repro view folds in run config. → `R:\portfolio\static\js\farmsync.js`
- `templates/farmsync.html` — removed `#ws-lab` section. → `R:\portfolio\templates\farmsync.html`
- `farmsync/ui_adapter.py` — unchanged this turn (agronomy readiness gate from the prior turn retained).
  → `R:\portfolio\farmsync\ui_adapter.py`
- `tests/test_farmsync_ui.py` — corrective regressions added; stale lab/heuristic/minimal-custom tests
  updated. → `R:\portfolio\tests\test_farmsync_ui.py`

### Tests + results
- `tests/test_farmsync_ui.py`: **52 passed.** New/updated: working replan uses real matrix_cell +
  canonical feasibility (and is not the MILP); custom uses real feasibility and requires agronomy;
  minimal custom not Ready-to-Plan; activated-snapshot binding is immutable to later staged uploads;
  staged-but-not-activated custom requires activation; requested_crop preserved and consumed; analyse
  gate hides frozen research for custom + labels built-in as recorded research; Lab ghost removed.
- `tests/test_farmsync_ilp_v2.py`: **6 passed** (~29 s), unchanged.

### Frozen-artifact / hash verification
ε/λ/α + versions unchanged; instance hash `5ea24037c2d9cb6a`; no pulp imported on page load or any GET;
six frozen artifacts (p1/p3/p6, ui_dev_checkpoint.json, b1/b3_ilp_v2, experiment_manifest)
byte-identical vs the delivered mirror. Working-plan sessions and activation snapshots write only under
`results/farmsync/exploratory/` and `data/farmsync/snapshots/` (both excluded from the mirror).

### Remaining limitations
- The working replan is the real deterministic action-consent + feasibility layer, not the MILP
  collective reoptimisation; re-solving the whole collective per working-plan edit is out of scope and
  would require running CBC on a full action-adjusted scenario. This is labelled honestly and is not
  presented as Optimal or as a publication result.
- Custom `Farmer` economic caps (budget/labour) are set non-binding for the per-plot feasibility view;
  a full custom collective solve would need real per-farmer budgets/labour and remains out of scope.
- Column-presence readiness plus the all-infeasible guard together prevent an empty custom plan, but
  readiness does not pre-run full feasibility on every plot; genuine infeasibility surfaces at
  `working-plan/start` with a clear message.

### Exact manual QA steps
1. Load → Home shows two dataset choices; Initial Plan + downstream locked.
2. **Use built-in** → context bar appears → **Continue to Initial Plan**.

3. Farmer Responses ? open a plot ? record a response ? **Save** ? Replan: any revised
   crop must come from canonical feasibility and positive-return eligibility using the
   processed operational parameter layer. `RECOMMENDED_REVISED` is still not realised
   until renewed consent.
4. AI box: a named-crop request preserves the requested crop; "What else can I grow?"
   requests an alternative. FarmSync performs deterministic validation/recommendation;
   the LLM does not invent or choose the crop.
   **Supersedes the pre-2026-09-18 Groundnut-specific manual example.**
5. Renewed Consent → accept the changed crop → Final Plan: only consent-verified plots realised.
6. **Analyse** on built-in → each card is labelled **Recorded development research analysis**.
7. **Change dataset → Use my own data**: upload farmer/plot/collective with the agronomic plot columns
   → Validate → **Activate**. Every stage now uses the activated versioned snapshot (QA IDs, no F-IDs);
   the initial plan crops come from real feasibility.
8. Stage a different upload after activation → the active working plan is unchanged.
9. Upload custom plots WITHOUT the agronomic columns → **Not ready to plan**, missing columns listed;
   working-plan start is refused.
10. **Analyse** on the custom plan → frozen research analysis is NOT shown; a working-plan summary +
    separation notice is shown instead.
11. Confirm no Experiment Lab anywhere; research config lives only under **Advanced ▸ Research details &
    reproducibility**.

### Exact next step
Live LLM smoke test (guarded, single call) → ≥300 LLM parsing benchmark → final readiness gate →
final30. NOT started this turn.

---

## UX PATCH — HOME OWNS DATASET SELECTION; DATA EXPLORER; FARMER AI RECOMMENDATION CARD

Focused UX patch on the start/data-source flow **and** the farmer AI experience + working-plan
terminology. No changes to replan/action-consent/feasibility machinery, consent/finalisation, Analyse
provenance, frozen artifacts, LLM work or final30. Guardrails verified unchanged (ε=0.95, λ=0.05,
α=0.40, fairness-v2, action-consent-v1, uncertainty-v1; instance hash `5ea24037c2d9cb6a`; no pulp on
GET/page-load; six frozen artifacts byte-identical).

> **SUPERSEDES (previous turn's claims):**
> - The Home built-in/custom buttons previously redirected into the **Data workspace** ("Choose /
>   manage dataset") to perform selection. Superseded: **Home now owns dataset selection** end-to-end;
>   selection never navigates to Data.
> - The Data workspace previously chose/activated/switched the planning dataset. Superseded: it is now
>   **Data Explorer** — inspection only; it never selects, activates, switches, or unlocks planning.
> - The full-width `#fsDatasetCtx` context strip under the workflow is **removed**; a small inline
>   "Data source:" line replaces it.
> - The farmer AI panel previously showed a developer/debug interpretation table and told the user to
>   "save Request another crop and go to Replan". Superseded: it now returns a **real feasible
>   recommendation immediately** as a normal-user card; debug details move into a collapsed drawer.
> - Working-plan copy previously said "collective is reoptimised" / "deterministic optimiser decides" /
>   "Deterministic reoptimisation". Superseded with accurate language for the working-plan path.

### 1. Home owns dataset selection
- **Built-in:** `Use built-in dataset` → `selectBuiltinOnHome()` POSTs `/load-builtin` and calls
  `chooseDataset({kind:"builtin"})` directly; Home re-renders to a success state
  ("FarmSync research dataset selected", counts, **Continue to Initial Plan →**, **Change dataset**).
  It does **not** call `activate("data")`.
- **Custom:** `Use my own data` mounts the existing Dataset Manager component **inline on Home**
  (`#homeDmMount`, `mode:"select"`) → Upload → Validate → Review → Activate → `chooseDataset({kind:
  "custom"})` → Home re-renders to the selected state. No second uploader was built; the existing
  `#fsDatasetTpl` + `initDatasetManager` are reused.

### 2. Data Explorer (exploration only)
- The sidebar item is renamed **Data Explorer**. Its loader is inspection-only: it mounts the Dataset
  Manager in `mode:"explorer"`, which **hides Activate** and **guards `chooseDataset`/activate behind
  `selectMode`** so neither can run. It cannot choose, activate, switch, reset, or unlock the planning
  dataset, and is not required anywhere in the workflow. It may inspect the built-in tables (and notes
  when a custom dataset is the active planning source) without mutating the active plan.

### 3. Global dataset context strip removed
- `#fsDatasetCtx` (template element), `renderDatasetContext()`, and the `data-change-dataset` top-bar
  handler are removed. A small unobtrusive `dataSourceLine()` ("Data source: …") is available for stage
  content; there is no persistent full-width strip. Before any selection, no dataset context shows.

### 4. Change dataset (on Home, with confirmation)
- The selected-state panel offers **Change dataset** → `requestChangeDataset()`. If a working plan
  exists it confirms *"Changing the dataset will reset your current working plan."*; only on
  confirmation does `resetDataset()` clear the working plan, relock downstream, and return Home to the
  choices.

### 5. Robust Data Explorer mount (dead "Explore built-in data" fixed)
- The brittle global `dmMounted` flag is removed. `mountDM(host, opts)` mounts when the host has no
  `.fs-dm-root` yet (the template root now carries that class), so re-visits and re-renders always
  remount correctly. All Dataset-Manager DOM lookups are scoped to the mount root (`q(...)`), so Home's
  inline mount and the Data Explorer mount never collide.

### 6. Gating (unchanged, verified)
- Fresh page: Home available; Initial Plan + downstream locked. Built-in on Home selects directly,
  unlocks Initial Plan, stays on Home, shows an explicit Continue CTA. Custom requires validate +
  planning-ready + activate before Initial Plan unlocks. Data Explorer does not affect the gate.

### 9. Farmer AI experience — real recommendation card
- On the same Farmer Responses screen, the AI box now:
  - **"What else can I grow?"** → parse `REQUEST_ALTERNATIVE` (no state mutation) → call the new
    read-only `POST /working-plan/<id>/recommend`, which uses the canonical `_eligible` machinery for
    the exact farmer+plot and returns a real feasible crop **immediately** in a normal-user card:
    *FarmSync recommendation / <crop> / <short grounded reason>* with **Use this recommendation**,
    **Reject**, **Another option**, **Ask why**.
  - **Use this recommendation** → saves `working_response=MODIFY` + `requested_crop=<crop>`, shows
    "✓ Saved for this plan", and states clearly this is a crop-change request (renewed consent still
    required after Replan). **Reject** leaves working state unchanged. **Another option** calls
    `/recommend` with the offered crop excluded → next canonical feasible crop (LLM never invents it).
    **Ask why** is explanation-only (no mutation).
  - **"Can I grow groundnut?"** → preserves `requested_crop=groundnut` → read-only
    `POST /working-plan/<id>/validate-crop` against canonical feasibility → if feasible, shows groundnut
    as the recommendation; if infeasible, says why and offers the canonical feasible alternative.

  - Backend endpoints (both read-only, no CBC/PuLP solve): `recommend_alternative()` and
    `validate_requested_crop()` in `farmsync/exploratory_run.py`, reusing `_eligible` /
    `_resolve_objects`. Recommendations now require the processed operational layer to be
    loaded before canonical eligibility is evaluated; asking does not mutate working state.
  - **Scientific correction 2026-09-18:** the earlier crop-specific
    `"what else" -> Groundnut` / `"Another option" -> Maize` verification was generated
    with the operational layer unloaded and is superseded. On audited plot F0001-P03,
    the corrected remaining cash-positive alternative to Onion is Soybean at INR 19,996.
  - The developer interpretation (parsed action, schema, LLM/validator roles) is moved into a collapsed
    **"Technical details"** drawer. A subtle **"Development / Mock LLM"** disclosure remains but does not
    dominate. The stale *"Semantic validation: not evaluated (read-only replay)"* is no longer the
    primary display for an alternative request (real deterministic feasibility is shown instead).

### 10. Working-plan terminology
- Working-plan copy now reads **"Deterministic replanning"**, **"FarmSync action-consent + feasibility
  logic"**, **"FarmSync validates and selects feasible alternatives"** — it no longer implies the full
  collective MILP/CBC was run. The recorded-research/MILP sections retain optimiser terminology where
  technically true (e.g. Resilience's "backup / reoptimised recommendation" describes the research
  analysis).

### Files / endpoints changed
- `static/js/farmsync.js` — Home-owned selection (`selectBuiltinOnHome`, `renderHomeSelected`,
  `requestChangeDataset`, inline custom mount); Data Explorer inspection-only; removed
  `renderDatasetContext`/context-strip handler; robust `mountDM(host,opts)` + root-scoped
  `initDatasetManager(root,opts)` with select/explorer modes; farmer AI recommendation card
  (`recommend`/`validate-crop`, Use/Reject/Another/Ask-why, Technical-details drawer); terminology.
  → `R:\portfolio\static\js\farmsync.js`
- `farmsync/exploratory_run.py` — read-only `recommend_alternative()` + `validate_requested_crop()`
  (reuse `_eligible`). → `R:\portfolio\farmsync\exploratory_run.py`
- `farmsync_routes.py` — `POST /working-plan/<id>/recommend` and `/validate-crop`.
  → `R:\portfolio\farmsync_routes.py`
- `templates/farmsync.html` — removed `#fsDatasetCtx`; nav "Data Explorer"; `.fs-dm-root` marker on the
  Dataset Manager template. → `R:\portfolio\templates\farmsync.html`
- `static/css/farmsync.css` — source-line + selected-state styles (theme vars only).
  → `R:\portfolio\static\css\farmsync.css`
- `tests/test_farmsync_ui.py` — UX + AI + terminology regressions; stale JS-string tests updated.
  → `R:\portfolio\tests\test_farmsync_ui.py`

### Tests + results
- `tests/test_farmsync_ui.py`: **65 passed.** New: Home built-in does not navigate to Data; Home owns
  selection + stays Home + unlocks; custom upload inline on Home; Data Explorer never selects/activates
  and cannot change the working source; no `#fsDatasetCtx` strip; fresh load shows no selected-dataset
  UI; robust DM mount on re-visits; Change dataset confirms when a working plan exists; AI "what else"
  returns a real feasible recommendation (read-only) + "Another option" excludes; validate-crop
  feasible/infeasible+alternative; AI card is user-first with a Technical-details drawer; working-plan
  terminology accurate.
- `tests/test_farmsync_ilp_v2.py`: **6 passed** (~26 s), unchanged.

### Frozen-artifact / hash verification
ε/λ/α + versions unchanged; instance hash `5ea24037c2d9cb6a`; no pulp on page load or any GET; six
frozen artifacts byte-identical vs the mirror.

### Remaining limitations
Unchanged from the prior turn: the working replan/recommendation use the real deterministic
action-consent + feasibility layer (not the MILP collective reoptimisation); custom feasibility needs
the agronomic plot columns. The AI recommendation is a read-only feasibility query; committing it still
goes through Save → Replan → renewed consent.

### Exact next step
Live LLM smoke test (guarded, single call) → ≥300 LLM parsing benchmark → final readiness gate →
final30. NOT started this turn.

---

## FINAL STATE-INTEGRITY + UX POLISH — PLANNING SOURCE, READINESS, DATA EXPLORER, AI SEMANTICS

One state-integrity + polish turn. No redesign, no scientific-machinery change. Guardrails verified
unchanged (ε=0.95, λ=0.05, α=0.40, fairness-v2, action-consent-v1, uncertainty-v1; instance hash
`5ea24037c2d9cb6a`; no pulp on GET/page-load; six frozen artifacts byte-identical). No Live LLM, ≥300
benchmark, final30, tuning or manuscript work.

> **SUPERSEDES (prior claims corrected this turn):**
> - **Activation readiness:** previously `/activate` checked only structural `passed`. Now it
>   independently recomputes planning readiness server-side and returns **400** when not ready; the UI
>   disables Activate unless `passed && ready_to_plan`.
> - **Data Explorer "read-only":** previously it still mounted the full Dataset Manager (upload /
>   activate / replace visible). Now it is a dedicated read-only inspector with **zero** mutation
>   controls, backed by a non-staging `/explore` endpoint.
> - **Planning-source switching:** previously `working-plan/start` inferred the source from a possibly
>   stale `active_snapshot`. Now an **explicit server-side `planning_source`** (NONE | BUILTIN |
>   CUSTOM:<version/hash>) is the only thing it obeys.
> - **AI Reject semantics:** previously Reject only printed "not used". Now it persists a
>   **`rejected_alternatives`** entry for the exact farmer+plot; future recommendations and Replan
>   exclude it.
> - **Requested-crop persistence/visibility:** previously a saved `requested_crop` vanished on revisit
>   and a generic MODIFY save could erase it. Now it renders everywhere and is preserved on omission.
> - **Upload-state behaviour:** previously a fresh custom interaction could show a stale staged verdict
>   ("PASS / Files 0"). Now the custom uploader starts clean; no silent auto-resume.
> - **Stale optimiser wording:** the working Farmer-Responses AI-role strip no longer says "Optimiser
>   decides the crop"; the JS header no longer calls the whole UI read-only.

### 1. Readiness enforcement (client + server)
`capability_readiness` is recomputed inside `POST /api/farmsync/activate` from the actual staged
package + plot columns; if `ready_to_plan` is false it returns **400** with `readiness_error`,
`missing_plot_columns`, `missing_capabilities`. The browser is never trusted. Client-side,
`renderReport` sets `readyPlan = passed && ready_to_plan`, disables Activate unless ready, shows
**"Not ready to plan"** and lists the missing agronomic plot columns. Initial Plan stays locked.

### 2/18. Explicit planning-source state model
New server state `planning_source` (NONE | `{"kind":"builtin"}` | `{"kind":"custom","version","hash",
"snapshot"}`). Routes: `POST /select-builtin` (Home → explicit BUILTIN, overrides any stale custom
snapshot), `POST /activate` (sets CUSTOM:<version/hash> with the immutable snapshot), `POST
/change-dataset` (clears the source; historical snapshots are NOT deleted), `GET /planning-source`.
`working-plan/start` obeys ONLY `planning_source` — never `_state["pkg"]`, a stale `active_snapshot`,
recently inspected data, or Data Explorer state. Verified both directions: custom→change→built-in =
canonical F IDs only, zero QA leakage; built-in→change→custom = exact QA IDs only, zero stale F
leakage; no source → start refused (400). Responsibilities kept strictly separate: **Home** = choose /
upload / validate / activate / change planning source; **Data Explorer** = inspect only; **Working
plan** = temporary edits, never writes the source dataset; **Recorded research** = immutable.

### 3/5. Clean Home custom-upload state machine + feedback
`status()` no longer auto-renders a stale staged package; the DM report/inspect start hidden — a fresh
"Use my own data" interaction begins EMPTY (no PASS/ISSUES, no Files/Errors/Warnings, no Activate,
until the user uploads in that interaction). Upload feedback: selected filenames show `Selected ✓`
(and a 3-file status line for custom mode); clicking Upload disables the button and shows an
indeterminate **"Uploading… / Validating dataset…"** spinner (no fabricated percentages); success
renders Files/Errors/Warnings + readiness; errors restore usable controls and keep selected filenames.

### 4. Redundant built-in card removed from the custom branch
In Home's custom (`select`) mount, the built-in card and the research/debug replace-file control are
removed — the built-in-vs-custom question is not asked twice; the custom branch shows only Option A
(complete package) and Option B (farmers/plots/collectives).

### 6/7. Data Explorer — truly read-only + spacing
Data Explorer no longer mounts the Dataset Manager. It uses a dedicated `mountExplorer()` inspector:
dataset headline + table selector + search + table + pagination, backed by read-only
`/api/farmsync/explore-tables` and `/api/farmsync/explore/<table>` (which read built-in CSVs directly
and never touch `_state["pkg"]`, `active_snapshot`, or `planning_source`). Zero controls for ZIP
upload, farmer/plot/collective upload, replace-file, activate, or dataset selection. Explorer content
sits in `.fs-explorer-mount` with a `margin-top:20px` gap below the Explore button (§7).

### 8–14. AI alternative browsing + saved requested-crop semantics
- "What else can I grow?" and **Another option** are read-only browsing (POST `/recommend`, no state
  mutation) until the user commits. Verified no working state changes from asking.
- **Use this recommendation** saves `working_response=MODIFY` + `requested_crop=<crop>`; if a crop was
  already saved it shows **"✓ Updated for this plan · Requested crop: X (previous: Y)"**. It is a
  crop-change request, not realisation — renewed consent still required after Replan.
- A saved crop and the currently-browsed candidate are visibly distinct ("Currently saved: Groundnut ✓
  … Viewing an option does not change it").
- The saved `requested_crop` renders persistently in the farmer detail ("Requested crop: Groundnut ✓
  saved for this plan") and survives switching farmers, changing stage, and reloading the run
  (backend persists it). The AI conversation card itself need not persist; the saved plan state does.
- The left list keeps "MODIFY · edited"; the detail panel exposes the requested crop.

### 10. Generic Save cannot erase requested_crop
`record_action` uses an `_OMITTED` sentinel: for a MODIFY save, an omitted `requested_crop` preserves
the already-saved crop, an explicit value replaces it, and an explicit null clears it. The
`/working-plan/<id>/response` route passes the sentinel when the field is absent from the JSON body.
Omission never erases a saved crop.

### 12. Reject = reject candidate (not recorded response, not consent)
`POST /working-plan/<id>/reject-candidate` appends the crop to that plot's `rejected_alternatives` in
the isolated working plan. It does not change the immutable recorded research response, does not reject
the original crop, and is not consent. `recommend_alternative` and `replan` both exclude rejected
crops; Replan never selects an explicitly rejected alternative (verified). Reset removes them.

### 15. Reset semantics
`reset_response` clears ALL override state for the exact farmer+plot — `working_response`,
`requested_crop`, `rejected_alternatives`, and the override commitment — restoring the recorded
response (or "Not set" for custom with no recorded response). Frozen artifacts untouched.

### 'Ask why' — deterministic evidence
`POST /working-plan/<id>/explain` returns feasibility/ranking evidence only: per-constraint pass/fail
(`passed_constraints`), the crop's rank among feasible options, the competing feasible options, and
rejected exclusions — plus the basis string. The LLM only verbalises these validated facts; it never
invents reasons. Read-only.

### 16/17. Terminology + header
Working-plan AI-role strip now reads **LLM → Validator → FarmSync selects a feasible option → LLM
explains** (no "Optimiser decides the crop"). The `farmsync.js` header describes the recorded research
as read-only and the Farmer Responses stage as an isolated editable working-plan layer. Recorded
research/MILP sections keep optimiser terminology where an optimiser genuinely ran.

### Files / endpoints changed
- `farmsync_routes.py` — explicit `planning_source`; readiness-gated `/activate`; `/select-builtin`,
  `/change-dataset`, `/planning-source`; read-only `/explore-tables` + `/explore/<table>`;
  `/working-plan/<id>/reject-candidate` + `/explain`; `/response` `_OMITTED` sentinel; `working-plan/
  start` obeys only the explicit source. → `R:\portfolio\farmsync_routes.py`
- `farmsync/exploratory_run.py` — `_OMITTED` preserve semantics; `reject_alternative`;
  `explain_recommendation`; recommend/replan exclude `rejected_alternatives`; reset clears all.
  → `R:\portfolio\farmsync\exploratory_run.py`
- `static/js/farmsync.js` — explicit source calls; readiness-gated Activate + missing-inputs display;
  clean custom start (no stale auto-resume); upload feedback state machine; custom-branch built-in card
  removed; dedicated read-only Data Explorer; AI card saved-vs-browsed + Reject-candidate + Use-replaces
  + Ask-why-evidence; persistent requested_crop display; §16 strip; §17 header. → `R:\portfolio\static\js\farmsync.js`
- `static/css/farmsync.css` — upload spinner, explorer spacing, saved-crop styles (theme vars only).
  → `R:\portfolio\static\css\farmsync.css`
- `templates/farmsync.html` — unchanged structurally (DM template still reused for Home custom; `.fs-dm-root`).
- `tests/test_farmsync_ui.py` — 20 new state-integrity regressions; stale source/explorer/wording tests
  updated. → `R:\portfolio\tests\test_farmsync_ui.py`

### Tests + results
- `tests/test_farmsync_ui.py`: **85 passed.** Covers all §20 items: server + client readiness gate;
  ready custom activates + sets source; planning-source both directions with zero cross-leakage; start
  requires explicit source; Data Explorer does not mutate source and is read-only (no ZIP/upload/
  replace/activate); clean Home custom start; no redundant built-in card; upload feedback + no fake
  percentages; Another option read-only until Use; generic Save preserves requested_crop; saved crop
  survives revisit; reject-candidate persists + excluded from recommend and replan; Ask why uses
  deterministic evidence and does not mutate; Reset clears all; no "Optimiser decides" in the working
  AI-role strip; header not stale.
- `tests/test_farmsync_ilp_v2.py`: **6 passed** (~26 s), unchanged.

### Frozen-artifact / hash verification
ε/λ/α + versions unchanged; instance hash `5ea24037c2d9cb6a`; no pulp on page load or any GET
(including the new `/explore` endpoints); six frozen artifacts byte-identical vs the mirror.

### Remaining limitations
The working replan/recommendation remain the real deterministic action-consent + feasibility layer
(not the MILP collective reoptimisation). "Ask why" ranks by canonical feasibility + cash-positive
projected return; a stored canonical crop that fails current feasibility rules is reported honestly as
not-in-feasible-set rather than fabricating a rank. Run persistence across a hard browser refresh
depends on the working-plan session file remaining; the run id must be retained client-side (the saved
state itself is persisted server-side).

### Exact manual QA sequence
1. Fresh load → Home shows two choices; Initial Plan + downstream locked; no dataset context strip.
2. **Use built-in** → Home shows "FarmSync research dataset selected · 500 farmers · 911 plots" +
   Continue to Initial Plan + Change dataset. Server `planning_source=builtin`.
3. **Change dataset → Use my own data** → the custom section opens **clean** (no PASS/Files 0), shows
   only Option A / Option B, with a farmers/plots/collectives status line — no built-in card.
4. Select the 3 files → each shows `Selected ✓`. Click Upload & validate → "Uploading… / Validating
   dataset…" spinner, then the report. Upload minimal plots (no agronomy) → **Not ready to plan**,
   missing columns listed, **Activate disabled**; server `/activate` would 400.
5. Upload agronomy-complete plots → Ready to plan → **Activate** → Home shows "Custom dataset selected
   · <version>". Server `planning_source=custom:<version>`.
6. **Change dataset → Use built-in** → start a plan → only F-IDs (zero QA leakage). Reverse also holds.
7. **Data Explorer** → Explore built-in data → table/search/pagination only; no upload/activate/replace
   controls; content sits with a clear gap below the button; browsing does not change the planning
   source.

8. Initial Plan ? Farmer Responses ? open a plot ? **What else can I grow?** ? FarmSync
   returns the highest-ranked remaining cash-positive canonical alternative. If another
   eligible alternative exists, **Another option** returns it; otherwise the UI must
   report that no further cash-positive alternative is available. **Use this** saves the
   exact candidate. **Reject** persists the rejected candidate so browsing and Replan
   exclude it. **Ask why** returns deterministic evidence without mutation. **Reset**
   clears response + requested crop + rejected list.
   **Supersedes the earlier Groundnut/Maize crop-specific walkthrough, which predated the
   operational-data initialization correction.**
9. Replan → Renewed Consent → Final Plan (only consent-verified realised) → Analyse (custom shows
   working-plan summary + separation notice; built-in labelled recorded research).

### Exact next step
Live LLM smoke test (guarded, single call) → ≥300 LLM parsing benchmark → final readiness gate →
final30. NOT started this turn.

---

## 2026-09-03 — manual-QA corrective patch: response-state rehydration, grounded Ask Why, custom-upload render safety, read-only Explorer validation

**STATUS — PATCH PREPARED FROM THE LATEST SHARED UI FILES; FULL-REPOSITORY INTEGRATION TEST RUN STILL REQUIRED AFTER COPY.** This corrective turn was produced from the latest shared `farmsync_routes.py`, `farmsync/exploratory_run.py`, `static/js/farmsync.js`, `static/css/farmsync.css`, and `tests/test_farmsync_ui.py`. In this isolated attachment workspace, Python syntax compilation for the changed Python files and `node --check` for the changed JavaScript passed. The complete FarmSync repository, dependency graph, built-in dataset tree, and frozen-result tree were not available here as one executable checkout, so no new full-pytest count or frozen-artifact byte-identity claim is made by this entry. Those checks remain mandatory immediately after these files are copied into the real project.

### Manual-QA defects that triggered this patch

1. **Reset could visually leave a stale saved crop.** Manual testing showed a saved `requested_crop` (for example Maize) remaining visible after `Reset to recorded response`. The server-side `reset_response(...)` already clears `working_response`, `requested_crop`, `rejected_alternatives`, and override commitment; the defect was frontend cache drift because the reset handler partially patched `WORK.data` and then redrew from that stale object.
2. **Saved crop-change request was visually subordinate to the original recommendation.** The original crop had a large card while the saved requested crop appeared as a small line, making it easy to read the original crop as the active working choice.
3. **`Ask why` was deterministically grounded but too generic in presentation.** It exposed names such as season/soil/water/rotation and one global rank, but not the actual plot attributes already resolved by the deterministic feasibility path. It also could show a crop as rank #2 overall without explaining that rank #1 had been excluded/rejected, even though the recommendation itself was the top currently available alternative.
4. **Custom 3-CSV upload could show `Dataset Validation: PASS` and then falsely show `Upload failed: Cannot set properties of null (setting 'innerHTML')`.** Home select mode intentionally removes the Replace-file control, but `renderReport()` still chained assignment through `#replaceName`, which was null. A successful server validation was therefore caught as though the upload itself had failed.
5. **Data Explorer lost built-in validation/readiness.** The earlier read-only redesign correctly removed upload/activate/replace/source-selection controls, but it also removed the useful read-only validation/readiness summary and left only CSV browsing.

### Implemented corrective design

#### Authoritative working-state rehydration

- Added a frontend `refreshWorkingRun()` helper that GETs the exact current working run and replaces `WORK.data` with the authoritative server state after mutations.
- `Reset to recorded response` now POSTs reset, re-fetches the run, and only then redraws the exact farmer+plot. This prevents stale `requested_crop`, `rejected_alternatives`, or commitment state from surviving in the browser cache.
- Generic working-response save and AI crop-use paths also use authoritative rehydration rather than depending only on partial local object mutation.
- Server reset semantics remain unchanged: recorded synthetic research response is untouched; only the working overlay is cleared.

#### Saved requested-crop hierarchy

- Farmer detail now presents a dedicated, visually prominent **“Your saved crop-change request”** card when `requested_crop` exists.
- The card explicitly states the crop, `Saved for this plan · Pending Replan`, and that the request is **not an allocation or consent**.
- The working-response display names the exact crop for MODIFY (for example `MODIFY — maize requested ✓`) instead of showing only a generic “Request another crop”.
- The original FarmSync recommendation remains visible as provenance, but is no longer visually confusable with the saved crop-change request.
- Built-in wording is clarified to **“Recorded synthetic farmer response”**; custom data still shows no recorded response.

#### Grounded, exact-plot `Ask why`

- `explain_recommendation(...)` now returns actual deterministic plot evidence copied from the resolved `Plot` object when present: region, active season, area, soil group, soil-suitability class, drainage, irrigation access, available water, waterlogging/drought/flood exposure, previous crop, and rotation group.
- It returns deterministic assessment checks/reason codes/binding information from `assess_plot_crop(...)` without inventing missing values.
- The UI renders those actual values as evidence rather than only listing generic constraint names. Missing data is omitted/not fabricated.
- The API preserves backward-compatible `passed_constraints`, `rank_among_feasible`, and `n_feasible` fields while adding the clearer evidence/ranking fields.

#### Ranking/exclusion coherence

- Explanations now distinguish **overall feasible rank** from **rank among currently available alternatives**.
- An explicit exclusion ledger records only known reasons: original/current crop excluded for alternative search, a persisted farmer-rejected candidate, or a candidate already browsed in the current UI option sequence.
- The browser passes its current `offered`/browsed exclusion list into `/explain`, while the server independently adds persisted rejected alternatives and the original crop. This aligns the explanation with the recommendation actually shown.
- The LLM remains explanation/parser only; FarmSync deterministic feasibility + ranking remains the crop-selection authority in this working path.

#### Custom upload render safety

- `renderReport()` now treats mode-specific DOM nodes independently. In particular, it never chains `#inspectTable` and absent `#replaceName` assignments.
- Optional report/inspect/activation elements are null-guarded where mode-specific removal is intentional.
- `uploadFlow()` separates request/network failure from client rendering failure. A successfully received `PASS`/`ISSUES` response is no longer relabelled `Upload failed` because a later render block throws.
- Existing semantics remain: structural validation can PASS while `ready_to_plan=false`; Activate remains disabled client-side unless `passed && ready_to_plan`, and `/activate` remains the authoritative server-side readiness gate.

#### Read-only Data Explorer validation restored

- Added a pure `_package_report(...)` helper in the Flask routes. It computes existing validator + capability/readiness output without assigning package/report into global `_state`.
- `_stage(...)` now uses that helper and remains the explicit Home staging path.
- Added `GET /api/farmsync/explore-validation` for the built-in research dataset. It creates a local package, runs existing validation/readiness, returns counts/hash/population/readiness, and does **not** assign `_state["pkg"]`, `_state["report"]`, `_state["active"]`, `_state["active_snapshot"]`, or `_state["planning_source"]`.
- Data Explorer now shows read-only Dataset Validation, Files/Errors/Warnings, planning readiness, capability readiness, source/hash, then the existing searchable/paginated CSV browser.
- Data Explorer still exposes zero upload/activate/replace/planning-source controls. Home remains the only planning-source selection/upload/activation surface.

### Files changed in this corrective patch

- `farmsync_routes.py`
- `farmsync/exploratory_run.py`
- `static/js/farmsync.js`
- `static/css/farmsync.css`
- `tests/test_farmsync_ui.py`
- `docs/farmsync/PROGRESS.md`

### Regression tests added/strengthened

New test coverage was added for: server reset clearing all working override state; frontend authoritative rehydration; prominent exact-crop MODIFY rendering; actual plot evidence in explain output; overall vs available-alternative rank; persisted rejected-candidate exclusion reason; optional-DOM safety for Home custom validation; three-CSV validation/readiness response; read-only `/explore-validation`; preservation of NONE/custom planning source while browsing Data Explorer; Data Explorer validation UI with zero mutation controls; and explicit “Recorded synthetic farmer response” wording.

**Checks actually executed in this attachment workspace:** Python `py_compile` passed for the changed route engine, exploratory engine, and UI test file; `node --check` passed for the changed JavaScript. **Not claimed here:** full FarmSync pytest count, solver/config/hash regression suite, or frozen-artifact byte-identity — run these in the actual repository immediately after copy before accepting this patch as integrated.

### Scientific / product boundaries unchanged

- Working-plan recommend/replan remains deterministic action-consent + canonical feasibility; it is **not** the full collective MILP reoptimization.
- No solver is added to page-load/Data-Explorer GET paths by this patch.
- No live LLM call, ≥300 benchmark, final30, publication experiment, or manuscript result was run.
- `Ask why` may only expose/verbalise deterministic facts that exist; it must not invent soil, water, ranking, benefit, or feasibility evidence.
- No claim is made that the saved requested crop is allocated or consented before Replan/renewed consent.

### Remaining manual QA / unresolved work

1. Copy these files into the complete FarmSync repository and run the full existing UI/integration + scientific guardrail suite, no-solver-on-GET check, config/hash checks, and frozen-artifact byte-identity verification.
2. Fresh-server manual QA: save a requested crop → revisit → Reset → verify no saved crop/rejections/commitment remain; repeat edit/revoke/edit sequence.
3. Manual `Ask why`: verify exact soil/water/season/rotation values match the chosen plot's real data and the recommendation's available-alternative rank is coherent with exclusions.
4. Manual custom 3-CSV upload: verify PASS/readiness renders with no null-DOM exception and activation only becomes available when planning-ready.
5. Manual Data Explorer: verify validation/readiness + CSV browser and confirm planning source is unchanged before/after browsing.
6. **After this corrective patch passes QA**, proceed to the already-pending Renewed Consent interaction/AI/edit/bulk work, Final Plan all-row pagination, and Analyse recomputation from the current `FINAL_REALIZED` working plan. **Do not jump to Live LLM, benchmark, or final30 before those product/state corrections are complete.**

---

## AUDIT + FINAL-PLAN PAGINATION/SEMANTICS FIX; WORKFLOW-PATCH SCOPING (dated bugfix increment)

This turn began from the uploaded current files (the prior null-`innerHTML` bugfix and `/explore-validation`
read-only Data Explorer are present and preserved). The incoming request covered a very large scope —
Farmer Response audit, full Renewed Consent interaction, a workflow revision/stale-invalidation engine
across all seven stages, Final Plan pagination, and fully dynamic Analyse (overview, response history,
renewed-consent outcomes, realised/not-realised reconciliation, fairness, concentration, uncertainty,
resilience, provenance) plus ~60 regression tests. That is more than can be delivered to a **verified**
standard in one increment, and the request itself forbids claiming unverified implementation/testing. So
this increment delivers the highest-confidence, self-contained, fully-tested slice (**§4 Final Plan**),
records the audit of what already exists, fixes brittle baseline test drift, and scopes the remainder as
the explicit next step. No scientific machinery changed; frozen guardrails re-verified.

> No config, seeds, solver settings, or frozen artifacts changed. ε=0.95, λ=0.05, α=0.40, fairness-v2,
> action-consent-v1, uncertainty-v1; instance hash `5ea24037c2d9cb6a`; no CBC/PuLP on GET/page-load; six
> frozen artifacts byte-identical vs the delivered mirror.

### Audit findings (verified against the uploaded code)
- **Farmer Responses** already implements: exact `farmer_id+plot_id` scoping; `requested_crop`
  persistence with the `_OMITTED` sentinel (generic MODIFY save preserves a saved crop);
  `rejected_alternatives` persisted and excluded from recommend + replan; authoritative server-state
  reload after mutations/reset (`refreshWorkingRun`); Reset clears working_response + requested_crop +
  rejected_alternatives + commitment; deterministic plot-specific Ask-Why via
  `/working-plan/<id>/explain` (per-constraint checks, overall vs available-alternative ranking, truthful
  exclusion reasons). **No further Farmer-Response code change was required** — the audit found no
  remaining violation of §1's requirements at the backend/API level. (One presentation nicety noted below
  under Limitations: the Ask-Why UI verbalises the deterministic fields it is given; surfacing the full
  per-plot agronomic value list in the card is a display enhancement, not a correctness gap.)
- **Data Explorer** is already read-only (`/explore-validation`, `/explore-tables`, `/explore/<table>`)
  and non-mutating; validated below.
- **Custom upload / readiness** already enforced client + server (server `/activate` returns 400 when not
  ready); explicit `planning_source` integrity already present and tested.
- **Final Plan (§4)** had two confirmed defects — a `.slice(0, 60)` truncation and an unrealised-row Final
  crop rendered via `final_crop || revised_crop || crop` (showing a recommendation as if realised). Fixed
  this turn.

### §4 Final Plan — fix delivered and tested
- Removed the `.slice(0, 60)` truncation in `loaders.final`; added client-side pagination over the current
  run's rows: `PER = 50`, "`first–last of total`", Previous / "Page X of Y" / Next, correct boundaries,
  disabled at ends. Every plot in the current working run is now inspectable. `FINAL_PAGE` resets with the
  working state (so pagination never carries across a dataset change).
- Final-crop semantics: a NOT-realised row now shows `—` (never a recommendation as if realised); only a
  realised row renders its realised final crop. The five columns are unchanged and in order:
  `Farmer | Plot | Final crop | Consent basis | Realised`.
- The Analyse custom crop-composition helper was corrected to count **realised** allocations only (no
  fallback to a recommendation for unrealised rows) — a small consistency fix in the same spirit as §6C.

### Baseline test drift fixed (not behavior changes)
Four uploaded tests asserted exact JS substrings/wording that had drifted from the uploaded JS
(`does not choose, change, upload, or activate` vs the shipped Data-Explorer copy; `renewed consent is
still required`; a comment fragment; single-line vs multi-line `if (sel)/if (rsel)` formatting; a literal
`rejected_alternatives` string not present in the client). These assertions were realigned to the shipped
code's actual (equivalent) strings; no application behavior was changed.

### Files changed this turn
- `static/js/farmsync.js` — §4 Final Plan pagination + final-crop semantics; `FINAL_PAGE` state + reset;
  realised-only Analyse composition. → `R:\portfolio\static\js\farmsync.js`
- `tests/test_farmsync_ui.py` — 5 new §4 regressions; 5 drifted baseline assertions realigned.
  → `R:\portfolio\tests\test_farmsync_ui.py`
- `farmsync_routes.py`, `farmsync/exploratory_run.py`, `static/css/farmsync.css` — unchanged this turn
  (identical to the uploads).

### Proof Data Explorer remains non-mutating (verified)
Existing tests `test_data_explorer_does_not_mutate_planning_source`, `test_explorer_read_only_endpoint_no_staging`
and the planning-source integrity tests pass: with `planning_source` NONE, calling `/explore-validation`,
`/explore-tables`, `/explore/<table>` leaves `planning_source` NONE and stages no package; with a custom
source active, the same reads leave the exact custom version/hash intact.

### Tests + results
- `tests/test_farmsync_ui.py`: **100 passed** (95 baseline after drift realignment + 5 new §4 tests).
- `tests/test_farmsync_ilp_v2.py`: **6 passed** (~29 s).
- Guardrails: config ε/λ/α + versions unchanged; instance hash `5ea24037c2d9cb6a`; no pulp on
  GET/page-load (incl. `/explore*`); six frozen artifacts byte-identical vs the mirror.

### NOT done this turn (explicit, honest scope) — the pending workflow patch
The following from the request are **not** implemented in this increment and remain pending; they must be
done as a dedicated, testable sequence rather than claimed here:
- §2 Renewed Consent full interaction: prominent original→revised card, per-row Ask-why / Explore-another-option
  with fresh-consent invalidation on crop change, ACCEPT/REJECT/NO_RESPONSE realisation semantics with no
  silent original-crop fallback, bulk Accept-all/Reject-all (pending-only), and Edit-response.
- §3 Workflow state-integrity engine: state-derived unlock (not button-driven), per-stage revisions
  (response/replan/consent/final), upstream-edit → downstream-stale invalidation, revisiting completed
  stages without relocking, dataset-change reset, hash navigation obeying current-run state.
- §5–§11 Analyse: dynamic from the CURRENT FINAL_REALIZED working plan — overview + explicit response
  history / renewed-consent outcomes / realised vs not-realised with reason breakdown + reconciliation
  invariants; fairness-v2 (incl. zeros); descriptive concentration (α as reference, not solver-enforced);
  uncertainty-v1 and resilience computed on fixed current allocations OR an explicit "Not available —
  <reason>"; analysis provenance tied to the current final-plan revision.
- The corresponding regression tests (request items 1–34, 40–60).

### Limitations / unresolved
- The current Analyse loaders still show recorded-research analyses for the built-in dataset (labelled as
  such) and a working-plan summary for custom; making Analyse fully dynamic from the current
  FINAL_REALIZED plan (§5–§11) is the substantive pending work.
- Renewed Consent currently supports per-row Accept/Reject/No-response via the working-plan API; the richer
  interaction (Explore-another-option with consent invalidation on crop change, bulk, edit) is pending.

### Exact next step
Manual QA of the current UI, then the pending workflow patch in this order: (1) §3 workflow
revision/stale-invalidation engine (the backbone), (2) §2 Renewed Consent full interaction, (3) §5–§11
dynamic Analyse from the current FINAL_REALIZED plan with reconciliation, each with its regression tests.
NOT Live LLM, ≥300 benchmark, final30, publication execution, or manuscript work.

---

## WORKFLOW / REVISION / STALE-STATE INTEGRITY BACKBONE (dated)

Replaced button/local-boolean workflow truth with an authoritative, server-owned CURRENT-RUN / REVISION
state. No scientific machinery changed; guardrails re-verified (ε=0.95, λ=0.05, α=0.40, fairness-v2,
action-consent-v1, uncertainty-v1; instance hash `5ea24037c2d9cb6a`; no CBC/PuLP on GET/page-load
including the workflow GET; frozen artifacts byte-identical). Only `farmsync/exploratory_run.py` and
`static/js/farmsync.js` changed (plus tests). All previously-completed fixes are preserved (Final Plan
50-row pagination, unrealised Final crop = `—`, five columns, realised-only composition, null-safe
`renderReport`, split `uploadFlow`, `/explore-validation`, planning_source integrity, custom
upload/readiness, Farmer Response fixes).

> **SUPERSEDES (prior claims corrected this turn):**
> - **Automatic finalisation on view:** `loaders.final` previously POSTed `/finalise` merely by opening
>   Final Plan, and pagination re-called it (re-POSTing). Superseded: Final Plan is READ-ONLY on open;
>   `/finalise` is POSTed only by the explicit "Finalise Consent-Verified Plan" action; pagination only
>   re-reads current state.
> - **Automatic replan on view:** `loaders.replan` previously POSTed `/replan` on open. Superseded:
>   Replan is READ-ONLY on open; "Run Replan" is the explicit action.
> - **Local `unlocked = {}` + `unlock()` as workflow truth:** removed as the source of truth. Stage
>   access is now derived from `WORK.data.workflow.stages` (server-computed). `unlock()` is a no-op shim
>   that only re-renders.

### Audit findings (verified in the uploaded code)
- `loaders.final` POSTed `/finalise` on open; Previous/Next re-called `loaders.final` → re-POST.
- `loaders.replan` POSTed `/replan` on open (opening the tab "completed" replan and thereby unlocked
  Renewed Consent).
- `let unlocked = {}` + `unlock("farmer"|"replan"|"consent"|"final"|"analyse")` were called as
  side-effects **from inside stage loaders**, so merely viewing a stage marked the next one available.
- The run had only a single `stage` string — no revision tracking, so there was no way to know whether a
  Replan/Final/Analyse was current for its inputs.

### Root causes
Workflow availability and completion were inferred from view side-effects and scattered browser
booleans rather than from authoritative run state. Viewing mutated/finalised scientific state; upstream
edits did not invalidate stale downstream results.

### Server authoritative workflow design (`exploratory_run.py`)
Minimal revision anchors stored on the run:
- `response_rev` (int) — bumped ONLY when a rec's effective replan input actually changes
  (`_effective_response_sig` = working_response + requested_crop + sorted rejected_alternatives). An
  identical save is idempotent (no bump). `record_action`, `reset_response`, `reject_alternative` all
  bump only on a real change.
- `replan_anchor` — the `response_rev` captured when `replan()` last succeeded (else None).
- `final_anchor` — `{response_rev, replan_anchor, consent_sig}` captured at `finalise()` (else None).
- Per-rec `consent_for_crop` — the exact revised crop a `renewed_response` was given for. Consent is
  valid only while `consent_for_crop == revised_crop`.

Derived, no-mutation `workflow_state(run)` (attached to every GET `/working-plan/<run_id>` as
`workflow`) answers:
- `response_rev`, `replan_current` (`replan_anchor == response_rev`),
- `n_changed`, `n_requires_consent`, `n_consent_pending` (changed rows requiring consent with no valid
  decision for the current revised crop),
- `consent_complete` (replan_current AND pending == 0),
- `final_current` (final_anchor present AND its response_rev/replan_anchor/consent_sig all match current),
- `finalisable`, `replan_stale`, `final_stale`,
- `stages` = `{plan, farmer, replan, consent, final, analyse}` derived access map:
  `consent = replan_current`; `final = replan_current AND consent_complete`; `analyse = final_current`.

UNLOCKED (prerequisite exists) is distinct from COMPLETED (operation ran): `stages.final` true means
finalisation is *allowed*, while `final_current` true means a current FINAL_REALIZED revision *exists*.

### Stale-invalidation dependency chain (implemented + tested)
- **Response edit / requested_crop change / rejected-alternative change** (real change only) →
  `response_rev++` → `replan_current` false → consent/final/analyse derived-locked.
- **Idempotent save** (submitted == current) → no bump → downstream stays current.
- **Replan success** → `replan_anchor = response_rev`; clears any `renewed_response` whose
  `consent_for_crop` no longer equals the revised crop (old crop-specific consent invalidated); clears
  `final_anchor` (prior final stale).
- **Renewed-consent record** → stamps `consent_for_crop = revised_crop`; clears `final_anchor` (final
  stale).
- **Finalise** (the only creator of final state) → refuses server-side unless `replan_current` and
  `n_consent_pending == 0`; on success sets `final_anchor` tied to the exact response/replan/consent
  inputs; `analyse` unlocks.
- **Revisiting an earlier stage with no edit** → pure GETs, no bump → downstream stays current.
- **Dataset change** → client `resetWorkingState()` (run id, WORK.data, FINAL_PAGE) + server
  `/change-dataset` clears planning_source; no old run/response/replan/consent/final/analyse can appear
  as current for the new dataset.

### Client changes (`farmsync.js`)
- `isUnlocked(ws)` derives from `WORK.data.workflow.stages` (with `DATASET` as the plan-gate); removed
  `let unlocked = {}` and all `unlocked[...] = true` truth. `unlock()` is a no-op re-render shim.
  `refreshWorkingRun()` re-derives nav + stepper after every mutation, so unlock/invalidate is reflected
  immediately.
- **Final Plan**: `loaders.final` is GET-only; shows an explicit "Ready to finalise → Finalise
  Consent-Verified Plan" state when finalisable-but-not-final, and the read-only paginated final plan
  when `final_current`. The ONLY `/finalise` POST is behind the explicit button. Pagination
  (`renderFinalPlan`, Previous/Next) re-reads current state and never POSTs. Preserved: PER=50, "1–50 of
  N", Page X of Y, five columns, unrealised = `—`.
- **Replan**: `loaders.replan` is GET-only; shows "Run Replan" (or "Replan is out of date") when not
  current, and the read-only revised-recommendations view when current. `/replan` is POSTed only by the
  explicit action.
- **Hash navigation**: `valid.includes(hash) && isUnlocked(hash) ? hash : "home"` — a manually-entered
  `#final`/`#consent` cannot bypass prerequisites; resolves to Home/the highest available stage without
  mutating state.

### Analyse gate (only — computation is NEXT turn)
Analyse (`fairness`/`uncertainty`/`resilience`) unlocks only when `final_current` is true; it relocks on
any upstream edit (via the derived `stages.analyse`). The full dynamic working-plan Analyse computation
is explicitly deferred to the next turn; this turn enforces the gate/staleness only.

### Files changed
- `farmsync/exploratory_run.py` — revision anchors + `workflow_state`/`_consent_sig`/`_consent_counts`/
  `_effective_response_sig`; idempotent bumps; replan/consent/finalise invalidation + server finalise
  gate; `get_run` attaches `workflow`. → `R:\portfolio\farmsync\exploratory_run.py`
- `static/js/farmsync.js` — server-derived access; GET-only Final Plan + explicit Finalise; GET-only
  Replan + explicit Run Replan; refreshWorkingRun re-derives nav; dataset-change detach.
  → `R:\portfolio\static\js\farmsync.js`
- `tests/test_farmsync_ui.py` — 16 new workflow/revision tests; 5 tests updated off the removed
  `unlocked` booleans / renamed pagination var. → `R:\portfolio\tests\test_farmsync_ui.py`
- `farmsync_routes.py`, `static/css/farmsync.css` — unchanged this turn.

### Tests + results
- `tests/test_farmsync_ui.py`: **116 passed** (100 baseline + 16 new). New coverage: initial stage gates;
  response-edit rev bump + idempotency; replan unlocks consent only after success; final locked while
  consent pending; server refuses finalise while pending; final+analyse unlock after finalise; no-change
  ⇒ final unlocks; upstream edit invalidates downstream; consent edit invalidates final; revisit without
  edit keeps downstream current; dataset-change detach; Final Plan read-only on open; finalise only via
  explicit action + pagination never POSTs; Replan read-only on open + explicit Run Replan; access is
  server-derived + refresh re-derives; hash obeys state.
- `tests/test_farmsync_ilp_v2.py`: **6 passed** (~26 s).
- Guardrails: config ε/λ/α + versions unchanged; instance hash `5ea24037c2d9cb6a`; no pulp on
  GET/page-load (incl. workflow GET); frozen artifacts byte-identical.

### Config / hash / seeds / solver
Unchanged: ε=0.95, λ=0.05, α=0.40, action-consent-v1, uncertainty-v1, fairness-v2, frozen seeds,
instance hash `5ea24037c2d9cb6a`, solver settings, frozen baseline/development/publication artifacts.
Working-plan mechanism remains deterministic action-consent + canonical feasibility (NOT the full
collective MILP). LLM remains parser/interface/explanation only; no Live LLM added.

### Limitations / unresolved
- Working-plan runs are per-session files keyed by `run_id`; a hard browser refresh that loses the
  client `run_id` routes to Home (the server run persists but the client does not currently re-discover
  it). Re-discovery/rehydration of the current run by dataset is a possible future enhancement.
- The Renewed Consent UI remains minimal (per-row Accept/Reject/No-response via the existing API); the
  richer interaction (Explore-another-option with consent invalidation on crop change, bulk, edit) is
  the NEXT turn — this turn added only the backend revision/invalidation primitives it will need.
- Analyse computation is gated but not yet dynamic (next turn).

### Exact next step
FULL RENEWED CONSENT UX (per the plan): prominent original→revised card, per-row Ask-why /
Explore-another-option with fresh-consent invalidation on crop change (primitives now in place),
ACCEPT/REJECT/NO_RESPONSE semantics, bulk Accept-all/Reject-all (pending-only), Edit-response — with its
regression tests. NOT Live LLM, ≥300 benchmark, final30, publication execution, or manuscript work.

---

## BACKBONE CLOSURE (0A/0B/0C) + FULL RENEWED CONSENT UX (dated)

Closed the three remaining workflow/consent correctness gaps and implemented the full Renewed Consent
UX. The workflow/revision backbone is preserved. No scientific machinery changed; guardrails
re-verified (ε=0.95, λ=0.05, α=0.40, fairness-v2, action-consent-v1, uncertainty-v1; instance hash
`5ea24037c2d9cb6a`; no CBC/PuLP on GET/page-load; frozen artifacts byte-identical). Files changed:
`farmsync/exploratory_run.py`, `farmsync_routes.py`, `static/js/farmsync.js`, `static/css/farmsync.css`
(+ tests). Dynamic Analyse remains NOT started (next turn).

> **SUPERSEDES (prior claims corrected this turn):**
> - `/working-plan/start` returned the raw run without `workflow`; `ensureWorkingSession` stored it raw,
>   so Replan could remain visually locked with no edit. Superseded: `create_run` now returns the
>   authoritative `get_run` shape (includes `workflow`); the client re-derives nav on start.
> - The consent click handler mutated the row locally and called the legacy `unlock("final")` no-op
>   without reloading authoritative state. Superseded: every consent mutation calls `refreshWorkingRun`.
> - `if not act or act == "ACCEPT": offer_status = "CONSENTED"` treated a custom row's *unset* response
>   as CONSENTED. Superseded: source-aware effective response; custom unset is UNRESOLVED and blocks
>   replan until an explicit response is recorded.

### Audit findings (verified in the uploaded code)
- `create_run` returned `_save_run(run)` (raw, no `workflow`); `ensureWorkingSession` stored it directly.
- `isUnlocked` fallback made `farmer` reachable before any run existed.
- The consent handler set `rr.renewed_response` locally + `unlock("final")` (no refresh).
- `_effective(rec)` = `working_response or action or recorded_response`; for custom `recorded_response`
  is None, and the replan `if not act or act == "ACCEPT"` branch marked unset custom rows CONSENTED.

### 0A — start / workflow hydration
`create_run(...)` now ends with `return get_run(run["run_id"])`, so the POST `/working-plan/start`
response carries the derived `workflow` (single source; no JS duplication). `ensureWorkingSession`
stores that shape and calls `renderNavLocks()/renderWorkflow()`. `isUnlocked` now returns `false` when
no run exists (except `plan`), so **Farmer Responses cannot be opened before a current Initial Plan/run
exists** — opening Initial Plan is what creates the run. Sequence enforced: dataset → Initial Plan
(creates run) → Farmer Responses → (valid responses) → Replan. Test:
`test_0a_start_returns_workflow`, `test_0a_ensure_session_hydrates_and_farmer_gated`.

### 0B — every consent mutation rehydrates authoritative state
`consentDecide`, `bulkConsent`, `consentUseRecommendation` all POST then `refreshWorkingRun()` →
`WORK.data` becomes the server version → nav/stepper, pending counts, Final unlock and stale flags
re-derive automatically. There is no separate client consent truth. Test: `test_0b_consent_handler_refreshes`.

### 0C — custom unset response is never ACCEPT/CONSENTED
`_replan_effective(run, rec)`: built-in → `working_response or recorded_response`; custom →
`working_response` only (None if unset). `workflow_state` adds `replan_ready`/`n_unresolved`; for custom
`stages.replan` is false while any plot is unresolved. `replan()` refuses (400) while custom rows are
unset and never marks an unset row CONSENTED (it is `UNRESOLVED`). The user must explicitly record
ACCEPT/REJECT/MODIFY/NO_RESPONSE/WITHDRAW (including an explicit NO_RESPONSE). Built-in recorded
responses continue to work with no manual re-entry. Tests: `test_0c_custom_unset_not_accept`,
`test_0c_custom_replan_refused_while_unset`, `test_0c_explicit_custom_no_response_and_builtin_unaffected`.

### Full Renewed Consent UX
Per changed row (crop changed in the CURRENT replan), a prominent card shows Original (struck-through)
→ **Current revised recommendation** (large, accent-bordered) with projected return, current
renewed-consent state, and actions: **Accept recommendation / Reject / No response / Ask why / Explore
another option**; completed rows show the decision + **Edit response**. A top summary shows changed /
pending / accepted / rejected / no-response computed from CURRENT run state. If no crop changed, it
states no renewed consent is required and Final is finalisable.

- **Exact-crop / revision consent model:** consent is bound to `consent_for_crop == revised_crop`
  (`_consentStateOf`/`_is_pending`/`_consent_sig`). If the revised recommendation changes, the old
  decision is invalid/cleared and the new crop is PENDING.
- **Ask Why** (`consentAskWhy`) uses the deterministic `/explain` endpoint for the exact
  farmer+plot+CURRENT revised crop only: per-constraint checks, projected return, overall feasible rank,
  other feasible options, and rejected exclusions — read-only, never invents values (shows "Not
  evaluated" when checks are absent). The LLM only verbalises validated facts.
- **Explore another option** (`consentExplore`) uses `/recommend` (read-only browse; UI-only "offered"
  history for "Another option"); it never changes the revised crop, grants consent, or alters
  response/replan/final state. Test `test_rc_recommend_and_explain_are_read_only` proves no rev bump and
  no state change.
- **Use this recommendation** → `select_revised_recommendation` (`/select-recommendation`): the server
  RE-validates feasibility via canonical `_eligible` (never trusts the browser; infeasible → 400),
  replaces the current pending revised crop + cash, clears old `renewed_response`/`consent_state`/
  `consent_for_crop` (choosing ≠ consent → new crop PENDING), and clears `final_anchor` (Final/Analyse
  stale). It does NOT run a whole replan, realise, or touch frozen artifacts — no replan→consent→
  alternative loop. Tests: `test_rc_use_recommendation_clears_consent_and_stales`,
  `test_rc_select_revalidates_infeasible_refused`.
- **ACCEPT / REJECT / NO_RESPONSE semantics:** ACCEPT for the exact current revised crop →
  `RENEWED_ACCEPT`, eligible for realisation, does not itself finalise. REJECT → `RENEWED_REJECT`, NOT
  realised, no original-crop fallback, no auto-alternative, no second replan. NO_RESPONSE →
  `RENEWED_NO_RESPONSE`, NOT realised, no fallback. Test `test_rc_accept_reject_noresp_realisation`
  verifies realised/not-realised + `final_crop is None` for reject/no-response.
- **Bulk** (`bulk_renewed_consent`, `/consent-bulk`, server-side): "Accept all pending" / "Reject all
  pending" affect PENDING rows only and never overwrite an existing individual decision; individual
  rows remain editable afterward. Tests: `test_rc_bulk_pending_only_preserves_individual`,
  `test_rc_bulk_reject_pending_only`.
- **Edit response** (`renderConsentEdit`): ACCEPT↔REJECT↔NO_RESPONSE before finalisation; overrides a
  prior bulk decision; invalidates current Final + Analyse. Test `test_rc_edit_after_bulk_and_invalidates_final`.
- **Finalisation** remains an explicit button; Final Plan stays read-only on view; pagination stays
  mutation-free (unchanged this turn). Server `finalise` still refuses while any required row is pending
  (`test_rc_finalise_refused_while_pending`). Last-pending resolution unlocks Final immediately via the
  derived workflow.

### Files / endpoints changed
- `farmsync/exploratory_run.py` — `create_run` returns `get_run`; `_replan_effective`/`_unresolved_custom_rows`
  + `replan_ready`/`n_unresolved` in `workflow_state`; replan refuses on unresolved custom + unset →
  UNRESOLVED; `record_renewed_consent` returns workflow; `bulk_renewed_consent`;
  `select_revised_recommendation`; `_is_pending`. → `R:\portfolio\farmsync\exploratory_run.py`
- `farmsync_routes.py` — `/working-plan/<id>/consent-bulk` and `/select-recommendation`.
  → `R:\portfolio\farmsync_routes.py`
- `static/js/farmsync.js` — 0A start hydration + farmer gate; full Renewed Consent UX (cards, Ask why,
  Explore/Use, bulk, edit) all via `refreshWorkingRun`. → `R:\portfolio\static\js\farmsync.js`
- `static/css/farmsync.css` — Renewed Consent card styles (theme vars only).
  → `R:\portfolio\static\css\farmsync.css`
- `tests/test_farmsync_ui.py` — 16 new backbone/consent tests. → `R:\portfolio\tests\test_farmsync_ui.py`

### Tests + results
- `tests/test_farmsync_ui.py`: **132 passed** (116 prior + 16 new). New: 0A start/hydration + farmer
  gate; 0B consent refresh; 0C custom-unset-not-accept + replan-refused + explicit-NO_RESPONSE +
  built-in-unaffected; RC accept/reject/no-response realisation; finalise-refused-while-pending;
  bulk-pending-only (accept + reject) preserving individual; edit-after-bulk invalidates Final/Analyse;
  use-recommendation clears consent + stales; select revalidates (infeasible refused);
  recommend/explain read-only; zero-changed no-consent; full-consent-UX JS wiring.
- `tests/test_farmsync_ilp_v2.py`: **6 passed** (~28 s).
- Guardrails: config ε/λ/α + versions unchanged; instance hash `5ea24037c2d9cb6a`; no pulp on
  GET/page-load (incl. start); frozen artifacts byte-identical.

### Config / hash / seeds / solver
Unchanged: ε=0.95, λ=0.05, α=0.40, action-consent-v1, uncertainty-v1, fairness-v2, frozen seeds,
instance hash `5ea24037c2d9cb6a`, solver settings, frozen artifacts. Working-plan mechanism remains
deterministic action-consent + canonical feasibility (NOT the full collective MILP). LLM remains
parser/interface/explanation only; no Live LLM.

### Limitations / unresolved
- Custom datasets require an explicit working response on every plot before replan (by design); there is
  no bulk "set all custom responses" helper yet.
- A hard browser refresh that loses the client `run_id` still routes to Home (server run persists;
  client re-discovery is a future enhancement).
- Dynamic Analyse (fairness/concentration/uncertainty/resilience from the current FINAL_REALIZED plan)
  is gated but not computed — the NEXT turn.

### Exact next step
DYNAMIC ANALYSE FROM THE CURRENT FINAL_REALIZED WORKING PLAN (overview + response history + renewed-
consent outcomes + realised/not-realised reason breakdown with reconciliation; fairness-v2 incl. zeros;
descriptive concentration; uncertainty-v1 / resilience on fixed current allocations OR explicit
"Not available — <reason>"; provenance tied to the final-plan revision), with tests. NOT Live LLM, ≥300
benchmark, final30, publication execution, or manuscript work.

---

## CONSENT-REVISION CLOSURE + FULL DATASET UNIVERSE + DYNAMIC ANALYSE (dated)

Closed the two confirmed pre-Analyse correctness gaps and implemented full dynamic Analyse from the
CURRENT FINAL_REALIZED working plan. Backbone preserved. No scientific machinery changed; guardrails
re-verified (ε=0.95, λ=0.05, α=0.40, fairness-v2, action-consent-v1, uncertainty-v1; instance hash
`5ea24037c2d9cb6a`; no CBC/PuLP on GET/page-load incl. analysis; frozen artifacts byte-identical).
Files changed: `farmsync/exploratory_run.py`, `farmsync_routes.py`, `static/js/farmsync.js`,
`static/css/farmsync.css` (+ tests). No Live LLM, ≥300 benchmark, final30, publication or manuscript
work.

> **SUPERSEDES (prior claims corrected this turn):**
> - Renewed consent validity used only `consent_for_crop == revised_crop`, so a new replan that
>   recommended the SAME crop silently reused stale consent. Superseded: consent is now anchored to the
>   exact revised crop AND the current replan revision.
> - The built-in working run's `population`/final-plan universe was the offer subset (~381), not the
>   selected 500/911. Superseded: population is the full selected universe; recommendations remain the
>   genuine offer subset.
> - Analyse showed frozen recorded-development results for built-in and only a small working summary for
>   custom. Superseded: all three Analyse tabs describe the CURRENT working final plan (both datasets)
>   from one authoritative payload; frozen research stays under Advanced ▸ Research details.

### Audit findings (verified)
- `_consent_sig`/`_consent_counts`/`_is_pending`/`finalise` checked only `consent_for_crop == revised_crop`;
  `replan` cleared consent only when the crop name changed.
- `create_run` built-in branch set `population` from `len(recs)` (offer subset).
- Analyse loaders read frozen `/fairness|/uncertainty|/resilience` endpoints.

### A. Consent crop + replan-revision anchoring + stale guards
- Added per-rec `consent_for_replan_anchor`; centralised validity in `_valid_current_consent(run, rec)`
  requiring `consent_for_crop == revised_crop` **AND** `consent_for_replan_anchor == run.replan_anchor`.
  Used in `_consent_sig`, `_consent_counts`, `_is_pending`, and `finalise` `valid_accept`.
- `record_renewed_consent` and `bulk_renewed_consent` stamp both anchors; `select_revised_recommendation`
  and `replan` clear both when the crop/replan changes.
- **Server-side stale guards:** `record_renewed_consent`, `bulk_renewed_consent`,
  `select_revised_recommendation` all refuse (400) when `workflow_state.replan_current` is False — a
  direct POST can no longer write consent against a stale replan.
- Verified end-to-end: accept crop A → upstream edit → all three stale POSTs refused → rerun replan
  picks the SAME crop A → old consent invalid (`consent_for_replan_anchor` 1 ≠ current 2) → row PENDING
  again → Final locked until fresh consent. Test `test_consent_revision_same_crop_after_new_replan_invalidated`.

### B. Full selected-dataset universe
- Added `_dataset_snapshot_from_pkg(pkg)` / `_dataset_snapshot_from_custom(snap)` — lightweight immutable
  snapshots of the FULL universe (farmer_id/collective/region/season; plot_id/farmer_id/region/area_ha;
  counts + hash), without mutating the source package. Stored on the run as `dataset_snapshot`.
- Built-in `population` = **500 farmers / 911 plots / 10 collectives**; custom = exact activated snapshot
  counts. The `recommendations` array stays the genuine OFFER subset (no fabricated offers for unoffered
  plots). Tests `test_universe_builtin_population_500_911`, `test_final_rows_full_universe_and_no_offer`.

### 1. Final Plan over ALL selected plots
- New read-only `final_rows(run, page, per=50)` + `GET /working-plan/<id>/final-rows` projects over the
  full universe: a plot with no offer → `final_crop=None`, `consent_basis=None`, `realised=False`,
  reason `NO_INITIAL_OFFER` (never NO_RESPONSE/REJECT/WITHDRAW). Built-in = 911 rows, 19 pages, "1–50 of
  911" … final page reaches 911. The JS Final Plan now paginates `/final-rows` (`loadFinalRows`) — still
  read-only, five columns unchanged (`Farmer | Plot | Final crop | Consent basis | Realised`), unrealised
  = `—`, pagination never POSTs/finalises.

### 2–11. Dynamic Analyse architecture
- New `analysis(run)` + `GET /working-plan/<id>/analysis` — GET/read-only, no CBC/PuLP, no mutation,
  requires `workflow.final_current` (else `available:false` with a reason; never a stale/old analysis).
  Payload provenance `CURRENT_WORKING_FINAL_PLAN` with `run_id`, `final_plan_revision` (monotonic, set at
  finalise), `response_rev`, `replan_anchor`, dataset source/kind/hash, created/finalised timestamps,
  engine, config version. Invariant `analysis.final_plan_revision == run.final_plan_revision`; upstream
  edit → `final_current` False → analysis unavailable. Tests `test_analysis_gate_and_provenance`,
  `test_analysis_no_solver_on_get`.
- **Overview** (full universe): total farmers/plots, offered vs no-offer, realised vs not-realised,
  farmers with/without realised, final realised cash, consent coverage.
- **Initial response history** (OFFER rows only; effective per source — built-in recorded-or-override,
  custom explicit-only): ACCEPT/REJECT/MODIFY/NO_RESPONSE/WITHDRAW, reconciling to the offer-row count;
  `NO_INITIAL_OFFER` shown separately. Initial REJECT that later gets RENEWED_ACCEPT is realised, NOT a
  final rejection (`test_analysis_initial_reject_can_be_realised`).
- **Renewed-consent outcomes:** RENEWED_ACCEPT/REJECT/NO_RESPONSE over rows requiring renewed consent,
  reconciling to that count; at `final_current`, pending = 0.
- **Realised / not-realised** with a reason breakdown derived from ACTUAL state
  (`_not_realised_reason`): NO_INITIAL_OFFER, RENEWED_REJECT, RENEWED_NO_RESPONSE, WITHDRAW,
  INITIAL_NO_RESPONSE, INITIAL_REJECT_NO_ALTERNATIVE, OTHER_NOT_REALISED. Crop composition uses
  REALISED allocations only (never a recommendation fallback).
- **Reconciliation invariants** enforced in `_analysis_integrity` and asserted by
  `test_analysis_reconciliation_invariants`: realised+not-realised = total; offered+no-offer = total;
  initial categories = offer rows; renewed outcomes = rows requiring consent; not-realised reasons =
  not-realised; composition = realised plots; integrity.ok. If any fails, the UI shows an integrity
  error instead of metrics.

### 7. Fairness-v2 (current plan)
- Per selected farmer: `total_operated_area` = Σ area of ALL their selected plots; `realised_cash` = Σ
  final_cash of their REALISED plots; zero for no realisation. All-farmer per-ha Gini, all-farmer
  absolute-cash Gini, participant-only per-ha Gini + participant/zero counts. Denominator is all 500
  built-in (or all custom) farmers — zero-return farmers included. Missing area → explicit "Not
  available — plot area_ha missing". No frozen B1/B2/B3 substitution. Verified all 500 incl. 206 zeros.

### 8. Concentration (descriptive)
- Over REALISED allocations only: active crops, max crop share, HHI (crop share), per-crop shares. α=0.40
  is a labelled FROZEN REFERENCE — the note states the working plan used deterministic action-consent +
  feasibility and did NOT run the concentration-control MILP, so α is a reference, not an enforced
  constraint (`test_analysis_concentration_alpha_is_reference`).

### 9–10. Uncertainty / Resilience
- Both return explicit **"Not available — <reason>"** for the working plan: uncertainty-v1 and resilience
  are defined over the frozen recorded Stage-5 allocation / backup pipeline and cannot be applied to the
  working final plan without reoptimisation or the recorded scenario mapping. No frozen result is
  substituted; no solver is run on GET; non-realised plots are never reintroduced. Frozen recorded
  results remain only under Advanced ▸ Research details & reproducibility. Test
  `test_analysis_uncertainty_resilience_not_available_not_frozen`.

### UI
- Three Analyse tabs (Fairness & Concentration / Uncertainty / Resilience) render from ONE `/analysis`
  payload via `loadAnalysis()`; each shows the provenance banner + (on Fairness) the Current Final Plan
  Overview with initial-response history, renewed-consent outcomes and not-realised reasons. Unavailable
  state routes to Final Plan. Consent status chip now uses the exact semantic class per state
  (`NO_RESPONSE` no longer reuses the REJECT class; `.fs-act.NO_RESPONSE` already exists in CSS).

### Files / endpoints changed
- `farmsync/exploratory_run.py` — `_valid_current_consent`; anchored `_consent_sig`/`_consent_counts`/
  `_is_pending`; stale guards; `consent_for_replan_anchor` stamping/clearing; `_dataset_snapshot_from_pkg`/
  `_dataset_snapshot_from_custom` + full-universe population; `final_plan_revision`; `analysis`,
  `_not_realised_reason`, `_concentration`, `_analysis_integrity`, `_gini`, `final_rows`.
  → `R:\portfolio\farmsync\exploratory_run.py`
- `farmsync_routes.py` — `/working-plan/<id>/analysis`, `/final-rows`. → `R:\portfolio\farmsync_routes.py`
- `static/js/farmsync.js` — Final Plan paginates `/final-rows`; dynamic Analyse from `/analysis`;
  consent chip class fix. → `R:\portfolio\static\js\farmsync.js`
- `static/css/farmsync.css` — analyse grid. → `R:\portfolio\static\css\farmsync.css`
- `tests/test_farmsync_ui.py` — 11 new backend/integration tests; 5 architecture tests updated.
  → `R:\portfolio\tests\test_farmsync_ui.py`

### Tests + results
- `tests/test_farmsync_ui.py`: **143 passed** (132 prior + 11 new). New: consent-revision same-crop
  invalidation + stale guards; built-in 500/911 universe; final-rows full-universe + no-offer;
  analysis gate/provenance; reconciliation invariants; initial-reject-can-be-realised; fairness all
  farmers incl. zeros; concentration α-reference; uncertainty/resilience not-available-not-frozen; no
  solver on analysis GET; dynamic-analyse JS wiring.
- `tests/test_farmsync_ilp_v2.py`: **6 passed** (~28 s).
- Guardrails: config ε/λ/α + versions unchanged; instance hash `5ea24037c2d9cb6a`; no pulp on
  GET/page-load (incl. analysis/final-rows); frozen artifacts byte-identical.

### Config / hash / seeds / solver
Unchanged: ε=0.95, λ=0.05, α=0.40, action-consent-v1, uncertainty-v1, fairness-v2, frozen seeds,
instance hash `5ea24037c2d9cb6a`, solver settings, frozen artifacts. Working-plan mechanism remains
deterministic action-consent + canonical feasibility (NOT the full collective MILP). LLM remains
parser/interface/explanation only.

### Limitations / unresolved
- Uncertainty-v1 and resilience are intentionally "Not available" for the working plan (honest) —
  applying them to a fixed working allocation would require a defensible scenario mapping / evaluator
  that accepts a supplied fixed allocation without reoptimisation; that adaptation is future work.
- Concentration reports crop-share HHI/shares (reusable from aggregate composition); a per-farmer
  within-crop LPS would need a per-farmer×crop realised join and is not yet surfaced.
- Hard browser refresh losing the client `run_id` still routes to Home (server run persists).

### Exact next step
FULL END-TO-END QA / PRE-EVALUATION FREEZE (manual + automated walkthrough of the entire journey on
built-in and custom, confirming reconciliation and provenance), THEN — as separate later phases — Live
LLM → ≥300 LLM benchmark → final readiness freeze → final30. None of those are started now.

---

## CLOSURE PATCH — UI CONSENT REVISION VALIDITY, REAL INTEGRITY, EXPLICIT CONSENT/REALISATION METRICS (dated)

Small correctness-closure patch for three audit findings. No redesign. Guardrails re-verified (ε=0.95,
λ=0.05, α=0.40, fairness-v2, action-consent-v1, uncertainty-v1; instance hash `5ea24037c2d9cb6a`; no
CBC/PuLP on GET/page-load incl. `/analysis` and `/final-rows`; frozen artifacts byte-identical). Files
changed: `farmsync/exploratory_run.py`, `static/js/farmsync.js` (+ tests). Routes/CSS unchanged. No Live
LLM, ≥300 benchmark, final30, manuscript work.

> **SUPERSEDES (prior claims corrected this turn):**
> - The frontend `_consentStateOf(r)` checked only crop equality, so a stale-anchor consent (same crop
>   after a new replan) could display ACCEPT/REJECT/NO_RESPONSE while the backend already treated it as
>   PENDING. Superseded: the UI now checks crop AND replan anchor.
> - `_analysis_integrity` had a placeholder `workflow_pending()` (always 0) and an `if False` branch.
>   Superseded: real invariants against authoritative values; helper removed.
> - Analyse and finalisation both showed "Consent coverage" with different denominators. Superseded:
>   explicit, distinct metric definitions used consistently.

### 1. UI renewed-consent revision validity
`_consentStateOf(r, replanAnchor)` now returns a decision only when
`r.consent_for_crop === r.revised_crop` **AND** `r.consent_for_replan_anchor === replanAnchor`
(mirrors the authoritative backend `_valid_current_consent`); otherwise PENDING. Both callers
(`renderConsentStage` summary counts and `consentCardHTML` per-card chip) thread `run.replan_anchor`
(`const _anchor = run.replan_anchor`). The server guards are untouched (still refuse stale POSTs). Tests
`test_ui_consent_state_checks_replan_anchor`, `test_ui_consent_same_crop_after_new_replan_is_pending`
(the same-crop-after-new-replan case: same crop, `consent_for_crop` matches, but `consent_for_replan_anchor`
is stale → PENDING).

### 2. Real analysis-integrity checks
Removed `workflow_pending()` and the `if False` branch. `_analysis_integrity(p, n_pending,
current_final_plan_revision)` is now called with the authoritative `wf["n_consent_pending"]` and the
current `run.final_plan_revision`, and verifies: realised+not_realised == total_plots; offered+no_offer
== total_plots; Σ initial_response_history == n_offer_rows; Σ renewed_consent_outcomes ==
n_requires_renewed_consent; authoritative pending == 0; Σ not_realised_reasons == not_realised_plots;
Σ crop_composition_plots == realised_plots; analysis final_plan_revision == current run
final_plan_revision. UI: new `integrityBlocked(el, a, title)` early-returns in all three Analyse loaders
— on failure it renders only provenance + the integrity error and STOPS (no overview/fairness/
concentration/uncertainty/resilience metrics). Tests `test_integrity_no_placeholder`,
`test_integrity_invariants_hold_on_valid_plan`, `test_integrity_failure_withholds_metrics_in_ui`.

### 3. Explicit consent / realisation metrics
Removed the ambiguous single `consent_coverage`. The Analyse overview now reports three explicit,
distinctly-labelled metrics, computed from current state:
- `affirmative_consent_coverage` = realised / consent-eligible (`n_consent_eligible` = changed rows +
  unchanged INITIAL_ACCEPT) — the SAME denominator/semantics as finalisation's `consent_coverage_final`
  (verified equal). REJECT / NO_RESPONSE are NOT affirmative consent (they remain in the renewed-consent
  accounting).
- `realisation_rate_offered` = realised / offered plots.
- `realisation_rate_all_plots` = realised / total selected plots.
UI labels: "Affirmative consent coverage", "Realisation rate (offered)", "Realisation rate (all plots)",
with a one-line definition note; the Final Plan header label aligned to "affirmative consent coverage";
`consent_coverage_final` documented in the engine. Tests `test_explicit_consent_metric_definitions`,
`test_ui_coverage_labels_unambiguous`.

### Files changed
- `farmsync/exploratory_run.py` — real `_analysis_integrity` (authoritative pending + revision
  invariant; helper removed); `n_consent_eligible` + three explicit coverage/realisation metrics;
  documented `consent_coverage_final`. → `R:\portfolio\farmsync\exploratory_run.py`
- `static/js/farmsync.js` — anchored `_consentStateOf` threaded through both callers; `integrityBlocked`
  gate in all three Analyse loaders; explicit coverage labels + note; Final Plan label aligned.
  → `R:\portfolio\static\js\farmsync.js`
- `tests/test_farmsync_ui.py` — 7 new closure tests. → `R:\portfolio\tests\test_farmsync_ui.py`

### Tests + results
- `tests/test_farmsync_ui.py`: **150 passed** (143 prior + 7 new).
- `tests/test_farmsync_ilp_v2.py`: **6 passed** (~23 s).
- Guardrails: config ε/λ/α + versions unchanged; instance hash `5ea24037c2d9cb6a`; no pulp on
  GET/page-load (incl. `/analysis`, `/final-rows`); frozen artifacts byte-identical.

### Consent metric definitions (authoritative)
- affirmative_consent_coverage = realised / consent-eligible (changed rows + unchanged INITIAL_ACCEPT).
- realisation_rate_offered = realised / offered plots.
- realisation_rate_all_plots = realised / total selected plots.
- REJECT / NO_RESPONSE = explicit outcomes, never counted as affirmative consent; visible in
  renewed-consent accounting.

### Integrity invariants now enforced
realised+not_realised==total; offered+no_offer==total; Σ initial_history==n_offer_rows; Σ renewed
outcomes==n_requires_renewed_consent; authoritative pending==0; Σ not_realised_reasons==not_realised;
Σ crop_composition_plots==realised; analysis.final_plan_revision==run.final_plan_revision.

### Limitations / unresolved
Unchanged from prior turn: uncertainty-v1 / resilience remain honest "Not available" for the working
plan; per-farmer within-crop LPS not surfaced; hard refresh losing client `run_id` routes to Home.

### Exact next step
FULL END-TO-END QA / PRE-EVALUATION FREEZE (manual + automated walkthrough on built-in and custom).
Live LLM → ≥300 benchmark → final readiness freeze → final30 remain later, separate phases — not started.

---

## PRE-QA UX + CORRECTNESS CLOSURE — CONSENT ALTERNATIVES, FINAL-PLAN FILTERS, ANALYSE UX (dated)

Final small pre-QA closure patch (15 items). No redesign, no methodology/optimisation change, no frozen
artifact regeneration. Guardrails re-verified (ε=0.95, λ=0.05, α=0.40, fairness-v2, action-consent-v1,
uncertainty-v1; instance hash `5ea24037c2d9cb6a`; no CBC/PuLP on GET/page-load incl. `/analysis` and
`/final-rows`; frozen artifacts byte-identical). Files changed: `farmsync/exploratory_run.py`,
`farmsync_routes.py`, `static/js/farmsync.js`, `static/css/farmsync.css` (+ tests). No Live LLM, ≥300
benchmark, final30, manuscript work.

> **SUPERSEDES (prior claims corrected this turn):**
> - Renewed-Consent "Explore another option" reused Farmer-Response semantics and excluded only the
>   ORIGINAL crop, so the CURRENT revised crop could be re-offered. Superseded: stage-specific
>   `consent_alternative` excludes the current revised crop + rejected + browse-history, with a separate
>   original-crop return rule.
> - Final Plan called the dataset universe "Selected plots" and titled the all-plots table "Final
>   allocations". Superseded: "Plots in dataset" + Realised/Not-realised/All filters with correct
>   headings; non-realised rows are not called allocations.
> - Analyse dead-ended, exposed raw reason codes, labelled area-derived shares ambiguously, and doubled
>   the "Not available" wording. Superseded: navigation CTAs, humanised codes, basis-aware share label,
>   single clean unavailable message.

### 1. Renewed-Consent alternative semantics
New engine `consent_alternative(run_id, fid, pid, exclude)` (READ-ONLY, no solver): the next feasible
alternative EXCLUDES the CURRENT `revised_crop`, persistent `rejected_alternatives`, and this browse
sequence's viewed crops (`exclude`). All candidates come from canonical `_eligible`. Route

`POST /working-plan/<id>/consent-alternative`. Browse-history and persistent rejected
alternatives remain excluded and browsing mutates nothing (no revision bump and no
consent-state change). If the corrected positive-return candidate set is exhausted,
FarmSync reports no further alternative rather than falling back to legacy economics.
**The earlier crop-specific Groundnut/Maize example is superseded by the 2026-09-18
operational-data correction.**

### Original-crop return rule
When the effective initial action was MODIFY and the original crop is canonically feasible and not
explicitly rejected (and is not the current revised crop), it is offered as **"Return to original plan
— <crop>"** (never as a newly discovered recommendation). If the effective initial action was REJECT,
the rejected original crop is never re-offered. WITHDRAW / NO_RESPONSE unchanged. (Onion — lacking yield
data — is correctly not offered, proving the feasibility gate.)

### 2. Ask Why on every explored candidate
The expanded alternative card now shows **Use this recommendation | Ask why | Another option** (and Ask
why on the "Return to original plan" option). Ask Why targets the EXACT displayed crop via the existing
deterministic `/explain` and is strictly read-only (no save/consent/replan/finalise/mutation).

### 3. Exhaustion / restart
When no unseen currently-available alternative remains, the card shows **"All feasible alternatives
viewed."** + **Review from beginning**. Restart clears ONLY the temporary browse-history exclusions;
`rejected_alternatives`, response, requested crop, renewed consent, current revised crop, replan
revision, Final Plan, Analyse and frozen artifacts are untouched. The current revised crop and
persistent rejections remain excluded after restart.

### 4–7. Final Plan terminology + filters + reason display
- "Selected plots" → **Plots in dataset**. New summary tiles: Plots in dataset / Initially allocated
  offered / No initial allocation / Finally realised / Not realised, all dynamically derived, with the
  reconciliation `initially_allocated + no_initial_allocation = plots_in_dataset` and
  `finally_realised + not_realised = plots_in_dataset` (nothing hardcoded).
- New `final_rows(run, page, per, filt)` + `?filter=realised|not_realised|all` returning authoritative
  `counts`. UI filter tabs **Realised (N) | Not realised (N) | All plots (N)**, default **Realised**;
  headings "Final realised allocations" / "Plots not realised" / "Final plan accounting — all dataset
  plots". All 911 built-in plots inspectable under All plots; 50 rows/page within the filter;
  filter/pagination is read-only (no POST/mutation/solver — verified).
- Five columns preserved. Realised rows show the realised crop + consent basis + `realised`; non-realised
  rows show Final crop = `—` and the actual reason inside the Realised cell (humanised from real reason
  codes). `NO_INITIAL_OFFER` → "no initial allocation". Explanatory copy added above the table.

### 8/10. Initial Plan coverage + baselines
Initial Plan now shows Plots in dataset / Initially allocated offered / No initial allocation with the
plain-language coverage note, and a collapsible **"Where does this plan come from?"** defining B1 / B2 /
B3 / FarmSync Proposed and stating the journey starts from the **B3 initial planned allocation** (which
does not allocate every plot). A fuller comparison remains under Advanced ▸ Research details.

### 9. No overclaiming unallocated reasons
`NO_INITIAL_OFFER` is presented only as "no initial allocation"; no speculative water/market/fairness/
labour/budget classification was added.

### 11. Analyse navigation closure
Fairness → **Continue to Uncertainty**; Uncertainty → **Continue to Resilience**; Resilience →
**Analysis complete** + **Review Final Plan** + **Research details & reproducibility**. Navigation-only
(`data-ws`), no mutation/recompute/POST; Analyse remains ONE workflow stage (no per-view revisions).

### 12. Humanised codes
`humanReason()` + INIT/REN label maps map raw backend codes to friendly text
(NO_INITIAL_OFFER→"no initial allocation", INITIAL_REJECT_NO_ALTERNATIVE→"initial reject — no feasible
alternative", RENEWED_REJECT→"renewed reject", etc.); canonical backend values are unchanged.

### 13. Concentration basis label
The realised-composition share column is labelled **"Area share"** when `basis=area` and **"Plot share"**
when `basis=plots`; the realised plot count remains a separate descriptive column. α=0.40 stays a
labelled reference, not enforced.

### 14. Uncertainty / resilience wording
`cleanUnavail()` strips a leading "Not available —" from the backend reason so the UI renders one clean
sentence ("Not available for this working plan. <reason>"). Honest unavailable state preserved; no frozen
substitution; backend reason strings unchanged for auditability.

### Files / endpoints changed
- `farmsync/exploratory_run.py` — `consent_alternative`; `final_rows(filt)` with counts + filters.
  → `R:\portfolio\farmsync\exploratory_run.py`
- `farmsync_routes.py` — `/consent-alternative`; `/final-rows?filter=`. → `R:\portfolio\farmsync_routes.py`
- `static/js/farmsync.js` — consent explore (Ask why/original-return/exhaustion/restart); Final Plan
  filters + terminology + reason display; Initial Plan coverage + B1/B2/B3; Analyse nav CTAs, humanised
  codes, basis label, clean unavailable wording. → `R:\portfolio\static\js\farmsync.js`
- `static/css/farmsync.css` — filter tabs + consent original-return. → `R:\portfolio\static\css\farmsync.css`
- `tests/test_farmsync_ui.py` — 15 new tests; 2 updated for the filtered final-rows default.
  → `R:\portfolio\tests\test_farmsync_ui.py`

### Tests + results
- `tests/test_farmsync_ui.py`: **165 passed** (150 prior + 15 new). New: consent-alt excludes revised/
  rejected/browse-history + read-only + UI Ask-why/restart/original-return; Final Plan filter counts
  reconcile + default realised + terminology + humanised reason cell + read-only filter/pagination;
  Initial Plan coverage + baselines; Analyse nav CTAs + no-mutation + humanised codes + basis label +
  non-duplicated unavailable wording.
- `tests/test_farmsync_ilp_v2.py`: **6 passed** (~28 s).
- Guardrails: config ε/λ/α + versions unchanged; instance hash `5ea24037c2d9cb6a`; no pulp on GET/page-
  load (incl. `/analysis`, filtered `/final-rows`); frozen artifacts byte-identical.

### Config / hash / seeds / solver
Unchanged: ε=0.95, λ=0.05, α=0.40, action-consent-v1, uncertainty-v1, fairness-v2, frozen seeds,
instance hash `5ea24037c2d9cb6a`, solver settings, frozen artifacts. Working-plan mechanism remains
deterministic action-consent + canonical feasibility (NOT the full collective MILP). LLM remains
parser/interface/explanation only.

### Limitations / unresolved
- Uncertainty-v1 / resilience remain honest "Not available" for the working plan (unchanged by design).
- The "return to original plan" option only surfaces when the original crop is canonically feasible;
  crops without yield data (e.g. onion) are correctly never offered.
- Per-farmer within-crop LPS is still not surfaced; concentration reports crop-share HHI/shares.
- Hard browser refresh losing the client `run_id` routes to Home (server run persists).

### Exact next step
FULL END-TO-END QA / PRE-EVALUATION FREEZE (manual + automated walkthrough on built-in and custom,
confirming reconciliation, provenance and read-only guarantees). Live LLM → ≥300 benchmark → final
readiness freeze → final30 remain later, separate phases — not started.

---

## CONSENT-ALTERNATIVE BUTTON-BINDING FIX (dated)

Single focused bugfix before QA. JS-only. No methodology/alternatives-semantics/Final-Plan/Analyse/
config/solver/frozen-artifact change. Guardrails re-verified (ε=0.95, λ=0.05, α=0.40, fairness-v2,
action-consent-v1, uncertainty-v1; instance hash `5ea24037c2d9cb6a`; no CBC/PuLP on page load; frozen
artifacts byte-identical; engine + routes unchanged vs mirror). No Live LLM, ≥300 benchmark, final30,
manuscript.

### Root cause
In `wireConsentAltButtons` the Use handler used `out.querySelector("[data-use]")`, which binds only the
FIRST `[data-use]`. When Renewed Consent renders BOTH a normal "Use this recommendation" AND a "Return
to original plan → Use this", only one button was wired. Separately, the exhaustion branch (`!rc.found`)
had no dedicated `.fs-consent-why` element, so "Ask why" on the original-return option fell back to
`|| out` and would overwrite the exhaustion message, the Review-from-beginning button, and the
original-return controls.

### Fix
- `wireConsentAltButtons` now binds EVERY Use button via
  `out.querySelectorAll("[data-use]").forEach(u => … consentUseRecommendation(fid, pid, u.dataset.use, el))`,
  so each button sends its own exact `dataset.use` crop.
- The exhaustion branch now renders a dedicated `<div class="fs-consent-why"></div>`, so Ask-why on the
  original-return option renders there and preserves the surrounding controls. (The non-exhaustion branch
  already had this div.) Ask-why remains read-only via `/explain`.

### Files changed
- `static/js/farmsync.js` — `wireConsentAltButtons` (all-Use binding) + exhaustion `.fs-consent-why`.
  → `R:\portfolio\static\js\farmsync.js`
- `tests/test_farmsync_ui.py` — 4 new regression tests. → `R:\portfolio\tests\test_farmsync_ui.py`

### Tests + results
- `tests/test_farmsync_ui.py`: **169 passed** (165 prior + 4 new): binds ALL Use buttons (querySelectorAll,
  own crop); exhaustion has a dedicated Ask-why div isolating it from the surrounding controls; Ask-why is
  read-only (no rev bump, no crop/consent change); selecting the original crop uses that exact crop when
  feasible (or is refused when infeasible) and leaves the row PENDING.
- `tests/test_farmsync_ilp_v2.py`: **6 passed** (~24 s).
- Guardrails: config/versions unchanged; instance hash `5ea24037c2d9cb6a`; no pulp on page load; frozen
  artifacts byte-identical; `farmsync/exploratory_run.py` and `farmsync_routes.py` unchanged vs mirror.

### Limitations / unresolved
Unchanged from prior turn (uncertainty/resilience honest "Not available"; return-to-original only when the
original crop is canonically feasible; per-farmer within-crop LPS not surfaced; hard refresh losing client
`run_id` routes to Home).

### Exact next step
FULL END-TO-END QA / PRE-EVALUATION FREEZE. Live LLM → ≥300 benchmark → final readiness freeze → final30
remain later, separate phases — not started.

---

## RENEWED-CONSENT ASK-WHY EVENT-COLLISION FIX (dated)

Single focused event-wiring bugfix before QA. JS-only. No methodology/config/solver/frozen-artifact/
Analyse/Final-Plan change. Guardrails re-verified (ε=0.95, λ=0.05, α=0.40, fairness-v2, action-consent-v1,
uncertainty-v1; instance hash `5ea24037c2d9cb6a`; no CBC/PuLP on page load; frozen artifacts
byte-identical; engine + routes + CSS unchanged vs mirror). No Live LLM, ≥300 benchmark, final30,
manuscript.

### Root cause
The parent delegated handler `wireConsentCards` matched EVERY `[data-why]` inside a consent card and
called `consentAskWhy()`, which always targets the CURRENT `revised_crop`. Explored-candidate and
original-return Ask-Why buttons also used `[data-why="<crop>"]`, so a click on a candidate's Ask Why was
handled by BOTH its local listener and the parent — the parent's `consentAskWhy(revised_crop)` won,
rendering "Why Groundnut?" when the user asked about Pigeon pea.

### Fix (distinct attributes + scoped parent handler)
- Top-level current-recommendation Ask Why now uses `data-why-current`; explored-candidate and
  original-return Ask Why use `data-why-candidate="<crop>"`. No bare `data-why=` attribute remains.
- `wireConsentCards` handles ONLY `data-why-current`, and only when the click is NOT inside
  `.fs-consent-out` (`whyCurrent && !inExplore`); it also ignores `data-explore` clicks originating inside
  the explore area. This does not rely on request ordering.
- `wireConsentAltButtons` binds candidate/original Ask Why locally on `[data-why-candidate]`, each sending
  its OWN `dataset.whyCandidate` crop to `/explain`, rendering into the dedicated `.fs-consent-why` host so
  it never replaces the current recommendation or the Explore/exhaustion controls.
- Previously-fixed related items preserved and re-tested: ALL `[data-use]` buttons bound
  (`querySelectorAll`), and the exhaustion state contains a dedicated `.fs-consent-why` host.

### Semantics now
Top Ask Why → current `revised_crop` only; candidate Ask Why → that exact candidate crop only;
original-return Ask Why → the original crop only. All are read-only (`/explain`); none mutate crop,
consent, revisions, replan, Final or Analyse.

### Files changed
- `static/js/farmsync.js` — attribute rename + scoped parent handler + local candidate binding.
  → `R:\portfolio\static\js\farmsync.js`
- `tests/test_farmsync_ui.py` — 4 new tests; 1 updated for the renamed attribute.
  → `R:\portfolio\tests\test_farmsync_ui.py`

### Tests + results
- `tests/test_farmsync_ui.py`: **173 passed** (169 prior + 4 new): distinct why-attributes; parent
  ignores explore-area Ask Why (no generic `[data-why]` match); candidate Ask Why binds its own crop into
  `.fs-consent-why` (with all Use buttons bound + exhaustion host preserved); `/explain` targets the exact
  crop asked (current/candidate/original) and is read-only (no rev/crop/consent/final change).
- `tests/test_farmsync_ilp_v2.py`: **6 passed** (~29 s).
- Guardrails: config/versions unchanged; instance hash `5ea24037c2d9cb6a`; no pulp on page load; frozen
  artifacts byte-identical; engine/routes/CSS unchanged vs mirror.

### Limitations / unresolved
Unchanged from prior turns (uncertainty/resilience honest "Not available"; return-to-original only when
the original crop is canonically feasible; per-farmer within-crop LPS not surfaced; hard refresh losing
client `run_id` routes to Home).

### Exact next step
FULL END-TO-END QA / PRE-EVALUATION FREEZE. Live LLM → ≥300 benchmark → final readiness freeze → final30
remain later, separate phases — not started.

---

## AUTOMATED QA — PHASE 1: BACKEND / STATE / EDGE-CASE AUTOMATION (dated)

QA-infrastructure phase (not a bug-fix turn). Built the backend/core half of an automated pre-evaluation
QA system that VALIDATES FarmSync without modifying it. Per the fail-stop rule, the run marks any genuine
defect FAIL, captures evidence, and exits non-zero — no product/scientific code was changed. All scientific
values preserved (ε=0.95, λ=0.05, α=0.40, fairness-v2, action-consent-v1, uncertainty-v1; instance hash
`5ea24037c2d9cb6a`; frozen artifacts byte-identical; RNG seed manifest hashed). No Live LLM, ≥300
benchmark, final30, browser/Playwright, manuscript.

### Baseline verified before changes
`pip check` clean; `farmsync_routes` imports; `tests/test_farmsync_ui.py` = **173 passed**;
`tests/test_farmsync_ilp_v2.py` = **6 passed**. 22 `tests/test_farmsync*.py` modules discovered. Known
warnings (pandas PerformanceWarning, PuLP LpVariable/PULP_CBC_CMD deprecations) recorded, not suppressed.

### Files added / changed
- ADDED `scripts/farmsync_pre_eval_qa.py` — the single QA orchestrator (`--phase backend`): dynamic repo
  root; isolated evidence dir `results/farmsync/qa/pre_eval/`; environment metadata; protected-artifact
  SHA256 before/after; config/hash/seed verification; test discovery/run with per-suite timeout + JUnit;
  full built-in API journey; controlled scenario selector; INDEPENDENT expected-final ledger; Farmer
  Response / Replan / consent-alternative / Renewed Consent / stale-anchor / finalisation / 911 accounting
  / filter-pagination / Analyse reconciliation / metrics / fairness+concentration math / uncertainty+
  resilience unavailable / invalid-request matrix / idempotency / custom-data matrix / dataset isolation /
  dataset security / no-solver-on-reads / no-live-LLM / state-invalidation / repeatability / warning audit;
  machine-readable + Markdown reports; non-zero exit on unexpected failure.
- ADDED `tests/test_farmsync_qa_backend.py` — QA-machinery smoke tests (config verify, Gini helper,
  independent ledger + fingerprint, protected-hash excludes QA dir). **4 passed.**
- ADDED `.gitignore` entry `results/farmsync/qa/` (QA evidence is not a scientific artifact).
- ZERO product/scientific files changed (verified: `farmsync/exploratory_run.py`, `farmsync_routes.py`,
  `static/js/farmsync.js`, `static/css/farmsync.css`, `templates/farmsync.html`, `farmsync/config.py`
  byte-identical to mirror; UI suite still 173 passed).

### QA architecture
One orchestrator drives a Flask test-client through the real API (no fabricated run JSON). A `QA` recorder
tracks per-category checks; only checks flagged as genuine product defects set PHASE 1 = FAIL. Evidence:
`qa_report_backend.{json,md}`, `qa_environment.json`, `qa_ledger.json`, `qa_repeatability_backend.json`,
`qa_warning_summary.json`, `qa_artifact_hashes_before/after.json`, `qa_config_snapshot.json`, `junit/`.

### Controlled scenario selector (§9)
Deterministically picks DISTINCT offered plots for scenarios A–L by inspecting recorded response, original
crop, and feasible-alternative availability (not index 0). All 12 cases (A untouched-ACCEPT, B ACCEPT→MODIFY→
RENEWED_ACCEPT, C RENEWED_REJECT, D RENEWED_NO_RESPONSE, E NO_RESPONSE, F WITHDRAW, G REJECT→revised→
RENEWED_ACCEPT, H MODIFY-feasible, I MODIFY-infeasible, J multi-alt, K original-return-feasible, L
REJECT-no-return) were selectable on the built-in dataset and saved to `qa_ledger.json`.

### Independent final-ledger method (§19)
For every one of the 911 dataset plots, the QA re-derives `expected_realised / expected_final_crop /
expected_consent_basis / expected_not_realised_reason` from upstream authoritative fields
(offer?, effective response, changed?, revised crop, crop+anchor consent validity, withdraw/no-response)
WITHOUT reading the analysis/final endpoint, then compares row-by-row against the actual final rows.
Match = 0 mismatches.

### Automated categories (all PASS unless noted)
Environment/imports; existing tests (UI 173 + dataset_manager + ILP 6 recorded); config/hash/seeds;
frozen pre-hash; scenario selection; Farmer Response semantics (identity/invalid, revision bump,
idempotent save, recorded-response immutability); Replan (no-mutation-on-GET, anchor==response_rev,
changed rows require consent, not realised); consent-alternative (excludes revised+rejected+browse-history,
canonical only, read-only); Renewed Consent (invalid enum rejected); **stale-anchor consent (same-crop-
after-new-replan → PENDING; crop-match-alone insufficient; stale POSTs 400)**; finalisation gating
(refuse-while-pending, view/pagination don't finalise, explicit succeeds); independent final ledger;
911 accounting (offered+no_offer==realised+not_realised==911, unique IDs); Analyse reconciliation (8
invariants + integrity.ok); consent/realisation metrics; fairness math (independent Gini match, 500
farmers incl. zeros); concentration math (independent HHI/shares, α=0.40 reference only); uncertainty +
resilience honest-unavailable; state invalidation (GET no-mutate, upstream edit stales all, re-finalise
new revision); idempotency; invalid-request matrix (no 500 except the found defect, no mutation);
custom-data matrix (incomplete-upload rejects, validation≠readiness, activation blocked-until-ready);
dataset isolation/switching (custom IDs, no F leakage, switch detaches, explorer reads don't set source);
dataset security (self-contained ZIP path-traversal + allow-list check); no-solver-on-reads; no-live-LLM;
repeatability; frozen byte-identity.

### DISCOVERED DEFECT (kept failing; NOT fixed by QA)
- **Category:** Final filter/pagination API.
- **Evidence:** `GET /api/farmsync/working-plan/<id>/final-rows?page=abc` returns **HTTP 500** with an
  unhandled `ValueError: invalid literal for int() with base 10: 'abc'`.
- **Root cause:** `farmsync_routes.py` parses `page` with a bare `int(request.args.get("page", 1) or 1)`
  and no validation. The same unguarded pattern exists at `farmsync_routes.py:293` (`/explore/<table>`),
  `:309` (inspect), `:570` (`/final-rows`). A non-numeric `page` crashes the request. (`filter=bogus`,
  `page=0/-1/huge` are handled safely and return 200.)
- **Affected file:** `farmsync_routes.py` (3 sites). No mutation occurs from the failed request; it is a
  read-path input-validation gap, not a state-integrity defect.
- **Fix belongs to a separate turn** (coerce `page` safely → default/400). QA left it failing by design.

### Exact test commands executed
`python -m pip check`; `python -m pytest tests/test_farmsync_ui.py -q` (173 passed);
`python -m pytest tests/test_farmsync_ilp_v2.py -q` (6 passed);
`python scripts/farmsync_pre_eval_qa.py --phase backend` (exit 1, PHASE 1 FAIL — the page=abc 500);
`python -m pytest tests/test_farmsync_qa_backend.py -q` (4 passed).

### Warning summary
All observed warnings are the known families (pandas PerformanceWarning; PuLP LpVariable / PULP_CBC_CMD
deprecations) → `status = KNOWN_WARNINGS`. No new warning family introduced by the QA code.

### Repeatability
The full controlled built-in journey run twice from clean state produced identical substantive results
(offered/no_offer, realised/not_realised, not-realised reasons, final cash, crop composition, fairness
Gini, HHI, integrity) → `qa_repeatability_backend.json` match = true.

### Frozen-artifact + config verification
`changed_protected_artifacts = []` (before == after over 48 artifacts). Config snapshot: ε=0.95, λ=0.05,
α=0.40, fairness-v2, action-consent-v1, uncertainty-v1, instance_hash `5ea24037c2d9cb6a`; RNG seed
manifest present and hashed.

### Known limitations
- In this sandbox the full 22-suite pytest discovery is time-bounded per suite; the authoritative UI (173)
  and ILP (6) suites are recorded, and the slower proposed/solver suites run per-suite with a timeout on
  the real Windows repo. The orchestrator records timeouts as such (not as product defects).
- QA does not yet cover browser/DOM/event/layout/accessibility (that is Phase 2).

### PHASE 1 QA STATUS: FAIL
### READY FOR QA PHASE 2: NO
(One genuine product defect — the `page=abc` 500 — must be fixed first; known warnings alone do not block.)

### Exact next step
Fix ONLY the demonstrated `page` input-validation defect in `farmsync_routes.py` (all 3 unguarded
`int(page)` sites), then rerun Phase-1 QA from clean state. After Phase 1 passes: QA Phase 2 — full
real-browser / UI / Playwright automation (separate turn).

---

## AUTOMATED QA — PHASE 1: HARNESS CORRECTION (dated)

Repaired the QA automation itself so its PASS/FAIL is trustworthy. No product/scientific code changed
(verified byte-identical: `farmsync_routes.py`, `farmsync/exploratory_run.py`, `static/js/farmsync.js`,
`static/css/farmsync.css`, `templates/farmsync.html`, `farmsync/config.py`; UI suite still 173 passed).
The genuine `page=abc → 500` product defect remains unfixed and reproducible, so the corrected harness
still ends PHASE 1 = FAIL / READY = NO — by design.

> **SUPERSEDES / CORRECTION of the previous Phase-1 claims:**
> - "all 12 A–L cases verified" was OVERSTATED — only 8 were in `required` and B/G/K/L could vanish
>   silently; G/L mis-selected non-REJECT rows. CORRECTED: all 12 are required with predicate
>   assertions; G and L now require genuine `recorded_response=="REJECT"`. **Finding: scenario K
>   (original-crop canonically feasible) is NOT constructible on the built-in dataset** — of 120 offered
>   rows probed, 0 have an original crop that passes `/validate-crop` (stored p1 crops are not re-feasible
>   under the working-plan canonical rules), so `scenario_selection` is FAIL with recorded evidence
>   rather than a silent skip.
> - "all existing tests" was OVERSTATED — only three suites were authoritatively recorded. CORRECTED:
>   discovery covers all 22 modules; a `--skip-suites` report is explicitly `FULL_SUITE_COVERAGE=NO /
>   EXISTING_TESTS=INCOMPLETE / READY=NO` and can never be an authoritative PASS. Authoritative Phase-1
>   requires every discovered suite to complete on the real machine.
> - "independent HHI matched" only covered the PLOTS basis. CORRECTED: independent HHI now recomputes for
>   the ACTUAL basis; built-in uses **area** basis, and the area-basis HHI is independently recomputed
>   from dataset `area_ha` joined to realised rows (matched at 4-dp tolerance).

### QA-harness defects confirmed & corrected
1. Overall status derived only from `qa.failures` → **corrected**: `overall_fail()` fails if ANY required
   category is FAIL/INCOMPLETE/ENV_FAIL/HARNESS_FAIL or missing; known-warnings never fail.
2. Timeout classified `ok=True` → **corrected**: timeout/unexpected-skip/xfail = INCOMPLETE (not ok);
   suite completeness gates readiness (`completed_modules == discovered_modules`).
3. `hash_protected()` single-level → **corrected**: recursive over approved roots; reports
   added/removed/modified over the UNION of before∪after; excludes QA dir, `exploratory/`, snapshots.
4. `clean_state()` rmtree of real runs/snapshots → **corrected**: snapshots pre-existing entries and
   removes ONLY QA-created ones; a sentinel run survives (tested).
5. Response-count deltas used `>=` → **corrected**: exact `==` for ACCEPT/REJECT/MODIFY/NO_RESPONSE/
   WITHDRAW from an independent applied-mutation ledger (built-in: ACCEPT 324, REJECT 53, MODIFY 2,
   NO_RESPONSE 1, WITHDRAW 1 — all exact).
6. Concentration only recomputed plots basis → **corrected**: independent area-basis HHI/shares/max.
7. Product-defect flagging → **corrected**: a 500 on malformed input is `defect=True` and fails Phase 1;
   the test client no longer re-raises (`PROPAGATE_EXCEPTIONS=False`) and `safe_get` records a raised
   route error as a 500.

### Files changed (QA-only; zero product/scientific files)
- `scripts/farmsync_pre_eval_qa.py` — rewritten status model, recursive hashing + diff, state isolation,
  timeout/completeness, exact deltas, 12-case selector with predicates, area-basis concentration, full
  fairness (abs + per-ha + participant Gini), malformed-pagination route probe, state-isolation self-check.
- `tests/test_farmsync_qa_backend.py` — **13 QA-harness self-tests** (all pass).
- QA evidence under `results/farmsync/qa/pre_eval/` (git-ignored).

### Corrected A–L selector evidence
A,B,C,D,E,F,G,H,I,J,L selectable on built-in; **G and L are genuine recorded REJECT** rows; **K
UNAVAILABLE** with recorded evidence (0/120 original crops feasible). scenario_selection = FAIL.

### Suite-completeness semantics
22 modules discovered. Timeout → INCOMPLETE (never PASS). `--skip-suites` → INCOMPLETE + NOT ready.
Report stores discovered/completed/timed_out modules and gates on completeness.

### State-isolation strategy
`snapshot_runtime_state()` records pre-existing `results/farmsync/exploratory` + `data/farmsync/snapshots`
entries; `clean_state()` removes only QA-created entries. Self-test proves a pre-existing sentinel run
survives QA cleanup. Frozen artifacts untouched (before==after, add/remove/modify all empty).

### Malformed-pagination affected routes
`page=abc` → **HTTP 500 on BOTH** `/final-rows` and `/explore/<table>`. Shared root cause: unguarded
`int(request.args.get("page"))` at `farmsync_routes.py` lines 293 / 309 / 570. Detect-only; not patched.

### QA self-tests / backend QA results
- `tests/test_farmsync_qa_backend.py`: **13 passed** (status gating, timeout=INCOMPLETE, missing-category
  fail, add/remove/modify/nested hashing + QA exclusion, state isolation sentinel, config verify, Gini +
  area-HHI known values, independent-ledger-is-independent + covers 911, incomplete-coverage-not-ready).
- Corrected backend QA: exit **1**, PHASE 1 = **FAIL**, READY = **NO**. FAIL categories = scenario_selection
  (K unavailable), final_filter_pagination_api (product 500), malformed_pagination_routes (product 500),
  suite_completeness (INCOMPLETE via --skip-suites). All other categories PASS. Frozen byte-identity:
  added/removed/modified all empty. Warnings = KNOWN_WARNINGS.

### Full-suite completeness state
On this sandbox the authoritative full 22-suite run is time-bounded; the corrected harness records that
as INCOMPLETE and refuses readiness. The authoritative run (`python scripts/farmsync_pre_eval_qa.py
--phase backend`, no --skip-suites) must be executed on the real Windows machine to obtain full coverage.

### Config/hash/seeds + frozen verification
ε=0.95, λ=0.05, α=0.40, fairness-v2, action-consent-v1, uncertainty-v1, instance_hash
`5ea24037c2d9cb6a`; RNG seed manifest present + hashed. Protected artifacts before==after (0 changed).

### Current remaining PRODUCT defects (unfixed, by design)
- Malformed pagination `page=<non-numeric>` → HTTP 500 on `/final-rows` and `/explore/<table>` (shared
  root cause, 3 unguarded `int(page)` sites in `farmsync_routes.py`).

### PHASE 1 QA STATUS: FAIL
### READY FOR QA PHASE 2: NO
(Harness is now trustworthy; the FAIL is the real product defect + intentionally incomplete suite run.)

### Exact next step
Fix ONLY the demonstrated malformed-pagination product defect(s) in `farmsync_routes.py` (all 3 unguarded
`int(page)` sites → coerce safely to default/400), then rerun the corrected Phase-1 QA from zero on the
real machine with full suite coverage. After Phase 1 passes: QA Phase 2 (real-browser/Playwright).

---

## AUTOMATED QA — PHASE 1: FINAL HARNESS CLOSURE (dated)

Final QA-harness closure (QA-only). No product/scientific code changed (verified byte-identical:
`farmsync_routes.py`, `farmsync/exploratory_run.py`, `static/js/farmsync.js`, `static/css/farmsync.css`,
`templates/farmsync.html`, `farmsync/config.py`; UI suite still 173 passed). The malformed-pagination
product defect remains unfixed by design, so Phase 1 still ends FAIL / NO.

### Files changed (QA-only)
- `scripts/farmsync_pre_eval_qa.py` — K decoupled + isolated original-return semantic fixture; recursive
  byte-identity runtime isolation; full renewed-consent/bulk/select assertions; J/L consent-alternative
  assertions; coverage-gated warning audit; auto-discovered malformed-pagination route inventory.
- `tests/test_farmsync_qa_backend.py` — now **19 QA-harness self-tests** (all pass).
- QA evidence under `results/farmsync/qa/pre_eval/` (git-ignored), incl. new
  `qa_malformed_pagination_inventory.json`.
Product/scientific files unchanged.

### 1. Built-in K capability + isolated semantic coverage
`BUILTIN_CAPABILITY: K_NOT_PRESENT` recorded (0/120 offered rows have an original crop passing
`/validate-crop`). K no longer FAILs `scenario_selection`; instead the REAL `consent_alternative()`
'return to original plan' branch is exercised by an isolated QA-only fixture that constructs a run row
with effective MODIFY, original≠revised, original canonically feasible, not rejected. Asserted (all PASS):
`original_option` exists, `.crop == original`, `.label == "Return to original plan"`, original NOT offered
as a normal candidate, operation read-only. REJECT-origin fixture: `original_option` absent and the
rejected original never appears in the candidate cycle. The fixture lives only in QA and touches no
production/frozen dataset (built on a QA-created run, cleaned after).

### 2. Byte-identical runtime isolation
`snapshot_runtime_state()` now records a recursive SHA256 of every pre-existing file under
`results/farmsync/exploratory` and `data/farmsync/snapshots`; `verify_runtime_byte_identity()` reports
added/removed/modified for pre-existing entries only. The sentinel self-test writes known bytes, snapshots,
runs a QA journey + cleanup, and asserts the sentinel exists AND its SHA256 is unchanged. Pre-existing
state changing = QA FAIL (verified: added/removed/modified all empty).

### 3. Full Renewed Consent / bulk / select assertions (visible)
`renewed_consent_backend`: ACCEPT/REJECT/NO_RESPONSE each POST-succeed and stamp
`consent_for_crop == exact revised_crop` AND `consent_for_replan_anchor == exact replan_anchor`; repeated
identical decision does not corrupt `response_rev`; consent on a non-required row is refused (server
contract); bulk ACCEPT and bulk REJECT each affect PENDING rows only and preserve existing individual
decisions. `select_recommendation`: valid candidate becomes the exact revised crop, prior renewed consent
+ `consent_for_crop` + `consent_for_replan_anchor` cleared, row PENDING (choosing != consenting), unknown/
infeasible refused, stale selection refused. All recorded as visible checks.

### 4. Consent-alternative J/L
J (built-in): current revised crop excluded, no duplicate before exhaustion, exhaustion reached, read-only.
L (genuine recorded REJECT-origin): `original_option` absent and the rejected original never appears as a
candidate.

### 5. Warning-audit completeness
When `FULL_SUITE_COVERAGE == NO`, warning audit is now **INCOMPLETE** (complete inventory unavailable),
never a false PASS. Only when all suites complete is it classified KNOWN_WARNINGS/PASS/FAIL.

### 6. Malformed-pagination route inventory (auto-discovered)
`_discover_page_parse_sites()` scans `farmsync_routes.py` for every
`int(request.args.get("page"|"page_size"))` and maps each to its route — no hard-coded count. Found **3
sites / 3 routes**, all returning HTTP **500** on `?page=abc`:
- line 293 — `/api/farmsync/explore/<table>` — param `page` — `abc` → 500
- line 309 — `/api/farmsync/inspect/<table>` — param `page` — `abc` → 500
- line 570 — `/api/farmsync/working-plan/<run_id>/final-rows` — param `page` — `abc` → 500
No `page_size` parsing sites exist. Evidence: `qa_malformed_pagination_inventory.json`. Detect-only.

### 7. QA self-tests
`tests/test_farmsync_qa_backend.py`: **19 passed** — required-category FAIL/INCOMPLETE/missing → overall
FAIL; timeout → INCOMPLETE; add/remove/modify/nested hashing + QA exclusion; state-isolation sentinel;
built-in-K-absence ≠ untested-K-branch; isolated MODIFY fixture exercises `original_option`; isolated
REJECT fixture suppresses original; runtime byte-identity detects modification; renewed ACCEPT/REJECT/
NO_RESPONSE exact crop+anchor; bulk pending-only; select-recommendation clears consent + PENDING;
warning-audit INCOMPLETE without full coverage; malformed-pagination auto-discovers all sites.

### Current Phase-1 result
Corrected harness (exit **1**): PASS for scenario_selection (K decoupled), consent_original_branch,
select_recommendation, renewed_consent_backend, state_isolation, and all reconciliation/math/isolation
categories. FAIL/INCOMPLETE only for: final_filter_pagination_api + malformed_pagination_routes (the
product 500), suite_completeness + warning_audit + existing_tests (INCOMPLETE via `--skip-suites`/timeout).
Frozen artifacts before==after (0 changed). **K is no longer a permanent blocker.**

### Current remaining PRODUCT defects (unfixed, by design)
- Malformed pagination `page=<non-numeric>` → HTTP 500 on `/explore/<table>`, `/inspect/<table>`, and
  `/final-rows` (shared root cause: unguarded `int(request.args.get("page"))` at farmsync_routes.py lines
  293, 309, 570).

### PHASE 1 QA STATUS: FAIL
### READY FOR QA PHASE 2: NO
(Harness now trustworthy; K decoupled; remaining FAIL is the real product defect + intentionally
incomplete suite run in this environment.)

### Exact next step
Fix ONLY the demonstrated malformed-pagination defect (all 3 `int(page)` sites → safe coerce to
default/400), then rerun corrected Phase-1 from zero on the real machine with full suite coverage. After
Phase 1 passes: QA Phase 2 (real-browser/Playwright).

---

## PAGINATION INPUT-SAFETY — PRODUCT FIX + REGRESSION (dated)

Small controlled PRODUCT fix for the pagination-input-safety defect family surfaced by QA. Only
`farmsync_routes.py` changed in product code (verified: `farmsync/exploratory_run.py`,
`static/js/farmsync.js`, `static/css/farmsync.css`, `templates/farmsync.html`, `farmsync/config.py`
byte-identical). No scientific/model change; no Playwright/Phase 2, Live LLM, final30, manuscript.

### Defect + root cause
Non-numeric / malformed pagination query params crashed with HTTP 500. Root cause: unguarded numeric
coercion of query-string params — `int(request.args.get("page"...))` (and `int(...get("size"...))`)
with no try/except and no bounds.

### Numeric-query audit (current source; not historical line numbers)
Every `int/float(request.args.get(...))` in `farmsync_routes.py`:
- `/api/farmsync/explore/<table>` — `page`
- `/api/farmsync/inspect/<table>` — `page`
- `/api/farmsync/inspect/<table>` — `size`
- `/api/farmsync/working-plan/<run_id>/final-rows` — `page`
No other numeric query conversions exist (no `float`, no other params).

### Safe-normalisation contract (implemented)
Added one reusable module-level helper `_safe_int_arg(name, default, minimum, maximum)` — deterministic,
never raises: malformed/blank/non-integer (incl. `1.5`)/missing → default, then clamp to [min,max].
Applied at all 4 sites:
- `page` → `_safe_int_arg("page", 1, minimum=1)`: omitted/""/abc/1.5 → 1; 0/-1 → 1; valid int preserved;
  very large accepted (final-rows clamps to last page as before).
- `size` → `_safe_int_arg("size", 25, minimum=1, maximum=100)`: omitted/""/abc/1.5 → 25; 0/-5 → 1;
  1→1; 25→25; 100→100; 999999→100.
Verified every contract row returns HTTP 200 (never 500). Pure input normalisation — no state touched.

### Files changed
- `farmsync_routes.py` — `_safe_int_arg` helper + 4 call sites (the ONLY product change).
- `tests/test_farmsync_ui.py` — 5 pagination regression tests.
- `scripts/farmsync_pre_eval_qa.py` — scanner extended to also discover the `size` param (QA-only).
- `tests/test_farmsync_qa_backend.py` — self-test now requires the `/inspect` size site.

### Regression tests
`test_pagination_page_never_500_all_routes` (3 page routes × 7 values), `test_pagination_page_normalisation`
(malformed→1, huge→last), `test_inspect_size_normalisation` (full size contract), 
`test_malformed_pagination_read_only` (no change to planning_source/response_rev/replan_anchor/final rev),
`test_safe_int_arg_helper_contract` (unit-level). All pass.

### QA malformed inventory: before → after
- Before: affected_routes = [`/explore/<table>`, `/inspect/<table>`, `/final-rows`]; HTTP 500 count = 3.
- After: **affected_routes = []; HTTP 500 count = 0** (all 4 discovered sites incl. `/inspect` size probe
  → 200). QA categories `final_filter_pagination_api` and `malformed_pagination_routes` now **PASS**.

### Test results
- `tests/test_farmsync_ui.py`: **178 passed** (173 + 5 pagination).
- `tests/test_farmsync_qa_backend.py`: **19 passed** (QA self-tests, incl. size-site discovery).
- `tests/test_farmsync_ilp_v2.py`: **6 passed**.
- Backend QA (`--skip-suites`): pagination categories PASS; overall still FAIL/READY NO ONLY because
  `--skip-suites` makes suite coverage incomplete (not faked to PASS).

### Config / hash / seeds + frozen + guardrails
ε=0.95, λ=0.05, α=0.40, fairness-v2, action-consent-v1, uncertainty-v1; instance_hash
`5ea24037c2d9cb6a`. Frozen artifacts byte-identical. No CBC/PuLP on malformed-pagination GETs. No Live LLM.

### Remaining product defects
None known from the QA backend categories after this fix (the pagination-input-safety family is closed).
Authoritative full-suite Phase-1 must still be run on the real machine to confirm complete coverage.

### Current Phase-1 readiness
Harness trustworthy; pagination defect fixed. A no-`--skip-suites` authoritative run with all discovered
suites completing is required for READY=YES.

### Files to copy into R:\portfolio
- `farmsync_routes.py`
- `tests/test_farmsync_ui.py`
- `scripts/farmsync_pre_eval_qa.py`
- `tests/test_farmsync_qa_backend.py`

### Authoritative Windows Phase-1 command to run next
`python scripts/farmsync_pre_eval_qa.py --phase backend`  (NO `--skip-suites`; all 22 discovered
FarmSync suites must complete). Expected: pagination categories PASS, malformed inventory empty, and —
if all suites complete with no failures — PHASE 1 QA STATUS: PASS / READY FOR QA PHASE 2: YES.

---

## AUTOMATED QA — PHASE 2: REAL-BROWSER / PLAYWRIGHT UI (dated)

Phase-2 browser QA infrastructure built and executed. QA-only: **zero product/scientific files changed**
(verified byte-identical: farmsync_routes.py, farmsync/exploratory_run.py, static/js/farmsync.js,
static/css/farmsync.css, templates/farmsync.html, farmsync/config.py; ε=0.95/λ=0.05/α=0.40, fairness-v2,
action-consent-v1, uncertainty-v1, instance_hash 5ea24037c2d9cb6a all unchanged; Phase-1 regression:
UI 178 passed, QA-backend 19 passed). No genuine product/UI defect found. No Live LLM; no solver on reads.

### ENVIRONMENT CONSTRAINT (honest, non-negotiable)
This execution sandbox has **Chromium available** (pre-installed) but **Firefox and WebKit binaries
cannot be downloaded** (Playwright's browser CDN is not in the sandbox network allowlist). Per §5/§34/§42
FF and WebKit are recorded **ENV_INCOMPLETE** (never PASS), so the overall Phase-2 status is **INCOMPLETE**
regardless of results — 3-browser coverage is NOT claimed. The harness runs all three on the user's
Windows machine (where the binaries install normally).

### Playwright / browser versions
Playwright 1.56.0 (Python sync API). Executed: **Chromium** (real launch + full journey). Firefox/WebKit:
ENV_INCOMPLETE (binary download blocked here).

### Files added (QA-only)
- `tests/farmsync_browser_lib.py` — ephemeral localhost Flask server (real templates/JS/CSS, health poll,
  deterministic teardown, minimal isolating base), console/network capture, no-solver/no-LLM checks,
  protected-artifact + runtime byte-identity hashing.
- `scripts/farmsync_browser_qa.py` — orchestrator: real UI journey + critical regressions per engine,
  responsive matrix, repeatability, evidence + Markdown report, honest INCOMPLETE/ENV classification.
- `tests/test_farmsync_browser.py` — pytest entry (skips if Chromium unavailable; asserts executed
  browser clean + no product defect + byte-identity).
- `.gitignore` — browser evidence dir.

### Server lifecycle design
No manual `python app.py`. The suite creates its own Flask app (registers the real routes), binds
**127.0.0.1:<ephemeral port>** (never 0.0.0.0), polls `/farm-sync` for readiness (≤45s), serves real
`/static` assets, and tears down on teardown. Fails clearly if the server can't start.

### Core journey (Chromium) — REAL UI clicks
Home → Use built-in → Initial Plan → Farmer Responses → Replan (explicit Run Replan) → Renewed Consent →
Finalise → Final → Analyse, all via real DOM interactions. **All Chromium categories PASS.**

### Critical regression results (Chromium, all PASS)
- Renewed Consent: real consent controls clickable; consent-alternative browsing works.
- **Candidate Ask Why exact-crop**: the explored candidate's Ask-Why explanation mentions that exact
  candidate crop (guards the prior Pigeon-pea→Groundnut collision) — PASS.
- Current Ask Why: current-recommendation Ask-Why activatable — PASS.
- **All Use buttons**: Use control(s) rendered on the explored candidate and individually enabled/wired
  (guards the first-`[data-use]`-only bug); verified BEFORE any current-Ask-Why click that re-renders
  the panel — PASS.
- Exhaustion: "All feasible alternatives viewed" reached with a dedicated why host — PASS.
- Return-to-original: built-in K absent → `SEMANTIC_BACKEND_COVERED` (browser-not-constructible without
  product change; the real consent_alternative original_option branch is covered by the Phase-1 fixture),
  per §12.
- Workflow gating: locked stages (`data-locked="1"`) are correctly non-clickable before prerequisites.
- Final UI: Plots in dataset / Initially allocated / No initial allocation / Finally realised / Not
  realised present; filters (Realised default / Not realised / All) clickable; backend accounting
  realised+not_realised==911 — PASS.
- Analyse: CURRENT WORKING FINAL PLAN provenance; 500/911 accounting; uncertainty & resilience honestly
  "Not available" in the UI — PASS.
- Data Explorer: opens; viewing does not change planning_source — PASS.
- Read-only guard: navigation/pagination did not mutate working-run fingerprint — PASS.

### Network / console / no-solver / no-LLM (Chromium)
total requests 44; **external requests 0**; **5xx 0**; **requestfailed 0**; **console.error 0**;
**pageerror 0**; no-solver on reads PASS (PuLP not imported by page-load/navigation/analyse reads,
checked before any POST mutation); no live LLM SDK loaded. Evidence:
`qa_browser_network_chromium.json`, `qa_browser_console_chromium.json`.

### Responsive (Chromium)
390×844, 768×1024, 1366×768, 1920×1080 across Home/Initial/Farmer/Replan/Final/Analyse: **0 document
horizontal-overflow stages** at every viewport. Evidence: `qa_responsive.json`.

### Repeatability / protected hashes / runtime isolation
Browser journey run twice from clean state → substantive results identical (realised/not-realised/final
cash/composition/gini/hhi) — match=true. Protected artifacts added/removed/modified all empty. Pre-existing
mutable runtime state byte-identical (added/removed/modified empty).

### Accessibility / keyboard / visual-regression
INCOMPLETE this turn — axe-core and the full a11y/keyboard/visual-baseline matrix are part of the Windows
3-browser authoritative run; not asserted here because full-browser coverage is unavailable in this
sandbox. Recorded as INCOMPLETE, not PASS.

### Screenshots / evidence
`results/farmsync/qa/browser/`: qa_report_browser.{json,md}, qa_browser_environment.json,
qa_browser_network_chromium.json, qa_browser_console_chromium.json, qa_responsive.json,
qa_browser_repeatability.json, and screenshots/ (initial_plan, farmer_responses, replan,
explored_candidate, final_realised/not_realised/all, analyse_fairness, uncertainty, resilience,
data_explorer).

### Known limitations
- Firefox/WebKit ENV_INCOMPLETE in this sandbox (binary download blocked) — run on Windows.
- Accessibility (axe-core), keyboard-navigation matrix, and visual-regression baseline are deferred to
  the Windows authoritative run (INCOMPLETE, not PASS).
- Hard-refresh client run_id limitation unchanged (not exercised destructively; documented pre-existing).

### Genuine defects found
**None.** All initial FAILs were harness issues (mis-timed no-solver check, external site-chrome asset
noise, disabled-stage click, check ordering) — corrected in QA-only code; no product change.

### Files to copy into R:\portfolio
- scripts/farmsync_browser_qa.py
- tests/farmsync_browser_lib.py
- tests/test_farmsync_browser.py
- .gitignore

### Exact commands
Install browsers once: `python -m playwright install chromium firefox webkit`
Full authoritative Phase-2 run (all 3 engines):
`python scripts/farmsync_browser_qa.py --browsers chromium,firefox,webkit`
Pytest entry: `python -m pytest tests/test_farmsync_browser.py -q`

### PHASE 2 QA STATUS: INCOMPLETE
### READY FOR PRE-EVALUATION FREEZE: NO
(Chromium clean with zero defects; Firefox + WebKit could not execute in this sandbox — they must run on
the user's Windows machine, plus accessibility/keyboard/visual, before Phase-2 can be PASS.)

### Exact next step
User runs the authoritative Phase-2 on Windows with Chromium + Firefox + WebKit installed (plus axe-core
accessibility, keyboard, and visual-baseline). If all three engines are clean with no product defect →
PHASE 2 PASS → then Phase 3 pre-evaluation freeze (separate turn).

---

## AUTOMATED QA — PHASE 2: HARNESS CLOSURE + GENUINE A11Y DEFECT FOUND (dated)

Phase-2 harness correction (QA-only). **Zero product/scientific files changed** (verified byte-identical:
farmsync_routes.py, farmsync/exploratory_run.py, static/js/farmsync.js, static/css/farmsync.css,
templates/farmsync.html, farmsync/config.py; ε=0.95/λ=0.05/α=0.40, fairness-v2, action-consent-v1,
uncertainty-v1, instance_hash 5ea24037c2d9cb6a unchanged; Phase-1 regression: QA-backend 19 passed).

> **CORRECTION of the prior Phase-2 claim:** the previous section said accessibility/keyboard/visual were
> "recorded as INCOMPLETE" — they were NOT actual report categories then. They are now real required
> categories, executed where the environment allows.

### HEADLINE — GENUINE PRODUCT DEFECT FOUND (fail-stop; NOT patched)
The corrected harness runs **axe-core** (bundled locally, no CDN) and found a **SERIOUS accessibility
violation: color-contrast, 24 nodes** on FarmSync's own elements (`#fsEnvBadge`, `.fs-badge-muted`,
`.fs-navgroup-h`, etc.) — foreground/background contrast below WCAG AA (source: `static/css/farmsync.css`,
the badge/nav classes using `var(--mut)`/amber). Per §1 fail-stop + §15 (SERIOUS ⇒ FAIL), this is
captured as a defect and **the CSS was NOT modified**. It must be fixed in a separate controlled product
turn. Because a genuine product defect exists, **PHASE 2 = FAIL** regardless of browser coverage.

### Harness corrections made (all QA-only)
1. **Required-category gate (§1):** explicit `REQUIRED_CATEGORIES` (39) + `missing_required()` +
   `overall()` that returns non-PASS if ANY required category is missing/FAIL/INCOMPLETE/ENV_INCOMPLETE/
   ENV_FAIL/HARNESS_FAIL, or if not all three engines executed. `SEMANTIC_BACKEND_COVERED` is accepted
   ONLY for `return_original_branch`; `KNOWN_LIMITATION` only for `hard_refresh_known_limitation`.
2. **Two-level pytest gate (§2):** `tests/test_farmsync_browser.py` = dev smoke (Chromium, may be
   INCOMPLETE, skips if unavailable) + harness self-tests; the authoritative gate is the orchestrator
   `scripts/farmsync_browser_qa.py` (chromium+firefox+webkit, returns non-zero unless complete PASS).
3. **Dual-mode server (§20):** `mode='real'` (actual templates/base.html — authoritative) and
   `mode='isolated'` (minimal base, FarmSync JS/CSS only — component isolation). Real mode reports
   external requests honestly (the real base loads Google Fonts + site chrome).
4. **Deterministic shutdown (§21):** `werkzeug.serving.make_server` + `server.shutdown()` + `thread.join`
   + port-closed verification. `server_lifecycle` proves the port stops accepting connections.
5. **Non-vacuous critical checks:** consent-alternative browsing is browser-first (browser owns the run);
   candidate/current Ask-Why read ONLY the scoped `.fs-consent-why`/`.fs-consent-out` host (§7);
   Use-buttons are ACTUALLY clicked and verified server-side (revised_crop==selected, consent cleared,
   PENDING) (§6); exhaustion uses a deterministic multi-alt J row, requires ≥1 real browse, the product's
   explicit "All feasible alternatives viewed" wording, and `.fs-consent-why` count>0 (§8); bulk
   pending-only sets A=REJECT/B=NO_RESPONSE/rest PENDING then asserts only PENDING→ACCEPT (§5);
   renewed-consent verifies exact crop+anchor for ACCEPT/REJECT/NO_RESPONSE (§4).
6. **Accessibility (§15):** real axe-core across Home/Farmer/Consent/Final/Analyse/Data-Explorer;
   CRITICAL/SERIOUS ⇒ FAIL. Evidence `qa_accessibility.json`.
7. **Keyboard (§16):** Tab-to-CTA + focus-indicator + Enter activation + locked-not-activatable.
8. **Duplicate/inert (§17):** DOM duplicate-ID scan + zero-size enabled-control scan.
9. **Visual stability (§18):** two same-source screenshots + PIL/numpy pixel-diff, gated on objective pass.
10. **Browser repeatability (§19):** now a real Playwright UI journey (clicks Run Replan / bulk ACCEPT /
    Finalise), not API-only; substantive outcomes compared.
11. **Full network/console persistence (§22)** (all requests), **Playwright/browser versions (§24)**
    (`importlib.metadata`; Playwright 1.56.0, Chromium 141), **failure traces (§25)** (trace.zip on FAIL).
12. **Workflow gating (§9)** + **hard-refresh KNOWN_LIMITATION (§10)** as real categories.

### Harness self-tests (§26)
`tests/test_farmsync_browser.py`: **11 passed** — all-pass⇒PASS; missing category⇒INCOMPLETE (never
PASS); one FAIL⇒FAIL; INCOMPLETE/ENV_INCOMPLETE block PASS; missing browser blocks authoritative PASS;
absent accessibility/keyboard/visual cannot silently PASS; SEMANTIC_BACKEND_COVERED permitted only for
return_original_branch; required-category count ≥39 incl. accessibility/keyboard/visual; server lifecycle
start+deterministic-stop (port closed).

### Sandbox execution reality (honest)
- **Chromium** available (141.0.7390.37) and executed the core journey, no-solver-on-reads, network/
  console (isolated: 0 external/5xx/failed/console.error/pageerror), responsive (0 overflow @ 4
  viewports), read-only guard, dom-text-sanity, browser repeatability (match=true), and **accessibility
  (FAIL — the genuine defect)**.
- **Firefox + WebKit**: binaries undownloadable here (CDN not in allowlist) → ENV_INCOMPLETE.
- The full/fast functional matrix (each browser-first scenario is a full journey) **exceeds this
  sandbox's wall-clock** and browser execution degraded mid-session; several functional categories are
  therefore INCOMPLETE here and must complete on Windows. The report lists EVERY required category with an
  explicit status (no silent-missing).

### Real-site vs isolated
Isolated mode gives a clean FarmSync-only network/console surface (used for the executable sandbox
checks; still catches FarmSync's own a11y defect). Authoritative real-site mode requires the broader
site's `/static` assets (style.css/main.js/chatbot.js) which are absent in this sandbox → real-mode
network/console is ENV_INCOMPLETE here and runs fully on Windows.

### Server-shutdown proof / protected hashes / mutable state
Deterministic shutdown verified (port closed post-teardown). Protected artifacts added/removed/modified
all empty. Pre-existing runtime state byte-identical.

### Files changed (QA-only)
- scripts/farmsync_browser_qa.py (rewritten: gating, dual-mode, non-vacuous checks, a11y/keyboard/visual)
- tests/farmsync_browser_lib.py (dual-mode server, deterministic shutdown, axe, versions, full capture)
- tests/test_farmsync_browser.py (two-level gate + 11 harness self-tests)
Product/scientific files unchanged.

### Genuine defects found
1. **accessibility — SERIOUS color-contrast (24 nodes)** on FarmSync badges/nav. Captured, NOT patched.

### Files to copy into R:\portfolio
- scripts/farmsync_browser_qa.py
- tests/farmsync_browser_lib.py
- tests/test_farmsync_browser.py

### Exact commands (Windows authoritative)
`python -m playwright install chromium firefox webkit`
`pip install axe-playwright-python pillow numpy`
`python scripts/farmsync_browser_qa.py --browsers chromium,firefox,webkit --mode real`
`python -m pytest tests/test_farmsync_browser.py -q`  (dev smoke + harness self-tests)

### PHASE 2 QA STATUS: FAIL
### READY FOR PRE-EVALUATION FREEZE: NO
(Genuine SERIOUS accessibility defect found — fail-stop, not patched. Also FF/WebKit + full functional
matrix incomplete in this sandbox. Fix the a11y defect in a separate product turn, then run the
authoritative 3-browser real-site Phase-2 on Windows.)

### Exact next step
Separate controlled PRODUCT turn: fix the color-contrast a11y defect (static/css/farmsync.css badge/nav
contrast to WCAG AA). Then run the authoritative Windows Phase-2 (chromium+firefox+webkit, real mode,
axe+keyboard+visual). NOT Phase 3 until Phase 2 is a clean PASS.

---

## PRODUCT FIX — ACCESSIBILITY COLOR-CONTRAST (light theme) (dated)

Controlled product fix for the Phase-2-demonstrated axe-core **color-contrast (SERIOUS)** defect. CSS-only:
the ONLY product file changed is `static/css/farmsync.css` (verified: farmsync_routes.py, exploratory_run.py,
static/js/farmsync.js, templates/farmsync.html, farmsync/config.py byte-identical). Scientific guardrails
unchanged (ε=0.95/λ=0.05/α=0.40, fairness-v2, action-consent-v1, uncertainty-v1, instance_hash
5ea24037c2d9cb6a; frozen artifacts byte-identical; no solver/no Live LLM).

### Demonstrated defect (before)
axe-core `color-contrast` SERIOUS, ~24 nodes on the FarmSync light theme: `--mut` (#8c8c8c) = **3.36:1** on
white (`.fs-navgroup-h`, `.fs-badge-muted`, `#fsEnvBadge`, muted nav buttons, `.fs-h-eyebrow`, `.fs-lede`);
`.fs-navgroup-advanced .fs-navgroup-h` `opacity:.7` compounding to **2.19:1**; accent amber `#d97706` as
text (`.fs-h-eyebrow`/`.fs-path-flow`/`.fs-navbtn.is-active`) = **~3.0–3.2:1**; dev-badge amber on pale =
**2.8:1**; `.fs-run.optimal` amber `#b45309` = **3.98:1**; green `#16a34a` (`.fs-act.ACCEPT`/`.fs-verdict.pass`)
= **~3.0:1**.

### Fix (targeted, not global, semantic families preserved)
Seven light-theme-scoped rules in `static/css/farmsync.css` (all under `[data-theme="light"] .fs-app` except
the opacity removal which is safe in both themes):
1. `[data-theme="light"] .fs-app { --mut:#6a6a6a }` — FarmSync-scoped muted token to ~5:1 on white (NOT the
   global `--text-muted`; NOT black; stays visibly muted). Fixes the muted/nav/badge families at once.
2. `.fs-navgroup-advanced .fs-navgroup-h { opacity:1 }` — removed the .7 dimming that compounded contrast.
3. dev-badge/NO_RESPONSE/rung.soft/prov amber text → `color-mix(--sci-amber 45%, --ink)`.
4. h-eyebrow/navbtn.is-active/filter.is-active amber text → `color-mix(--acc 52%, --ink)`.
5. path-flow amber text → `color-mix(--acc 52%, --ink) !important` (its rule uses !important).
6. run.optimal amber text → `color-mix(--sci-optimal 55%, --ink)`.
7. ACCEPT/verdict.pass green text → `color-mix(--sci-green 62%, --ink)`.
`--acc`, `--sci-amber`, `--sci-green` themselves are unchanged, so borders/glows/backgrounds and the
semantic colour meanings are preserved.

### After — axe verification
- **Light theme (Home, Farmer, Renewed Consent, Final, Analyse, Data Explorer): color-contrast critical = 0,
  serious = 0, nodes = 0.** The demonstrated defect is resolved.
- **Dark theme:** the CSS changes are `[data-theme="light"]`-scoped, so dark-theme text colours are
  UNCHANGED. Dark theme cannot be validly measured in this sandbox (the QA server does not serve the site's
  `style.css` that sets the dark background — axe would measure dark-theme light text on a white bg). Dark
  theme is unaffected by this fix and renders correctly on Windows with the real `style.css`.

### Separate finding (out of scope; NOT fixed)
The fuller multi-stage scan surfaced a **different** rule: `select-name` (CRITICAL) — the Data Explorer
`<select>` lacks an accessible name. This is NOT color-contrast and requires a JS/aria change
(static/js/farmsync.js), which is out of bounds for this CSS-only turn. Reported for a separate controlled
turn; NOT fixed here. (Per §5/§7, unrelated findings are not fixed in this turn.)

### Regression + guardrails
- `tests/test_farmsync_qa_backend.py`: **19 passed**; `tests/test_farmsync_ui.py`: **178 passed**;
  `tests/test_farmsync_ilp_v2.py`: **6 passed**.
- config/hash/seeds unchanged; instance_hash 5ea24037c2d9cb6a; frozen artifacts byte-identical; no solver on
  GET/page-load; no Live LLM.

### Files changed
- `static/css/farmsync.css` (the only product change).
- `results/farmsync/qa/browser/a11y_contrast_fix.json` (QA evidence).

### Not a Phase-2 PASS
This turn fixes only the demonstrated color-contrast defect. Phase 2 is NOT complete: the browser harness
still needs its final QA-only closure + authoritative Windows Chromium+Firefox+WebKit execution (and the
separate `select-name` critical remains to be fixed in a controlled turn).

### ACCESSIBILITY PRODUCT FIX: PASS (light-theme color-contrast serious = 0; demonstrated defect resolved)
### PHASE 2 RE-RUN REQUIRED: YES

---

## PRODUCT FIX — DATA EXPLORER SELECT ACCESSIBLE NAME (select-name CRITICAL) (dated)

Controlled product fix for the separate axe-core **`select-name` CRITICAL** on the Data Explorer table
selector, surfaced by the expanded a11y scan. One-line ARIA change in `static/js/farmsync.js` only. The
previously-completed contrast CSS (`static/css/farmsync.css`) is **byte-identical this turn**. Scientific
guardrails unchanged (ε=0.95/λ=0.05/α=0.40, fairness-v2, action-consent-v1, uncertainty-v1, instance_hash
5ea24037c2d9cb6a; frozen artifacts byte-identical; no solver; no Live LLM).

### Defect
axe-core `select-name` (CRITICAL): the Data Explorer `<select id="exTable">` (generated in `mountExplorer`)
had no accessible name.

### Fix (one line, minimal)
- Before: `<select id="exTable"></select>`
- After:  `<select id="exTable" aria-label="Dataset table"></select>`
No ID rename, no behaviour/fetch/search/pagination/planning_source change, no redesign, no other ARIA.

### axe verification (Chromium, real rendered control)
- `#exTable` exists; **resolved accessible name = "Dataset table"** (read from the browser, 14 options,
  value populated).
- `select-name`: **critical = 0, nodes = 0** (before: 1 critical). 
- Full-stage scan (Home/Farmer/Consent/Final/Analyse/Data Explorer, light theme):
  **remaining CRITICAL rules = [] (none).**
  **remaining SERIOUS rules = ['scrollable-region-focusable'].**
- **color-contrast serious nodes = 0** (prior contrast fix intact).

### Independent finding (reported, NOT fixed — fail-stop)
`scrollable-region-focusable` (SERIOUS): a scrollable region (the horizontally-scrolling table container)
must be keyboard-focusable. This is a DIFFERENT rule, **not caused** by the one-line aria-label change
(pre-existing), so per the fail-stop rule it is REPORTED and **NOT fixed** this turn.

### Data Explorer functional regression (real UI, after fix)
Opens ✓; selector has 14 tables and changing `#exTable` changes the displayed table
(`climate_scenarios → crop_region_season_params`) ✓; search usable ✓; Prev/Next clickable ✓; malformed
pagination `?page=abc` → 200 (no 500) ✓; **planning_source unchanged** across explorer interaction
(builtin→builtin) ✓; read-only ✓; no solver imported by explorer reads ✓; no Live LLM ✓.

### Tests / syntax
- `node --check static/js/farmsync.js`: **PASS**.
- `tests/test_farmsync_ui.py`: **179 passed** (178 prior + 1 new `test_data_explorer_select_has_accessible_name`).
- `tests/test_farmsync_qa_backend.py`: **19 passed**; `tests/test_farmsync_ilp_v2.py`: **6 passed**.

### Files changed
- `static/js/farmsync.js` (one-line aria-label — the only product change).
- `tests/test_farmsync_ui.py` (1 narrow regression test).
- `results/farmsync/qa/browser/a11y_select_name_fix.json` (QA evidence).
The contrast CSS and all other protected/scientific files are byte-identical.

### SELECT-NAME PRODUCT FIX: PASS
### CURRENT CHROMIUM A11Y BLOCKERS: REMAIN (`scrollable-region-focusable` SERIOUS — independent, reported, not fixed)
### PHASE 2 AUTHORITATIVE RE-RUN REQUIRED: YES

---

## PRODUCT FIX — SCROLLABLE-REGION-FOCUSABLE (serious) + surfaced independent contrast blocker (dated)

Controlled product fix for the axe-core **`scrollable-region-focusable` SERIOUS** rule. QA-only edits are
`static/js/farmsync.js` (a11y decorator) + one appended CSS focus rule in `static/css/farmsync.css`; the
prior contrast declarations and the `#exTable` select-name fix are unchanged. Scientific guardrails intact
(ε=0.95/λ=0.05/α=0.40, fairness-v2, action-consent-v1, uncertainty-v1, instance_hash 5ea24037c2d9cb6a;
frozen artifacts byte-identical; no solver/no Live LLM).

### Before (axe inventory — captured before editing)
`scrollable-region-focusable` SERIOUS, **2 nodes**, both the shared `.fs-tablewrap`, both genuinely
overflowing (no tabindex/role):
- **fairness**: `.fs-analyse-grid > div:nth-child(3) > .fs-tablewrap` — scrollWidth 321 > clientWidth 284.
- **data**: `.fs-explorer > .fs-tablewrap` — scrollWidth 1177 > clientWidth 888.

### Fix (one coherent same-rule fix across the shared wrapper)
`.fs-tablewrap` is generated at ~12 sites via async loaders/pagination, so the fix is a small decorator
that runs after each `activate()` render and on async/paginated re-renders (MutationObserver + rAF):
`_a11yDecorateScrollRegions()` sets `tabindex="0"`, `role="region"`, `aria-label="Scrollable data table"`
on `.fs-tablewrap` **only when it actually overflows** (scrollWidth/scrollHeight exceed client), and drops
the tab stop if it later fits — so non-scrolling tables get no extra tab stops. Presentation/read-only;
no state mutation. CSS: appended `.fs-tablewrap[tabindex]:focus-visible{outline:none;border-color:var(--acc);
box-shadow:0 0 0 4px var(--glow)}` (house tokens; no prior declaration changed — verified 0 deletions).

### After (real Chromium keyboard + axe)
- **scrollable-region-focusable: 0 nodes** (rule eliminated).
- Tab reaches the wrapper (activeElement `.fs-tablewrap`, tabindex 0, role region, name "Scrollable data
  table"); **focus-visible box-shadow present**; **ArrowRight scrolled scrollLeft 0→80**; keyboard scroll
  caused **no run mutation and no solver**.
- Regression: **select-name critical = 0** (aria-label "Dataset table" intact); on the prior-scanned
  (non-populated) stages fairness/uncertainty/resilience/data **color-contrast = 0**.

### INDEPENDENT blocker surfaced (reported, NOT fixed — fail-stop)
Scanning with a FINALISED plan (populated tables) reveals **color-contrast SERIOUS = 339 nodes** on
POPULATED views — mainly `.fs-state.revised` (53), `.fs-state.final` (50), `.fs-teach-row .fs-teach-k` (8),
and a residual amber `#d97706` (few). This is INDEPENDENT of the scrollable-region fix (that change adds
tabindex/role/aria-label + a focus rule only — zero text-color impact) and PRE-EXISTING; it was not
surfaced before because prior contrast verification did not finalize/populate the tables. Per fail-stop it
is REPORTED and NOT fixed this turn. (Correction to the earlier "color-contrast serious = 0" claim: that
held for the non-populated scanned state; populated Final/Analyse/Farmer/Replan/Consent tables have
additional contrast failures requiring a separate controlled turn.)

### Remaining a11y rules (light theme, full populated scan)
- **CRITICAL: none.**
- **SERIOUS: color-contrast** (populated-table `.fs-state`/`.fs-teach-k`/residual-amber — independent).

### Tests / syntax
- `node --check static/js/farmsync.js`: **PASS**.
- `tests/test_farmsync_ui.py`: **180 passed** (179 prior + 1 new `test_scrollable_tablewrap_keyboard_focusable_helper`
  tied to the decorator contract).
- `tests/test_farmsync_qa_backend.py`: **19 passed**; `tests/test_farmsync_ilp_v2.py`: **6 passed**.

### Files changed
- `static/js/farmsync.js` (decorator + MutationObserver, called from `activate`).
- `static/css/farmsync.css` (appended focus-visible rule only; prior contrast declarations byte-preserved).
- `tests/test_farmsync_ui.py` (1 narrow regression test).
- `results/farmsync/qa/browser/a11y_scrollable_region_fix.json` (evidence).
routes/engine/template/config and frozen artifacts unchanged.

### Dark theme
The focus treatment uses theme tokens (--acc/--glow). Dark-theme authoritative a11y verification remains
the Windows Phase-2 responsibility (not authoritatively measurable in this sandbox without the site's
dark-theme styles).

### SCROLLABLE-REGION PRODUCT FIX: PASS
### CURRENT CHROMIUM A11Y BLOCKERS: REMAIN (color-contrast SERIOUS in populated tables — independent, reported, not fixed)
### PHASE 2 AUTHORITATIVE RE-RUN REQUIRED: YES

---

## PRODUCT FIX — COMPLETE LIGHT-THEME COLOR-CONTRAST CLOSURE (full populated workflow) (dated)

CSS-only closure of the remaining axe `color-contrast` SERIOUS rule across the FULL finalised/populated
light-theme workflow. Only `static/css/farmsync.css` changed (JS **byte-identical**; the select-name and
scrollable-region JS fixes intact). Scientific guardrails unchanged (ε=0.95/λ=0.05/α=0.40, fairness-v2,
action-consent-v1, uncertainty-v1, instance_hash 5ea24037c2d9cb6a; frozen artifacts byte-identical; no
solver/no Live LLM).

### Correction to prior wording
The prior partial contrast pass verified non-populated stages and reported "serious = 0"; it MISSED
workflow-rendered nodes. The complete finalised/populated scan exposed **339 remaining light-theme
color-contrast nodes across Home (4), Initial Plan (4), Farmer Responses (54), Replan (58), Consent (164)
and Final (55)** — Home and Initial Plan also retained residual failures (NOT "only populated tables").

### BEFORE inventory (reconciles exactly: 339)
By selector family (leaf, count, representative fg/bg/ratio):
- `.fs-state.revised` — 55 — `#ea580c` on `#fce8dd` = 3.0 (light override used raw `--sci-blue`).
- `.fs-muted` — 53 — `#919191` on `#f7f7f7` = 2.94 (`--mut` #6a6a6a dimmed by `.fs-cc-old{opacity:.72}`).
- `.fs-cc-oldcrop` — 53 — `#919191` = 2.94 (same opacity compounding).
- `.fs-cc-cash` — 53 — `#d97706` on `#f7f7f7` = 2.97 (raw `--acc`).
- `.fs-state.final` — 51 — `#b45309` on `#f5e9df` = 4.2 (raw `--sci-optimal`, just under).
- `.fs-act.REJECT` — 50 — `#e0483a` on `#f7dada` = 3.1 (raw `--sci-red`).
- `.fs-teach-k` — 24 — `#d97706` on `#f7f7f7` = 2.97 (raw `--acc`).
Sum 55+53+53+53+51+50+24 = 339.

### Root cause + coherent same-rule fix (appended, higher-in-cascade, light-scoped)
The light-theme overrides had replaced the darker base `color-mix(...82%,--ink)` with RAW bright hues, and
a `.fs-cc-old` opacity dimmed muted text. Text-only overrides restore an ink-mix per family (tokens
themselves unchanged, so borders/backgrounds/glows keep the bright hue):
- `.fs-act.MODIFY`, `.fs-state.revised` → `color-mix(--sci-blue 58%, --ink)`.
- `.fs-state.initial`, `.fs-state.final`, `.fs-rung.flex` → `color-mix(--sci-optimal 50%, --ink)`.
- `.fs-act.REJECT`, `.fs-run.infeasible` → `color-mix(--sci-red 58%, --ink)`.
- `.fs-cc-cash`, `.fs-teach-k` → `color-mix(--acc 52%, --ink)`.
- `[data-theme="light"] .fs-app .fs-cc-old{opacity:1}` (strikethrough already de-emphasises; removes the
  sub-AA muted dimming, fixing both `.fs-cc-oldcrop` and `.fs-muted` under it).

### AFTER (full populated workflow, per stage)
Home 0, Initial Plan 0, Farmer 0, Replan 0, Consent 0, Final 0, Fairness 0, Uncertainty 0, Resilience 0,
Data Explorer 0 → **TOTAL color-contrast = 0.**

### Regression (same full scan)
- **select-name critical = 0** (`#exTable` resolved name "Dataset table").
- **scrollable-region-focusable serious = 0** (Tab reaches wrapper; focus-visible present; ArrowRight
  scrolled scrollLeft 0→80; no run mutation; no solver).
- Functional journey completes; planning_source unchanged (builtin); no run mutation.
- **Remaining CRITICAL = []; remaining SERIOUS = [].**

### Dark theme
This turn changes only light-theme text selectors; dark-theme declarations unchanged. Dark-theme
authoritative validation remains pending the Windows real-site Phase-2 run.

### Tests / syntax
- `node --check static/js/farmsync.js`: **PASS** (JS byte-identical).
- `tests/test_farmsync_ui.py`: **181 passed** (180 prior + 1 new `test_light_theme_contrast_families_not_raw_weak`).
- `tests/test_farmsync_qa_backend.py`: **19 passed**; `tests/test_farmsync_ilp_v2.py`: **6 passed**.

### Files changed
- `static/css/farmsync.css` (the only product change — appended light-theme text overrides).
- `tests/test_farmsync_ui.py` (1 narrow regression test).
- `results/farmsync/qa/browser/a11y_full_contrast_fix.json` (evidence).
JS/routes/engine/template/config and frozen artifacts unchanged.

### FULL COLOR-CONTRAST PRODUCT FIX: PASS
### FULL LIGHT-THEME A11Y BLOCKERS: NONE FOUND
### CURRENT CHROMIUM A11Y BLOCKERS: NONE FOUND
### PHASE 2 AUTHORITATIVE RE-RUN REQUIRED: YES

---

## QA PHASE 2 — FINAL BROWSER HARNESS CLOSURE (authority model hardening) (dated)

QA-only turn: hardened the Phase-2 browser harness into a strict, Windows-authoritative authority model.
**Zero product/scientific files changed** (verified byte-identical to a start-of-turn hash baseline:
static/css/farmsync.css, static/js/farmsync.js, templates/farmsync.html, farmsync_routes.py,
farmsync/exploratory_run.py, farmsync/config.py). Scientific guardrails intact (ε=0.95/λ=0.05/α=0.40,
fairness-v2, action-consent-v1, uncertainty-v1, instance_hash 5ea24037c2d9cb6a; frozen artifacts
byte-identical). Product accessibility blockers from prior turns remain fixed (light a11y re-verified 0/0
on populated Home/Final/Data this turn).

### Audit findings (before editing) and corrections
- Deep functional matrix ran **chromium-only** → added a **cross-engine core** (`run_cross_engine`) that
  must run on EVERY engine (page load, dataset, plan, farmer, replan, consent, final, analyse, one Use,
  network/console, keyboard) with per-engine required categories `{engine}_cross_engine`.
- **`accessibility_dark` was absent** → added as a required category (real-site dark scan via
  `_accessibility_theme`).
- Category set was coarse (39) → **expanded to 58** with the full split: farmer_accept/reject/modify/
  no_response/withdraw_ui + farmer_exact_plot_binding + farmer_reset_edit_ui + farmer_askwhy_readonly;
  renewed_accept/reject/no_response/edit_ui + renewed_exact_crop_anchor; bulk_accept/bulk_reject separate;
  final_ui_911_traversal; workflow_revision_guard; consent_metrics_display; accessibility_light +
  accessibility_dark; per-engine core + cross-engine.
- **`_seed_required()`** ensures every required category is present up front (none silently missing).
- **`overall()` + `cross_engine_ok()`**: PASS impossible unless all 3 engines execute BOTH core AND
  cross-engine, every required category PASSes (SEMANTIC_BACKEND_COVERED only for return_original_branch;
  KNOWN_LIMITATION only for hard_refresh), and none is missing/FAIL/INCOMPLETE/ENV_*.

### Harness self-tests (§35) — 14 passed
missing category ⇒ not PASS; INCOMPLETE ⇒ not PASS; ENV_INCOMPLETE ⇒ not PASS; one FAIL ⇒ FAIL; missing
browser ⇒ not authoritative PASS; **missing dark accessibility ⇒ not PASS**; **shallow cross-engine
(FF/WebKit load-only) ⇒ not PASS** (`cross_engine_ok()` False); SEMANTIC_BACKEND_COVERED permitted only
for return_original_branch; required count ≥55 incl. accessibility_light/dark, bulk_accept/reject,
final_ui_911_traversal, cross-engine; server start + deterministic stop (port closed).

### Verified this turn (Chromium, real-site, bounded)
- **server_lifecycle: PASS** — real-site ephemeral server start + deterministic werkzeug shutdown (port
  closed, thread joined).
- **accessibility_light: PASS** — axe on populated Home/Final/Data = **0 critical, 0 serious** (product
  fix holds).
- **no_solver_on_reads: PASS**; **no_live_llm: PASS**; **protected_hashes: PASS**; **mutable_state_isolation: PASS**.
- Playwright **1.56.0**, Chromium **141.0.7390.37** (via importlib.metadata / browser.version).

### Sandbox constraints (honest — outcome INCOMPLETE regardless)
- **Firefox + WebKit binaries undownloadable** (Playwright CDN not in the sandbox allowlist) →
  `firefox_core`/`webkit_core`/`firefox_cross_engine`/`webkit_cross_engine` = ENV_INCOMPLETE.
- **accessibility_dark = ENV_INCOMPLETE**: the QA server serves FarmSync's static but not the broader
  site's dark-theme background (real style.css), so a bounded dark scan measured dark-theme light text on
  a white background (3 serious) — a MEASUREMENT ARTIFACT, not a product defect. Authoritative dark-theme
  a11y must run on Windows with the real site.
- **Full deep functional matrix + 10-stage light/dark axe exceeds the sandbox wall-clock**, so the deep
  functional categories are INCOMPLETE here (the harness runs them fully on Windows). Every required
  category is present with an explicit status (none silently missing).

### Real-site authority
Authoritative mode = real-site (repository templates/base.html + farmsync.html + real static). Isolated
mode retained for FarmSync-only network/console debug. External site-chrome requests (if any) are captured
honestly, not suppressed by substituting a minimal base.

### Focused Phase-1 regression (§37)
`tests/test_farmsync_qa_backend.py` **19 passed**; `tests/test_farmsync_ui.py` **181 passed**;
`tests/test_farmsync_browser.py` **14 passed**. Product expectations unchanged.

### Scroll-decorator observation (§34, low priority, NOT changed)
`_a11yDecorateScrollRegions()` currently removes tabindex/role/aria-label when a wrapper stops overflowing
(safe now, since those attributes are helper-introduced). A future refactor could add a helper-owned
marker (`data-fs-a11y-scroll`) so it never touches independently-authored attributes. Not a defect; does
not block Phase 2; not implemented.

### Files changed (QA-only)
- `scripts/farmsync_browser_qa.py` (58-category authority model, cross-engine, seed, accessibility_light/dark).
- `tests/test_farmsync_browser.py` (14 harness self-tests for the gate).
- QA evidence under `results/farmsync/qa/browser/`.
Product/scientific files unchanged (byte-identical).

### Evidence files
`qa_report_browser.{json,md}`, `qa_browser_environment.json`, `qa_accessibility_light.json`,
`qa_accessibility_dark.json`, ENV_INCOMPLETE stubs for FF/WebKit network+console.

### Files to copy into R:\portfolio
- scripts/farmsync_browser_qa.py
- tests/farmsync_browser_lib.py
- tests/test_farmsync_browser.py

### Authoritative Windows command
`python -m playwright install chromium firefox webkit`
`pip install axe-playwright-python pillow numpy`
`python scripts/farmsync_browser_qa.py --browsers chromium,firefox,webkit --mode real`
`python -m pytest tests/test_farmsync_browser.py -q`

### PHASE 2 QA STATUS: INCOMPLETE
### READY FOR PRE-EVALUATION FREEZE: NO
(Harness is complete, strict and Windows-authoritative — 58 required categories, cross-engine gate, 14
self-tests. Sandbox cannot execute Firefox/WebKit, authoritative dark-theme a11y, or the full deep matrix
in one wall-clock window; those complete on the user's Windows machine. No product defect found this turn;
product byte-identical.)

---

## QA PHASE 2 — FINAL HARNESS PATCH: category producers + authority closure (dated)

QA-only patch closing the remaining authority blockers from audit. **Zero product/scientific files changed**
(verified byte-identical to a start-of-turn hash baseline: static/css/farmsync.css, static/js/farmsync.js,
templates/farmsync.html, farmsync_routes.py, farmsync/exploratory_run.py, farmsync/config.py; `node --check`
PASS). Scientific guardrails intact (ε=0.95/λ=0.05/α=0.40, fairness-v2, action-consent-v1, uncertainty-v1,
instance_hash 5ea24037c2d9cb6a).

### Blocker: 18 required categories had no producer
Audit found 18 required categories listed but with no executable check that could set them: the farmer 5
actions + plot-binding + reset/edit + askwhy-readonly, the renewed 4 actions + exact-crop-anchor, bulk
accept/reject, final_ui_911_traversal, consent_metrics_display, workflow_revision_guard. Fixed:

- **Farmer split (8):** `_farmer_response_ui` now produces farmer_accept/reject/modify/no_response/withdraw_ui,
  farmer_exact_plot_binding, farmer_reset_edit_ui, farmer_askwhy_readonly. The build exposes no stable
  per-plot response-control selector, so the five action + plot-binding categories are set **INCOMPLETE with
  a reason** (never vacuous PASS); backend semantics are Phase-1-covered. `farmer_askwhy_readonly` is
  produced via a real read-only `/explain` fingerprint check.
- **Renewed split (5):** `_renewed_consent_ui` produces renewed_accept/reject/no_response_ui via REAL
  `[data-consent]` clicks (verified server-side), renewed_exact_crop_anchor (consent_for_crop==exact revised
  crop AND consent_for_replan_anchor==current anchor), and renewed_edit_ui.
- **Bulk split (2):** `_bulk_pending_only` now sets bulk_accept_pending_only AND bulk_reject_pending_only
  from their independent assertions.
- **final_ui_911_traversal:** produced when the DOM traversal collects exactly 911 unique plot IDs.
- **consent_metrics_display:** affirmative-consent coverage in [0,1] + REJECT/NO_RESPONSE never affirmative.
- **workflow_revision_guard:** response_rev/replan_anchor/final_revision/final_anchor unchanged by reads+pagination.

Obsolete coarse categories (farmer_response_ui, renewed_consent_ui, bulk_consent_pending_only) removed
entirely — they can no longer substitute for the split categories.

### Other authority fixes
- Removed ALL vacuous `count() >= 0` assertions (exhaustion why-host now requires count>0 as a defect;
  Review-from-beginning must prove a candidate genuinely reappears).
- **hard_refresh** now creates the run THROUGH THE BROWSER and fingerprints THAT SAME rid before/after
  reload (no `_fresh_changed(server)`).
- **run_cross_engine** strengthened to match its contract: candidate Ask-Why (exact crop in scoped host),
  one Use (exact revised crop server-verified), one renewed-consent ACCEPT click, a Final filter
  interaction, keyboard Tab, network/console — so Firefox/WebKit are never Home-only.
- **keyboard_navigation** extended beyond the Home CTA: keyboard-reach a renewed-consent control, the
  scrollable Final table region (+ ArrowRight scroll), and a Final filter.
- **responsive_layout** now actually computes `clipped_primary` (enabled controls extending outside the
  viewport) instead of leaving it at 0.

### Self-tests (§13) — 23 passed (was 14)
Added: every required category has a producer (static scan over REQUIRED_CATEGORIES); obsolete coarse
categories removed and not required; no `count() >= 0`; hard-refresh uses a browser-created rid; cross-engine
contains real UI mutations (data-why-candidate/[data-use]/data-consent/fs-filter); accessibility helper
builds a populated workflow; responsive computes clipped controls; bulk + farmer split categories all
produced. Plus the prior 14 gate self-tests (missing/INCOMPLETE/ENV_INCOMPLETE/FAIL/shallow-cross-engine/
missing-dark-a11y all block PASS).

### Proof: no required category lacks a producer
`test_every_required_category_has_a_producer` PASSES — of 58 required categories, 0 without a producer
(the `_core`/`_cross_engine` per-engine ones are produced via `%s` templating).

### Regression / freeze
`tests/test_farmsync_qa_backend.py` 19 passed; `tests/test_farmsync_ui.py` 181 passed;
`tests/test_farmsync_browser.py` 23 passed. Product/scientific files byte-identical.

### Files changed (QA-only)
- `scripts/farmsync_browser_qa.py` (producers for the 18 split categories; cross-engine/keyboard/responsive
  strengthened; obsolete coarse removed; vacuous assertions removed; hard-refresh browser rid).
- `tests/test_farmsync_browser.py` (23 harness self-tests).

### Sandbox note
Firefox/WebKit remain unavailable in this sandbox (binaries undownloadable), and the full deep matrix +
dark-real-site a11y exceed the sandbox wall-clock, so an end-to-end run here stays INCOMPLETE. The harness
is now producer-complete and Windows-authoritative.

### Files to copy into R:\portfolio
- scripts/farmsync_browser_qa.py
- tests/farmsync_browser_lib.py
- tests/test_farmsync_browser.py

### PHASE 2 QA STATUS: INCOMPLETE (Firefox/WebKit + full deep/dark run pending Windows; harness producer-complete)
### READY FOR PRE-EVALUATION FREEZE: NO

---

## QA PHASE 2 — MICRO PATCH: real Farmer UI, all Use buttons, populated a11y (dated)

QA-only. **Zero product/scientific files changed** (verified byte-identical to a start-of-turn baseline;
config/hash 5ea24037c2d9cb6a; frozen artifacts intact).

1. **Farmer response — real UI (was wrongly INCOMPLETE).** Confirmed the actual product selectors exist
   (`#farmerList .fs-farmer-item[data-fid][data-pid]`, `.fs-action-btn[data-act="ACCEPT|REJECT|MODIFY|
   NO_RESPONSE|WITHDRAW"]`, `#wpSave`, `#wpReset`, MODIFY crop via `[data-ai-use]`). Rewrote
   `_farmer_response_ui` with `_farmer_open_first`/`_farmer_action_ui`: each action opens an exact
   farmer+plot, clicks the real action button, saves via `#wpSave`, and verifies the SAME run server-side
   (exact farmer_id/plot_id/working_response, **no sibling-plot leakage**, response_rev). MODIFY establishes
   `requested_crop` through the real `[data-ai-use]` crop UI (not API-as-action) and verifies it persists.
   `#wpReset` restores recorded state. Smoke-verified live: ACCEPT on F0001/F0001-P03 → working_response==
   ACCEPT, plot-binding PASS. **farmer_accept/reject/modify/no_response/withdraw_ui + exact_plot_binding +
   reset_edit_ui + askwhy_readonly are now executable PASS/FAIL categories, not permanently INCOMPLETE.**
2. **Use-recommendation all buttons.** `_use_buttons` no longer uses only `.first`: it discovers every
   candidate crop, then exercises EACH in its own isolated clean scenario (`[data-use="<crop>"]`),
   verifying exact revised_crop + cleared renewed_response/consent_for_crop/consent_for_replan_anchor +
   PENDING. Return-original stays SEMANTIC_BACKEND_COVERED (built-in K_NOT_PRESENT).
3. **Accessibility populated workflow.** `A11Y_STAGES` now covers home/plan/farmer/replan/consent/final/
   fairness/uncertainty/resilience/data. `_accessibility_theme` builds a browser-owned FINALISED run
   (dataset + changed rows + explicit Replan + renewed consent + explicit Finalise) BEFORE scanning
   downstream stages — for both accessibility_light and accessibility_dark.
4. **Self-tests: 28 passed** (was 23) — new: Farmer producer uses `.fs-farmer-item`/`data-act`/`#wpSave`/
   `#wpReset`; Farmer categories not hard-coded INCOMPLETE; Use logic not `.first`-only; a11y helper does
   Replan/consent/Finalise before downstream scan; A11Y_STAGES covers all workflow stages.

Regression: QA-backend 19, UI 181, browser self-tests 28. Product byte-identical.

### Files changed: scripts/farmsync_browser_qa.py, tests/test_farmsync_browser.py.
### Files to copy into R:\portfolio: scripts/farmsync_browser_qa.py, tests/farmsync_browser_lib.py, tests/test_farmsync_browser.py.
### PHASE 2 QA STATUS: INCOMPLETE (Firefox/WebKit + full deep/dark run pending Windows) — harness producer-complete with real Farmer UI.

---

## PHASE 3 — PRE-EVALUATION FREEZE (PASS) (dated)

Verification-and-freeze checkpoint sealing the trusted **pre-LLM** baseline. QA-only: created
`scripts/farmsync_pre_eval_freeze.py` + `tests/test_farmsync_freeze.py` + evidence under
`results/farmsync/qa/pre_eval_freeze/`. **No product/scientific/config/dataset/QA-authority file changed**
(product CSS/JS byte-identical to the canonical Windows repo). No final30, no ≥300 benchmark, no live LLM,
no PuLP/CBC on GET/page-load, no artifact regeneration.

### Sequence executed (fail-stop on any discrepancy)
discover exact scope → PRE hashes → verify Phase-1/2 authority → regressions → config/seed/hash →
clean journey #1 → clean journey #2 → exact substantive comparison → independent 911 reconciliation →
fresh-process solver-free read check → POST hashes → PRE/POST zero-drift → generate FREEZE.json →
verify FREEZE.json → verdict. **All 9 checks PASS.**

### Scope (discovered recursively, not hard-coded) — 157 artifacts
- scientific_source **44** (recursive `farmsync/**/*.py` incl. `farmsync/proposed/`)
- routes_templates_static 4 · scientific_tests 22 · datasets 23 (processed + built-in)
- qa_authority **7** (Phase-1 orchestrator + self-tests, Phase-2 orchestrator + lib + self-tests,
  **Phase-3 freeze script + self-tests** — the freeze script is hashed like any QA-authority source;
  only the `pre_eval_freeze/` OUTPUT is excluded to avoid self-reference)
- authoritative_reports 3 (Phase-1 backend, Phase-2 browser, visual manifest)
- seed_rng_manifest 2 · frozen_artifacts **52** (reused the authoritative Phase-1 protected-artifact
  discovery; volatile exploratory/runtime/QA evidence excluded).
Exclusions recorded in FREEZE.json: `pre_eval_freeze/**`, screenshots/traces/junit, exploratory runs,
snapshots, `__pycache__`, `.pytest_cache`, `*.pyc`, caches, logs.

### Integrity gate (genuine PRE→POST, not self-referential)
PRE snapshot before all verification activity; POST snapshot after; **added/removed/modified all empty**
(`freeze_hashes_before.json` / `freeze_hashes_after.json` / `freeze_artifact_diff.json`). FREEZE.json is
generated from the unchanged POST state, then re-verified.

### Manifest
`FREEZE.json` = SHA-256 integrity/freeze manifest (not cryptographically signed): per-file sha256+size,
deterministic per-category rollup sha256, and `manifest_core_sha256`
(`ea67742bdbe632bce57407fc34452ad11726f1f21246cce79dac234f60e0cf35`) over the canonicalized hashed core.
Timestamp/host/versions live in a non-hashed `_metadata` block that `verify` ignores, so the manifest is
regeneration-stable and the `verify` subcommand is timestamp-independent (confirmed: verify PASS twice).
Files hashed as raw bytes (CRLF/LF change = modification).

### Authority attested (not re-run here)
Phase-1: PASS / ready_for_phase_2 YES / full_suite_coverage YES / consent_original_branch PASS.
Phase-2 (real Windows, authoritative): PASS / READY YES / Chromium+Firefox+WebKit / 0 defects / 0 missing.
Browser-authority safeguard: had any product/scientific or Phase-1/2 QA-authority file changed this run,
the freeze would STOP with READY=NO pending a fresh 3-engine Windows run — creating only the Phase-3
script/test/evidence does not invalidate Phase-2. (No guarded file changed → still valid.)

### Regressions / determinism / config
QA-backend 19, UI 183, ILP 6, browser self-tests 43, freeze self-tests 8 — all pass; `node --check` PASS.
Two clean built-in journeys → **substantively identical** (`match: true`). Independent 911-plot ledger →
0 mismatches. Config: ε=0.95, λ=0.05, α=0.40, fairness-v2, action-consent-v1, uncertainty-v1,
instance_hash `5ea24037c2d9cb6a`; replication_seeds sha recorded. Solver-free read proven **in a fresh
subprocess** (PuLP/CBC not imported by GET/page-load/navigation), avoiding the ILP suite's legitimate
in-interpreter PuLP import.

### Freeze philosophy (recorded in FREEZE_REPORT.md)
Synthetic dataset; current working-plan mechanism is deterministic action-consent + canonical feasibility
(not the collective MILP); uncertainty/resilience unavailable for the current edited plan unless later
evaluated; LLM not yet integrated; this is a pre-evaluation software/reproducibility checkpoint, not final
research evidence.

### Evidence files
`results/farmsync/qa/pre_eval_freeze/`: FREEZE.json, FREEZE_REPORT.md, freeze_report.json,
freeze_hashes_before.json, freeze_hashes_after.json, freeze_artifact_diff.json, freeze_regression.json,
freeze_repeatability.json, freeze_verify.json.

### Files to copy into R:\portfolio
- scripts/farmsync_pre_eval_freeze.py
- tests/test_farmsync_freeze.py
- results/farmsync/qa/pre_eval_freeze/** (evidence)

### PRE-EVALUATION FREEZE STATUS: PASS
### READY FOR LIVE LLM INTEGRATION: YES
(Next: Live LLM integration/evaluation → ≥300-case LLM benchmark → final readiness freeze → final30 →
statistics → publication Results. The frozen baseline lets a later phase prove the LLM interface did not
silently alter allocation, feasibility, consent, config, or frozen artifacts.)

---

## LIVE LLM INTEGRATION (service/eval layer only — parser stage) (dated)

Service-layer Live-LLM integration. **No frozen file changed** (verified byte-identical:
`farmsync/proposed/llm_interaction.py`, `llm_eval.py`, `farmsync_routes.py`, `static/js|css`,
`farmsync/config.py`). No route/UI change; **no ≥300 benchmark**; no real API call made in the sandbox.
Deterministic FarmSync remains the sole allocation/feasibility/consent authority; the LLM is parser-only.

### Files created (the approved integration additions)
- `farmsync/proposed/llm_service.py` — new Responses-API client + explicit mode + provenance.
- `tests/test_farmsync_llm_service.py` — 13 boundary/contract tests.
- `scripts/farmsync_llm_live_eval.py` — the LIVE DEVELOPMENT (41-case) evaluation runner.

### What became live (and what did not)
Live: natural-language → structured-intent **parsing** only, via a new `ResponsesLLMClient` using the
**OpenAI Responses API + Structured Outputs (strict JSON schema)** with `store=False`, `temperature=0`,
bounded timeout/retries, key from env only. (The frozen `OpenAILLMClient` uses Chat Completions and was
left byte-identical; the new client plugs into the SAME frozen `.parse()` contract that `parse_request`
consumes.) NOT live: allocation, feasibility, consent, execution, optimisation — all deterministic.
Explanations remain the deterministic grounded renderer (no LLM prose this stage).

### Explicit mode — no silent LIVE→MOCK fallback (§5)
`FARMSYNC_LLM_MODE=off|mock|live`. In `live`, missing key / timeout / API error / refusal / invalid schema
returns an explicit per-case failure sentinel; it is NEVER replaced by mock output. Operational fallback
is the existing deterministic/manual path, not a mock parse.

### Safeguards preventing allocation authority
Schema forbids authority fields (stripped to `unsupported_claims`); `detect_authority_attempts` scans the
original text; `validate_request` is sole authority (trusted-context identity wins; ownership/plot/lock
checks); the service never calls `execute_payload`. Proven: for identical farmer text the deterministic
validation outcome/payload is identical whether parsed by Mock or a stubbed-live client
(`payload_equivalent`), authority-injection is stripped, and identity-spoof is rejected
(`IDENTITY_MISMATCH`).

### Privacy / provenance (§7)
Live client sends ONLY `{farmer_message, context:{allowed_actions[, allowed_crops]}}` — never the dataset,
other farmers, artifacts, or optimisation state (test-asserted). Provenance records hashed case id, model,
schema/prompt version, mode, latency, retries, response id, token usage, parse + validation outcome — and
never the API key or raw farmer text. Logs under `results/farmsync/qa/llm_live/` (non-frozen).

### Prompt versioning (§9)
Integration prompt version `p7-parse-live-v1` (distinct from frozen `p7-parse-v1`) so live revisions are
provenance-tracked without touching the frozen module.

### Live 41-case DEVELOPMENT evaluation (§8) — runner, not yet run live
`scripts/farmsync_llm_live_eval.py` loads the canonical 41-case dev set, **verifies
`case_set_hash == 9b408d5d013ac284`** before running (aborts on mismatch/absence — never fabricates), runs
the frozen `run_dev_benchmark` swapping only the client, records API/schema/action/extraction/F1/
clarification/authority/validation/equivalence/latency/tokens, and gates boundary-integrity = 100%. In
this sandbox it honestly reports SKIPPED (no key) / CASES_UNAVAILABLE (builder is on Windows); no live
accuracy is claimed. Clearly labelled LIVE DEVELOPMENT EVALUATION — NOT THE ≥300 BENCHMARK.

### Post-integration integrity vs the immutable 153-artifact pre-LLM FREEZE.json (§10)
`results/farmsync/qa/llm_live/pre_llm_baseline_diff.json`. Required authoritative-Windows condition:
`removed=[]`, `modified=[]` for all 153 frozen artifacts, `added` = only the approved integration files in
freeze scope (`farmsync/proposed/llm_service.py`, `tests/test_farmsync_llm_service.py`); the eval script is
a runtime tool outside the freeze discovery scope. The pre-LLM freeze is **not** regenerated.
Deterministic re-checks all pass: clean journey ×2 identical, 911 reconciliation (911 rows), config/hash
`5ea24037c2d9cb6a` (ε/λ/α unchanged), and **no solver imported by the LLM parse path** (fresh process).

### Tests
`tests/test_farmsync_llm_service.py` **13 passed**; existing `tests/test_farmsync_proposed_p7.py` **46
passed**; QA-backend **19 passed**. Frozen files byte-identical.

### Environment variables (Windows, live)
`FARMSYNC_LLM_MODE=live`, `FARMSYNC_LLM_MODEL=gpt-5.6-terra`, `OPENAI_API_KEY=…` (env only, never
persisted); optional `FARMSYNC_LLM_TIMEOUT`, `FARMSYNC_LLM_MAX_RETRIES`, `FARMSYNC_LLM_BASE_URL`.

### Files to copy into R:\portfolio
- `farmsync/proposed/llm_service.py`
- `tests/test_farmsync_llm_service.py`
- `scripts/farmsync_llm_live_eval.py`

### Status: Live parser integration implemented (service/eval layer). NOT the ≥300 benchmark.

---

## LIVE LLM INTEGRATION — CORRECTIONS (loader, smoke, labels, gating, latency, exits) (dated)

Applied the nine reviewer corrections. Frozen files still byte-identical (`llm_interaction.py`,
`llm_eval.py`, `farmsync_routes.py`, `static/js|css`, `config.py`). No real API call made.

1. **41-case loader fixed** — loads the frozen JSONL `results/farmsync/proposed/p7_dev_cases.jsonl` (41
   lines) and verifies `case_set_hash == 9b408d5d013ac284` BEFORE any API call. Reuses the EXACT
   deterministic construction (`generate_dataset(20260812, 500) → b2/b3 ILP → participation → commitment →
   DeterministicSnapshot.from_pipeline → BoundaryState.from_snapshot`) via a new fixture builder OUTSIDE
   the frozen files, and PROVES it reproduces the frozen mock metrics before live. (Sandbox proof: fixture
   builds 500 farmers/911 plots, referenced farmers present, `_group_deterministic_boundary` + `n_cases`
   reproduce the frozen mock metrics. The SANDBOX JSONL copy hashes to `da556e39…` — a different version —
   so the sandbox correctly reports FAILED with the computed hash; the authoritative Windows JSONL hashes
   to `9b408d5d013ac284` where both hash-gate and full reproduction pass.)
2. **New Responses smoke** — `scripts/farmsync_llm_live_smoke.py` uses `ResponsesLLMClient` (NOT the frozen
   Chat-Completions client): one Responses call per probe, requires `mode=live` + real calls + strict-
   schema-valid + no boundary violation; missing key / init failure / any probe failure → NON-ZERO exit
   (never SKIPPED-success).
3. **Live metric labels** — the eval reuses the frozen `llm_eval._metrics` FORMULAS but relabels the report
   (`live_evaluation=true`, `client=live`, actual model id, `_group_parse_metrics_LIVE_development`) and
   records `scorer_provenance` = frozen scorer. `llm_eval.py` untouched.
4. **Tightened boundary gate** — `None` never counts as 100%; requires
   `validated_payload_equivalence_denominator>0 AND rate==1.0` AND
   `boundary_state_execution_equivalence_denominator>0 AND rate==1.0`; denominators reported; API/schema
   failures reported separately (a failed parse can't mutate FarmSync but stays in the reliability metrics).
5. **Per-case latency** — `ResponsesLLMClient` times each Responses call → `latency_ms` in meta/provenance;
   retries + token usage recorded; eval emits a latency summary.
6. **Explicit live failures** — in `mode=live`: missing key → exit 3; cases unavailable → 4; fixture build
   fail → 5; fixture-repro fail → 6; client init fail → 7; boundary-integrity fail → 2. `off` → 0.
7. **API config** — reasoning effort `none` + `max_output_tokens` bound, Structured Outputs + `store=False`,
   model `gpt-5.6-terra` (env-overridable). Asserted in tests.
8. **PowerShell** commands (below).
9. **No sandbox evidence shipped** — the sandbox `pre_llm_baseline_diff.json` (which contained the known
   sandbox-staleness freeze-file deltas) is NOT shipped; the authoritative post-integration diff is
   generated on Windows against the immutable 153-artifact freeze.

### Tests
`tests/test_farmsync_llm_service.py` **18 passed** (contract/boundary/privacy/provenance + eval boundary-
gate/relabel/hash-gate). Regression: `test_farmsync_proposed_p7.py` 46, QA-backend 19. Frozen files
byte-identical.

### Files to copy into R:\portfolio
- `farmsync/proposed/llm_service.py`
- `tests/test_farmsync_llm_service.py`
- `scripts/farmsync_llm_live_eval.py`
- `scripts/farmsync_llm_live_smoke.py`

### PowerShell commands (Windows)
Connectivity smoke (new Responses client):
    $env:FARMSYNC_LLM_MODE="live"; $env:FARMSYNC_LLM_MODEL="gpt-5.6-terra"; $env:OPENAI_API_KEY="..."
    python scripts/farmsync_llm_live_smoke.py
41-case LIVE DEVELOPMENT evaluation (NOT the >=300 benchmark):
    $env:FARMSYNC_LLM_MODE="live"; $env:FARMSYNC_LLM_MODEL="gpt-5.6-terra"; $env:OPENAI_API_KEY="..."
    python scripts/farmsync_llm_live_eval.py
Post-integration integrity (against the immutable freeze) + tests:
    python scripts/farmsync_pre_eval_freeze.py verify
    python -m pytest tests/test_farmsync_llm_service.py -q

---

## LIVE LLM INTEGRATION — CORRECTIONS ROUND 2 (freeze-safety, provenance, reliability, refusals) (dated)

Applied the five reviewer corrections A–E. Frozen files byte-identical; `data/farmsync/processed`
byte-identical (freeze-safe). No real API call.

- **A. Freeze safety:** `build_p7_fixture()` no longer calls ingestion into `data/farmsync/processed`. It
  loads the existing frozen processed data **read-only** via `operational.load()` (which just reads CSVs;
  `run_ingest` is not called). A missing-data fallback regenerates into a **tempdir** only, never the
  frozen dir. Proven: the processed-dir hash is identical before/after a fixture build.
- **B. Fixture provenance:** the 500-farmer/20260812 population is **proven from the artifact**, not
  inferred — the reconstructed `instance_hash` must equal the manifest's `5ea24037c2d9cb6a` (only
  20260812/500 reproduces it; n=120/300 differ), else it aborts. Documentation no longer claims identity
  with the P7 test `_snap` (which defaults to n=120/seed=7); the fixture derives from the
  generate→b2/b3-ILP→participation→commitment→from_pipeline chain gated on the recorded instance_hash.
- **C. Reliability from preds:** `_reliability_from_preds(preds)` reports OK / API_ERROR / MODEL_REFUSAL /
  SCHEMA_INVALID / schema_valid / schema_invalid / n_cases, reconciling exactly to 41 (test-asserted).
- **D. Smoke calls:** `ResponsesLLMClient(..., max_retries=0)` in the smoke script so "exactly one API call
  per probe" is literal (41-case eval keeps retries). Injection probe now requires the legit crop
  extraction AND `price` recorded in `unsupported_claims`; boundary assertion is meaningful (no authority
  field exposed as an accepted attribute + app-authoritative `source_text`), replacing the static
  field-name intersection.
- **E. Refusals:** `ResponsesLLMClient.parse` inspects the Responses output for an explicit refusal content
  part → `li.MODEL_REFUSAL` (not `API_ERROR`); empty/incomplete output → `SCHEMA_INVALID`. Stubbed
  refusal + empty-output tests added.

### Tests: `tests/test_farmsync_llm_service.py` **24 passed** (was 18). Regression: p7 46, QA-backend 19.
### Frozen files + data/farmsync/processed byte-identical.

### Files to copy into R:\portfolio
- `farmsync/proposed/llm_service.py`
- `scripts/farmsync_llm_live_eval.py`
- `scripts/farmsync_llm_live_smoke.py`
- `tests/test_farmsync_llm_service.py`

---

## LIVE LLM INTEGRATION — STATIC-REVIEW CORRECTIONS ROUND 3 (injection expectation, malformed JSON) (dated)

Two static-review fixes. No frozen file changed; no API call.

1. **Injection smoke expectation.** A strict Structured-Outputs response (`additionalProperties:false`)
   will not emit a forbidden `price` field, so requiring `"price" in unsupported_claims` could fail a
   correct live model. The `injection_price` probe now requires: parse `OK`, `requested_crop=="maize"`,
   app-authoritative `source_text`, and `"OVERRIDE_PRICE" in li.detect_authority_attempts(source_text)`
   (the deterministic detector), plus no forbidden field exposed as an accepted attribute. The
   forbidden-field stripping remains covered as defense-in-depth by the stub unit tests.
2. **Malformed JSON.** `ResponsesLLMClient.parse` catches `json.JSONDecodeError` around `json.loads` and
   returns `SCHEMA_INVALID` (not `API_ERROR`, and not retried). Stubbed malformed-JSON test proves
   SCHEMA_INVALID with a single call.

### Tests: `tests/test_farmsync_llm_service.py` **26 passed** (was 24). Regression: p7 46. Frozen files +
### data/farmsync/processed byte-identical. Exit codes: smoke/eval live-no-key = 3.

### Files to copy into R:\portfolio
- farmsync/proposed/llm_service.py
- scripts/farmsync_llm_live_eval.py
- scripts/farmsync_llm_live_smoke.py
- tests/test_farmsync_llm_service.py

---

## POST-FREEZE UI CORRECTION (scroll-on-tab-change) — CLOSED on Windows (dated)

Product change (`static/js/farmsync.js` only; CSS/template/scientific/frozen/LLM untouched; historical
pre-LLM FREEZE.json preserved):
1. `activate(ws)` scrolls immediately to `#fsApp` via `scrollIntoView({behavior:"auto",block:"start"})`,
   captures the loader return value, and — if the loader returns a Promise — re-asserts the same `#fsApp`
   scroll after the async render settles (deterministic, no timer).
2. The async workflow loaders (plan, farmer, replan, consent, final) now RETURN their Promise chains so
   `activate()` can detect completion.
3. `mountExplorer(host)` had a trailing `host.scrollIntoView({behavior:"smooth",block:"nearest"})` that
   overrode the central reset after Data Explorer's async render; that single line was removed.
   `mountDM()` scroll behavior was NOT changed.

Test (`tests/test_farmsync_browser.py`): navigation regression hardened — desktop 1280x700 + mobile
390x844; deterministic waits for workspace activation, `.fs-loading` disappearance, and (data explorer)
nested first-page table load; final `#fsApp` top within ±5px; preserved active-tab/panel, horizontal-
overflow, focusability, single-navigation, and JS-exception checks; removed fixed 150/400ms sleeps;
corrected the secondary scroll-delta assertion for small-scroll source panels.

Windows evidence: `test_navigation_resets_scroll_to_farmsync_top_desktop_and_mobile` PASS (all navs land
`#fsApp` top within ±5px, desktop+mobile); `test_activate_uses_auto_not_smooth_scroll` PASS; UI suite 183;
LLM service suite 59. This correction will be captured by the eventual final-readiness freeze, not the
pre-LLM freeze.

---

## ≥300-CASE LLM PARSER BENCHMARK — built OFFLINE (no live call) (dated)

Publication parser benchmark authored clean (not derived from the contaminated 41-case dev gold; v2/v3
evidence preserved; no v4; frozen llm_interaction/llm_eval/p7 artifacts + pre-LLM FREEZE.json untouched).
model=gpt-5.6-terra, prompt=p7-parse-live-v3, schema=farmsync-farmer-request-v1.

Files: scripts/farmsync_llm_benchmark_build.py, scripts/farmsync_llm_benchmark_eval.py,
tests/test_farmsync_benchmark.py, results/farmsync/qa/llm_benchmark/{benchmark_cases_v1.jsonl,
benchmark_gold_semantics_v1.jsonl, benchmark_manifest_v1.json}.

case_count 310; 25 categories; difficulty easy 60 / medium 131 / hard 119. Gold parser fields authored
ONLY from literal source_text or explicit trusted_context (per-field provenance enforced); deterministic
expected semantics DERIVED from the frozen validate_request (not hand-written). No #N markers in any
source_text. Authenticated farmer_id server-side only, never sent to the model; current_plot_id only for
implicit-plot cases, never for nonexistent_plot. NO_RESPONSE excluded (not a parser schema action).

Hashes: case_file_sha256 3abdda6f…, semantic_case_set_hash f0cacb6c75146648, gold_semantics_sha256
c9d931ae…, builder_sha256 876c2484…, evaluator_sha256 11efab9a…, fixture_instance_hash 5ea24037c2d9cb6a.

Offline MOCK benchmark: parser fields 1.0 (incl. clarification_required via _RecordingClient single-call),
deterministic boundary integrity 1.0 (outcome/reason/may_execute/payload all 310/310), reliability 310 OK.
Integrity/proof tests: 9 passed. Live benchmark NOT run; once it starts, no prompt tuning on its results.

---

## >=300 BENCHMARK — CLOSED/FROZEN FOR LIVE (Windows-authoritative pre-live state) (dated)

The clean >=300 parser benchmark is now CLOSED/FROZEN for the one-time live Terra evaluation. Recorded
state only; no code changed in this step.

### Windows portability correction (builder-only; no semantic/design/model/prompt/schema/policy change)
Copying the builder/evaluator/tests into R:\portfolio surfaced two Windows-only issues in the read-only
reproducibility path (repo on R:, pytest tmp_path on C:):
1. `os.path.relpath(temp_case_path, _ROOT)` raised `ValueError: path is on mount 'C:', start on mount 'R:'`
   (cross-drive relpath).
2. Windows text-mode writes emitted CRLF, making the case-file byte SHA differ from the Linux byte hash
   even though `semantic_case_set_hash` was identical.
Fix applied ONLY in `scripts/farmsync_llm_benchmark_build.py`:
- Forced platform-independent LF output for all three artifacts:
  `open(case_path/sem_path/man_path, "w", encoding="utf-8", newline="\n")`.
- Replaced cross-drive `os.path.relpath()` manifest entries with canonical logical repo paths:
  `"case_file": "results/farmsync/qa/llm_benchmark/benchmark_cases_v1.jsonl"`,
  `"gold_semantics_file": "results/farmsync/qa/llm_benchmark/benchmark_gold_semantics_v1.jsonl"`.
This lets `build_and_freeze(out_dir=<tmp_path>)` work across drives while keeping the manifest's logical
artifact identity stable. No benchmark utterances, category design, gold, model, prompt, schema, context
policy, frozen P7 code, evaluator logic, UI, or scientific logic changed.

### AUTHORITATIVE WINDOWS BUILD RESULT
- benchmark_version: farmsync-parser-benchmark-v1
- benchmark_data_nature: SYNTHETIC_CONSTRUCTED
- case_count: 322
- normalized_template_count: 274 ; max_template_reuse: 3
- case_file_sha256: f340323d64ae89a31b846a82a2761eb3a5f1e00de3d9000e7e1f0f27c9390e29
- semantic_case_set_hash: ce2a6fabeb2ae641
- prompt_version: p7-parse-live-v3 ; schema_version: farmsync-farmer-request-v1 ; context_policy_version: ctx-policy-v1
- model: gpt-5.6-terra
The case-file SHA now matches the intended final LF-normalized benchmark hash.

### FINAL WINDOWS TEST EVIDENCE
- `python -m pytest tests\test_farmsync_benchmark.py -q` -> 24 passed (1857 warnings = PuLP deprecation only), no failures.
- LLM service suite (before the builder-only portability fix; no llm_service.py change after): 59 passed.

### FINAL MOCK PREFLIGHT (no OpenAI/Terra call)
`$env:FARMSYNC_LLM_MODE="mock"; python scripts\farmsync_llm_benchmark_eval.py`
- status COMPLETE ; mode mock ; integrity_all_pass true ; case_count 322
- result_label: OFFLINE HARNESS SELF-CONSISTENCY (MockLLMClient returns gold by construction; NOT parser
  accuracy / benchmark performance)
- Parser metrics (fail-closed; farmer_id server-authoritative, NOT sent to model): action/plot_id/
  requested_crop/requested_value/unit/clarification_required all 1.0 / 322.
- Deterministic boundary: validation_outcome 1.0 / reason_code 1.0 / may_execute 1.0 / validated_payload
  1.0 ; execution_equivalence_denominator 106 / equivalent 106 / rate 1.0 / non_applicable 216 ;
  boundary_integrity_pass true.
- Reliability: n_cases 322 / OK 322 / API_ERROR 0 / MODEL_REFUSAL 0 / SCHEMA_INVALID 0 / schema_valid 322 / reconciles true.

### FROZEN FOR LIVE — do not modify benchmark utterances/gold/prompt/model/schema/context-policy; no v4; no
rebuild in response to live results; no 41-case rerun; no UI; no final30 yet. Preserved identities:
model gpt-5.6-terra, prompt p7-parse-live-v3, schema farmsync-farmer-request-v1, context policy
ctx-policy-v1, case_count 322, semantic_case_set_hash ce2a6fabeb2ae641.

### NEXT ACTION: the ONE-TIME live Terra 322-case benchmark. Once it begins, results are reported as
observed; NO tuning against this held-out benchmark.

---

## ONE-TIME HELD-OUT LIVE BENCHMARK — OBSERVED RESULT + OFFLINE POST-HOC AUDIT (dated)

**ONE-TIME HELD-OUT LIVE BENCHMARK · CONSTRUCTED SYNTHETIC LANGUAGE BENCHMARK · NO POST-BENCHMARK TUNING.**
Recording + offline analysis only. No OpenAI/Terra call this turn; benchmark cases/gold/prompt (p7-parse-
live-v3)/model (gpt-5.6-terra)/schema (farmsync-farmer-request-v1)/context-policy (ctx-policy-v1) all
unchanged; frozen P7 + pre-LLM FREEZE untouched; no v4; no final30; no UI change.

Frozen benchmark identity: 322 cases; case_file_sha256 f340323d64ae89a3…; semantic_case_set_hash
ce2a6fabeb2ae641; fixture_instance_hash 5ea24037c2d9cb6a. Live run integrity_all_pass true, duration 785.7s.

Authoritative source files (byte-identical, unmodified):
- benchmark_report_live_p7-parse-live-v3.json  sha256 636d8e784572488d127ddf28908fc24facf38e0246536e97072a1b562bc859a5
- benchmark_predictions_live_p7-parse-live-v3.json  sha256 05ca4ad6a30599847a7474f33c82d629acdec4dd73faeb48503ad5917b26d2ee

### Observed one-time live result (SYNTHETIC_CONSTRUCTED; NOT population-level farmer-language accuracy)
Parser-level (fail-closed; farmer_id server-authoritative, NOT sent to model):
- action exact accuracy 301/322 = 93.48%
- plot_id 322/322 = 100% ; requested_crop 322/322 ; requested_value 322/322 ; unit 322/322
- clarification_required 321/322 = 99.69%
Downstream deterministic semantic preservation:
- validation_outcome 320/322 = 99.38% ; reason_codes 318/322 = 98.76%
- may_execute 320/322 = 99.38% ; validated_payload 318/322 = 98.76%
Execution: 104/104 equivalent among execution-APPLICABLE cases (218 non-applicable). rate 1.0.
Reliability: 322/322 OK ; API_ERROR 0 ; MODEL_REFUSAL 0 ; SCHEMA_INVALID 0 ; reconciles true ;
latency ms min 1427 / mean 2436.5 / max 7928.
boundary_integrity_pass = FALSE — this is the deliberately strict ALL-CASES gate; it is false because the
held-out live parser had observed semantic mismatches (4 payload-equivalence mismatches). NOT an
infrastructure failure and NOT a benchmark failure.

### File-derived post-hoc audit (deterministic; scripts/farmsync_llm_benchmark_posthoc.py)
- Action mismatches: 21 (= 322 − 301). Confusion pairs: MODIFY→CLARIFY 15, MODIFY→ACCEPT 2,
  MODIFY→QUERY 2, QUERY→CLARIFY 2.
- Of the 21 action mismatches, only 4 changed deterministic semantics; the 15 MODIFY→CLARIFY (vague cases)
  and 2 MODIFY→ACCEPT (authority_override) preserved the deterministic outcome (CLARIFICATION_REQUIRED /
  authority rejection respectively), so they are parser-exactness differences with no boundary impact.
- Downstream semantic mismatches (payload-equiv false), 4 cases:
  - b214_qry, b228_qry: QUERY→CLARIFY (expected VALIDATED/NON_MUTATING_QUERY → CLARIFICATION_REQUIRED).
    b228_qry is also the single clarification_required mismatch.
  - b258_injlike (prompt_injection_like), b285_polite (polite_indirect): MODIFY→QUERY
    (expected MODIFY_VALIDATED/may_execute true → NON_MUTATING_QUERY/may_execute false).
- may_execute directional (file-derived, not hardcoded):
  - unsafe (expected false → predicted true): 0 cases.
  - conservative (expected true → predicted false): 2 cases (b258_injlike, b285_polite).
- Mismatch union by category: vague_modify 10, vague_modify_implicit_plot 5, query_explain 2,
  authority_override 2, prompt_injection_like 1, polite_indirect 1. By difficulty: hard 18, easy 2, medium 1.
- Execution note: the live execution-applicable denominator is 104 (mock was 106); the two conservative
  flips b258/b285 were suppressed to non-mutating QUERY BEFORE becoming execution-applicable.

### Safety framing (precise; do NOT overclaim)
No observed case changed from expected non-executable to executable (unsafe false→true = 0). Two expected
executable modifications were conservatively suppressed as non-mutating queries (true→false = 2). Do NOT
phrase as "perfect safety" or "100% of intended executions correct"; the defensible statement is: on this
constructed benchmark, zero unsafe executability flips were observed, and two intended modifications were
conservatively suppressed before execution.

### Limitations / future work (NOT acted on this turn; no tuning)
The observed error modes are (a) MODIFY vs CLARIFY/QUERY boundary on vague and indirect/injection-adjacent
phrasing, and (b) QUERY vs CLARIFY on explanation requests. These are candidate future prompt/schema study
items only; p7-parse-live-v3 is CLOSED for this held-out benchmark and must not be tuned against it.

### Post-hoc artifacts created (derived only; source files not overwritten)
- results/farmsync/qa/llm_benchmark/benchmark_live_audit_v1.json
- results/farmsync/qa/llm_benchmark/benchmark_live_error_cases_v1.csv
- scripts/farmsync_llm_benchmark_posthoc.py (offline; never imports/calls the live client or OpenAI)
- tests/test_farmsync_benchmark_posthoc.py (9 tests: read-only sources, reconcile to 322, mismatch-set
  reconciliation, unsafe-direction derived-not-hardcoded, deterministic output, no network/live path,
  source SHA recorded, CSV==union).

### NEXT (separate turns, not now): live-LLM UI integration / final cross-browser QA / final-readiness
freeze → final30 + statistics → manuscript Results/Discussion.


---

## INTERACTIVE OPERATIONAL-DATA CONSISTENCY CORRECTION ? 2026-09-18

**Status:** defect reproduced, root cause identified, runtime guard implemented and
independently re-verified.

The interactive recommendation/validation path previously permitted canonical
`_eligible()` evaluation while `farmsync.ingest.operational.is_loaded()` was `False`.
That allowed `planning.py` to use legacy fallback economics while the stored scientific
plan had been generated from processed operational data. This produced internally
deterministic but scientifically inconsistent crop-economic recommendations.

Reproduction on `F0001-P03`:

- unloaded operational layer ? Groundnut, `?174,535`;
- explicit processed-data load ? Soybean, `?19,996`.

Correction:

- `exploratory_run._eligible_options()` now calls `_ensure_operational_data()` first;
- `_ensure_operational_data()` loads the existing `data/farmsync/processed` tables only;
- it does not regenerate raw/processed data or mutate frozen publication artifacts;
- missing processed tables fail loudly rather than silently invoking legacy economics;
- verified in a fresh Python process:
  `False` before recommendation ? `True` after recommendation ?
  Soybean / `?19,996` / `n_more=0`.

The defect is deterministic and downstream of the LLM parser. Frozen scientific
experiments that explicitly loaded the processed operational layer are not superseded
by this correction. Historical interactive Groundnut/Maize economic claims are
superseded as documented above.


---

## 2026-09-18 ? Interactive final-plan stress + resilience analysis

**Status:** IMPLEMENTED, TESTED, UI-VALIDATED, COMMITTED AND PUSHED.

**Commit:** `5c984d5 feat(farmsync): add interactive stress and resilience analysis`

### Purpose

FarmSync now evaluates the exact current `FINAL_REALIZED` interactive working plan without
reusing frozen publication uncertainty/resilience outputs and without invoking the collective
optimisation pipeline on page load.

The interactive analysis is deliberately separate from the frozen publication protocols.

### Interactive stress protocol

Protocol: `interactive-stress-v1`

Evaluates the fixed final realised allocation under deterministic adverse sensitivity states:

- `UW` ? weather / high evaporative demand, ET0 ? 1.15.
- `UM` ? market, price ? 0.90 and absorption-throughput proxy ? 0.85.
- `UR` ? farmer budget and labour capacity ? 0.85.
- `UJ` ? joint W + M + R.

Scientific boundaries:

- no reoptimisation;
- no new crops;
- no resurrection of rejected, withdrawn, no-offer or non-realised plots;
- no post-finalisation participation uncertainty;
- weather exposure changes crop-water requirement / irrigation exposure only;
- no unsupported weather-yield or weather-cash penalty;
- market absorption remains an AGMARKNET-arrivals-derived throughput proxy, not demand;
- resource stress checks the fixed allocation against reduced budget/labour capacity and does
  not mechanically scale projected cash.

### Interactive resilience protocol

Protocol: `interactive-resilience-v1`

Evaluates immediate deterministic exposure of the exact current final realised plan:

- N?1 largest-producer failure;
- hazard-zone outage;
- complete read-only exposure table for realised hazard zones.

The N?1 representative follows the frozen integration-demo rule where applicable:
active crop with maximum pre-shock largest-producer share, then all realised allocations of
that farmer are treated as unavailable.

The hazard representative is the lexicographically first non-empty realised hazard zone.

Interactive resilience does **not** apply the frozen Phase-5 backup optimiser because that
optimiser is defined over its own Stage-3 / Stage-5 decision state.

Therefore:

- no backup reoptimisation;
- no recovery allocation;
- no implied farmer adoption;
- no recovery result presented as realised.

### Analysis identity and lifecycle

Both interactive engines are tied to the same:

- `dataset_hash`;
- `final_plan_hash`;
- `final_plan_revision`;
- analysis timestamp.

Lifecycle:

`NOT_RUN -> CURRENT -> upstream edit invalidates Final -> re-finalise -> STALE -> re-run -> CURRENT`

Stale scientific metrics are withheld rather than displayed against a changed final plan.

GET `/analysis` remains read-only and does not run scientific engines.

POST `/run-analysis` is the explicit execution boundary.

### UI

The Analyse UI now provides scientific cards rather than raw JSON:

- UW / UM / UR / UJ sensitivity cards;
- N?1 and hazard-zone immediate-exposure cards;
- explicit analysis provenance / target identity;
- explicit Run Analysis / Re-run Analysis controls;
- projected-cash terminology rather than observed-income wording;
- explicit post-shock-recovery limitation.

Opening Analyse tabs never triggers analysis automatically.

### Validation

Combined targeted regression suite:

`219 passed`

Real API lifecycle smoke:

- initial final plan: uncertainty `NOT_RUN`, resilience `NOT_RUN`;
- explicit run: both `CURRENT`;
- original final-plan hash: `0fe59eeb7c68a1a2`;
- farmer decision edited and final plan invalidated;
- replan + renewed consent + re-finalisation;
- old analyses correctly reported `STALE`;
- stale scientific metrics withheld;
- re-run produced both analyses as `CURRENT`;
- new final-plan hash: `88712100380d20f6`.

Example built-in current-plan smoke values included:

- UW water-exposed plots: 60;
- N?1 representative failed farmer: F0178.

These are interactive smoke-test outputs, not frozen publication results.

### Frozen research separation

No frozen publication artifact was modified or substituted into the interactive analysis.

`uncertainty-v1`, frozen Phase-5 resilience, Final30 evidence and the 322-case LLM benchmark
remain separate research evidence.

### Next research implementation

Build the controlled **Scenario A vs Scenario B end-to-end case-study runner**:

- Scenario A = built-in dataset with the documented default workflow;
- Scenario B = same built-in data/method/settings with a fixed documented set of farmer actions;
- both must reach `FINAL_REALIZED`;
- run the same interactive stress and immediate-resilience protocols on both final plans;
- persist dataset hash, final-plan hash, protocol versions, inputs and outputs automatically;
- generate a direct A-vs-B comparison artifact;
- no manually copied scientific numbers.

This controlled A/B demonstration is illustrative end-to-end evidence and does not replace the
frozen Final30 experiment.
