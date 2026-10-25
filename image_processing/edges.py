"""
image_processing/edges.py - Step 4: Independent 4-Edge Geometric Defect Analysis
Faithful Python port of analyze_note_edges.m using NumPy.
"""

from typing import Dict, Any, List, Tuple, Optional
import numpy as np
from .config import PipelineConfig, get_default_config

def point_to_segment_dist(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> Tuple[float, np.ndarray, float]:
    """
    Computes shortest Euclidean distance from point p to line segment a-b,
    returning (distance, projected_point, t_parameter).
    """
    ab = b - a
    len_sq = float(np.sum(ab ** 2))
    if len_sq < 1e-12:
        return float(np.linalg.norm(p - a)), a.copy(), 0.0

    t = float(np.sum((p - a) * ab) / len_sq)
    t_clamped = np.clip(t, 0.0, 1.0)
    proj_pt = a + t_clamped * ab
    dist = float(np.linalg.norm(p - proj_pt))
    return dist, proj_pt, t_clamped

def get_points_for_edge(
    all_pts: np.ndarray,
    a: np.ndarray,
    b: np.ndarray,
    centroid: np.ndarray,
    edge_defs: List[Tuple[str, np.ndarray, np.ndarray]],
    edge_idx: int
) -> np.ndarray:
    """Filter contour points whose nearest edge segment is edge_idx."""
    n = len(all_pts)
    if n == 0:
        return np.zeros((0, 2), dtype=np.float64)

    keep = np.zeros(n, dtype=bool)
    for i in range(n):
        p = all_pts[i]
        d_curr, _, _ = point_to_segment_dist(p, a, b)

        is_closest = True
        for other_idx in range(4):
            if other_idx != edge_idx:
                oa, ob = edge_defs[other_idx][1], edge_defs[other_idx][2]
                d_other, _, _ = point_to_segment_dist(p, oa, ob)
                if d_other < d_curr:
                    is_closest = False
                    break
        if is_closest:
            keep[i] = True

    return all_pts[keep]

def evaluate_cluster(
    pts: np.ndarray,
    deviations: np.ndarray,
    t_vals: np.ndarray,
    projs: np.ndarray,
    s_idx: int,
    e_idx: int,
    nominal_len: float,
    min_len: float,
    min_depth: float
) -> Optional[Dict[str, Any]]:
    """
    Evaluate candidate defect cluster against physical length & depth criteria.
    Length is measured as the projected linear span along the nominal edge segment,
    ensuring consistent length units and strictly preventing damaged length from
    exceeding the nominal edge length.
    """
    cluster_pts = pts[s_idx:e_idx + 1]
    cluster_devs = deviations[s_idx:e_idx + 1]
    cluster_projs = projs[s_idx:e_idx + 1]

    t_start = float(t_vals[s_idx])
    t_end = float(t_vals[e_idx])
    span_len = float(max(t_end - t_start, 0.0) * nominal_len)

    # In case of discrete sampling, ensure span reflects minimum spatial extent of points
    if len(cluster_pts) > 1:
        chord_len = float(np.linalg.norm(cluster_pts[-1] - cluster_pts[0]))
        span_len = max(span_len, min(chord_len, nominal_len))
    else:
        span_len = min(1.0, nominal_len)

    span_len = min(span_len, nominal_len)
    max_d = float(np.max(cluster_devs))

    if span_len >= min_len and max_d >= min_depth:
        return {
            "indices": list(range(s_idx, e_idx + 1)),
            "points": cluster_pts,
            "projections": cluster_projs,
            "t_range": (t_start, t_end),
            "length": span_len,
            "max_depth": max_d
        }
    return None

def cluster_defects(
    pts: np.ndarray,
    is_defect_raw: np.ndarray,
    deviations: np.ndarray,
    t_vals: np.ndarray,
    projs: np.ndarray,
    nominal_len: float,
    min_length_px: float,
    min_depth_px: float
) -> List[Dict[str, Any]]:
    """Cluster contiguous defect runs along an edge using projected linear spans."""
    clusters: List[Dict[str, Any]] = []
    n = len(is_defect_raw)
    if n == 0:
        return clusters

    in_cluster = False
    start_idx = 0

    for i in range(n):
        if is_defect_raw[i] and not in_cluster:
            in_cluster = True
            start_idx = i
        elif not is_defect_raw[i] and in_cluster:
            in_cluster = False
            end_idx = i - 1
            c = evaluate_cluster(
                pts, deviations, t_vals, projs, start_idx, end_idx,
                nominal_len, min_length_px, min_depth_px
            )
            if c is not None:
                clusters.append(c)

    if in_cluster:
        end_idx = n - 1
        c = evaluate_cluster(
            pts, deviations, t_vals, projs, start_idx, end_idx,
            nominal_len, min_length_px, min_depth_px
        )
        if c is not None:
            clusters.append(c)

    return clusters

def analyze_note_edges(
    boundary_data: Dict[str, Any],
    gray_img: np.ndarray,
    cfg: PipelineConfig = None
) -> Dict[str, Any]:
    """
    Performs independent geometric defect analysis on Top, Right, Bottom, Left edges.
    """
    if cfg is None:
        cfg = get_default_config()

    edge_analysis: Dict[str, Any] = {
        "edges": [],
        "total_nominal_perimeter": 0.0,
        "total_visible_perimeter": 0.0,
        "total_damaged_length": 0.0,
        "max_defect_depth": 0.0,
        "total_defect_count": 0,
        "is_valid": False
    }

    if (
        boundary_data.get("status") == "FAILED" or
        len(boundary_data.get("contour", [])) == 0 or
        len(boundary_data.get("corners", [])) < 4
    ):
        return edge_analysis

    corners = np.asarray(boundary_data["corners"], dtype=np.float64)
    tl, tr, br, bl = corners[0], corners[1], corners[2], corners[3]
    centroid = np.mean(corners, axis=0)

    contour_pts = np.asarray(boundary_data["contour"], dtype=np.float64)
    step = max(1, round(cfg.edge.contour_sample_step))
    if step > 1:
        contour_pts = contour_pts[::step]

    edge_defs: List[Tuple[str, np.ndarray, np.ndarray]] = [
        ("Top", tl, tr),
        ("Right", tr, br),
        ("Bottom", br, bl),
        ("Left", bl, tl)
    ]

    total_nom = 0.0
    total_vis = 0.0
    total_dam = 0.0
    global_max_depth = 0.0
    global_defect_count = 0
    edges_list: List[Dict[str, Any]] = []

    for i in range(4):
        e_name, p_start, p_end = edge_defs[i]
        nominal_len = float(np.linalg.norm(p_end - p_start))
        total_nom += nominal_len

        edge_pts = get_points_for_edge(contour_pts, p_start, p_end, centroid, edge_defs, i)

        if len(edge_pts) == 0:
            edge_struct = {
                "name": e_name,
                "corners": np.vstack([p_start, p_end]),
                "nominal_length": round(nominal_len, 1),
                "visible_length": round(nominal_len, 1),
                "damaged_length": 0.0,
                "max_defect_depth": 0.0,
                "defect_count": 0,
                "status": "INTACT",
                "defect_points": np.zeros((0, 2), dtype=np.float64),
                "intact_points": np.zeros((0, 2), dtype=np.float64)
            }
            edges_list.append(edge_struct)
            total_vis += nominal_len
            continue

        n_pts = len(edge_pts)
        deviations = np.zeros(n_pts, dtype=np.float64)
        t_vals = np.zeros(n_pts, dtype=np.float64)
        is_inward = np.zeros(n_pts, dtype=bool)
        projs = np.zeros((n_pts, 2), dtype=np.float64)

        mid_edge = (p_start + p_end) / 2.0
        inward_dir = centroid - mid_edge
        inward_norm = float(np.linalg.norm(inward_dir))
        inward_dir = inward_dir / max(inward_norm, 1e-6)

        for k in range(n_pts):
            pt = edge_pts[k]
            dist, proj, t = point_to_segment_dist(pt, p_start, p_end)
            deviations[k] = dist
            t_vals[k] = t
            projs[k] = proj
            disp_vec = pt - proj
            is_inward[k] = (np.dot(disp_vec, inward_dir) > 0)

        sort_order = np.argsort(t_vals)
        edge_pts_sorted = edge_pts[sort_order]
        deviations_sorted = deviations[sort_order]
        t_vals_sorted = t_vals[sort_order]
        projs_sorted = projs[sort_order]
        is_inward_sorted = is_inward[sort_order]

        tol = cfg.edge.defect_tolerance_px
        min_depth = cfg.edge.tear_depth_threshold_px
        is_defect_raw = is_inward_sorted & (deviations_sorted > tol)

        defect_clusters = cluster_defects(
            edge_pts_sorted,
            is_defect_raw,
            deviations_sorted,
            t_vals_sorted,
            projs_sorted,
            nominal_len,
            cfg.edge.min_defect_length_px,
            min_depth
        )

        # Merge overlapping t-intervals to calculate exact non-duplicated damaged length
        intervals = [c["t_range"] for c in defect_clusters]
        if intervals:
            intervals.sort(key=lambda iv: iv[0])
            merged_intervals = [intervals[0]]
            for current in intervals[1:]:
                prev = merged_intervals[-1]
                if current[0] <= prev[1]:
                    merged_intervals[-1] = (prev[0], max(prev[1], current[1]))
                else:
                    merged_intervals.append(current)
            
            total_t_span = sum(end - start for start, end in merged_intervals)  # in [0, 1]
            damaged_len = min(nominal_len, float(total_t_span * nominal_len))
        else:
            damaged_len = 0.0

        max_edge_depth = 0.0
        defect_pts_all = []
        defect_projs_all = []
        is_defect_final = np.zeros(n_pts, dtype=bool)

        for cluster in defect_clusters:
            max_edge_depth = max(max_edge_depth, cluster["max_depth"])
            defect_pts_all.append(cluster["points"])
            defect_projs_all.append(cluster["projections"])
            for idx in cluster["indices"]:
                is_defect_final[idx] = True

        defect_pts_arr = np.vstack(defect_pts_all) if defect_pts_all else np.zeros((0, 2), dtype=np.float64)
        defect_projs_arr = np.vstack(defect_projs_all) if defect_projs_all else np.zeros((0, 2), dtype=np.float64)
        intact_pts = edge_pts_sorted[~is_defect_final]

        vis_len = max(0.0, nominal_len - damaged_len)
        status_str = "DAMAGED" if (damaged_len > 0.0 and max_edge_depth >= min_depth) else "INTACT"

        edge_struct = {
            "name": e_name,
            "corners": np.vstack([p_start, p_end]),
            "nominal_length": float(round(nominal_len, 1)),
            "visible_length": float(round(vis_len, 1)),
            "damaged_length": float(round(damaged_len, 1)),
            "max_defect_depth": float(round(max_edge_depth, 1)),
            "defect_count": len(defect_clusters),
            "status": status_str,
            "defect_points": defect_pts_arr,
            "defect_projections": defect_projs_arr,
            "defect_clusters": defect_clusters,
            "intact_points": intact_pts
        }
        edges_list.append(edge_struct)

        total_vis += vis_len
        total_dam += damaged_len
        global_max_depth = max(global_max_depth, max_edge_depth)
        global_defect_count += len(defect_clusters)

    edge_analysis["edges"] = edges_list
    edge_analysis["total_nominal_perimeter"] = float(round(total_nom, 1))
    edge_analysis["total_visible_perimeter"] = float(round(total_vis, 1))
    edge_analysis["total_damaged_length"] = float(round(total_dam, 1))
    edge_analysis["max_defect_depth"] = float(round(global_max_depth, 1))
    edge_analysis["total_defect_count"] = global_defect_count
    edge_analysis["is_valid"] = True

    return edge_analysis
