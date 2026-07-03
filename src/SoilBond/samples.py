#!/usr/bin/env python3
"""Deterministic sample parcels for SoilBond."""

import copy
import json
import os

SAMPLE_PARCELS = [
    {
        "parcel_id": "P-ALPHA",
        "carbon_reduction_tco2": 150.0,
        "resilience_score": 0.85,
        "area_hectares": 20.0,
    },
    {
        "parcel_id": "P-BETA",
        "carbon_reduction_tco2": 80.0,
        "resilience_score": 0.92,
        "area_hectares": 12.0,
    },
    {
        "parcel_id": "P-GAMMA",
        "carbon_reduction_tco2": 220.0,
        "resilience_score": 0.70,
        "area_hectares": 35.0,
    },
    {
        "parcel_id": "P-DELTA",
        "carbon_reduction_tco2": 45.0,
        "resilience_score": 0.95,
        "area_hectares": 8.0,
    },
]

DEFAULT_POOL = {
    "pool_size": 100000.0,
    "per_parcel_cap": 35000.0,
    "parcels": copy.deepcopy(SAMPLE_PARCELS),
}


def parcels():
    return copy.deepcopy(SAMPLE_PARCELS)


def default_pool():
    return copy.deepcopy(DEFAULT_POOL)


def write_samples(out_dir):
    """Write sample fixtures to *out_dir* and return {name: path}."""
    os.makedirs(out_dir, exist_ok=True)
    written = {}

    for p in parcels():
        path = os.path.join(out_dir, f"{p['parcel_id'].lower()}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(p, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
        written[p["parcel_id"]] = path

    pool_path = os.path.join(out_dir, "allocation.json")
    with open(pool_path, "w", encoding="utf-8") as f:
        json.dump(default_pool(), f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    written["allocation"] = pool_path

    return written
