"""
image_processing/pipeline.py - Master Digital Image Processing Orchestrator
Faithful Python port of process_currency_note.m.
"""

from typing import Dict, Any, Optional, Union
import time
import numpy as np

from .config import PipelineConfig, get_default_config
from .preprocess import preprocess_note
from .boundary import detect_note_boundary
from .edges import analyze_note_edges
from .damage import calculate_damage_percentage
from .classify import classify_note_condition
from .visualize import visualize_damage

def process_currency_note(
    input_source: Union[str, np.ndarray],
    custom_cfg: Optional[PipelineConfig] = None,
    manual_corners: Optional[np.ndarray] = None
) -> Dict[str, Any]:
    """
    Executes the complete end-to-end Digital Image Processing workflow:
      Step 1: Input validation & integrity checks.
      Step 2: Preprocessing (color-to-grayscale, normalization, Gaussian denoising).
      Step 3: Boundary extraction, 4-corner estimation, and boundary quality scoring.
      Step 4: Independent per-edge analysis (Top, Right, Bottom, Left).
      Step 5: Defect mask and vivid red overlay generation.
      Step 6: Precise edge damage percentage calculation.
      Step 7: Rule-based classification (Good, Folded, Torn, Old/Worn, Manual Inspection).
    """
    t_start = time.perf_counter()
    cfg = custom_cfg if custom_cfg is not None else get_default_config()

    result: Dict[str, Any] = {
        "status": "PENDING",
        "error_message": "",
        "execution_time_sec": 0.0,
        "input_info": {},
        "preprocessed": {},
        "boundary": {},
        "edges": {},
        "damage": {},
        "classification": {},
        "visualization": {}
    }

    # Step 1 & 2: Preprocessing
    try:
        gray_img, normalized_img, orig_img, info = preprocess_note(input_source, cfg)
        result["input_info"] = info
        result["preprocessed"] = {
            "gray_image": gray_img,
            "normalized_image": normalized_img,
            "original_image": orig_img
        }
    except Exception as e:
        result["status"] = "ERROR"
        result["error_message"] = f"Preprocessing failed: {str(e)}"
        result["execution_time_sec"] = round(time.perf_counter() - t_start, 4)
        result["classification"] = {
            "category": "Needs Manual Inspection",
            "confidence": 0.0,
            "reason": result["error_message"],
            "is_definitive": False
        }
        result["damage"] = {
            "is_reliable": False,
            "damage_percentage": None,
            "display_text": "Unable to estimate reliably",
            "damaged_edge_length_px": 0.0,
            "total_perimeter_px": 0.0,
            "note_area_damage_pct": 0.0
        }
        result["boundary"] = {
            "status": "FAILED",
            "confidence": 0.0,
            "message": result["error_message"]
        }
        result["edges"] = {"is_valid": False, "edges": []}
        return result

    # Step 3: Note Boundary & 4-Corner Detection
    boundary_data = detect_note_boundary(gray_img, cfg=cfg, manual_corners=manual_corners, rgb_img=normalized_img)
    result["boundary"] = boundary_data

    if boundary_data.get("status") == "FAILED":
        result["status"] = "WARNING"
        result["error_message"] = f"Boundary extraction failed: {boundary_data.get('message', '')}"
        result["edges"] = {"is_valid": False, "edges": []}
        result["damage"] = {
            "is_reliable": False,
            "damage_percentage": None,
            "display_text": "Unable to estimate reliably",
            "damaged_edge_length_px": 0.0,
            "total_perimeter_px": 0.0,
            "note_area_damage_pct": 0.0
        }
        result["classification"] = {
            "category": "Needs Manual Inspection",
            "confidence": 0.15,
            "reason": boundary_data.get("message", "Boundary failure"),
            "is_definitive": False
        }
        result["visualization"] = visualize_damage(
            normalized_img, boundary_data, result["edges"],
            result["damage"], result["classification"], cfg
        )
        result["execution_time_sec"] = round(time.perf_counter() - t_start, 4)
        return result

    # Step 4: Per-Edge Defect Analysis
    edge_analysis = analyze_note_edges(boundary_data, gray_img, cfg)
    result["edges"] = edge_analysis

    # Step 5 & 6: Damage Percentage Calculation
    damage_metric = calculate_damage_percentage(edge_analysis, boundary_data, cfg)
    result["damage"] = damage_metric

    # Step 7: Classification Decision
    classification_result = classify_note_condition(
        damage_metric, edge_analysis, boundary_data, gray_img, cfg
    )
    result["classification"] = classification_result

    # Step 8: Visualizations & Overlay Generation
    viz_data = visualize_damage(
        normalized_img, boundary_data, edge_analysis,
        damage_metric, classification_result, cfg
    )
    result["visualization"] = viz_data

    # Finalize Status & Timing
    if boundary_data.get("status") == "WARNING_LOW_CONFIDENCE":
        result["status"] = "WARNING"
    else:
        result["status"] = "SUCCESS"

    result["execution_time_sec"] = round(time.perf_counter() - t_start, 4)
    return result
