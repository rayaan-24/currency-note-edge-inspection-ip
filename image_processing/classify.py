"""
image_processing/classify.py - Step 7: Rule-Based Condition Classification
Faithful Python port of classify_note_condition.m.
"""

from typing import Dict, Any, Tuple
import numpy as np
from scipy.ndimage import convolve
from skimage.morphology import disk, binary_erosion

from .config import PipelineConfig, get_default_config

def compute_sobel_gradients(gray_img: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Computes Sobel gradient components gx, gy, and magnitude gmag."""
    gray_d = gray_img.astype(np.float64)
    hx = np.array([[-1.0, 0.0, 1.0], [-2.0, 0.0, 2.0], [-1.0, 0.0, 1.0]], dtype=np.float64)
    hy = np.array([[-1.0, -2.0, -1.0], [0.0, 0.0, 0.0], [1.0, 2.0, 1.0]], dtype=np.float64)

    gx = convolve(gray_d, hx, mode="nearest")
    gy = convolve(gray_d, hy, mode="nearest")
    gmag = np.sqrt(gx ** 2 + gy ** 2)
    return gx, gy, gmag

def detect_fold_crease(
    gray_img: np.ndarray,
    interior_mask: np.ndarray,
    boundary_data: Dict[str, Any],
    cfg: PipelineConfig
) -> Tuple[bool, float, float]:
    """Detects continuous directional crease traversing the banknote interior."""
    if not np.any(interior_mask):
        return False, 0.0, 0.0

    img_h, img_w = gray_img.shape
    corners = np.asarray(boundary_data.get("corners", []), dtype=np.float64)
    if len(corners) == 4:
        note_w = float(np.linalg.norm(corners[1] - corners[0]))
        note_h = float(np.linalg.norm(corners[3] - corners[0]))
    else:
        note_w = float(img_w)
        note_h = float(img_h)

    gx, gy, _ = compute_sobel_gradients(gray_img)
    gx_int = gx * interior_mask
    gy_int = gy * interior_mask

    mask_sum_cols = np.maximum(np.sum(interior_mask, axis=0), 1)
    mask_sum_rows = np.maximum(np.sum(interior_mask, axis=1), 1)

    col_contrast = np.sum(np.abs(gx_int), axis=0) / mask_sum_cols
    row_contrast = np.sum(np.abs(gy_int), axis=1) / mask_sum_rows

    max_intensity = 0.0
    max_span_ratio = 0.0

    # Search central 60% of width
    x_min = int(round(img_w * 0.20))
    x_max = int(round(img_w * 0.80))
    if x_max > x_min:
        central_cols = col_contrast[x_min:x_max]
        if len(central_cols) > 0:
            idx_c = int(np.argmax(central_cols))
            peak_c = float(central_cols[idx_c])
            col_pos = x_min + idx_c
            crease_len = float(np.sum(interior_mask[:, col_pos]))
            span_ratio_c = crease_len / max(note_h, 1.0)
            if peak_c > max_intensity:
                max_intensity = peak_c
                max_span_ratio = span_ratio_c

    # Search central 60% of height
    y_min = int(round(img_h * 0.20))
    y_max = int(round(img_h * 0.80))
    if y_max > y_min:
        central_rows = row_contrast[y_min:y_max]
        if len(central_rows) > 0:
            idx_r = int(np.argmax(central_rows))
            peak_r = float(central_rows[idx_r])
            row_pos = y_min + idx_r
            crease_len = float(np.sum(interior_mask[row_pos, :]))
            span_ratio_r = crease_len / max(note_w, 1.0)
            if peak_r > max_intensity:
                max_intensity = peak_r
                max_span_ratio = span_ratio_r

    has_fold = (
        max_intensity >= cfg.classify.fold_gradient_threshold and
        max_span_ratio >= cfg.classify.fold_min_length_ratio
    )
    return has_fold, float(round(max_intensity, 1)), float(round(max_span_ratio, 3))

def compute_wear_indicators(
    gray_img: np.ndarray,
    interior_mask: np.ndarray
) -> Tuple[float, float, float]:
    """Computes surface wear and fading index from texture roughness and contrast range."""
    if not np.any(interior_mask):
        return 0.0, 0.0, 1.0

    int_pixels = gray_img[interior_mask].astype(np.float64)
    p05 = float(np.percentile(int_pixels, 5))
    p95 = float(np.percentile(int_pixels, 95))
    dynamic_range = (p95 - p05) / 255.0

    _, _, gmag = compute_sobel_gradients(gray_img)
    gmag_int = gmag[interior_mask]
    roughness = float(np.std(gmag_int))

    if dynamic_range < 0.05:
        fading_penalty = 0.0
    else:
        fading_penalty = max(0.0, 0.50 - dynamic_range) * 20.0
    wear_index = roughness + fading_penalty
    return float(round(wear_index, 1)), float(round(roughness, 1)), float(round(dynamic_range, 3))

def classify_note_condition(
    damage_metric: Dict[str, Any],
    edge_analysis: Dict[str, Any],
    boundary_data: Dict[str, Any],
    gray_img: np.ndarray,
    cfg: PipelineConfig = None
) -> Dict[str, Any]:
    """
    Categorizes currency note condition into one of 5 academic classes:
      'Good', 'Torn', 'Folded', 'Old/Worn', 'Needs Manual Inspection'
    """
    if cfg is None:
        cfg = get_default_config()

    classification_result: Dict[str, Any] = {
        "category": "Needs Manual Inspection",
        "confidence": 0.0,
        "reason": "",
        "indicators": {},
        "is_definitive": False
    }

    # 1. Guard against boundary failure, low confidence, or background inclusion
    b_status = boundary_data.get("status", "FAILED") if boundary_data else "FAILED"
    b_conf = float(boundary_data.get("confidence", 0.0)) if boundary_data else 0.0

    if (
        not boundary_data or
        b_status in ("FAILED", "WARNING_LOW_CONFIDENCE") or
        b_conf < cfg.boundary.min_confidence_threshold
    ):
        classification_result["category"] = "Needs Manual Inspection"
        classification_result["confidence"] = float(round(min(0.30, max(b_conf, 0.10)), 2))
        msg = boundary_data.get("message", "") if boundary_data else ""
        classification_result["reason"] = (
            f"Uncertain note boundary segmentation: {msg}" if msg
            else "Boundary detection confidence below acceptable operating threshold."
        )
        classification_result["is_definitive"] = False
        return classification_result

    b_conf = float(boundary_data.get("confidence", 0.5))

    # 2. Compute Quantitative Defect & Wear Indicators
    edge_dam_pct = 0.0
    if damage_metric and damage_metric.get("is_reliable", False):
        edge_dam_pct = float(damage_metric.get("damage_percentage") or 0.0)

    max_tear_depth = 0.0
    if edge_analysis and edge_analysis.get("is_valid", False):
        max_tear_depth = float(edge_analysis.get("max_defect_depth", 0.0))

    note_mask = boundary_data.get("mask", np.zeros(gray_img.shape, dtype=bool))
    try:
        interior_mask = binary_erosion(note_mask, footprint=disk(20))
    except Exception:
        interior_mask = note_mask

    has_fold, fold_intensity, fold_span_ratio = detect_fold_crease(
        gray_img, interior_mask, boundary_data, cfg
    )
    wear_index, roughness_val, contrast_fade = compute_wear_indicators(
        gray_img, interior_mask
    )

    indicators = {
        "edge_damage_pct": edge_dam_pct,
        "max_tear_depth_px": max_tear_depth,
        "boundary_confidence": b_conf,
        "has_fold": has_fold,
        "fold_intensity": fold_intensity,
        "fold_span_ratio": fold_span_ratio,
        "wear_index": wear_index,
        "roughness_val": roughness_val,
        "contrast_fade": contrast_fade
    }
    classification_result["indicators"] = indicators

    # 3. Decision Rules

    # Rule 1: TORN NOTE
    is_torn_by_pct = (edge_dam_pct >= cfg.classify.torn_min_damage_pct)
    is_torn_by_depth = (max_tear_depth >= cfg.classify.torn_min_defect_depth_px)

    if is_torn_by_pct or is_torn_by_depth:
        classification_result["category"] = "Torn"
        tear_conf = min(1.0, 0.70 + 0.30 * min(edge_dam_pct / 10.0, 1.0))
        classification_result["confidence"] = float(round(tear_conf * b_conf, 2))
        classification_result["reason"] = (
            f"Physical edge damage detected: {edge_dam_pct:.2f}% damaged perimeter, "
            f"max tear depth {int(round(max_tear_depth))} px."
        )
        classification_result["is_definitive"] = True
        return classification_result

    # Rule 2: FOLDED NOTE
    if (
        has_fold and
        fold_intensity >= cfg.classify.fold_gradient_threshold and
        fold_span_ratio >= cfg.classify.fold_min_length_ratio
    ):
        classification_result["category"] = "Folded"
        fold_conf = min(1.0, 0.65 + 0.35 * min(fold_span_ratio, 1.0))
        classification_result["confidence"] = float(round(fold_conf * b_conf, 2))
        classification_result["reason"] = (
            f"Prominent continuous fold crease detected traversing note body "
            f"(Intensity: {fold_intensity:.1f}, Span: {fold_span_ratio*100:.1f}%)."
        )
        classification_result["is_definitive"] = True
        return classification_result

    # Rule 3: OLD / WORN NOTE
    if wear_index >= cfg.classify.worn_roughness_threshold:
        classification_result["category"] = "Old/Worn"
        wear_conf = min(1.0, 0.60 + 0.40 * min(wear_index / 30.0, 1.0))
        classification_result["confidence"] = float(round(wear_conf * b_conf, 2))
        classification_result["reason"] = (
            f"Surface aging detected: Texture roughness index {wear_index:.1f} "
            f"exceeds wear threshold {cfg.classify.worn_roughness_threshold:.1f}."
        )
        classification_result["is_definitive"] = True
        return classification_result

    # Rule 4: GOOD NOTE
    if (
        edge_dam_pct <= cfg.classify.good_max_damage_pct and
        max_tear_depth < cfg.classify.torn_min_defect_depth_px and
        b_conf >= 0.60
    ):
        classification_result["category"] = "Good"
        classification_result["confidence"] = float(round(b_conf, 2))
        classification_result["reason"] = (
            "All 4 edges intact and smooth; no tears, prominent folds, or excessive wear detected."
        )
        classification_result["is_definitive"] = True
        return classification_result

    # Rule 5: Fallback to Manual Inspection
    classification_result["category"] = "Needs Manual Inspection"
    classification_result["confidence"] = 0.50
    classification_result["reason"] = (
        f"Borderline measurements (Damage: {edge_dam_pct:.2f}%, Wear: {wear_index:.1f}). "
        f"Automated confidence insufficient for definitive grading."
    )
    classification_result["is_definitive"] = False
    return classification_result
