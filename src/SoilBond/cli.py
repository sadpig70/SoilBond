#!/usr/bin/env python3
"""CLI for SoilBond."""

import argparse
import json
import sys

from .core import allocate_matching_pool, render_report, score_parcel
from .samples import write_samples


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _dump_json(doc, path=None):
    text = json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.write(text)


def cmd_sample(args):
    written = write_samples(args.out)
    _dump_json({"written": written})
    return 0


def cmd_score(args):
    if args.input:
        parcel = _load_json(args.input)
    else:
        parcel = {
            "parcel_id": args.parcel_id,
            "carbon_reduction_tco2": args.carbon,
            "resilience_score": args.resilience,
            "area_hectares": args.area,
        }
    result = score_parcel(
        parcel["parcel_id"],
        parcel["carbon_reduction_tco2"],
        parcel["resilience_score"],
        parcel["area_hectares"],
    )
    _dump_json(result, args.out)
    return 0


def cmd_allocate(args):
    doc = _load_json(args.input)
    result = _allocate_from_config(doc)
    _dump_json(result, args.out)
    return 0


def _allocate_from_config(doc):
    pool_size = doc["pool_size"]
    cap = doc.get("per_parcel_cap")
    parcels = [
        score_parcel(
            p["parcel_id"],
            p["carbon_reduction_tco2"],
            p["resilience_score"],
            p["area_hectares"],
        )
        for p in doc["parcels"]
    ]
    return allocate_matching_pool(parcels, pool_size, cap)


def cmd_report(args):
    doc = _load_json(args.input)
    if "parcels" in doc and "pool_size" in doc:
        doc = _allocate_from_config(doc)
    text = render_report(doc)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.write(text)
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="SoilBond")
    sub = p.add_subparsers(dest="cmd", required=True)

    sample = sub.add_parser("sample", help="emit deterministic sample parcel fixtures")
    sample.add_argument("--out", default="examples")
    sample.set_defaults(func=cmd_sample)

    score = sub.add_parser("score", help="score a single parcel")
    score.add_argument("--input", help="path to a parcel JSON file")
    score.add_argument("--parcel-id")
    score.add_argument("--carbon", type=float)
    score.add_argument("--resilience", type=float)
    score.add_argument("--area", type=float)
    score.add_argument("--out")
    score.set_defaults(func=cmd_score)

    allocate = sub.add_parser("allocate", help="allocate a quadratic-funding pool")
    allocate.add_argument("--input", required=True, help="path to an allocation config JSON")
    allocate.add_argument("--out")
    allocate.set_defaults(func=cmd_allocate)

    report = sub.add_parser("report", help="render a Markdown report for an allocation result")
    report.add_argument("--input", required=True, help="path to an allocation result JSON")
    report.add_argument("--out")
    report.set_defaults(func=cmd_report)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)
