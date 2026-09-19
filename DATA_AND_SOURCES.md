# Data and Sources

## Scope

FarmSync combines:

1. original third-party public data,
2. processed derivatives produced by the FarmSync ingestion pipeline,
3. synthetic research data, and
4. generated experimental results.

These classes are intentionally kept separate.

## Third-party raw data

The directory:

`data/farmsync/raw_sources/`

contains source artifacts used to construct the processed agricultural
parameter tables.

Third-party data is NOT relicensed under the FarmSync software license.
Each source remains subject to its own upstream licence, attribution
requirements, and terms.

### AGMARKNET

Provider:

Directorate of Marketing & Inspection (DMI),
Department of Agriculture & Farmers Welfare,
Government of India.

FarmSync preserves five AGMARKNET market-report CSV exports covering the
price and arrivals data used by the ingestion pipeline.

The corresponding Government of India Open Government Data catalogue
identifies the daily mandi-price dataset as generated through AGMARKNET
and released under the National Data Sharing and Accessibility Policy
(NDSAP).

Government Open Data License - India permits lawful use, copying,
publication, adaptation, and derivative works subject to attribution,
non-endorsement, and the other licence conditions.

FarmSync transformations include:

- median monthly modal prices,
- documented outlier handling,
- Rs/quintal to Rs/kg conversion,
- arrivals aggregation, and
- an explicitly labelled market-absorption proxy.

Arrivals are never represented as market demand.

Primary upstream portal:

`https://agmarknet.gov.in/`

### Cost of Cultivation

Underlying provider:

Directorate of Economics & Statistics,
Department of Agriculture & Farmers Welfare,
Government of India.

Distribution used by FarmSync:

India Data Portal.

The India Data Portal Cost of Cultivation dataset/resource declares:

`Open Data Commons Attribution License`

FarmSync uses the Cost-of-Cultivation CSV and its associated codebook.

Processed transformations retain, among other fields:

- A2+FL,
- C2,
- human labour,
- derived person-days per hectare.

Upstream references are recorded in:

`data/farmsync/processed/source_manifest.json`

### DES Area / Production / Yield

Provider:

Directorate of Economics & Statistics,
Department of Agriculture & Farmers Welfare,
Government of India.

FarmSync preserves an official APY report export used for the 2021-22
and 2022-23 crop data.

Government of India Open Government Data records publish DES
district-wise, season-wise crop area and production statistics under
NDSAP.

The DES website itself contains separately copyrighted website material.
FarmSync therefore makes no claim that the DES website, interface,
branding, or other website content is licensed by this repository.

The preserved source artifact is used only as the data input supporting
the documented research transformations.

FarmSync transformations include:

- state aggregation,
- yield = SUM(production) / SUM(area),
- tonne/ha to kg/ha conversion, and
- the documented cotton lint-to-kapas conversion.

Primary upstream data portal:

`https://data.desagri.gov.in/website/crops-apy-report-web`

## Processed derivatives

`data/farmsync/processed/`

contains FarmSync-generated processed tables derived from the raw
sources.

These include:

- `yield_state.csv`
- `cost_state.csv`
- `market_price_state.csv`
- `arrivals_state.csv`
- `absorption_proxy.csv`
- `source_manifest.json`

The source manifest records source organisations, source locations,
periods, original units, transformations, and source hashes.

Processed data must continue to be cited with its upstream provenance.

## Synthetic research data

`data/farmsync/builtin/`

contains the constructed FarmSync research instance, including the
synthetic 500-farmer / 911-plot population used by the frozen
publication experiments.

Synthetic, experimental, observed, derived, and source-grounded values
are kept explicitly distinguished through the FarmSync provenance
metadata.

No synthetic uncertainty parameter or behavioural probability is
represented as an empirically observed government statistic.

## Frozen results

`results/farmsync/`

contains generated research outputs.

The Final30 evaluation used the frozen experiment design, dataset,
solver configuration, seeds, and protocols recorded in the repository.

Generated FarmSync result artifacts are distinct from third-party raw
source data.

## Attribution and licence boundary

The FarmSync repository software licence applies only to material for
which the repository authors hold the relevant rights.

It does not override or replace licences attached to third-party data.

Users redistributing upstream source artifacts should preserve source
attribution and comply with the applicable upstream licence and terms.

Government names, logos, crests, and official marks are not licensed by
this repository, and inclusion of public data does not imply government
endorsement of FarmSync.

## Integrity

Hashes for preserved raw source artifacts are recorded in:

`data/farmsync/raw_sources/SHA256SUMS.txt`

Processed-source provenance is recorded in:

`data/farmsync/processed/source_manifest.json`

The repository's frozen scientific artifacts additionally contain their
own integrity manifests and SHA-256 records.
