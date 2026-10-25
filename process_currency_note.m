function result = process_currency_note(input_source, custom_cfg, manual_corners)
% PROCESS_CURRENCY_NOTE - Main Image Processing Pipeline Orchestrator
%
% Executes the complete end-to-end Digital Image Processing workflow for inspecting
% currency note edge quality:
%   Step 1: Image loading, format validation, and integrity checks.
%   Step 2: Preprocessing (color-to-grayscale, normalization, Gaussian denoising).
%   Step 3: Boundary extraction, 4-corner estimation, and boundary quality scoring.
%   Step 4: Independent per-edge analysis (Top, Right, Bottom, Left).
%   Step 5: Defect mask and vivid red overlay generation.
%   Step 6: Precise edge damage percentage calculation.
%   Step 7: Rule-based classification (Good, Folded, Torn, Old/Worn, Manual Inspection).
%
% Syntax:
%   result = process_currency_note(input_source)
%   result = process_currency_note(input_source, custom_cfg)
%   result = process_currency_note(input_source, custom_cfg, manual_corners)
%
% Inputs:
%   input_source   - File path string (PNG, JPG, BMP, TIF) OR image array (RGB/Gray).
%   custom_cfg     - (Optional) Custom configuration struct (from config.m).
%   manual_corners - (Optional) 4x2 matrix [TL; TR; BR; BL] to override boundary corners.
%
% Outputs:
%   result struct with complete pipeline outputs:
%     .input_info         - Metadata regarding original input image.
%     .preprocessed       - Preprocessed grayscale & normalized representations.
%     .boundary           - Detected contour, 4 corners, mask, and confidence.
%     .edges              - Per-edge measurements (Top, Right, Bottom, Left).
%     .damage             - Damage percentage, damaged length, visible perimeter.
%     .classification     - Category, confidence, rationale, and quantitative indicators.
%     .visualization      - Overlay image, damage mask, boundary image, quad composite.
%     .execution_time_sec - Total pipeline runtime in seconds.
%     .status             - 'SUCCESS', 'WARNING', or 'ERROR'.
%     .error_message      - Description if an error or failure occurred.

    t_start = tic;

    if nargin < 2 || isempty(custom_cfg)
        cfg = config();
    else
        cfg = custom_cfg;
    end

    if nargin < 3
        manual_corners = [];
    end

    result = struct();
    result.status = 'PENDING';
    result.error_message = '';
    result.execution_time_sec = 0.0;

    %% Step 1 & 2: Preprocessing
    try
        [gray_img, normalized_img, orig_img, info] = preprocess_note(input_source, cfg);
        result.input_info = info;
        result.preprocessed = struct('gray_image', gray_img, ...
                                     'normalized_image', normalized_img, ...
                                     'original_image', orig_img);
    catch ME
        result.status = 'ERROR';
        result.error_message = sprintf('Preprocessing failed: %s', ME.message);
        result.execution_time_sec = toc(t_start);
        result.classification = struct('category', 'Needs Manual Inspection', ...
                                      'confidence', 0.0, ...
                                      'reason', result.error_message, ...
                                      'is_definitive', false);
        result.damage = struct('is_reliable', false, ...
                               'damage_percentage', NaN, ...
                               'display_text', 'Unable to estimate reliably', ...
                               'damaged_edge_length_px', 0.0, ...
                               'total_perimeter_px', 0.0, ...
                               'note_area_damage_pct', 0.0);
        result.boundary = struct('status', 'FAILED', 'confidence', 0.0, 'message', result.error_message);
        result.edges = struct('is_valid', false, 'edges', []);
        result.visualization = struct('damage_mask', [], 'overlay_image', [], ...
                                      'boundary_image', [], 'quad_comparison_image', [], ...
                                      'summary_text', result.error_message);
        return;
    end

    %% Step 3: Note Boundary & 4-Corner Detection
    boundary_data = detect_note_boundary(gray_img, cfg, manual_corners);
    result.boundary = boundary_data;

    if strcmp(boundary_data.status, 'FAILED')
        result.status = 'WARNING';
        result.error_message = sprintf('Boundary extraction failed: %s', boundary_data.message);
        result.edges = struct('is_valid', false, 'edges', []);
        result.damage = struct('is_reliable', false, ...
                               'damage_percentage', NaN, ...
                               'display_text', 'Unable to estimate reliably', ...
                               'damaged_edge_length_px', 0.0, ...
                               'total_perimeter_px', 0.0, ...
                               'note_area_damage_pct', 0.0);
        result.classification = struct('category', 'Needs Manual Inspection', ...
                                       'confidence', 0.15, ...
                                       'reason', boundary_data.message, ...
                                       'is_definitive', false);
        result.visualization = visualize_damage(normalized_img, boundary_data, result.edges, ...
                                                result.damage, result.classification, cfg);
        result.execution_time_sec = toc(t_start);
        return;
    end

    %% Step 4: Per-Edge Defect Analysis
    edge_analysis = analyze_note_edges(boundary_data, gray_img, cfg);
    result.edges = edge_analysis;

    %% Step 5 & 6: Damage Percentage Calculation
    damage_metric = calculate_damage_percentage(edge_analysis, boundary_data, cfg);
    result.damage = damage_metric;

    %% Step 7: Classification Decision
    classification_result = classify_note_condition(damage_metric, edge_analysis, boundary_data, gray_img, cfg);
    result.classification = classification_result;

    %% Step 8: Visualizations & Overlay Generation
    viz_data = visualize_damage(normalized_img, boundary_data, edge_analysis, damage_metric, classification_result, cfg);
    result.visualization = viz_data;

    %% Finalize Status & Timing
    if strcmp(boundary_data.status, 'WARNING_LOW_CONFIDENCE')
        result.status = 'WARNING';
    else
        result.status = 'SUCCESS';
    end

    result.execution_time_sec = round(toc(t_start), 4);
end
