function edge_analysis = analyze_note_edges(boundary_data, gray_img, cfg)
% ANALYZE_NOTE_EDGES - Step 4: Independent 4-Edge Geometric Defect Analysis
%
% Performs rigorous geometric defect inspection across all four individual banknote
% borders (Top, Right, Bottom, Left). Measures deviations against the expected intact
% envelope, identifies tears, notches, missing sections, and calculates damaged spans.
%
% Syntax:
%   edge_analysis = analyze_note_edges(boundary_data, gray_img, cfg)
%
% Inputs:
%   boundary_data - Struct returned by detect_note_boundary.m.
%   gray_img      - Preprocessed grayscale image.
%   cfg           - Configuration struct (from config.m).
%
% Outputs:
%   edge_analysis struct with fields:
%     .edges                    - 1x4 struct array for [Top, Right, Bottom, Left] edges.
%     .total_nominal_perimeter  - Sum of expected 4 edge lengths (px).
%     .total_visible_perimeter  - Sum of detected intact perimeter sections (px).
%     .total_damaged_length     - Total length of damaged/missing edge sections (px).
%     .max_defect_depth         - Maximum tear penetration depth across all edges (px).
%     .total_defect_count       - Total number of distinct defect clusters detected.
%     .is_valid                 - Boolean indicating successful edge analysis.

    if nargin < 3 || isempty(cfg)
        cfg = config();
    end

    edge_analysis = struct();
    edge_analysis.edges = struct('name', {}, 'corners', {}, 'nominal_length', {}, ...
                                 'visible_length', {}, 'damaged_length', {}, ...
                                 'max_defect_depth', {}, 'defect_count', {}, ...
                                 'status', {}, 'defect_points', {}, 'intact_points', {});
    edge_analysis.total_nominal_perimeter = 0.0;
    edge_analysis.total_visible_perimeter = 0.0;
    edge_analysis.total_damaged_length = 0.0;
    edge_analysis.max_defect_depth = 0.0;
    edge_analysis.total_defect_count = 0;
    edge_analysis.is_valid = false;

    if strcmp(boundary_data.status, 'FAILED') || isempty(boundary_data.contour) || size(boundary_data.corners, 1) < 4
        return;
    end

    corners = boundary_data.corners;
    tl = corners(1, :);
    tr = corners(2, :);
    br = corners(3, :);
    bl = corners(4, :);

    % Compute centroid for inward orientation
    centroid = [mean(corners(:, 1)), mean(corners(:, 2))];

    contour_pts = boundary_data.contour;
    % Subsample contour if necessary for speed
    step = max(1, round(cfg.edge.contour_sample_step));
    if step > 1
        contour_pts = contour_pts(1:step:end, :);
    end

    edge_defs = {
        'Top',    tl, tr;
        'Right',  tr, br;
        'Bottom', br, bl;
        'Left',   bl, tl
    };

    total_nom = 0.0;
    total_vis = 0.0;
    total_dam = 0.0;
    global_max_depth = 0.0;
    global_defect_count = 0;

    for i = 1:4
        e_name = edge_defs{i, 1};
        p_start = edge_defs{i, 2};
        p_end   = edge_defs{i, 3};

        nominal_len = norm(p_end - p_start);
        total_nom = total_nom + nominal_len;

        % Filter contour points closest to this edge segment
        edge_pts = get_points_for_edge(contour_pts, p_start, p_end, centroid, edge_defs, i);

        if isempty(edge_pts)
            % Fallback if sparse
            edge_struct = struct('name', e_name, 'corners', [p_start; p_end], ...
                                 'nominal_length', nominal_len, 'visible_length', nominal_len, ...
                                 'damaged_length', 0.0, 'max_defect_depth', 0.0, ...
                                 'defect_count', 0, 'status', 'INTACT', ...
                                 'defect_points', zeros(0, 2), 'intact_points', zeros(0, 2));
            edge_analysis.edges(i) = edge_struct;
            total_vis = total_vis + nominal_len;
            continue;
        end

        % Compute orthogonal distances and projections
        n_pts = size(edge_pts, 1);
        deviations = zeros(n_pts, 1);
        t_vals = zeros(n_pts, 1);
        is_inward = false(n_pts, 1);

        % Inward normal vector points toward centroid
        mid_edge = (p_start + p_end) / 2.0;
        inward_dir = centroid - mid_edge;
        inward_dir = inward_dir / max(norm(inward_dir), 1e-6);

        for k = 1:n_pts
            pt = edge_pts(k, :);
            [dist, proj, t] = matlab_fallback_utils.point_to_segment_dist(pt, p_start, p_end);
            deviations(k) = dist;
            t_vals(k) = t;

            % Vector from projection to point
            disp_vec = pt - proj;
            % Dot product with inward direction
            dot_prod = sum(disp_vec .* inward_dir);
            is_inward(k) = (dot_prod > 0);
        end

        % Sort edge points along line direction (t parameter from 0 to 1)
        [t_sorted, sort_order] = sort(t_vals);
        edge_pts_sorted = edge_pts(sort_order, :);
        deviations_sorted = deviations(sort_order);
        is_inward_sorted = is_inward(sort_order);

        % Mark defect points: inward deviations exceeding threshold
        tol = cfg.edge.defect_tolerance_px;
        min_depth = cfg.edge.tear_depth_threshold_px;
        is_defect_raw = is_inward_sorted & (deviations_sorted > tol);

        % Cluster defect points into continuous runs
        defect_clusters = cluster_defects(edge_pts_sorted, is_defect_raw, deviations_sorted, ...
                                         cfg.edge.min_defect_length_px, min_depth);

        % Calculate damaged length and intact points
        damaged_len = 0.0;
        max_edge_depth = 0.0;
        defect_pts_all = zeros(0, 2);
        is_defect_final = false(n_pts, 1);

        for c = 1:length(defect_clusters)
            cluster = defect_clusters(c);
            damaged_len = damaged_len + cluster.length;
            max_edge_depth = max(max_edge_depth, cluster.max_depth);
            defect_pts_all = [defect_pts_all; cluster.points];
            is_defect_final(cluster.indices) = true;
        end

        intact_pts = edge_pts_sorted(~is_defect_final, :);

        % Clamp damaged length to not exceed nominal edge length
        damaged_len = min(damaged_len, nominal_len);
        vis_len = max(0.0, nominal_len - damaged_len);

        if damaged_len > 0.0 && max_edge_depth >= min_depth
            status_str = 'DAMAGED';
        else
            status_str = 'INTACT';
        end

        edge_struct = struct();
        edge_struct.name = e_name;
        edge_struct.corners = [p_start; p_end];
        edge_struct.nominal_length = round(nominal_len, 1);
        edge_struct.visible_length = round(vis_len, 1);
        edge_struct.damaged_length = round(damaged_len, 1);
        edge_struct.max_defect_depth = round(max_edge_depth, 1);
        edge_struct.defect_count = length(defect_clusters);
        edge_struct.status = status_str;
        edge_struct.defect_points = defect_pts_all;
        edge_struct.intact_points = intact_pts;

        edge_analysis.edges(i) = edge_struct;

        total_vis = total_vis + vis_len;
        total_dam = total_dam + damaged_len;
        global_max_depth = max(global_max_depth, max_edge_depth);
        global_defect_count = global_defect_count + length(defect_clusters);
    end

    edge_analysis.total_nominal_perimeter = round(total_nom, 1);
    edge_analysis.total_visible_perimeter = round(total_vis, 1);
    edge_analysis.total_damaged_length = round(total_dam, 1);
    edge_analysis.max_defect_depth = round(global_max_depth, 1);
    edge_analysis.total_defect_count = global_defect_count;
    edge_analysis.is_valid = true;
end

%% Helper: Filter points belonging to a specific edge
function pts = get_points_for_edge(all_pts, a, b, centroid, edge_defs, edge_idx)
    n = size(all_pts, 1);
    keep = false(n, 1);

    for i = 1:n
        p = all_pts(i, :);
        [d_curr, ~, ~] = matlab_fallback_utils.point_to_segment_dist(p, a, b);

        % Compare distance against the other 3 edges
        is_closest = true;
        for other = 1:4
            if other ~= edge_idx
                oa = edge_defs{other, 2};
                ob = edge_defs{other, 3};
                [d_other, ~, ~] = matlab_fallback_utils.point_to_segment_dist(p, oa, ob);
                if d_other < d_curr
                    is_closest = false;
                    break;
                end
            end
        end

        if is_closest
            keep(i) = true;
        end
    end

    pts = all_pts(keep, :);
end

%% Helper: Cluster continuous defect runs along an edge
function clusters = cluster_defects(pts, is_defect_raw, deviations, min_length_px, min_depth_px)
    clusters = struct('indices', {}, 'points', {}, 'length', {}, 'max_depth', {});
    n = length(is_defect_raw);
    if n == 0, return; end

    in_cluster = false;
    start_idx = 1;

    for i = 1:n
        if is_defect_raw(i) && ~in_cluster
            in_cluster = true;
            start_idx = i;
        elseif ~is_defect_raw(i) && in_cluster
            in_cluster = false;
            end_idx = i - 1;
            c = evaluate_cluster(pts, deviations, start_idx, end_idx, min_length_px, min_depth_px);
            if ~isempty(c)
                clusters(end+1) = c;
            end
        end
    end

    if in_cluster
        end_idx = n;
        c = evaluate_cluster(pts, deviations, start_idx, end_idx, min_length_px, min_depth_px);
        if ~isempty(c)
            clusters(end+1) = c;
        end
    end
end

function c = evaluate_cluster(pts, deviations, s_idx, e_idx, min_len, min_depth)
    idx_range = s_idx:e_idx;
    cluster_pts = pts(idx_range, :);
    cluster_devs = deviations(idx_range);

    % Compute span length along points
    diffs = diff(cluster_pts, 1, 1);
    span_len = sum(sqrt(sum(diffs.^2, 2)));
    % Add point extent if single/few points
    span_len = max(span_len, norm(cluster_pts(end, :) - cluster_pts(1, :)));

    max_d = max(cluster_devs);

    % Only keep if it satisfies minimum physical defect criteria
    if span_len >= min_len && max_d >= min_depth
        c = struct();
        c.indices = idx_range;
        c.points = cluster_pts;
        c.length = span_len;
        c.max_depth = max_d;
    else
        c = [];
    end
end
