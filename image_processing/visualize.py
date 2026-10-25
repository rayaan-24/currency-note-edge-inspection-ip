"""
image_processing/visualize.py - Step 5: Boundary, Defect Mask & Red Overlay Generation
Faithful Python port of visualize_damage.m using NumPy and Pillow.
"""

from typing import Dict, Any, List
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from skimage.morphology import disk, binary_erosion

from .config import PipelineConfig, get_default_config

def get_font(size: int = 14) -> ImageFont.ImageFont:
    """Attempts to load a standard truetype font, falls back to default font."""
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:
        try:
            return ImageFont.truetype("Arial.ttf", size)
        except Exception:
            return ImageFont.load_default()

def draw_banner(panel_img: Image.Image, text: str) -> Image.Image:
    """Draw dark top banner with clean text header."""
    w, h = panel_img.size
    banner_h = 28
    draw = ImageDraw.Draw(panel_img)
    # Dark banner background
    draw.rectangle([0, 0, w, banner_h], fill=(28, 32, 40))
    # Accent separator line
    draw.line([(0, banner_h), (w, banner_h)], fill=(80, 140, 220), width=1)
    # Header text
    font = get_font(13)
    draw.text((12, 6), text, fill=(240, 245, 255), font=font)
    return panel_img

def visualize_damage(
    img_display: np.ndarray,
    boundary_data: Dict[str, Any],
    edge_analysis: Dict[str, Any],
    damage_metric: Dict[str, Any],
    classification_result: Dict[str, Any],
    cfg: PipelineConfig = None
) -> Dict[str, Any]:
    """
    Generates all diagnostic visual representations:
      1. Binary damage mask.
      2. Vivid red defect overlay.
      3. Boundary & 4-corner visualization.
      4. 2x2 Quad-comparison panel.
      5. Text summary.
    """
    if cfg is None:
        cfg = get_default_config()

    # Ensure 3-channel uint8
    if img_display.ndim == 2:
        base_rgb = np.stack([img_display] * 3, axis=-1).astype(np.uint8)
    elif img_display.shape[2] == 1:
        base_rgb = np.concatenate([img_display] * 3, axis=-1).astype(np.uint8)
    else:
        base_rgb = img_display[:, :, :3].astype(np.uint8)

    img_h, img_w, _ = base_rgb.shape

    # 1. Binary Damage Mask
    dam_mask = np.zeros((img_h, img_w), dtype=bool)
    b_status = boundary_data.get("status", "FAILED") if boundary_data else "FAILED"
    
    if (
        b_status in ("SUCCESS", "MANUAL_OVERRIDE") and
        edge_analysis and
        edge_analysis.get("is_valid", False)
    ):
        mask_pil = Image.new("1", (img_w, img_h), 0)
        draw_dam = ImageDraw.Draw(mask_pil)

        for e in edge_analysis.get("edges", []):
            clusters = e.get("defect_clusters", [])
            for c in clusters:
                c_pts = c.get("points", [])
                p_pts = c.get("projections", [])
                if len(c_pts) > 0 and len(p_pts) > 0:
                    # Construct defect pocket polygon: contour points + reversed projected points
                    poly = [(p[0], p[1]) for p in c_pts] + [(p[0], p[1]) for p in p_pts[::-1]]
                    if len(poly) >= 3:
                        draw_dam.polygon(poly, fill=1, outline=1)

            # Also include defect points with brush
            pts = e.get("defect_points", [])
            if len(pts) > 0:
                for p in pts:
                    px = int(round(p[0]))
                    py = int(round(p[1]))
                    draw_dam.ellipse([px - 3, py - 3, px + 3, py + 3], fill=1, outline=1)

        raw_dam_mask = np.array(mask_pil, dtype=bool)

        # Strictly constrain damage mask to the banknote interior or its nominal envelope
        corners = np.asarray(boundary_data.get("corners", []), dtype=np.float64)
        if len(corners) == 4:
            obb_pil = Image.new("1", (img_w, img_h), 0)
            draw_obb = ImageDraw.Draw(obb_pil)
            draw_obb.polygon([(p[0], p[1]) for p in corners], fill=1, outline=1)
            envelope_mask = np.array(obb_pil, dtype=bool)
        else:
            envelope_mask = np.ones((img_h, img_w), dtype=bool)

        note_mask = boundary_data.get("mask", np.zeros((img_h, img_w), dtype=bool))
        # Damage mask must strictly reside on the note or in the missing defect pocket inside the envelope
        dam_mask = raw_dam_mask & (note_mask | envelope_mask)

    # 2. Vivid Red Defect Overlay
    overlay = base_rgb.copy().astype(np.float64)
    alpha = cfg.viz.overlay_alpha
    red_color = np.array([round(c * 255) for c in cfg.viz.defect_overlay_color], dtype=np.float64)
    green_color = np.array([round(c * 255) for c in cfg.viz.intact_edge_color], dtype=np.float64)

    # Subtle green highlight on intact points (only if boundary verified)
    if b_status in ("SUCCESS", "MANUAL_OVERRIDE") and edge_analysis and edge_analysis.get("is_valid", False):
        for e in edge_analysis.get("edges", []):
            pts = e.get("intact_points", [])
            if len(pts) > 0:
                for p in pts:
                    px = int(round(p[0]))
                    py = int(round(p[1]))
                    if 0 <= py < img_h and 0 <= px < img_w:
                        overlay[py, px] = overlay[py, px] * 0.75 + green_color * 0.25

    # Semi-transparent red on damaged regions
    if np.any(dam_mask):
        overlay[dam_mask] = overlay[dam_mask] * (1.0 - alpha) + red_color * alpha

        # Solid red outline around damage clusters
        try:
            eroded_mask = binary_erosion(dam_mask, footprint=disk(1))
            dam_boundary = dam_mask & (~eroded_mask)
            overlay[dam_boundary] = red_color
        except Exception:
            pass

    overlay_u8 = np.clip(overlay, 0, 255).astype(np.uint8)

    # 3. Boundary & Corner Visualization Image
    b_img = base_rgb.copy()
    if boundary_data and boundary_data.get("status") != "FAILED":
        # Draw yellow contour
        contour_pts = boundary_data.get("contour", [])
        if len(contour_pts) > 0:
            for p in contour_pts:
                cx = int(round(p[0]))
                cy = int(round(p[1]))
                if 0 <= cy < img_h and 0 <= cx < img_w:
                    b_img[cy, cx] = [255, 235, 20]

        # Draw quadrilateral dashed line & cyan circular corners
        corners = np.asarray(boundary_data.get("corners", []), dtype=np.float64)
        if len(corners) == 4:
            b_pil = Image.fromarray(b_img)
            b_draw = ImageDraw.Draw(b_pil)
            quad_loop = list(corners) + [corners[0]]

            # Dashed magenta quadrilateral
            for k in range(4):
                p1, p2 = quad_loop[k], quad_loop[k + 1]
                dist = np.linalg.norm(p2 - p1)
                n_steps = max(2, int(round(dist * 1.5)))
                xs = np.linspace(p1[0], p2[0], n_steps)
                ys = np.linspace(p1[1], p2[1], n_steps)
                for step_idx in range(n_steps):
                    if (step_idx // 6) % 2 == 0:
                        x = int(round(xs[step_idx]))
                        y = int(round(ys[step_idx]))
                        if 0 <= x < img_w and 0 <= y < img_h:
                            b_draw.point((x, y), fill=(255, 60, 220))
                            if y + 1 < img_h:
                                b_draw.point((x, y + 1), fill=(255, 60, 220))

            # Cyan circular discs on corners
            corner_col = tuple(round(c * 255) for c in cfg.viz.corner_color)
            r_c = 7
            for c in corners:
                cx, cy = int(round(c[0])), int(round(c[1]))
                b_draw.ellipse([cx - r_c, cy - r_c, cx + r_c, cy + r_c], fill=corner_col, outline=(0, 0, 0))

            b_img = np.array(b_pil, dtype=np.uint8)

    # 4. Quad-Comparison Panel (2x2 Composite)
    pil_orig = draw_banner(Image.fromarray(base_rgb), "1. Original Image")

    # Grayscale representation
    from .preprocess import rgb_to_grayscale
    gray = rgb_to_grayscale(base_rgb)
    gray_3ch = np.stack([gray] * 3, axis=-1)
    pil_gray = draw_banner(Image.fromarray(gray_3ch), "2. Preprocessed Grayscale")

    b_conf = float(boundary_data.get("confidence", 0.0) * 100) if boundary_data else 0.0
    pil_bound = draw_banner(Image.fromarray(b_img), f"3. Boundary (Conf: {b_conf:.0f}%)")

    cat_str = classification_result.get("category", "") if classification_result else ""
    dam_str = damage_metric.get("display_text", "") if damage_metric else ""
    overlay_title = f"4. {cat_str} (Damage: {dam_str})" if cat_str else "4. Damage Overlay"
    pil_overlay = draw_banner(Image.fromarray(overlay_u8), overlay_title)

    quad_img = Image.new("RGB", (img_w * 2, img_h * 2))
    quad_img.paste(pil_orig, (0, 0))
    quad_img.paste(pil_gray, (img_w, 0))
    quad_img.paste(pil_bound, (0, img_h))
    quad_img.paste(pil_overlay, (img_w, img_h))
    quad_comparison_image = np.array(quad_img, dtype=np.uint8)

    # 5. Formatted Text Summary
    lines = ["=== Currency Note Edge Inspection Summary ==="]
    if classification_result:
        lines.append(
            f"Classification: {classification_result.get('category')} "
            f"(Confidence: {classification_result.get('confidence', 0.0)*100:.1f}%)"
        )
        lines.append(f"Reason: {classification_result.get('reason')}")
    if damage_metric:
        lines.append(f"Edge Damage Percentage: {damage_metric.get('display_text')}")
        lines.append(
            f"Total Damaged Length: {damage_metric.get('damaged_edge_length_px', 0.0):.1f} px | "
            f"Total Visible Perimeter: {damage_metric.get('total_perimeter_px', 0.0):.1f} px"
        )
        lines.append(f"Note Surface Area Loss: {damage_metric.get('note_area_damage_pct', 0.0):.2f}%")
    if edge_analysis and edge_analysis.get("is_valid", False):
        lines.append("--- Individual Edge Measurements ---")
        for e in edge_analysis.get("edges", []):
            lines.append(
                f"  [{e.get('name')} Edge] Status: {e.get('status'):<7} | "
                f"Damaged: {e.get('damaged_length', 0.0):5.1f} px | "
                f"Max Depth: {e.get('max_defect_depth', 0.0):4.1f} px | "
                f"Defects: {e.get('defect_count', 0)}"
            )

    return {
        "damage_mask": dam_mask,
        "overlay_image": overlay_u8,
        "boundary_image": b_img,
        "quad_comparison_image": quad_comparison_image,
        "summary_text": "\n".join(lines)
    }
