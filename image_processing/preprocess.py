"""
image_processing/preprocess.py - Step 1 & 2: Input Validation, Normalization & Denoising
Faithful Python port of preprocess_note.m using Pillow, NumPy, and scipy.
"""

from typing import Union, Tuple, Dict, Any
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

from .config import PipelineConfig, get_default_config

def rgb_to_grayscale(img: np.ndarray) -> np.ndarray:
    """Converts RGB/RGBA image to grayscale using ITU-R BT.601 luma formula."""
    if img.ndim == 2:
        return img.astype(np.uint8)
    r = img[:, :, 0].astype(np.float64)
    g = img[:, :, 1].astype(np.float64)
    b = img[:, :, 2].astype(np.float64)
    gray = 0.2989 * r + 0.5870 * g + 0.1140 * b
    return np.clip(np.round(gray), 0, 255).astype(np.uint8)

def normalize_dimensions(img: np.ndarray, target_w: int = 800) -> Tuple[np.ndarray, float]:
    """Aspect-ratio preserving proportional scaling to target width."""
    orig_h, orig_w = img.shape[:2]
    if target_w <= 0 or orig_w == target_w:
        return img.copy(), 1.0
    scale = target_w / float(orig_w)
    new_h = max(1, int(round(orig_h * scale)))
    pil_img = Image.fromarray(img)
    resized = pil_img.resize((target_w, new_h), Image.Resampling.BICUBIC)
    return np.array(resized), scale

def preprocess_note(
    input_source: Union[str, Path, np.ndarray, Image.Image],
    cfg: PipelineConfig = None
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    Validate, normalize, denoise, and convert currency note image to preprocessed grayscale.

    Returns:
        gray_img: 2D uint8 numpy array (denoised, contrast enhanced)
        normalized_img: 3D uint8 numpy array (RGB, scaled to target width)
        orig_img: 3D uint8 numpy array (unmodified original image)
        info: dictionary of metadata and scaling parameters
    """
    if cfg is None:
        cfg = get_default_config()

    info: Dict[str, Any] = {
        "is_valid": False,
        "error_message": "",
        "source_path": "",
        "original_size": (0, 0, 0),
        "normalized_size": (0, 0, 0),
        "scale_factor": 1.0,
        "dynamic_range": 0.0,
        "mean_intensity": 0.0,
        "contrast_enhanced": False
    }

    # Step 1: Input Loading & Validation
    if isinstance(input_source, (str, Path)):
        p = Path(input_source)
        info["source_path"] = str(p)
        if not p.is_file():
            raise FileNotFoundError(f"Image file not found: {p}")
        try:
            with Image.open(p) as pil_img:
                # Ensure RGB
                if pil_img.mode in ("RGBA", "LA") or (pil_img.mode == "P" and "transparency" in pil_img.info):
                    pil_img = pil_img.convert("RGBA")
                    # Background composite on white/black or strip alpha
                    bg = Image.new("RGB", pil_img.size, (40, 44, 52))
                    bg.paste(pil_img, mask=pil_img.split()[3])
                    orig_img = np.array(bg)
                else:
                    orig_img = np.array(pil_img.convert("RGB"))
        except Exception as e:
            raise ValueError(f"Unable to read image file: {p} ({str(e)})")
    elif isinstance(input_source, Image.Image):
        info["source_path"] = "<PIL.Image>"
        orig_img = np.array(input_source.convert("RGB"))
    elif isinstance(input_source, np.ndarray):
        info["source_path"] = "<numpy.ndarray>"
        if input_source.ndim == 2:
            orig_img = np.stack([input_source] * 3, axis=-1)
        elif input_source.ndim == 3:
            if input_source.shape[2] == 4:
                orig_img = input_source[:, :, :3]
            elif input_source.shape[2] == 1:
                orig_img = np.repeat(input_source, 3, axis=2)
            else:
                orig_img = input_source[:, :, :3]
        else:
            raise ValueError(f"Unexpected image array shape: {input_source.shape}")
        if orig_img.dtype != np.uint8:
            orig_img = np.clip(orig_img, 0, 255).astype(np.uint8)
    else:
        raise TypeError(f"Invalid input_source type: {type(input_source)}")

    orig_h, orig_w, orig_c = orig_img.shape
    info["original_size"] = (orig_h, orig_w, orig_c)

    # Step 2: Normalization (Aspect-Ratio Preserving Scaling)
    target_w = cfg.preproc.target_width
    if target_w > 0 and orig_w != target_w:
        scale = target_w / float(orig_w)
        new_h = max(1, int(round(orig_h * scale)))
        new_w = target_w
        # Resize using high quality bicubic via Pillow
        pil_tmp = Image.fromarray(orig_img)
        resized_pil = pil_tmp.resize((new_w, new_h), Image.Resampling.BICUBIC)
        normalized_img = np.array(resized_pil)
        info["scale_factor"] = scale
    else:
        normalized_img = orig_img.copy()
        info["scale_factor"] = 1.0

    norm_h, norm_w, norm_c = normalized_img.shape
    info["normalized_size"] = (norm_h, norm_w, norm_c)

    # Convert to Grayscale using ITU-R BT.601 luma formula: Y = 0.2989*R + 0.5870*G + 0.1140*B
    r = normalized_img[:, :, 0].astype(np.float64)
    g = normalized_img[:, :, 1].astype(np.float64)
    b = normalized_img[:, :, 2].astype(np.float64)
    raw_gray = 0.2989 * r + 0.5870 * g + 0.1140 * b
    raw_gray_u8 = np.clip(np.round(raw_gray), 0, 255).astype(np.uint8)

    # Denoising via Gaussian Smoothing Filter
    sigma = cfg.preproc.denoise_sigma
    denoised_d = gaussian_filter(raw_gray_u8.astype(np.float64), sigma=sigma, mode="nearest")
    denoised_gray = np.clip(np.round(denoised_d), 0, 255).astype(np.uint8)

    # Selective Contrast Enhancement
    gray_norm = denoised_gray.astype(np.float64) / 255.0
    p_low, p_high = np.percentile(gray_norm, [cfg.preproc.contrast_stretch_limits[0] * 100, 
                                             cfg.preproc.contrast_stretch_limits[1] * 100])
    dynamic_range = float(p_high - p_low)
    info["dynamic_range"] = dynamic_range
    info["mean_intensity"] = float(np.mean(gray_norm))

    if cfg.preproc.enable_contrast_enhancement and dynamic_range < 0.85:
        denom = max(dynamic_range, 1e-4)
        stretched = np.clip((gray_norm - p_low) / denom, 0.0, 1.0)
        gray_img = np.clip(np.round(stretched * 255.0), 0, 255).astype(np.uint8)
        info["contrast_enhanced"] = True
    else:
        gray_img = denoised_gray
        info["contrast_enhanced"] = False

    info["is_valid"] = True
    return gray_img, normalized_img, orig_img, info
