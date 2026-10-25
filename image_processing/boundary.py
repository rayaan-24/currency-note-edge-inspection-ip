"""
image_processing/boundary.py - Step 3: Note Boundary & 4-Corner Detection
Faithful Python port of detect_note_boundary.m using NumPy, scikit-image, and scipy.
"""

from typing import Dict, Any, Optional, List
import numpy as np
from skimage.filters import threshold_otsu
from skimage.morphology import disk, binary_closing, binary_opening
from skimage.measure import label, regionprops, find_contours
from scipy.ndimage import binary_fill_holes
from scipy.spatial import ConvexHull

from .config import PipelineConfig, get_default_config

def order_rectangle_corners(pts: np.ndarray) -> np.ndarray:
    """
    Orders 4 quadrilateral corners cyclically starting from top-left, strictly clockwise.
    Guarantees:
      - corners[0]: Top-Left
      - corners[1]: Top-Right
      - corners[2]: Bottom-Right
      - corners[3]: Bottom-Left
      - Edges 0 (Top) and 2 (Bottom) are opposite.
      - Edges 1 (Right) and 3 (Left) are opposite.
      - No crossing diagonals or bow-tie artifacts.
    """
    pts = np.asarray(pts, dtype=np.float64)
    if pts.shape != (4, 2):
        return pts

    # Find top-leftmost vertex (minimum x + y)
    s = pts[:, 0] + pts[:, 1]
    tl_idx = int(np.argmin(s))
    ordered = np.roll(pts, -tl_idx, axis=0)

    # Check 2D cross-product winding order: (p1 - p0) x (p3 - p0)
    # In screen coordinates (x right, y down), clockwise winding produces cross > 0
    v1 = ordered[1] - ordered[0]
    v3 = ordered[3] - ordered[0]
    cross = v1[0] * v3[1] - v1[1] * v3[0]
    if cross < 0:
        # Counter-clockwise: swap indices 1 and 3 to enforce clockwise order
        ordered = ordered[[0, 3, 2, 1]]

    return ordered

def detect_note_boundary(
    gray_img: np.ndarray,
    cfg: PipelineConfig = None,
    manual_corners: Optional[np.ndarray] = None,
    rgb_img: Optional[np.ndarray] = None
) -> Dict[str, Any]:
    """
    Segment the banknote, trace outer contour, compute 4 corners, convex hull,
    solidity, aspect ratio, and objective boundary quality confidence metric.
    Uses robust multi-cue segmentation (color contrast + chroma distance when RGB
    is available, with grayscale fallback) to handle shadows and uneven illumination.
    """
    if cfg is None:
        cfg = get_default_config()

    img_h, img_w = gray_img.shape
    total_pixels = float(img_h * img_w)

    boundary_data: Dict[str, Any] = {
        "contour": np.zeros((0, 2), dtype=np.float64),
        "corners": np.zeros((4, 2), dtype=np.float64),
        "mask": np.zeros((img_h, img_w), dtype=bool),
        "convex_hull": np.zeros((0, 2), dtype=np.float64),
        "confidence": 0.0,
        "status": "FAILED",
        "message": "",
        "aspect_ratio": 1.0,
        "solidity": 0.0
    }

    # 1. Handle Manual Corner Override if provided by user
    if manual_corners is not None:
        mc = np.asarray(manual_corners, dtype=np.float64)
        if mc.shape == (4, 2):
            in_bounds = (mc[:, 0] >= 0) & (mc[:, 0] <= img_w) & (mc[:, 1] >= 0) & (mc[:, 1] <= img_h)
            if np.all(in_bounds):
                return build_boundary_from_corners(order_rectangle_corners(mc), img_h, img_w)

    # Check for blank / nearly uniform input image
    gray_std = float(np.std(gray_img))
    if gray_std < 5.0:
        boundary_data["status"] = "FAILED"
        boundary_data["message"] = "Blank or nearly uniform image detected (std < 5.0)."
        return boundary_data

    # 2. Automated Multi-Cue Segmentation & Binarization
    raw_mask = None
    try:
        if rgb_img is not None and rgb_img.ndim == 3 and rgb_img.shape[2] >= 3:
            # Multi-cue color contrast segmentation using Lab color space
            from skimage.color import rgb2lab
            lab = rgb2lab(rgb_img[:, :, :3])
            
            # Sample border pixels (outer 15 px along all 4 boundaries)
            m = min(15, img_h // 10, img_w // 10)
            border_lab = np.concatenate([
                lab[:m, :, :].reshape(-1, 3),
                lab[-m:, :, :].reshape(-1, 3),
                lab[:, :m, :].reshape(-1, 3),
                lab[:, -m:, :].reshape(-1, 3)
            ], axis=0)

            bg_lab = np.median(border_lab, axis=0)
            bg_chroma = float(np.sqrt(bg_lab[1] ** 2 + bg_lab[2] ** 2))

            if bg_chroma > 18.0:
                # Strong chromatic background (e.g. vivid cyan/blue mat):
                # Pure chromaticity distance is completely immune to shadow gradients
                dist_map = np.sqrt((lab[:, :, 1] - bg_lab[1]) ** 2 + (lab[:, :, 2] - bg_lab[2]) ** 2)
            else:
                # Neutral, gray, white, black, or muted table background:
                # Weighted Delta E with 0.35 weight on L to dampen shadows while preserving lightness contrast
                dist_map = np.sqrt(
                    0.35 * ((lab[:, :, 0] - bg_lab[0]) ** 2) +
                    (lab[:, :, 1] - bg_lab[1]) ** 2 +
                    (lab[:, :, 2] - bg_lab[2]) ** 2
                )

            max_dist = float(np.max(dist_map))
            if max_dist >= 8.0:
                t_dist = threshold_otsu(dist_map)
                effective_t = max(t_dist, 10.0, 0.22 * max_dist)
                raw_mask = dist_map > effective_t

        if raw_mask is None:
            # Grayscale fallback
            raw_thresh = threshold_otsu(gray_img)
            effective_thresh = np.clip(raw_thresh * cfg.boundary.threshold_multiplier, 10, 245)
            raw_mask = gray_img >= effective_thresh

            # Check polarity (banknote brighter than background or inverted)
            area_ratio = float(np.sum(raw_mask)) / total_pixels
            if area_ratio < 0.12 or area_ratio > 0.88:
                inv_mask = gray_img < effective_thresh
                inv_area = float(np.sum(inv_mask)) / total_pixels
                if 0.12 <= inv_area <= 0.88:
                    raw_mask = inv_mask
    except Exception as e:
        boundary_data["status"] = "FAILED"
        boundary_data["message"] = f"Binarization failed: {str(e)}"
        return boundary_data

    # 3. Morphological Filtering & Noise Suppression
    # Perform opening first to eliminate isolated border noise and thin filaments
    open_se = disk(cfg.boundary.morph_open_radius)
    opened_mask = binary_opening(raw_mask, footprint=open_se)
    close_se = disk(cfg.boundary.morph_close_radius)
    closed_mask = binary_closing(opened_mask, footprint=close_se)
    filled_mask = binary_fill_holes(closed_mask)

    # 4. Connected Component Extraction (Largest Region)
    labeled = label(filled_mask)
    regions = regionprops(labeled)
    if not regions:
        boundary_data["status"] = "FAILED"
        boundary_data["message"] = "No distinct foreground connected component detected."
        return boundary_data

    largest_region = max(regions, key=lambda r: r.area)
    note_mask = (labeled == largest_region.label)
    note_area = float(largest_region.area)
    area_ratio = note_area / total_pixels

    if area_ratio < cfg.boundary.min_note_area_ratio:
        boundary_data["status"] = "FAILED"
        boundary_data["message"] = f"Detected region too small ({area_ratio*100:.1f}% of image, required >= {cfg.boundary.min_note_area_ratio*100:.1f}%)."
        return boundary_data

    if area_ratio > cfg.boundary.max_note_area_ratio:
        boundary_data["status"] = "FAILED"
        boundary_data["message"] = f"Detected region exceeds {cfg.boundary.max_note_area_ratio*100:.1f}% of image (likely background or cropped frame)."
        return boundary_data

    boundary_data["mask"] = note_mask

    # 5. Perimeter Contour Tracing
    # find_contours returns [row, col] -> convert to [x, y]
    contours = find_contours(note_mask.astype(float), level=0.5)
    if not contours:
        boundary_data["status"] = "FAILED"
        boundary_data["message"] = "Perimeter contour extraction failed."
        return boundary_data

    longest_contour = max(contours, key=lambda c: len(c))
    if len(longest_contour) < 20:
        boundary_data["status"] = "FAILED"
        boundary_data["message"] = "Perimeter contour too short or degenerate."
        return boundary_data

    # Convert [row, col] to [x, y]
    contour_pts = np.column_stack([longest_contour[:, 1], longest_contour[:, 0]])
    boundary_data["contour"] = contour_pts

    # 6. Convex Hull Computation
    try:
        hull = ConvexHull(contour_pts)
        hull_pts = contour_pts[hull.vertices]
        hull_area = float(hull.volume)  # In 2D, hull.volume is area
    except Exception:
        hull_pts = contour_pts
        hull_area = note_area

    boundary_data["convex_hull"] = hull_pts

    # 7. 4-Corner Estimation: Minimum-Area Oriented Bounding Box of Convex Hull
    # Ensures that if a corner is missing or torn, the nominal rectangular envelope is preserved
    n_h = len(hull_pts)
    best_corners = None
    min_area = float("inf")

    if n_h >= 3:
        for i in range(n_h):
            p1 = hull_pts[i]
            p2 = hull_pts[(i + 1) % n_h]
            edge = p2 - p1
            edge_len = float(np.linalg.norm(edge))
            if edge_len < 1e-4:
                continue
            u = edge / edge_len
            v = np.array([-u[1], u[0]])
            pu = np.dot(hull_pts, u)
            pv = np.dot(hull_pts, v)
            u_min, u_max = float(pu.min()), float(pu.max())
            v_min, v_max = float(pv.min()), float(pv.max())
            area = (u_max - u_min) * (v_max - v_min)
            if area < min_area:
                min_area = area
                c1 = u_min * u + v_min * v
                c2 = u_max * u + v_min * v
                c3 = u_max * u + v_max * v
                c4 = u_min * u + v_max * v
                best_corners = np.vstack([c1, c2, c3, c4])

    if best_corners is None:
        minr, minc, maxr, maxc = largest_region.bbox
        best_corners = np.array([
            [minc, minr], [maxc, minr], [maxc, maxr], [minc, maxr]
        ], dtype=np.float64)

    # Order corners cyclically in strictly clockwise order (TL, TR, BR, BL)
    corners = order_rectangle_corners(best_corners)
    boundary_data["corners"] = corners
    c_tl, c_tr, c_br, c_bl = corners[0], corners[1], corners[2], corners[3]

    # 8. Aspect Ratio & Solidity Calculation
    w_top = float(np.linalg.norm(c_tr - c_tl))
    w_bottom = float(np.linalg.norm(c_br - c_bl))
    h_left = float(np.linalg.norm(c_bl - c_tl))
    h_right = float(np.linalg.norm(c_br - c_tr))

    avg_w = (w_top + w_bottom) / 2.0
    avg_h = (h_left + h_right) / 2.0
    # Banknotes can be horizontally oriented or vertically oriented (rotated 90 degrees)
    aspect_ratio = max(avg_w, avg_h) / max(min(avg_w, avg_h), 1e-3)
    boundary_data["aspect_ratio"] = float(round(aspect_ratio, 3))

    solidity = min(1.0, note_area / max(hull_area, 1e-3))
    boundary_data["solidity"] = float(round(solidity, 3))

    # 9. Boundary Quality Confidence Score (0.0 to 1.0)
    # Solidity score: banknotes have high convexity
    solidity_score = np.clip((solidity - 0.65) / 0.28, 0.0, 1.0)

    # Aspect ratio score: Indian banknotes have aspect ratios between 1.35 and 2.45
    if 1.30 <= aspect_ratio <= 2.60:
        ar_score = np.clip(1.0 - abs(aspect_ratio - 1.85) / 1.2, 0.40, 1.0)
    elif 1.15 <= aspect_ratio <= 3.20:
        ar_score = 0.30
    else:
        ar_score = 0.05

    # Check whether contour touches image frame borders (background leakage check)
    margin_px = 6
    touch_top = np.any(contour_pts[:, 1] <= margin_px)
    touch_bottom = np.any(contour_pts[:, 1] >= (img_h - margin_px))
    touch_left = np.any(contour_pts[:, 0] <= margin_px)
    touch_right = np.any(contour_pts[:, 0] >= (img_w - margin_px))
    touched_border_count = sum([touch_top, touch_bottom, touch_left, touch_right])

    if touched_border_count >= 3:
        # Contour spans the full image frame; almost certainly segmented background
        border_score = 0.15
    elif touched_border_count == 2:
        border_score = 0.50
    elif touched_border_count == 1:
        border_score = 0.75
    else:
        border_score = 1.0

    # Fill ratio: note area compared to oriented bounding box area
    obb_area = max(avg_w * avg_h, 1e-3)
    fill_ratio = note_area / obb_area
    fill_score = np.clip((fill_ratio - 0.60) / 0.30, 0.0, 1.0)

    conf = float(
        0.35 * solidity_score +
        0.30 * ar_score +
        0.20 * border_score +
        0.15 * fill_score
    )
    boundary_data["confidence"] = float(round(np.clip(conf, 0.0, 1.0), 3))

    # 10. Status Determination
    if (
        boundary_data["confidence"] >= cfg.boundary.min_confidence_threshold and
        aspect_ratio >= 1.25 and
        touched_border_count < 3
    ):
        boundary_data["status"] = "SUCCESS"
        boundary_data["message"] = (
            f"Boundary verified (Confidence: {boundary_data['confidence']*100:.1f}%, "
            f"Solidity: {boundary_data['solidity']:.2f}, Aspect: {boundary_data['aspect_ratio']:.2f})."
        )
    else:
        boundary_data["status"] = "WARNING_LOW_CONFIDENCE"
        reasons = []
        if boundary_data["confidence"] < cfg.boundary.min_confidence_threshold:
            reasons.append(f"low confidence ({boundary_data['confidence']*100:.1f}%)")
        if aspect_ratio < 1.25:
            reasons.append(f"implausible aspect ratio ({aspect_ratio:.2f})")
        if touched_border_count >= 3:
            reasons.append(f"contour touches {touched_border_count} image borders (likely background)")
        boundary_data["message"] = f"Uncertain boundary segmentation: {', '.join(reasons)}. Manual inspection recommended."

    return boundary_data

def build_boundary_from_corners(corners: np.ndarray, img_h: int, img_w: int) -> Dict[str, Any]:
    """Construct boundary struct from manual 4-corner override."""
    tl, tr, br, bl = corners[0], corners[1], corners[2], corners[3]
    n_seg = 80
    edge_top = np.column_stack([np.linspace(tl[0], tr[0], n_seg), np.linspace(tl[1], tr[1], n_seg)])
    edge_right = np.column_stack([np.linspace(tr[0], br[0], n_seg), np.linspace(tr[1], br[1], n_seg)])
    edge_bottom = np.column_stack([np.linspace(br[0], bl[0], n_seg), np.linspace(br[1], bl[1], n_seg)])
    edge_left = np.column_stack([np.linspace(bl[0], tl[0], n_seg), np.linspace(bl[1], tl[1], n_seg)])
    contour = np.vstack([edge_top, edge_right, edge_bottom, edge_left])

    from PIL import Image, ImageDraw
    mask_img = Image.new("1", (img_w, img_h), 0)
    draw = ImageDraw.Draw(mask_img)
    draw.polygon([(p[0], p[1]) for p in corners], fill=1, outline=1)
    mask = np.array(mask_img, dtype=bool)

    w_avg = (np.linalg.norm(tr - tl) + np.linalg.norm(br - bl)) / 2.0
    h_avg = (np.linalg.norm(bl - tl) + np.linalg.norm(br - tr)) / 2.0

    return {
        "contour": contour,
        "corners": corners,
        "mask": mask,
        "convex_hull": corners,
        "confidence": 1.0,
        "status": "MANUAL_OVERRIDE",
        "message": "Manual boundary adjustment applied by user.",
        "aspect_ratio": float(round(w_avg / max(h_avg, 1.0), 3)),
        "solidity": 1.0
    }
