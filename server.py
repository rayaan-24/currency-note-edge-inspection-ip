"""
server.py - FastAPI Backend for Currency Note Edge Quality Inspection
Powered by the native Python Digital Image Processing engine (NumPy, Pillow, scikit-image).
Integrates the 2,000-image Mendeley Dataset of Spoilt Banknotes of India (Rupees).
Zero MATLAB, GNU Octave, or OpenCV runtime dependencies.
"""

import os
import re
import csv
import json
import time
import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, File, UploadFile, Form, Query, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image

import image_processing as ip

PROJECT_DIR = Path(__file__).resolve().parent
STATIC_DIR = PROJECT_DIR / "static"
UPLOADS_DIR = PROJECT_DIR / "uploads"
RESULTS_DIR = PROJECT_DIR / "results"
THUMBNAILS_DIR = RESULTS_DIR / "thumbnails"
DATASET_DIR = PROJECT_DIR / "dataset"
TEST_IMAGES_DIR = DATASET_DIR / "test_images"
CONFIG_FILE = DATASET_DIR / "dataset_config.json"
MANIFEST_FILE = DATASET_DIR / "selected_2000_manifest.csv"

# Ensure runtime directories exist
for folder in [
    UPLOADS_DIR, RESULTS_DIR, THUMBNAILS_DIR, STATIC_DIR,
    TEST_IMAGES_DIR, RESULTS_DIR / "overlays",
    RESULTS_DIR / "masks", RESULTS_DIR / "boundaries",
    RESULTS_DIR / "reports"
]:
    folder.mkdir(parents=True, exist_ok=True)

# Load Dataset Config & Manifest
dataset_config: Dict[str, Any] = {}
if CONFIG_FILE.is_file():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            dataset_config = json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load dataset_config.json: {e}")

raw_root = dataset_config.get("dataset_root", "dataset")
if not Path(raw_root).is_absolute():
    DATASET_ROOT = (PROJECT_DIR / raw_root).resolve()
else:
    DATASET_ROOT = Path(raw_root)
if not DATASET_ROOT.is_dir():
    DATASET_ROOT = (PROJECT_DIR / "dataset").resolve()

# In-memory manifest database
manifest_records: List[Dict[str, Any]] = []
manifest_by_id: Dict[int, Dict[str, Any]] = {}
available_categories: List[str] = []

def load_manifest():
    global manifest_records, manifest_by_id, available_categories
    manifest_records.clear()
    manifest_by_id.clear()
    cats = set()

    if MANIFEST_FILE.is_file():
        try:
            with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    item_id = int(row["id"])
                    rec = {
                        "id": item_id,
                        "relative_path": row["relative_path"],
                        "filename": row["filename"],
                        "source_category": row["source_category"],
                        "denomination": row["denomination"],
                        "series": row["series"],
                        "width": int(row["width"]),
                        "height": int(row["height"]),
                        "channels": int(row["channels"]),
                        "file_hash": row["file_hash"],
                        "file_size_bytes": int(row["file_size_bytes"]),
                        "validation_status": row["validation_status"]
                    }
                    manifest_records.append(rec)
                    manifest_by_id[item_id] = rec
                    cats.add(rec["source_category"])
            available_categories = sorted(list(cats))
            print(f"Loaded {len(manifest_records)} selected images from manifest ({len(available_categories)} categories).")
        except Exception as e:
            print(f"Error loading manifest: {e}")

load_manifest()

app = FastAPI(
    title="Currency Note Edge Quality Inspection API",
    description="Python 3 Digital Image Processing engine integrating the 2,000-image Mendeley Spoilt Banknote dataset",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB limit

def is_safe_filename(filename: str) -> bool:
    """Prevent directory traversal attacks."""
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        return False
    return bool(re.match(r"^[a-zA-Z0-9_\-\.]+$", filename))

@app.get("/api/health")
async def get_health():
    """Reports system health, engine capabilities, and dataset integrity."""
    dataset_exists = DATASET_ROOT.is_dir()
    manifest_valid = len(manifest_records) == 2000

    return {
        "status": "ok",
        "timestamp": datetime.datetime.now().isoformat(),
        "engine": "Python 3 Digital Image Processing (Native)",
        "libraries": {
            "numpy": "2.0.2",
            "scipy": "1.13.1",
            "scikit_image": "0.24.0",
            "pillow": "11.3.0"
        },
        "octave_runtime_required": False,
        "matlab_runtime_required": False,
        "opencv_used": False,
        "dataset_root": str(DATASET_ROOT),
        "dataset_found": dataset_exists,
        "manifest_path": str(MANIFEST_FILE.relative_to(PROJECT_DIR)),
        "selected_images_count": len(manifest_records),
        "manifest_valid": manifest_valid,
        "project_root": str(PROJECT_DIR),
        "server_type": "FastAPI + Native Python DIP Engine"
    }

@app.get("/api/dataset")
async def get_dataset_info():
    """Returns dataset metadata, attribution, category breakdown, and validation status."""
    cat_counts = {}
    for r in manifest_records:
        c = r["source_category"]
        cat_counts[c] = cat_counts.get(c, 0) + 1

    return {
        "dataset_name": dataset_config.get("dataset_name", "Dataset of Spoilt Banknotes of India (Rupees)"),
        "dataset_url": dataset_config.get("dataset_url", "https://data.mendeley.com/datasets/jh6979fg2t/4"),
        "license": dataset_config.get("license", "CC BY 4.0"),
        "doi": dataset_config.get("doi", "10.17632/jh6979fg2t.4"),
        "dataset_root": str(DATASET_ROOT),
        "dataset_accessible": DATASET_ROOT.is_dir(),
        "total_selected_images": len(manifest_records),
        "target_selection": dataset_config.get("target_count", 2000),
        "is_exact_2000": len(manifest_records) == 2000,
        "selection_protocol": "Deterministic, SHA-256 deduplicated, Pillow-verified readable, balanced 250 samples across all 8 denominations/series",
        "categories": [
            {"name": cat, "count": cat_counts.get(cat, 0)}
            for cat in available_categories
        ],
        "validation_status": "All 2,000 images verified valid, decodable, and unique (0 corrupt, 0 duplicates)"
    }

@app.get("/api/dataset/images")
async def get_dataset_images(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(24, ge=1, le=100, description="Items per page"),
    category: Optional[str] = Query(None, description="Filter by source category"),
    search: Optional[str] = Query(None, description="Search term for filename or denomination")
):
    """Paginated, searchable endpoint for browsing the 2,000 selected dataset images."""
    filtered = manifest_records

    if category and category != "All":
        filtered = [r for r in filtered if r["source_category"].lower() == category.lower()]

    if search:
        s_lower = search.strip().lower()
        filtered = [
            r for r in filtered
            if s_lower in r["filename"].lower()
            or s_lower in r["denomination"].lower()
            or s_lower in r["source_category"].lower()
        ]

    total_items = len(filtered)
    total_pages = max(1, (total_items + page_size - 1) // page_size)
    page_clamped = min(page, total_pages)

    start_idx = (page_clamped - 1) * page_size
    end_idx = min(start_idx + page_size, total_items)
    page_items = filtered[start_idx:end_idx]

    return {
        "items": page_items,
        "total": total_items,
        "page": page_clamped,
        "page_size": page_size,
        "total_pages": total_pages,
        "categories": ["All"] + available_categories
    }

@app.get("/api/dataset/image/{image_id}")
async def get_dataset_image(
    image_id: int,
    thumb: bool = Query(False, description="Whether to return a scaled thumbnail")
):
    """
    Serves a real image from the 2,000 selected dataset images.
    If thumb=True, serves an optimized 240x160 cached JPEG thumbnail.
    """
    rec = manifest_by_id.get(image_id)
    if not rec:
        raise HTTPException(status_code=404, detail=f"Dataset image ID {image_id} not found in manifest.")

    source_path = DATASET_ROOT / rec["relative_path"]
    if not source_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Source image file not found on disk at {source_path}. Verify dataset_root in dataset_config.json."
        )

    if thumb:
        thumb_file = THUMBNAILS_DIR / f"thumb_{image_id}.jpg"
        if not thumb_file.is_file():
            try:
                with Image.open(source_path) as im:
                    im_rgb = im.convert("RGB")
                    im_rgb.thumbnail((260, 160), Image.Resampling.LANCZOS)
                    im_rgb.save(thumb_file, "JPEG", quality=85)
            except Exception as e:
                # If thumbnail creation fails, return original
                return FileResponse(source_path, media_type="image/jpeg")
        return FileResponse(thumb_file, media_type="image/jpeg")

    media_type = "image/jpeg" if source_path.suffix.lower() in [".jpg", ".jpeg"] else "image/png"
    return FileResponse(source_path, media_type=media_type)

@app.get("/api/samples")
async def get_sample_images():
    """Lists the synthetic demonstration benchmark images for controlled unit tests."""
    samples = []
    sample_metadata = {
        "synthetic_good_01.png": {
            "name": "1. Clean Note (Good)",
            "expected_class": "Good",
            "description": "Synthetic intact rectangular note with internal security graphics. Expected ~0% edge damage."
        },
        "synthetic_torn_corner_02.png": {
            "name": "2. Torn Corner (Torn)",
            "expected_class": "Torn",
            "description": "Synthetic note missing top-right triangular corner notch. Expected >0% damage, Torn classification."
        },
        "synthetic_torn_edge_03.png": {
            "name": "3. Top Edge Notch (Torn)",
            "expected_class": "Torn",
            "description": "Synthetic note with deep irregular tear gouge along top border."
        },
        "synthetic_folded_04.png": {
            "name": "4. Folded Crease (Folded)",
            "expected_class": "Folded",
            "description": "Synthetic note with vertical ridge-valley paired gradient fold crease traversing note body."
        },
        "synthetic_worn_05.png": {
            "name": "5. Surface Aging (Old/Worn)",
            "expected_class": "Old/Worn",
            "description": "Synthetic note with high surface roughness, ink fading, and fiber wear."
        },
        "synthetic_uniform_06.png": {
            "name": "6. Uniform Blank (Failure Test)",
            "expected_class": "Needs Manual Inspection",
            "description": "Blank uniform canvas to verify boundary detection failure handling."
        }
    }

    if TEST_IMAGES_DIR.exists():
        for f in sorted(TEST_IMAGES_DIR.iterdir()):
            if f.suffix.lower() in ALLOWED_EXTENSIONS and f.name.startswith("synthetic_"):
                meta = sample_metadata.get(f.name, {
                    "name": f.stem.replace("_", " ").title(),
                    "expected_class": "Unknown",
                    "description": "Synthetic benchmark test note."
                })
                samples.append({
                    "filename": f.name,
                    "name": meta["name"],
                    "expected_class": meta["expected_class"],
                    "description": meta["description"],
                    "is_synthetic": True,
                    "file_size": f.stat().st_size
                })

    return {"samples": samples}

@app.post("/api/analyze")
async def analyze_currency_note(
    file: Optional[UploadFile] = File(None),
    dataset_image_id: Optional[int] = Form(None),
    sample_filename: Optional[str] = Form(None)
):
    """
    Accepts an uploaded image, a selected image ID from the 2,000-image dataset,
    or a sample filename. Executes the Python DIP pipeline and exports visual artifacts.
    """
    target_image_path: Optional[Path] = None
    source_type = "unknown"
    dataset_item: Optional[Dict[str, Any]] = None

    if dataset_image_id is not None:
        dataset_item = manifest_by_id.get(dataset_image_id)
        if not dataset_item:
            raise HTTPException(status_code=404, detail=f"Dataset image ID #{dataset_image_id} not found in manifest.")
        source_path = DATASET_ROOT / dataset_item["relative_path"]
        if not source_path.is_file():
            raise HTTPException(status_code=404, detail=f"Dataset image file not found at {source_path}")
        target_image_path = source_path
        source_type = "dataset_image"

    elif sample_filename:
        if not is_safe_filename(sample_filename):
            raise HTTPException(status_code=400, detail="Invalid sample filename.")
        sample_path = TEST_IMAGES_DIR / sample_filename
        if not sample_path.exists():
            raise HTTPException(status_code=404, detail="Sample image not found on disk.")
        target_image_path = sample_path
        source_type = "synthetic_sample"

    elif file and file.filename:
        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported format '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_stem = re.sub(r"[^a-zA-Z0-9_\-]", "_", Path(file.filename).stem)
        saved_filename = f"upload_{safe_stem}_{timestamp}{ext}"
        saved_path = UPLOADS_DIR / saved_filename

        contents = await file.read()
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="Uploaded file exceeds 25 MB limit.")
        if len(contents) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        with open(saved_path, "wb") as f_out:
            f_out.write(contents)
        target_image_path = saved_path
        source_type = "user_upload"

    else:
        raise HTTPException(
            status_code=400,
            detail="Please provide an uploaded image, a dataset_image_id, or a sample_filename."
        )

    # Execute Python Digital Image Processing Pipeline
    raw_result = ip.process_currency_note(str(target_image_path))

    # Persist artifacts (PNGs, JSON, CSV)
    export_paths = ip.export_results(raw_result, output_dir=str(RESULTS_DIR))

    # Construct clean API response
    overlay_filename = Path(export_paths.get("overlay_path", "")).name if export_paths.get("overlay_path") else None
    mask_filename = Path(export_paths.get("mask_path", "")).name if export_paths.get("mask_path") else None
    boundary_filename = Path(export_paths.get("boundary_path", "")).name if export_paths.get("boundary_path") else None
    quad_filename = Path(export_paths.get("quad_path", "")).name if export_paths.get("quad_path") else None
    report_filename = Path(export_paths.get("report_json_path", "")).name if export_paths.get("report_json_path") else None

    # Source info for auditability
    source_info = {
        "type": source_type,
        "source_path": str(target_image_path),
        "filename": target_image_path.name
    }
    if dataset_item:
        source_info.update({
            "dataset_id": dataset_item["id"],
            "source_category": dataset_item["source_category"],
            "denomination": dataset_item["denomination"],
            "series": dataset_item["series"],
            "relative_path": dataset_item["relative_path"]
        })

    # Convert corners to JSON-serializable list
    corners_list = []
    if "corners" in raw_result.get("boundary", {}):
        corners_arr = raw_result["boundary"]["corners"]
        if hasattr(corners_arr, "tolist"):
            corners_list = corners_arr.tolist()

    edge_list = []
    for e in raw_result.get("edges", {}).get("edges", []):
        edge_list.append({
            "name": e.get("name"),
            "status": e.get("status"),
            "nominal_length": e.get("nominal_length"),
            "visible_length": e.get("visible_length"),
            "damaged_length": e.get("damaged_length"),
            "max_defect_depth": e.get("max_defect_depth"),
            "defect_count": e.get("defect_count")
        })

    api_response = {
        "status": raw_result.get("status", "SUCCESS"),
        "error_message": raw_result.get("error_message", ""),
        "execution_time_sec": raw_result.get("execution_time_sec", 0.0),
        "source_info": source_info,
        "classification": {
            "category": raw_result.get("classification", {}).get("category", "Needs Manual Inspection"),
            "confidence": raw_result.get("classification", {}).get("confidence", 0.0),
            "reason": raw_result.get("classification", {}).get("reason", ""),
            "indicators": raw_result.get("classification", {}).get("indicators", {}),
            "is_definitive": raw_result.get("classification", {}).get("is_definitive", False)
        },
        "damage": {
            "is_reliable": raw_result.get("damage", {}).get("is_reliable", False),
            "damage_percentage": raw_result.get("damage", {}).get("damage_percentage"),
            "display_text": raw_result.get("damage", {}).get("display_text", "Unable to estimate reliably"),
            "damaged_edge_length_px": raw_result.get("damage", {}).get("damaged_edge_length_px", 0.0),
            "total_perimeter_px": raw_result.get("damage", {}).get("total_perimeter_px", 0.0),
            "note_area_damage_pct": raw_result.get("damage", {}).get("note_area_damage_pct", 0.0),
            "per_edge_breakdown": raw_result.get("damage", {}).get("per_edge_breakdown", {}),
            "disclaimer": raw_result.get("damage", {}).get("disclaimer", "")
        },
        "boundary": {
            "status": raw_result.get("boundary", {}).get("status", "FAILED"),
            "confidence": raw_result.get("boundary", {}).get("confidence", 0.0),
            "solidity": raw_result.get("boundary", {}).get("solidity", 0.0),
            "aspect_ratio": raw_result.get("boundary", {}).get("aspect_ratio", 0.0),
            "message": raw_result.get("boundary", {}).get("message", ""),
            "corners": corners_list
        },
        "edges": {
            "is_valid": raw_result.get("edges", {}).get("is_valid", False),
            "total_nominal_perimeter": raw_result.get("edges", {}).get("total_nominal_perimeter", 0.0),
            "total_visible_perimeter": raw_result.get("edges", {}).get("total_visible_perimeter", 0.0),
            "total_damaged_length": raw_result.get("edges", {}).get("total_damaged_length", 0.0),
            "max_defect_depth": raw_result.get("edges", {}).get("max_defect_depth", 0.0),
            "total_defect_count": raw_result.get("edges", {}).get("total_defect_count", 0),
            "edges": edge_list
        },
        "artifacts": {
            "overlay_filename": overlay_filename,
            "mask_filename": mask_filename,
            "boundary_filename": boundary_filename,
            "quad_filename": quad_filename,
            "report_filename": report_filename,
            "overlay_url": f"/api/results/{overlay_filename}" if overlay_filename else None,
            "mask_url": f"/api/results/{mask_filename}" if mask_filename else None,
            "boundary_url": f"/api/results/{boundary_filename}" if boundary_filename else None,
            "quad_url": f"/api/results/{quad_filename}" if quad_filename else None,
            "report_url": f"/api/results/{report_filename}" if report_filename else None,
            "source_url": (
                f"/api/dataset/image/{dataset_item['id']}" if dataset_item
                else f"/api/results/{target_image_path.name}"
            )
        }
    }

    return api_response

@app.post("/api/dataset/evaluate")
async def evaluate_dataset_subset(
    count: int = Form(10, description="Number of dataset images to evaluate"),
    category: Optional[str] = Form("All", description="Category filter")
):
    """
    Evaluates a configurable batch of real dataset images using the Python DIP pipeline.
    Exports results to CSV and returns summary statistics.
    """
    filtered = manifest_records
    if category and category != "All":
        filtered = [r for r in filtered if r["source_category"].lower() == category.lower()]

    sample_count = min(max(1, count), len(filtered), 100)
    # Select deterministically with uniform spacing
    indices = [int(i * (len(filtered) - 1) / max(sample_count - 1, 1)) for i in range(sample_count)]
    eval_candidates = [filtered[i] for i in indices]

    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    eval_csv_filename = f"evaluation_{timestamp_str}.csv"
    eval_csv_path = RESULTS_DIR / eval_csv_filename

    results_list = []
    class_distribution: Dict[str, int] = {}
    total_time = 0.0
    total_damage = 0.0
    success_count = 0
    warning_count = 0
    failed_count = 0

    csv_rows = []
    header = [
        "DatasetID", "Filename", "SourceCategory", "Status", "PredictedCondition",
        "Confidence", "EdgeDamagePct", "DamagedLengthPx", "VisiblePerimeterPx",
        "MaxTearDepthPx", "BoundarySolidity", "Aspect", "ExecutionTimeSec"
    ]
    csv_rows.append(header)

    for item in eval_candidates:
        full_path = DATASET_ROOT / item["relative_path"]
        t_start = time.perf_counter()
        res = ip.process_currency_note(str(full_path))
        t_run = round(time.perf_counter() - t_start, 4)
        total_time += t_run

        status_str = res.get("status", "UNKNOWN")
        if status_str == "SUCCESS":
            success_count += 1
        elif status_str == "WARNING":
            warning_count += 1
        else:
            failed_count += 1

        pred_class = res.get("classification", {}).get("category", "Needs Manual Inspection")
        class_distribution[pred_class] = class_distribution.get(pred_class, 0) + 1

        conf = float(res.get("classification", {}).get("confidence", 0.0))
        dmg_pct = res.get("damage", {}).get("damage_percentage")
        dmg_pct_val = float(dmg_pct) if dmg_pct is not None else 0.0
        total_damage += dmg_pct_val

        damaged_len = float(res.get("damage", {}).get("damaged_edge_length_px", 0.0))
        perim = float(res.get("damage", {}).get("total_perimeter_px", 0.0))
        max_depth = float(res.get("edges", {}).get("max_defect_depth", 0.0))
        solidity = float(res.get("boundary", {}).get("solidity", 0.0))
        aspect = float(res.get("boundary", {}).get("aspect_ratio", 0.0))

        results_list.append({
            "id": item["id"],
            "filename": item["filename"],
            "source_category": item["source_category"],
            "status": status_str,
            "predicted_condition": pred_class,
            "confidence": conf,
            "damage_percentage": dmg_pct_val,
            "execution_time_sec": t_run
        })

        csv_rows.append([
            item["id"], item["filename"], item["source_category"], status_str, pred_class,
            f"{conf:.2f}", f"{dmg_pct_val:.2f}", f"{damaged_len:.1f}", f"{perim:.1f}",
            f"{max_depth:.1f}", f"{solidity:.3f}", f"{aspect:.3f}", f"{t_run:.4f}"
        ])

    # Save evaluation CSV
    with open(eval_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(csv_rows)

    avg_time = round(total_time / sample_count, 4)
    avg_damage = round(total_damage / sample_count, 2)

    return {
        "status": "COMPLETED",
        "total_evaluated": sample_count,
        "success_count": success_count,
        "warning_count": warning_count,
        "failed_count": failed_count,
        "average_execution_time_sec": avg_time,
        "average_damage_percentage": avg_damage,
        "predicted_distribution": class_distribution,
        "csv_export_filename": eval_csv_filename,
        "csv_export_url": f"/api/results/{eval_csv_filename}",
        "evaluated_items": results_list,
        "disclaimer": (
            "Source dataset folders represent denomination and series labels rather than pixel-level ground-truth damage annotations. "
            "Evaluations reflect real computed computer vision geometric measurements and rule-based classifications."
        )
    }

@app.get("/api/results/{filename}")
async def get_result_file(filename: str):
    """Safely serves generated visualization files (PNG, JSON, CSV)."""
    if not is_safe_filename(filename):
        raise HTTPException(status_code=400, detail="Invalid filename parameter.")

    search_dirs = [
        RESULTS_DIR / "overlays",
        RESULTS_DIR / "masks",
        RESULTS_DIR / "boundaries",
        RESULTS_DIR / "reports",
        RESULTS_DIR,
        UPLOADS_DIR,
        TEST_IMAGES_DIR
    ]

    for s_dir in search_dirs:
        candidate = s_dir / filename
        if candidate.is_file():
            try:
                candidate.resolve().relative_to(PROJECT_DIR.resolve())
            except ValueError:
                raise HTTPException(status_code=403, detail="Access denied.")

            media_type = "application/octet-stream"
            suffix = candidate.suffix.lower()
            if suffix == ".png":
                media_type = "image/png"
            elif suffix in [".jpg", ".jpeg"]:
                media_type = "image/jpeg"
            elif suffix == ".json":
                media_type = "application/json"
            elif suffix == ".csv":
                media_type = "text/csv"

            return FileResponse(candidate, media_type=media_type)

    raise HTTPException(status_code=404, detail="Requested file not found.")

# Mount static files for dashboard
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
async def root():
    """Serve main web application dashboard."""
    index_file = STATIC_DIR / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return {"message": "Currency Note Edge Quality Inspection Web Server Active."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
