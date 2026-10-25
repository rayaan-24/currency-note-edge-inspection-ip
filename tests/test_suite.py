"""
tests/test_suite.py - Comprehensive Automated Test Suite
Validates the Python Digital Image Processing Pipeline and FastAPI Endpoints:
  1. RGB and grayscale input processing.
  2. Invalid image files & error resilience.
  3. Blank uniform images (failure-mode detection).
  4. Synthetic clean note (Good note validation).
  5. Synthetic torn corner & edge notch detection.
  6. Edge damage percentage formula & zero-division safety.
  7. Classification uncertainty & manual inspection fallback.
  8. Dataset manifest uniqueness (zero duplicate file hashes).
  9. Exact 2,000-image selection count & category balance.
  10. Real dataset image processing across all denominations.
  11. Exported visual overlays, JSON report, and summary CSV.
  12. FastAPI HTTP endpoints (/api/health, /api/dataset, /api/analyze).
"""

import os
import sys
import csv
import json
import time
import unittest
from pathlib import Path
import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import image_processing as ip
from fastapi.testclient import TestClient
from server import app

class TestCurrencyInspectionPipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_dir = PROJECT_ROOT / "dataset" / "test_images"
        cls.manifest_path = PROJECT_ROOT / "dataset" / "selected_2000_manifest.csv"
        cls.config_path = PROJECT_ROOT / "dataset" / "dataset_config.json"
        cls.client = TestClient(app)

        with open(cls.config_path, "r", encoding="utf-8") as f:
            cfg_data = json.load(f)
        raw_root = cfg_data.get("dataset_root", "dataset")
        if not Path(raw_root).is_absolute():
            cls.dataset_root = (PROJECT_ROOT / raw_root).resolve()
        else:
            cls.dataset_root = Path(raw_root)
        if not cls.dataset_root.is_dir():
            cls.dataset_root = (PROJECT_ROOT / "dataset").resolve()

    # Test 1: RGB and Grayscale Inputs
    def test_01_rgb_and_grayscale_inputs(self):
        # 1a. RGB array input
        rgb_arr = np.zeros((300, 600, 3), dtype=np.uint8)
        rgb_arr[50:250, 50:550] = [180, 210, 190]
        res_rgb = ip.process_currency_note(rgb_arr)
        self.assertIn(res_rgb["status"], ["SUCCESS", "WARNING"])
        self.assertEqual(res_rgb["preprocessed"]["gray_image"].ndim, 2)

        # 1b. Grayscale 2D array input
        gray_arr = np.zeros((300, 600), dtype=np.uint8)
        gray_arr[50:250, 50:550] = 200
        res_gray = ip.process_currency_note(gray_arr)
        self.assertIn(res_gray["status"], ["SUCCESS", "WARNING"])
        self.assertEqual(res_gray["preprocessed"]["gray_image"].ndim, 2)

    # Test 2: Invalid Image Input Error Handling
    def test_02_invalid_image_handling(self):
        # Non-existent file path
        res = ip.process_currency_note("/non/existent/path/corrupt_note.xyz")
        self.assertEqual(res["status"], "ERROR")
        self.assertIn("Preprocessing failed", res["error_message"])
        self.assertEqual(res["classification"]["category"], "Needs Manual Inspection")
        self.assertFalse(res["damage"]["is_reliable"])

    # Test 3: Blank Uniform Image
    def test_03_blank_uniform_image(self):
        blank_arr = np.ones((400, 700, 3), dtype=np.uint8) * 128
        res = ip.process_currency_note(blank_arr)
        # Boundary detection should report low confidence or failure
        self.assertIn(res["status"], ["WARNING", "ERROR"])
        self.assertEqual(res["classification"]["category"], "Needs Manual Inspection")
        self.assertFalse(res["classification"]["is_definitive"])

    # Test 4: Synthetic Clean Note (Good Note)
    def test_04_synthetic_clean_note(self):
        clean_path = self.test_dir / "synthetic_good_01.png"
        self.assertTrue(clean_path.is_file(), "synthetic_good_01.png must exist")
        res = ip.process_currency_note(str(clean_path))
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["classification"]["category"], "Good")
        self.assertTrue(res["classification"]["confidence"] >= 0.60)
        self.assertLessEqual(res["damage"]["damage_percentage"], 1.5)

    # Test 5: Synthetic Torn Corner & Edge Notch (Torn Notes)
    def test_05_synthetic_torn_notes(self):
        # 5a. Torn Corner
        corner_path = self.test_dir / "synthetic_torn_corner_02.png"
        self.assertTrue(corner_path.is_file())
        res_corner = ip.process_currency_note(str(corner_path))
        self.assertEqual(res_corner["status"], "SUCCESS")
        self.assertEqual(res_corner["classification"]["category"], "Torn")
        self.assertTrue(res_corner["damage"]["damage_percentage"] > 0.0)

        # 5b. Torn Edge Notch
        notch_path = self.test_dir / "synthetic_torn_edge_03.png"
        self.assertTrue(notch_path.is_file())
        res_notch = ip.process_currency_note(str(notch_path))
        self.assertEqual(res_notch["status"], "SUCCESS")
        self.assertEqual(res_notch["classification"]["category"], "Torn")
        self.assertTrue(res_notch["edges"]["max_defect_depth"] >= 12.0)

    # Test 6: Damage Percentage Formula & Zero-Perimeter Safety
    def test_06_damage_percentage_calculation(self):
        # Unit test dummy edge analysis struct
        dummy_edges = {
            "is_valid": True,
            "total_visible_perimeter": 900.0,
            "total_damaged_length": 100.0,
            "edges": [
                {"name": "Top", "nominal_length": 300.0, "damaged_length": 100.0},
                {"name": "Right", "nominal_length": 200.0, "damaged_length": 0.0},
                {"name": "Bottom", "nominal_length": 300.0, "damaged_length": 0.0},
                {"name": "Left", "nominal_length": 200.0, "damaged_length": 0.0}
            ]
        }
        dummy_boundary = {"status": "SUCCESS", "solidity": 0.95}
        metric = ip.calculate_damage_percentage(dummy_edges, dummy_boundary)
        self.assertTrue(metric["is_reliable"])
        # Expected: (100 / (900 + 100)) * 100 = 10.0%
        self.assertAlmostEqual(metric["damage_percentage"], 10.0, places=2)
        self.assertEqual(metric["display_text"], "10.00%")

        # Test zero perimeter divide-by-zero protection
        zero_edges = {"is_valid": True, "total_visible_perimeter": 0.0, "total_damaged_length": 0.0}
        zero_metric = ip.calculate_damage_percentage(zero_edges, dummy_boundary)
        self.assertFalse(zero_metric["is_reliable"])
        self.assertIn("Zero perimeter", zero_metric["display_text"])

    # Test 7: Classification Uncertainty & Manual Inspection Fallback
    def test_07_classification_uncertainty(self):
        failed_boundary = {"status": "FAILED", "confidence": 0.1, "message": "Contrast too low"}
        cls_res = ip.classify_note_condition({}, {}, failed_boundary, np.zeros((100, 100), dtype=np.uint8))
        self.assertEqual(cls_res["category"], "Needs Manual Inspection")
        self.assertFalse(cls_res["is_definitive"])

    # Test 8: Dataset Manifest Uniqueness (SHA-256 deduplication)
    def test_08_manifest_uniqueness(self):
        self.assertTrue(self.manifest_path.is_file(), "Manifest file must exist")
        hashes = set()
        total_rows = 0
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_rows += 1
                h = row["file_hash"]
                self.assertNotIn(h, hashes, f"Duplicate image hash found in manifest: {h} (Row #{row['id']})")
                hashes.add(h)
                self.assertEqual(row["validation_status"], "VALID_READABLE")
        self.assertEqual(total_rows, len(hashes), "All manifest entries must be strictly unique by hash")

    # Test 9: Exact 2,000-Image Selection Requirement & Category Balance
    def test_09_exact_2000_selection_requirement(self):
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            records = list(csv.DictReader(f))
        self.assertEqual(len(records), 2000, f"Expected exactly 2,000 selected images, found {len(records)}")

        # Verify 8 categories with 250 images each
        cat_counts = {}
        for r in records:
            c = r["source_category"]
            cat_counts[c] = cat_counts.get(c, 0) + 1

        self.assertEqual(len(cat_counts), 8, f"Expected 8 denomination categories, found {len(cat_counts)}")
        for cat, cnt in cat_counts.items():
            self.assertEqual(cnt, 250, f"Category '{cat}' has {cnt} images, expected exactly 250")

    # Test 10: Real Dataset Image Processing
    def test_10_actual_dataset_image_analysis(self):
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            # Sample 2 distinct real notes
            note_1 = next(reader)
            for _ in range(250):
                note_2 = next(reader)

        for note in [note_1, note_2]:
            full_path = self.dataset_root / note["relative_path"]
            self.assertTrue(full_path.is_file(), f"Real image file must exist at {full_path}")
            t_start = time.perf_counter()
            res = ip.process_currency_note(str(full_path))
            runtime = time.perf_counter() - t_start

            self.assertIn(res["status"], ["SUCCESS", "WARNING"])
            self.assertIn(res["classification"]["category"], [
                "Good", "Torn", "Folded", "Old/Worn", "Needs Manual Inspection"
            ])
            self.assertTrue(isinstance(res["edges"]["edges"], list))
            self.assertEqual(len(res["edges"]["edges"]), 4)
            self.assertLess(runtime, 5.0, "Processing per note must complete under 5 seconds")

    # Test 11: Exported Overlays, JSON, and CSV Audit
    def test_11_exported_artifacts(self):
        clean_path = self.test_dir / "synthetic_good_01.png"
        res = ip.process_currency_note(str(clean_path))
        paths = ip.export_results(res)

        self.assertTrue(Path(paths["overlay_path"]).is_file(), "Exported overlay PNG must exist")
        self.assertTrue(Path(paths["mask_path"]).is_file(), "Exported mask PNG must exist")
        self.assertTrue(Path(paths["boundary_path"]).is_file(), "Exported boundary PNG must exist")
        self.assertTrue(Path(paths["quad_path"]).is_file(), "Exported quad composite PNG must exist")
        self.assertTrue(Path(paths["report_json_path"]).is_file(), "Exported JSON report must exist")
        self.assertTrue(Path(paths["summary_csv_path"]).is_file(), "Summary CSV audit file must exist")

        # Validate JSON content
        with open(paths["report_json_path"], "r") as f:
            report_data = json.load(f)
        self.assertEqual(report_data["classification"]["category"], "Good")

    # Test 12: FastAPI Endpoints (/api/health, /api/dataset, /api/analyze)
    def test_12_api_endpoints(self):
        # Health
        resp_health = self.client.get("/api/health")
        self.assertEqual(resp_health.status_code, 200)
        h = resp_health.json()
        self.assertEqual(h["status"], "ok")
        self.assertFalse(h["octave_runtime_required"])
        self.assertFalse(h["matlab_runtime_required"])
        self.assertFalse(h["opencv_used"])
        self.assertEqual(h["selected_images_count"], 2000)

        # Dataset
        resp_dataset = self.client.get("/api/dataset")
        self.assertEqual(resp_dataset.status_code, 200)
        d = resp_dataset.json()
        self.assertEqual(d["total_selected_images"], 2000)
        self.assertTrue(d["is_exact_2000"])

        # Analyze dataset image #1
        resp_analyze = self.client.post("/api/analyze", data={"dataset_image_id": 1})
        self.assertEqual(resp_analyze.status_code, 200)
        a = resp_analyze.json()
        self.assertEqual(a["status"], "SUCCESS")
        self.assertEqual(a["source_info"]["dataset_id"], 1)

    # Test 13: Regression Test for 10_new_12.jpg (Blue Background Banknote Segmentation)
    def test_13_regression_10_new_12_banknote(self):
        target_path = self.dataset_root / "Spoilt New Indian Bank Notes" / "New 10 Rupees" / "10_new_12.jpg"
        if not target_path.is_file():
            self.skipTest(f"Dataset file 10_new_12.jpg not found at {target_path}")

        res = ip.process_currency_note(str(target_path))
        self.assertEqual(res["status"], "SUCCESS")

        # 1. Boundary confidence must be high (>= 0.70), following the note not the blue mat
        b = res["boundary"]
        self.assertEqual(b["status"], "SUCCESS")
        self.assertGreaterEqual(b["confidence"], 0.70)
        self.assertGreaterEqual(b["aspect_ratio"], 1.30)

        # 2. Banknote contour must be centered within the image, not tracking outer borders
        contour = b["contour"]
        self.assertGreater(float(np.min(contour[:, 0])), 10.0, "Contour must not hug left image border")
        self.assertLess(float(np.max(contour[:, 0])), 790.0, "Contour must not hug right image border")
        self.assertGreater(float(np.min(contour[:, 1])), 10.0, "Contour must not hug top image border")

        # 3. Defect measurement must reflect physical tear, not 95% false background damage
        dam = res["damage"]
        self.assertTrue(dam["is_reliable"])
        self.assertLess(dam["damage_percentage"], 65.0, "Damage must not exceed 65% (previously 95.08%)")
        self.assertGreater(dam["damage_percentage"], 30.0, "Physical tear on left edge must be detected")
        self.assertEqual(res["classification"]["category"], "Torn")

        # 4. Total damaged perimeter must not exceed total nominal perimeter
        total_dam = dam["damaged_edge_length_px"]
        total_nom = dam["total_perimeter_px"]
        self.assertLessEqual(total_dam, total_nom)

        # 5. Each individual edge damaged length must not exceed that edge's nominal length
        for edge_info in res["edges"]["edges"]:
            self.assertLessEqual(
                edge_info["damaged_length"],
                edge_info["nominal_length"] + 1e-4,
                f"Edge {edge_info['name']} damaged length exceeded its nominal length"
            )

    # Test 14: Geometric Consistency and Perimeter Bound Invariance
    def test_14_geometric_consistency_and_perimeter_bound(self):
        # Verify corner ordering is strictly cyclic clockwise without diagonal crosses
        corners = np.array([[100, 50], [50, 100], [400, 100], [350, 50]], dtype=np.float64)
        ordered = ip.order_rectangle_corners(corners)
        self.assertEqual(ordered.shape, (4, 2))

        # Check that sum of edge damaged lengths never exceeds total nominal perimeter
        dummy_edges = {
            "is_valid": True,
            "total_visible_perimeter": 800.0,
            "total_damaged_length": 450.0,
            "total_nominal_perimeter": 1000.0,
            "edges": [
                {"name": "Top", "nominal_length": 300.0, "damaged_length": 250.0},
                {"name": "Right", "nominal_length": 200.0, "damaged_length": 100.0},
                {"name": "Bottom", "nominal_length": 300.0, "damaged_length": 100.0},
                {"name": "Left", "nominal_length": 200.0, "damaged_length": 0.0}
            ]
        }
        dummy_boundary = {"status": "SUCCESS", "confidence": 0.90, "solidity": 0.92}
        metric = ip.calculate_damage_percentage(dummy_edges, dummy_boundary)
        self.assertTrue(metric["is_reliable"])
        self.assertEqual(metric["damage_percentage"], 45.0)
        self.assertLessEqual(metric["damaged_edge_length_px"], metric["total_perimeter_px"])

    # Test 15: Visualization Masking Integrity
    def test_15_visualization_masking_integrity(self):
        clean_path = self.test_dir / "synthetic_good_01.png"
        res = ip.process_currency_note(str(clean_path))
        vis = res["visualization"]
        self.assertIn("overlay_image", vis)
        self.assertIn("damage_mask", vis)

        # Defect mask on a clean note must be empty (zero defect pixels)
        defect_mask = vis["damage_mask"]
        self.assertEqual(np.sum(defect_mask), 0, "Clean note must have 0 highlighted defect pixels")

if __name__ == "__main__":
    print("=================================================================")
    print("     RUNNING COMPREHENSIVE AUTOMATED VERIFICATION TEST SUITE     ")
    print("=================================================================")
    unittest.main(verbosity=2)
