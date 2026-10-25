function classification_result = classify_note_condition(damage_metric, edge_analysis, boundary_data, gray_img, cfg)
% CLASSIFY_NOTE_CONDITION - Step 7: Rule-Based Condition Classification
%
% Categorizes currency note condition into one of 5 distinct academic classes:
%   1. 'Good'                    - Intact edges, clean surface, high confidence.
%   2. 'Torn'                    - One or more missing sections, notches, or tears.
%   3. 'Folded'                  - Validated paired ridge/valley crease traversing note body.
%   4. 'Old/Worn'                - Elevated surface texture roughness, fading, or fiber wear.
%   5. 'Needs Manual Inspection' - Low image quality, uncertain boundary, or ambiguous defect.
%
% Inputs:
%   damage_metric - Struct from calculate_damage_percentage.m.
%   edge_analysis - Struct from analyze_note_edges.m.
%   boundary_data - Struct from detect_note_boundary.m.
%   gray_img      - Preprocessed grayscale image.
%   cfg           - Configuration struct (from config.m).
%
% Outputs:
%   classification_result struct with fields:
%     .category      - String class name.
%     .confidence    - Scalar (0.0 to 1.0) estimation confidence.
%     .reason        - Detailed human-readable rationale for the decision.
%     .indicators    - Struct containing all quantitative numerical measurements.
%     .is_definitive - Boolean indicating whether algorithmic rules reached a clear verdict.

    if nargin < 5 || isempty(cfg)
        cfg = config();
    end

    classification_result = struct();
    classification_result.category = 'Needs Manual Inspection';
    classification_result.confidence = 0.0;
    classification_result.reason = '';
    classification_result.indicators = struct();
    classification_result.is_definitive = false;

    %% 1. Guard against boundary failure or poor image quality
    if isempty(boundary_data) || strcmp(boundary_data.status, 'FAILED') || ...
       boundary_data.confidence < cfg.boundary.min_confidence_threshold
        classification_result.category = 'Needs Manual Inspection';
        classification_result.confidence = 0.20;
        if isfield(boundary_data, 'message') && ~isempty(boundary_data.message)
            classification_result.reason = sprintf('Low boundary quality: %s', boundary_data.message);
        else
            classification_result.reason = 'Boundary detection confidence below acceptable operating threshold.';
        end
        return;
    end

    %% 2. Compute Quantitative Defect & Wear Indicators
    edge_dam_pct = 0.0;
    max_tear_depth = 0.0;
    if ~isempty(damage_metric) && damage_metric.is_reliable
        edge_dam_pct = damage_metric.damage_percentage;
    end
    if ~isempty(edge_analysis) && edge_analysis.is_valid
        max_tear_depth = edge_analysis.max_defect_depth;
    end

    % Extract Interior Mask for Surface Analysis (erode boundary by 20px to avoid border artifacts)
    note_mask = boundary_data.mask;
    interior_mask = matlab_fallback_utils.morphology_safe(note_mask, 'erode', 20);

    % Indicator: Fold Crease Detection (directional ridge-valley paired gradient)
    [has_fold, fold_intensity, fold_span_ratio] = detect_fold_crease(gray_img, interior_mask, boundary_data, cfg);

    % Indicator: Surface Wear & Fading Index (high-frequency roughness + contrast compression)
    [wear_index, roughness_val, contrast_fade] = compute_wear_indicators(gray_img, interior_mask);

    % Store indicators for transparency and debugging
    indicators = struct();
    indicators.edge_damage_pct = edge_dam_pct;
    indicators.max_tear_depth_px = max_tear_depth;
    indicators.boundary_confidence = boundary_data.confidence;
    indicators.has_fold = has_fold;
    indicators.fold_intensity = fold_intensity;
    indicators.fold_span_ratio = fold_span_ratio;
    indicators.wear_index = wear_index;
    indicators.roughness_val = roughness_val;
    indicators.contrast_fade = contrast_fade;
    classification_result.indicators = indicators;

    %% 3. Hierarchical Classification Decision Tree

    % Rule 1: TORN NOTE
    % Check for significant edge damage percentage OR deep localized tear/notch
    is_torn_by_pct = (edge_dam_pct >= cfg.classify.torn_min_damage_pct);
    is_torn_by_depth = (max_tear_depth >= cfg.classify.torn_min_defect_depth_px);

    if is_torn_by_pct || is_torn_by_depth
        classification_result.category = 'Torn';
        % Confidence increases with tear magnitude and boundary clarity
        tear_conf = min(1.0, 0.70 + 0.30 * min(edge_dam_pct / 10.0, 1.0));
        classification_result.confidence = round(tear_conf * boundary_data.confidence, 2);
        classification_result.reason = sprintf('Physical edge damage detected: %.2f%% damaged perimeter, max tear depth %d px.', ...
            edge_dam_pct, round(max_tear_depth));
        classification_result.is_definitive = true;
        return;
    end

    % Rule 2: FOLDED NOTE
    % Check if a prominent transverse or longitudinal crease traverses the note body
    if has_fold && fold_intensity >= cfg.classify.fold_gradient_threshold && ...
       fold_span_ratio >= cfg.classify.fold_min_length_ratio
        classification_result.category = 'Folded';
        fold_conf = min(1.0, 0.65 + 0.35 * min(fold_span_ratio, 1.0));
        classification_result.confidence = round(fold_conf * boundary_data.confidence, 2);
        classification_result.reason = sprintf('Prominent continuous fold crease detected traversing note body (Intensity: %.1f, Span: %.1f%%).', ...
            fold_intensity, fold_span_ratio * 100);
        classification_result.is_definitive = true;
        return;
    end

    % Rule 3: OLD / WORN NOTE
    % Check documented wear indicators (surface texture roughness and ink fading)
    if wear_index >= cfg.classify.worn_roughness_threshold
        classification_result.category = 'Old/Worn';
        wear_conf = min(1.0, 0.60 + 0.40 * min(wear_index / 30.0, 1.0));
        classification_result.confidence = round(wear_conf * boundary_data.confidence, 2);
        classification_result.reason = sprintf('Surface aging detected: Texture roughness index %.1f exceeds wear threshold %.1f.', ...
            wear_index, cfg.classify.worn_roughness_threshold);
        classification_result.is_definitive = true;
        return;
    end

    % Rule 4: GOOD NOTE
    % Edge damage is negligible, boundary is sharp, no folds, no severe wear
    if edge_dam_pct <= cfg.classify.good_max_damage_pct && ...
       max_tear_depth < cfg.classify.torn_min_defect_depth_px && ...
       boundary_data.confidence >= 0.60
        classification_result.category = 'Good';
        classification_result.confidence = round(boundary_data.confidence, 2);
        classification_result.reason = 'All 4 edges intact and smooth; no tears, prominent folds, or excessive wear detected.';
        classification_result.is_definitive = true;
        return;
    end

    % Rule 5: Fallback to Manual Inspection (ambiguous or borderline metrics)
    classification_result.category = 'Needs Manual Inspection';
    classification_result.confidence = 0.50;
    classification_result.reason = sprintf('Borderline measurements (Damage: %.2f%%, Wear: %.1f). Automated confidence insufficient for definitive grading.', ...
        edge_dam_pct, wear_index);
    classification_result.is_definitive = false;

end

%% Helper: Physical Crease / Fold Line Detector
function [has_fold, max_intensity, max_span_ratio] = detect_fold_crease(gray_img, interior_mask, boundary_data, cfg)
    has_fold = false;
    max_intensity = 0.0;
    max_span_ratio = 0.0;

    if ~any(interior_mask(:))
        return;
    end

    gray_d = double(gray_img);
    [h, w] = size(gray_d);

    % Banknote dimensions
    corners = boundary_data.corners;
    note_w = norm(corners(2, :) - corners(1, :));
    note_h = norm(corners(4, :) - corners(1, :));

    % Sobel vertical and horizontal gradients
    [~, gx, gy] = matlab_fallback_utils.sobel_gradients_safe(gray_img);

    % A vertical fold crease has strong gx (horizontal contrast change)
    % A horizontal fold crease has strong gy (vertical contrast change)
    
    % Zero out non-interior pixels
    gx_int = gx .* interior_mask;
    gy_int = gy .* interior_mask;

    % Look for paired negative and positive gradients (dark valley + bright ridge)
    % Vertical projection of horizontal gradient:
    col_contrast = sum(abs(gx_int), 1) ./ max(sum(interior_mask, 1), 1);
    row_contrast = sum(abs(gy_int), 2) ./ max(sum(interior_mask, 2), 1);

    % Find prominent column peak (central 60% of width)
    x_min = round(w * 0.20); x_max = round(w * 0.80);
    if x_max > x_min
        central_cols = col_contrast(x_min:x_max);
        [peak_c, idx_c] = max(central_cols);
        col_pos = x_min + idx_c - 1;

        % Verify continuity along column
        col_pixels = interior_mask(:, col_pos);
        crease_len = sum(col_pixels);
        span_ratio_c = crease_len / max(note_h, 1);

        if peak_c > max_intensity
            max_intensity = peak_c;
            max_span_ratio = span_ratio_c;
        end
    end

    % Find prominent row peak (central 60% of height)
    y_min = round(h * 0.20); y_max = round(h * 0.80);
    if y_max > y_min
        central_rows = row_contrast(y_min:y_max);
        [peak_r, idx_r] = max(central_rows);
        row_pos = y_min + idx_r - 1;

        row_pixels = interior_mask(row_pos, :);
        crease_len = sum(row_pixels);
        span_ratio_r = crease_len / max(note_w, 1);

        if peak_r > max_intensity
            max_intensity = peak_r;
            max_span_ratio = span_ratio_r;
        end
    end

    if max_intensity >= cfg.classify.fold_gradient_threshold && ...
       max_span_ratio >= cfg.classify.fold_min_length_ratio
        has_fold = true;
    end
end

%% Helper: Surface Wear & Texture Degradation Indicators
function [wear_index, roughness, dynamic_range] = compute_wear_indicators(gray_img, interior_mask)
    if ~any(interior_mask(:))
        wear_index = 0.0;
        roughness = 0.0;
        dynamic_range = 1.0;
        return;
    end

    gray_d = double(gray_img);
    int_pixels = gray_d(interior_mask);

    % 1. Dynamic range / fading index (5th to 95th percentile)
    s = sort(int_pixels);
    n = length(s);
    p05 = s(max(1, floor(0.05 * n)));
    p95 = s(min(n, ceil(0.95 * n)));
    dynamic_range = (p95 - p05) / 255.0;

    % 2. High-frequency texture roughness (standard deviation of gradient)
    [gmag, ~, ~] = matlab_fallback_utils.sobel_gradients_safe(gray_img);
    gmag_int = gmag(interior_mask);
    roughness = std(gmag_int(:));

    % Composite wear index: roughness is boosted if dynamic range is washed out
    fading_penalty = max(0.0, 0.50 - dynamic_range) * 20.0;
    wear_index = roughness + fading_penalty;
end
