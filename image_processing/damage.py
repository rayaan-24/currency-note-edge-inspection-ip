"""
image_processing/damage.py - Step 6: Edge Damage Metric Computation
Faithful Python port of calculate_damage_percentage.m.
"""

from typing import Dict, Any, Optional
import math
from .config import PipelineConfig, get_default_config

def calculate_damage_percentage(
    edge_analysis: Dict[str, Any],
    boundary_data: Dict[str, Any],
    cfg: PipelineConfig = None
) -> Dict[str, Any]:
    """
    Computes percentage of banknote visible perimeter that is damaged,
    according to:
      Edge damage percentage = (estimated damaged edge length / estimated total visible note perimeter) * 100
    """
    if cfg is None:
        cfg = get_default_config()

    damage_metric: Dict[str, Any] = {
        "is_reliable": False,
        "damage_percentage": None,
        "display_text": "Unable to estimate reliably",
        "damaged_edge_length_px": 0.0,
        "total_perimeter_px": 0.0,
        "note_area_damage_pct": 0.0,
        "per_edge_breakdown": {},
        "disclaimer": (
            "Algorithmic estimate derived from 2D digital image processing. "
            "Not an official central bank grading standard or legal tender certification."
        )
    }

    # 1. Guard against failed or degenerate boundary
    if (
        not boundary_data or
        boundary_data.get("status") == "FAILED" or
        boundary_data.get("confidence", 1.0) < 0.35 or
        not edge_analysis or
        not edge_analysis.get("is_valid", False)
    ):
        if boundary_data and boundary_data.get("confidence", 1.0) < 0.35:
            damage_metric["display_text"] = "Unable to estimate reliably (Low boundary confidence)"
        return damage_metric

    total_nom_perim = float(edge_analysis.get("total_nominal_perimeter", 0.0))
    if total_nom_perim <= 1e-4:
        total_nom_perim = (
            float(edge_analysis.get("total_visible_perimeter", 0.0)) +
            float(edge_analysis.get("total_damaged_length", 0.0))
        )
    total_dam_len = float(edge_analysis.get("total_damaged_length", 0.0))

    if total_nom_perim <= 1e-4:
        damage_metric["display_text"] = "Unable to estimate reliably (Zero perimeter)"
        return damage_metric

    # 2. Calculate Edge Damage Percentage
    raw_pct = (total_dam_len / total_nom_perim) * 100.0
    clamped_pct = min(max(raw_pct, 0.0), 100.0)
    rounded_pct = round(clamped_pct, 2)

    damage_metric["is_reliable"] = True
    damage_metric["damage_percentage"] = rounded_pct
    damage_metric["display_text"] = f"{rounded_pct:.2f}%"
    damage_metric["damaged_edge_length_px"] = round(total_dam_len, 1)
    damage_metric["total_perimeter_px"] = round(total_nom_perim, 1)

    # 3. 2D Note Area Loss Calculation
    solidity = boundary_data.get("solidity", 0.0)
    if 0.0 < solidity <= 1.0:
        area_loss = (1.0 - solidity) * 100.0
        damage_metric["note_area_damage_pct"] = round(min(max(area_loss, 0.0), 100.0), 2)
    else:
        damage_metric["note_area_damage_pct"] = 0.0

    # 4. Per-Edge Breakdown
    breakdown = {}
    for e in edge_analysis.get("edges", []):
        e_nom = max(e.get("nominal_length", 0.0), 1e-4)
        e_dam_len = e.get("damaged_length", 0.0)
        e_dam_pct = round((e_dam_len / e_nom) * 100.0, 2)
        e_name = str(e.get("name", "")).lower()
        if e_name == "top":
            breakdown["top_damage_pct"] = e_dam_pct
        elif e_name == "right":
            breakdown["right_damage_pct"] = e_dam_pct
        elif e_name == "bottom":
            breakdown["bottom_damage_pct"] = e_dam_pct
        elif e_name == "left":
            breakdown["left_damage_pct"] = e_dam_pct

    damage_metric["per_edge_breakdown"] = breakdown
    return damage_metric
