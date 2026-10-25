"""
image_processing - Complete Python Digital Image Processing Package
for Currency Note Edge Quality Inspection.
Academic port of the MATLAB implementation without OpenCV or Octave runtime requirements.
"""

from .config import PipelineConfig, get_default_config
from .preprocess import preprocess_note, rgb_to_grayscale, normalize_dimensions
from .boundary import detect_note_boundary, order_rectangle_corners
from .edges import analyze_note_edges
from .damage import calculate_damage_percentage
from .classify import classify_note_condition
from .visualize import visualize_damage
from .export import export_results
from .pipeline import process_currency_note

__all__ = [
    "PipelineConfig",
    "get_default_config",
    "preprocess_note",
    "rgb_to_grayscale",
    "normalize_dimensions",
    "detect_note_boundary",
    "order_rectangle_corners",
    "analyze_note_edges",
    "calculate_damage_percentage",
    "classify_note_condition",
    "visualize_damage",
    "export_results",
    "process_currency_note"
]
