"""
image_processing/export.py - Step 8: Multi-Format Result Persistence (PNG, JSON, CSV)
Faithful Python port of export_results.m.
"""

from typing import Dict, Any, Optional
import os
import json
import csv
import re
from datetime import datetime
from PIL import Image
import numpy as np

from .config import PipelineConfig, get_default_config

def export_results(
    result: Dict[str, Any],
    output_dir: Optional[str] = None,
    cfg: PipelineConfig = None
) -> Dict[str, str]:
    """
    Exports complete visual and numerical results:
      - PNG Overlay (results/overlays/)
      - PNG Damage Mask (results/masks/)
      - PNG Boundary (results/boundaries/)
      - PNG Quad-Comparison composite (results/overlays/)
      - JSON Detailed Analysis Report (results/reports/)
      - Appends audit record to summary.csv (results/summary.csv)
    """
    if cfg is None:
        cfg = get_default_config()

    if output_dir is None:
        output_dir = cfg.paths.results_dir

    overlays_dir = os.path.join(output_dir, "overlays")
    masks_dir = os.path.join(output_dir, "masks")
    boundaries_dir = os.path.join(output_dir, "boundaries")
    reports_dir = os.path.join(output_dir, "reports")
    summary_csv = os.path.join(output_dir, "summary.csv")

    for d in [output_dir, overlays_dir, masks_dir, boundaries_dir, reports_dir]:
        os.makedirs(d, exist_ok=True)

    export_paths: Dict[str, str] = {}

    # 1. Generate Safe Unique Filename Prefix
    src_path = result.get("input_info", {}).get("source_path", "note_inspection")
    from pathlib import Path
    proj_dir = Path(__file__).resolve().parent.parent
    try:
        p_src = Path(src_path)
        if p_src.is_absolute() and str(p_src).startswith(str(proj_dir)):
            portable_src = str(p_src.relative_to(proj_dir))
        else:
            portable_src = os.path.basename(src_path)
    except Exception:
        portable_src = os.path.basename(src_path)

    base_name = os.path.splitext(os.path.basename(src_path))[0]
    clean_base = re.sub(r"[^a-zA-Z0-9_\-]", "_", base_name)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_prefix = f"{clean_base}_{timestamp_str}"

    viz = result.get("visualization", {})

    # 2. Export Visual PNG Artifacts
    # 2a. Overlay Image
    if "overlay_image" in viz and viz["overlay_image"] is not None:
        overlay_file = os.path.join(overlays_dir, f"{file_prefix}_overlay.png")
        Image.fromarray(viz["overlay_image"]).save(overlay_file)
        export_paths["overlay_path"] = overlay_file

    # 2b. Damage Mask
    if "damage_mask" in viz and viz["damage_mask"] is not None:
        mask_file = os.path.join(masks_dir, f"{file_prefix}_mask.png")
        mask_arr = (viz["damage_mask"].astype(np.uint8) * 255)
        Image.fromarray(mask_arr).save(mask_file)
        export_paths["mask_path"] = mask_file

    # 2c. Boundary Visualization
    if "boundary_image" in viz and viz["boundary_image"] is not None:
        bound_file = os.path.join(boundaries_dir, f"{file_prefix}_boundary.png")
        Image.fromarray(viz["boundary_image"]).save(bound_file)
        export_paths["boundary_path"] = bound_file

    # 2d. Quad-Comparison Composite
    if "quad_comparison_image" in viz and viz["quad_comparison_image"] is not None:
        quad_file = os.path.join(overlays_dir, f"{file_prefix}_quad.png")
        Image.fromarray(viz["quad_comparison_image"]).save(quad_file)
        export_paths["quad_path"] = quad_file

    # 3. Export Comprehensive JSON Report
    report_file = os.path.join(reports_dir, f"{file_prefix}_report.json")
    report_data = {
        "timestamp": timestamp_str,
        "source_image": portable_src,
        "status": result.get("status", "UNKNOWN"),
        "execution_time_sec": result.get("execution_time_sec", 0.0),
        "classification": {
            "category": result.get("classification", {}).get("category", "Needs Manual Inspection"),
            "confidence": result.get("classification", {}).get("confidence", 0.0),
            "reason": result.get("classification", {}).get("reason", ""),
            "is_definitive": result.get("classification", {}).get("is_definitive", False)
        },
        "damage_metrics": {
            "is_reliable": result.get("damage", {}).get("is_reliable", False),
            "edge_damage_percentage": result.get("damage", {}).get("damage_percentage"),
            "display_text": result.get("damage", {}).get("display_text", ""),
            "damaged_edge_length_px": result.get("damage", {}).get("damaged_edge_length_px", 0.0),
            "total_visible_perimeter_px": result.get("damage", {}).get("total_perimeter_px", 0.0),
            "note_area_damage_pct": result.get("damage", {}).get("note_area_damage_pct", 0.0)
        },
        "boundary_quality": {
            "status": result.get("boundary", {}).get("status", "FAILED"),
            "confidence": result.get("boundary", {}).get("confidence", 0.0),
            "solidity": result.get("boundary", {}).get("solidity", 0.0),
            "aspect_ratio": result.get("boundary", {}).get("aspect_ratio", 0.0),
            "message": result.get("boundary", {}).get("message", "")
        },
        "edge_analysis": [
            {
                "edge": e.get("name", ""),
                "status": e.get("status", "INTACT"),
                "nominal_len_px": e.get("nominal_length", 0.0),
                "damaged_len_px": e.get("damaged_length", 0.0),
                "max_depth_px": e.get("max_defect_depth", 0.0),
                "defects": e.get("defect_count", 0)
            }
            for e in result.get("edges", {}).get("edges", [])
        ]
    }

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)
    export_paths["report_json_path"] = report_file

    # 4. Append to CSV Audit Summary
    write_summary_csv(summary_csv, result, timestamp_str, file_prefix, portable_src)
    export_paths["summary_csv_path"] = summary_csv

    return export_paths

def write_summary_csv(
    csv_path: str,
    result: Dict[str, Any],
    timestamp_str: str,
    file_prefix: str,
    src_path: str
):
    """Appends single execution row into summary.csv."""
    is_new = not os.path.exists(csv_path)

    header = [
        "Timestamp", "FilePrefix", "SourceFile", "Status", "Classification", "Confidence",
        "EdgeDamagePct", "DamagedLengthPx", "VisiblePerimeterPx", "MaxTearDepthPx",
        "TopEdgeStatus", "RightEdgeStatus", "BottomEdgeStatus", "LeftEdgeStatus", "Reason"
    ]

    status = result.get("status", "UNKNOWN")
    cls_data = result.get("classification", {})
    cat = cls_data.get("category", "Needs Manual Inspection")
    conf = cls_data.get("confidence", 0.0)

    dmg_data = result.get("damage", {})
    if dmg_data.get("is_reliable", False):
        dam_pct = f"{dmg_data.get('damage_percentage', 0.0):.2f}"
    else:
        dam_pct = "N/A"

    dam_len = f"{dmg_data.get('damaged_edge_length_px', 0.0):.1f}"
    perim = f"{dmg_data.get('total_perimeter_px', 0.0):.1f}"

    edges = result.get("edges", {}).get("edges", [])
    if result.get("edges", {}).get("is_valid", False) and len(edges) == 4:
        max_depth = f"{result.get('edges', {}).get('max_defect_depth', 0.0):.1f}"
        top_st = edges[0].get("status", "N/A")
        right_st = edges[1].get("status", "N/A")
        bot_st = edges[2].get("status", "N/A")
        left_st = edges[3].get("status", "N/A")
    else:
        max_depth = "N/A"
        top_st, right_st, bot_st, left_st = "N/A", "N/A", "N/A", "N/A"

    reason = cls_data.get("reason", "").replace("\n", " ").replace('"', '""')

    row = [
        timestamp_str, file_prefix, src_path, status, cat, f"{conf:.2f}",
        dam_pct, dam_len, perim, max_depth, top_st, right_st, bot_st, left_st, reason
    ]

    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(header)
        writer.writerow(row)
