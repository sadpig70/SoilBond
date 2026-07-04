#!/usr/bin/env python3
"""Stdlib-only tests for the standalone SoilBond package."""

import json
import math
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)
ENV = {**os.environ, "PYTHONPATH": SRC}

from SoilBond.core import (  # noqa: E402
    REFERENCE_CARBON_DENSITY,
    allocate_matching_pool,
    render_report,
    score_parcel,
)
from SoilBond.samples import default_pool, parcels  # noqa: E402


class TestScoreParcel(unittest.TestCase):
    def test_deterministic_values(self):
        result = score_parcel("P-ALPHA", 150.0, 0.85, 20.0)
        self.assertEqual(result["parcel_id"], "P-ALPHA")
        self.assertEqual(result["carbon_reduction_tco2"], 150.0)
        self.assertEqual(result["resilience_score"], 0.85)
        self.assertEqual(result["area_hectares"], 20.0)
        self.assertAlmostEqual(result["carbon_density"], 150.0 / 20.0)
        density_factor = math.sqrt((150.0 / 20.0) / REFERENCE_CARBON_DENSITY)
        expected_score = math.sqrt(150.0) * 0.85 * density_factor
        self.assertAlmostEqual(result["density_factor"], density_factor)
        self.assertAlmostEqual(result["combined_score"], expected_score)

    def test_repeated_call_is_identical(self):
        a = score_parcel("P-X", 100.0, 0.8, 10.0)
        b = score_parcel("P-X", 100.0, 0.8, 10.0)
        self.assertEqual(a, b)

    def test_zero_carbon(self):
        result = score_parcel("P-ZERO", 0.0, 0.5, 10.0)
        self.assertEqual(result["combined_score"], 0.0)
        self.assertEqual(result["carbon_density"], 0.0)

    def test_invalid_area_raises(self):
        with self.assertRaises(ValueError):
            score_parcel("P-BAD", 10.0, 0.5, 0.0)


class TestAllocateMatchingPool(unittest.TestCase):
    def _scored(self):
        return [score_parcel(p["parcel_id"], p["carbon_reduction_tco2"],
                             p["resilience_score"], p["area_hectares"])
                for p in parcels()]

    def test_total_equals_pool_without_cap(self):
        scored = self._scored()
        result = allocate_matching_pool(scored, pool_size=100000.0)
        self.assertAlmostEqual(result["total_allocated"], 100000.0, places=6)
        self.assertEqual(len(result["allocations"]), 4)
        for a in result["allocations"]:
            self.assertFalse(a["capped"])
            self.assertAlmostEqual(a["raw_match"], a["final_match"], places=6)

    def test_quadratic_proportion(self):
        scored = self._scored()
        result = allocate_matching_pool(scored, pool_size=100000.0)
        weights = [a["score"] ** 2 for a in result["allocations"]]
        total_weight = sum(weights)
        for a, w in zip(result["allocations"], weights):
            expected = 100000.0 * (w / total_weight)
            self.assertAlmostEqual(a["raw_match"], expected, places=6)

    def test_cap_respected_and_total_preserved(self):
        scored = self._scored()
        cap = 25000.0
        result = allocate_matching_pool(scored, pool_size=100000.0, per_parcel_cap=cap)
        self.assertAlmostEqual(result["total_allocated"], 100000.0, places=4)
        self.assertAlmostEqual(result["unallocated_amount"], 0.0, places=4)
        self.assertFalse(result["cap_exhausted"])
        for a in result["allocations"]:
            self.assertLessEqual(a["final_match"], cap + 1e-6)
        at_least_one_capped = any(a["capped"] for a in result["allocations"])
        self.assertTrue(at_least_one_capped)

    def test_deterministic_repeat(self):
        scored = self._scored()
        a = allocate_matching_pool(scored, 50000.0, 20000.0)
        b = allocate_matching_pool(scored, 50000.0, 20000.0)
        self.assertEqual(a, b)

    def test_unallocated_amount_when_cap_exhausted(self):
        scored = self._scored()
        result = allocate_matching_pool(scored, pool_size=100000.0, per_parcel_cap=10000.0)
        self.assertAlmostEqual(result["total_allocated"], 40000.0, places=4)
        self.assertAlmostEqual(result["unallocated_amount"], 60000.0, places=4)
        self.assertTrue(result["cap_exhausted"])


class TestRenderReport(unittest.TestCase):
    def test_report_contains_key_sections(self):
        scored = [score_parcel(p["parcel_id"], p["carbon_reduction_tco2"],
                               p["resilience_score"], p["area_hectares"])
                  for p in parcels()]
        result = allocate_matching_pool(scored, 100000.0)
        text = render_report(result)
        self.assertIn("# SoilBond Matching Pool Report", text)
        self.assertIn("## Allocations", text)
        self.assertIn("P-ALPHA", text)
        self.assertIn("total_allocated", text)


class TestCLI(unittest.TestCase):
    def test_sample_score_allocate_report(self):
        with tempfile.TemporaryDirectory() as d:
            sample_out = subprocess.check_output(
                [sys.executable, "-m", "SoilBond", "sample", "--out", d],
                cwd=ROOT, env=ENV, text=True,
            )
            written = json.loads(sample_out)["written"]
            self.assertIn("allocation", written)

            score_out = subprocess.check_output(
                [sys.executable, "-m", "SoilBond", "score",
                 "--input", written["P-ALPHA"]],
                cwd=ROOT, env=ENV, text=True,
            )
            scored = json.loads(score_out)
            self.assertEqual(scored["parcel_id"], "P-ALPHA")
            self.assertIn("combined_score", scored)

            alloc_out = subprocess.check_output(
                [sys.executable, "-m", "SoilBond", "allocate",
                 "--input", written["allocation"]],
                cwd=ROOT, env=ENV, text=True,
            )
            alloc = json.loads(alloc_out)
            self.assertAlmostEqual(alloc["total_allocated"], 100000.0, places=4)
            self.assertEqual(len(alloc["allocations"]), 4)

            report_path = os.path.join(d, "report.md")
            subprocess.check_output(
                [sys.executable, "-m", "SoilBond", "report",
                 "--input", written["allocation"], "--out", report_path],
                cwd=ROOT, env=ENV, text=True,
            )
            with open(report_path, "r", encoding="utf-8") as f:
                report = f.read()
            self.assertIn("# SoilBond Matching Pool Report", report)

    def test_score_via_flags(self):
        out = subprocess.check_output(
            [sys.executable, "-m", "SoilBond", "score",
             "--parcel-id", "P-CLI", "--carbon", "100", "--resilience", "0.8", "--area", "10"],
            cwd=ROOT, env=ENV, text=True,
        )
        result = json.loads(out)
        self.assertEqual(result["parcel_id"], "P-CLI")
        self.assertAlmostEqual(result["carbon_density"], 10.0)


if __name__ == "__main__":
    unittest.main()
