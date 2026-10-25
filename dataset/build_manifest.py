#!/usr/bin/env python3
"""
build_manifest.py - Deterministic 2,000-Image Selection & Manifest Builder
Processes the Mendeley "Dataset of Spoilt Banknotes of India (Rupees)".
Verifies image readability, checks duplicates, and builds dataset/selected_2000_manifest.csv.
"""

import os
import sys
import csv
import json
import hashlib
from pathlib import Path
from collections import defaultdict
from PIL import Image

PROJECT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_DIR / "dataset" / "dataset_config.json"
MANIFEST_PATH = PROJECT_DIR / "dataset" / "selected_2000_manifest.csv"

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}

def compute_file_hash(filepath: Path) -> str:
    """Compute SHA-256 hash of file content for exact duplicate detection."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def verify_and_get_info(filepath: Path):
    """Verify image readability with Pillow and return dimensions and mode."""
    try:
        with Image.open(filepath) as img:
            w, h = img.size
            mode = img.mode
            channels = len(mode) if mode else 3
            # Ensure image can be decoded
            img.verify()
        return True, w, h, channels, "VALID_READABLE"
    except Exception as e:
        return False, 0, 0, 0, f"CORRUPT_OR_UNREADABLE: {str(e)}"

def build_manifest():
    print("=" * 65)
    print("     MENDELEY SPOILT BANKNOTE DATASET: 2,000-IMAGE MANIFEST BUILDER     ")
    print("=" * 65)

    if not CONFIG_PATH.exists():
        print(f"Error: Config file not found at {CONFIG_PATH}")
        sys.exit(1)

    with open(CONFIG_PATH, "r") as f:
        cfg = json.load(f)

    raw_root = cfg.get("dataset_root", "dataset")
    if not Path(raw_root).is_absolute():
        dataset_root = (PROJECT_DIR / raw_root).resolve()
    else:
        dataset_root = Path(raw_root)
    if not dataset_root.is_dir():
        dataset_root = (PROJECT_DIR / "dataset").resolve()
    target_count = cfg.get("target_selection_count", 2000)

    print(f"Dataset Root:    {dataset_root}")
    print(f"Target Count:    {target_count} images")

    if not dataset_root.exists() or not dataset_root.is_dir():
        print(f"\n❌ Error: Dataset directory not found at: {dataset_root}")
        print("Please verify the dataset folder inside the project or dataset/dataset_config.json.")
        sys.exit(1)

    print("\n[1/4] Scanning dataset directory recursively...")
    category_candidates = defaultdict(list)
    total_scanned = 0

    for root, _, files in os.walk(dataset_root):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in SUPPORTED_EXTS:
                full_path = Path(root) / f
                rel_path = full_path.relative_to(dataset_root)
                if "test_images" in rel_path.parts:
                    continue
                total_scanned += 1
                # Category is parent relative folder
                cat = str(rel_path.parent)
                category_candidates[cat].append((full_path, rel_path, f))

    print(f"Discovered {total_scanned} candidate image files across {len(category_candidates)} categories.")

    print("\n[2/4] Verifying readability & filtering duplicates via SHA-256...")
    seen_hashes = {}
    valid_by_category = defaultdict(list)
    duplicate_count = 0
    corrupt_count = 0

    # Sort categories for determinism
    sorted_categories = sorted(category_candidates.keys())

    for cat in sorted_categories:
        # Deterministically sort files by filename
        file_list = sorted(category_candidates[cat], key=lambda x: x[2])
        for full_path, rel_path, filename in file_list:
            f_hash = compute_file_hash(full_path)
            if f_hash in seen_hashes:
                duplicate_count += 1
                continue

            is_ok, w, h, ch, status = verify_and_get_info(full_path)
            if not is_ok:
                corrupt_count += 1
                continue

            seen_hashes[f_hash] = full_path
            
            # Extract metadata
            series = "New" if "New" in cat else "Old"
            # Extract denomination
            denom = "Unknown"
            for d in ["10", "20", "50", "100"]:
                if d in cat:
                    denom = f"Rs {d}"
                    break

            valid_by_category[cat].append({
                "full_path": str(full_path),
                "relative_path": str(rel_path),
                "filename": filename,
                "source_category": cat,
                "denomination": denom,
                "series": series,
                "width": w,
                "height": h,
                "channels": ch,
                "file_hash": f_hash,
                "file_size_bytes": full_path.stat().st_size,
                "validation_status": status
            })

    total_valid = sum(len(v) for v in valid_by_category.values())
    print(f"Total valid unique images: {total_valid} (Excluded {duplicate_count} duplicates, {corrupt_count} corrupt).")

    print(f"\n[3/4] Performing deterministic balanced selection of {target_count} images...")
    num_cats = len(valid_by_category)
    quota_per_cat = target_count // num_cats  # 2000 // 8 = 250
    remainder = target_count % num_cats

    selected_images = []
    print(f"Balanced quota per category: {quota_per_cat} images")

    for idx, cat in enumerate(sorted_categories):
        cat_items = valid_by_category[cat]
        # Deterministically sort by filename
        cat_items.sort(key=lambda x: (x["filename"], x["file_hash"]))
        
        take = quota_per_cat + (1 if idx < remainder else 0)
        selected_for_cat = cat_items[:take]
        selected_images.extend(selected_for_cat)
        print(f"  • {cat:<44}: Selected {len(selected_for_cat)} / {len(cat_items)}")

    # Ensure exact selection count
    if len(selected_images) < target_count and total_valid >= target_count:
        # Fill from available
        current_set = set(x["file_hash"] for x in selected_images)
        for cat in sorted_categories:
            for item in valid_by_category[cat]:
                if item["file_hash"] not in current_set and len(selected_images) < target_count:
                    selected_images.append(item)
                    current_set.add(item["file_hash"])

    final_count = len(selected_images)
    print(f"\nTotal selected: {final_count} images.")

    # Assign deterministic numeric IDs 1 to 2000
    for idx, item in enumerate(selected_images, 1):
        item["id"] = idx

    print(f"\n[4/4] Writing manifest to {MANIFEST_PATH}...")
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "id", "relative_path", "filename", "source_category", "denomination",
        "series", "width", "height", "channels", "file_hash", "file_size_bytes",
        "validation_status"
    ]

    with open(MANIFEST_PATH, "w", newline="", encoding="utf-8") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(selected_images)

    print("=" * 65)
    if final_count == target_count:
        print(f"✓ SUCCESS: Exactly {target_count} unique, verified images selected and registered!")
    else:
        print(f"ℹ Selection completed with {final_count} images.")
    print(f"Manifest: {MANIFEST_PATH}")
    print("=" * 65)

if __name__ == "__main__":
    build_manifest()
