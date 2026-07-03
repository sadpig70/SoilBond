#!/usr/bin/env python3
"""Deterministic soil-carbon matching-pool engine (stdlib only).

SoilBond = FieldRoot (precision agriculture)
         + ClimateMesh (climate resilience)
         + QuadraticCarbonFund (quadratic funding).

Parcels are scored by carbon density and climate resilience, then a
quadratic-funding pool is allocated proportionally to score^2 with an
optional per-parcel cap whose excess is redistributed to uncapped parcels.
"""

import math


def score_parcel(parcel_id, carbon_reduction_tco2, resilience_score, area_hectares):
    """Score one agricultural parcel.

    - carbon_density  = carbon_reduction_tco2 / area_hectares
    - combined_score  = sqrt(carbon_reduction_tco2) * resilience_score

    Returns a deterministic dict describing the parcel and its scores.
    """
    if area_hectares <= 0:
        raise ValueError("area_hectares must be positive")
    if carbon_reduction_tco2 < 0:
        raise ValueError("carbon_reduction_tco2 must be non-negative")
    if not 0.0 <= resilience_score <= 1.0:
        raise ValueError("resilience_score must be within [0.0, 1.0]")

    carbon_density = carbon_reduction_tco2 / area_hectares
    combined_score = math.sqrt(carbon_reduction_tco2) * resilience_score
    return {
        "parcel_id": parcel_id,
        "carbon_reduction_tco2": carbon_reduction_tco2,
        "resilience_score": resilience_score,
        "area_hectares": area_hectares,
        "carbon_density": carbon_density,
        "combined_score": combined_score,
    }


def allocate_matching_pool(parcels, pool_size, per_parcel_cap=None):
    """Allocate a quadratic-funding pool across scored parcels.

    Quadratic funding rule: each parcel's raw match is
        pool_size * score_i^2 / sum(score_j^2).

    When *per_parcel_cap* is set, parcels whose share would exceed the cap
    are locked at the cap and the surplus is redistributed to the remaining
    uncapped parcels proportionally to their weight.  The process repeats
    until no uncapped parcel breaches the cap (water-filling).

    Returns a deterministic allocation document.
    """
    n = len(parcels)
    scores = [p["combined_score"] for p in parcels]
    weights = [s ** 2 for s in scores]
    total_weight = sum(weights)

    if total_weight <= 0:
        raw_matches = [0.0 for _ in range(n)]
    else:
        raw_matches = [pool_size * (w / total_weight) for w in weights]

    final = list(raw_matches)
    capped_flags = [False] * n

    if per_parcel_cap is not None and n > 0 and total_weight > 0:
        locked = set()
        while True:
            unlocked = [i for i in range(n) if i not in locked]
            if not unlocked:
                break
            unlocked_weight = sum(weights[i] for i in unlocked)
            if unlocked_weight <= 0:
                break
            locked_total = per_parcel_cap * len(locked)
            remaining = pool_size - locked_total
            shares = {}
            new_locks = []
            for i in unlocked:
                share = remaining * (weights[i] / unlocked_weight)
                shares[i] = share
                if share >= per_parcel_cap:
                    new_locks.append(i)
            if new_locks:
                for i in new_locks:
                    final[i] = per_parcel_cap
                    capped_flags[i] = True
                    locked.add(i)
            else:
                for i in unlocked:
                    final[i] = shares[i]
                break

    allocations = []
    for i, p in enumerate(parcels):
        allocations.append({
            "parcel_id": p["parcel_id"],
            "score": scores[i],
            "raw_match": raw_matches[i],
            "capped": capped_flags[i],
            "final_match": final[i],
        })
    total_allocated = sum(a["final_match"] for a in allocations)
    return {
        "pool_size": pool_size,
        "per_parcel_cap": per_parcel_cap,
        "allocations": allocations,
        "total_allocated": total_allocated,
    }


def render_report(result):
    """Render an allocation result as a Markdown report string."""
    pool_size = result.get("pool_size", 0.0)
    cap = result.get("per_parcel_cap")
    total_allocated = result.get("total_allocated", 0.0)
    allocations = result.get("allocations", [])

    cap_display = "none" if cap is None else f"{cap:.2f}"

    lines = [
        "# SoilBond Matching Pool Report",
        "",
        "Quadratic-funding allocation for soil-carbon reduction parcels.",
        "",
        f"- pool_size: {pool_size:.2f}",
        f"- per_parcel_cap: {cap_display}",
        f"- total_allocated: {total_allocated:.2f}",
        f"- parcels: {len(allocations)}",
        "",
        "## Allocations",
        "",
        "| parcel_id | score | raw_match | capped | final_match |",
        "|---|---|---|---|---|",
    ]
    for a in allocations:
        capped_str = "yes" if a.get("capped") else "no"
        lines.append(
            f"| {a['parcel_id']} "
            f"| {a['score']:.4f} "
            f"| {a['raw_match']:.2f} "
            f"| {capped_str} "
            f"| {a['final_match']:.2f} |"
        )
    lines.append("")
    return "\n".join(lines)
