"""
Crop/commodity mapping across sources (spec items 5, 6, 10, 11).

Explicit, documented mapping from source commodity/crop labels to FarmSync crops,
with excluded aliases and reasons, to prevent double-counting (e.g. Paddy vs Rice)
and product-unit mismatches (e.g. cotton lint vs kapas).
"""

# AGMARKNET commodity -> FarmSync crop (SELECTED marketed commodity only).
AGMARKNET_MAP = {
    "Paddy(Common)":                     "rice",
    "Wheat":                             "wheat",
    "Maize":                             "maize",
    "Jowar(Sorghum)":                    "sorghum",
    "Bajra(Pearl Millet/Cumbu)":         "pearl_millet",
    "Bengal Gram(Gram)(Whole)":          "chickpea",
    "Red gram/Arhar/Tur(whole)":         "pigeon_pea",
    "Groundnut":                         "groundnut",
    "Soyabean":                          "soybean",
    "Mustard":                           "mustard",
    "Cotton":                            "cotton",     # fibre group = seed cotton (kapas)
    "Potato":                            "potato",
    "Onion":                             "onion",
    "Tomato":                            "tomato",
}

# Excluded AGMARKNET aliases (documented so reviewers see the dedup decisions).
AGMARKNET_EXCLUDED = {
    "rice":       [("Rice", "milled product, different unit than paddy yield"),
                   ("Paddy(Basmati)", "premium variety, not the common production stream")],
    "chickpea":   [("Bengal Gram Dal(Chana Dal)", "split/processed dal, not whole grain"),
                   ("Kabuli Chana(Chickpeas-White)", "distinct white chickpea variety")],
    "pigeon_pea": [("Red gram split/Arhar dal/Tur dal", "processed dal, not whole grain")],
    "groundnut":  [("Ground Nut Seed", "seed for sowing, not the produce")],
    "mustard":    [("Toria", "distinct oilseed"), ("Taramira", "distinct oilseed")],
    "cotton":     [("Lint", "ginned lint — INCOMPATIBLE with kapas yield/cost"),
                   ("Cotton Seed", "oilseed byproduct, not seed cotton")],
    "pearl_millet": [("Sajje", "regional alias — avoid double count"),
                     ("Hybrid Cumbu", "variety alias"), ("T.V. Cumbu", "variety alias")],
    "onion":      [("Onion Green", "different product per FarmSync spec")],
    "potato":     [("Sweet Potato", "different crop")],
}

# DES APY crop label -> FarmSync crop. Cotton(lint) needs lint->kapas conversion.
DES_MAP = {
    "Rice": "rice", "Wheat": "wheat", "Maize": "maize", "Jowar": "sorghum",
    "Bajra": "pearl_millet", "Gram": "chickpea", "Arhar/Tur": "pigeon_pea",
    "Groundnut": "groundnut", "Soyabean": "soybean", "Rapeseed &Mustard": "mustard",
    "Cotton(lint)": "cotton", "Potato": "potato", "Onion": "onion",
    # tomato intentionally absent in DES export
}
DES_COTTON_IS_LINT = True
COTTON_GINNING_RATIO = 0.35     # kapas = lint / 0.35 (ICAR-typical)

# Cost of Cultivation crop label -> FarmSync crop.
COC_MAP = {
    "Paddy": "rice", "Wheat": "wheat", "Maize": "maize", "Jowar": "sorghum",
    "Bajra": "pearl_millet", "Gram": "chickpea", "Tur (Arhar)": "pigeon_pea",
    "Groundnut": "groundnut", "Soyabean": "soybean",
    "Rapeseed & Mustard (Toria/Taramira)": "mustard", "Cotton": "cotton",
    "Onion": "onion", "Potato": "potato",
    # tomato not present in CoC -> no cost -> not admitted
}

# FarmSync crop -> season for parameterisation (matches schemas crop seasons; veg both).
CROP_PRIMARY_SEASON = {
    "rice": "kharif", "wheat": "rabi", "maize": "kharif", "sorghum": "kharif",
    "pearl_millet": "kharif", "chickpea": "rabi", "pigeon_pea": "kharif",
    "groundnut": "kharif", "soybean": "kharif", "mustard": "rabi", "cotton": "kharif",
    "potato": "rabi", "onion": "rabi", "tomato": "kharif",
}
