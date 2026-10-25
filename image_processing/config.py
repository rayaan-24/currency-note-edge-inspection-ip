"""
image_processing/config.py - Configuration Parameters for Currency Note Edge Inspection
Direct 1-to-1 port of config.m with identical defaults, thresholds, and tolerances.
"""

from dataclasses import dataclass, field
from typing import Tuple, List
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent

@dataclass
class PreprocessingConfig:
    target_width: int = 800
    denoise_sigma: float = 1.2
    filter_kernel_size: int = 5
    enable_contrast_enhancement: bool = True
    contrast_stretch_limits: Tuple[float, float] = (0.03, 0.97)

@dataclass
class BoundaryConfig:
    binarize_method: str = "otsu"
    threshold_multiplier: float = 0.95
    min_note_area_ratio: float = 0.12
    max_note_area_ratio: float = 0.96
    morph_close_radius: int = 5
    morph_open_radius: int = 3
    min_confidence_threshold: float = 0.55

@dataclass
class EdgeConfig:
    defect_tolerance_px: float = 4.0
    tear_depth_threshold_px: float = 7.0
    min_defect_length_px: float = 10.0
    contour_sample_step: int = 2

@dataclass
class ClassifyConfig:
    good_max_damage_pct: float = 2.0
    torn_min_damage_pct: float = 2.0
    torn_min_defect_depth_px: float = 8.0
    fold_gradient_threshold: float = 200.0
    fold_min_length_ratio: float = 0.48
    worn_roughness_threshold: float = 24.0
    worn_contrast_fade_threshold: float = 0.42

@dataclass
class VizConfig:
    defect_overlay_color: Tuple[int, int, int] = (255, 38, 38)     # Vivid red
    intact_edge_color: Tuple[int, int, int] = (38, 217, 64)       # Green
    corner_color: Tuple[int, int, int] = (0, 217, 255)            # Cyan
    overlay_alpha: float = 0.45
    boundary_line_width: int = 3

@dataclass
class PathConfig:
    dataset_dir: Path = field(default_factory=lambda: PROJECT_DIR / "dataset")
    results_dir: Path = field(default_factory=lambda: PROJECT_DIR / "results")
    overlays_dir: Path = field(default_factory=lambda: PROJECT_DIR / "results" / "overlays")
    masks_dir: Path = field(default_factory=lambda: PROJECT_DIR / "results" / "masks")
    boundaries_dir: Path = field(default_factory=lambda: PROJECT_DIR / "results" / "boundaries")
    reports_dir: Path = field(default_factory=lambda: PROJECT_DIR / "results" / "reports")
    summary_csv: Path = field(default_factory=lambda: PROJECT_DIR / "results" / "summary.csv")

@dataclass
class PipelineConfig:
    preproc: PreprocessingConfig = field(default_factory=PreprocessingConfig)
    boundary: BoundaryConfig = field(default_factory=BoundaryConfig)
    edge: EdgeConfig = field(default_factory=EdgeConfig)
    classify: ClassifyConfig = field(default_factory=ClassifyConfig)
    viz: VizConfig = field(default_factory=VizConfig)
    paths: PathConfig = field(default_factory=PathConfig)

def get_default_config() -> PipelineConfig:
    """Return an initialized default pipeline configuration."""
    return PipelineConfig()
