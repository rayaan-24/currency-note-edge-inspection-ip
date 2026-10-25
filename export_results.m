function export_paths = export_results(result, output_dir, cfg)
% EXPORT_RESULTS - Step 8: Multi-Format Result Persistence (PNG, JSON, CSV)
%
% Exports complete visual and numerical results for an inspected currency note:
%   - PNG Overlay visualization (results/overlays/)
%   - PNG Damage Mask (results/masks/)
%   - PNG Boundary visualization (results/boundaries/)
%   - PNG Quad-Comparison composite (results/overlays/)
%   - JSON Detailed Analysis Report (results/reports/)
%   - Appends audit record to summary.csv (results/summary.csv)
%
% Syntax:
%   export_paths = export_results(result, output_dir, cfg)
%
% Inputs:
%   result     - Result struct returned by process_currency_note.m.
%   output_dir - (Optional) Root results directory (default: 'results').
%   cfg        - (Optional) Configuration struct.
%
% Outputs:
%   export_paths struct containing absolute paths to all saved artifacts.

    if nargin < 3 || isempty(cfg)
        cfg = config();
    end

    if nargin < 2 || isempty(output_dir)
        output_dir = cfg.paths.results_dir;
    end

    overlays_dir   = fullfile(output_dir, 'overlays');
    masks_dir      = fullfile(output_dir, 'masks');
    boundaries_dir = fullfile(output_dir, 'boundaries');
    reports_dir    = fullfile(output_dir, 'reports');
    summary_csv    = fullfile(output_dir, 'summary.csv');

    % Ensure directories exist
    dirs = {output_dir, overlays_dir, masks_dir, boundaries_dir, reports_dir};
    for d = 1:length(dirs)
        if ~exist(dirs{d}, 'dir')
            mkdir(dirs{d});
        end
    end

    export_paths = struct();

    %% 1. Generate Safe Unique Filename Prefix
    [~, base_name, ~] = fileparts(result.input_info.source_path);
    if isempty(base_name)
        base_name = 'note_inspection';
    end
    % Sanitize filename
    clean_base = regexprep(base_name, '[^a-zA-Z0-9_\-]', '_');
    timestamp_str = datestr(now, 'yyyymmdd_HHMMSS');
    file_prefix = sprintf('%s_%s', clean_base, timestamp_str);

    %% 2. Export Visual PNG Artifacts
    % 2a. Overlay Image
    if isfield(result, 'visualization') && isfield(result.visualization, 'overlay_image')
        overlay_file = fullfile(overlays_dir, sprintf('%s_overlay.png', file_prefix));
        imwrite(result.visualization.overlay_image, overlay_file);
        export_paths.overlay_path = overlay_file;
    end

    % 2b. Damage Mask
    if isfield(result, 'visualization') && isfield(result.visualization, 'damage_mask')
        mask_file = fullfile(masks_dir, sprintf('%s_mask.png', file_prefix));
        imwrite(uint8(result.visualization.damage_mask * 255), mask_file);
        export_paths.mask_path = mask_file;
    end

    % 2c. Boundary Visualization
    if isfield(result, 'visualization') && isfield(result.visualization, 'boundary_image')
        bound_file = fullfile(boundaries_dir, sprintf('%s_boundary.png', file_prefix));
        imwrite(result.visualization.boundary_image, bound_file);
        export_paths.boundary_path = bound_file;
    end

    % 2d. Quad-Comparison Composite
    if isfield(result, 'visualization') && isfield(result.visualization, 'quad_comparison_image')
        quad_file = fullfile(overlays_dir, sprintf('%s_quad.png', file_prefix));
        imwrite(result.visualization.quad_comparison_image, quad_file);
        export_paths.quad_path = quad_file;
    end

    %% 3. Export Comprehensive JSON Report
    report_file = fullfile(reports_dir, sprintf('%s_report.json', file_prefix));
    fid = fopen(report_file, 'w');
    if fid ~= -1
        json_str = serialize_result_json(result, timestamp_str);
        fprintf(fid, '%s', json_str);
        fclose(fid);
        export_paths.report_json_path = report_file;
    end

    %% 4. Append to CSV Audit Summary
    write_summary_csv(summary_csv, result, timestamp_str, file_prefix);
    export_paths.summary_csv_path = summary_csv;

end

%% Helper: Write record into summary.csv
function write_summary_csv(csv_path, result, timestamp_str, file_prefix)
    is_new = ~exist(csv_path, 'file');
    fid = fopen(csv_path, 'a');
    if fid == -1
        warning('export_results:CSVOpenFailed', 'Could not open CSV file: %s', csv_path);
        return;
    end

    if is_new
        % Write header line
        header = ['Timestamp,FilePrefix,SourceFile,Status,Classification,Confidence,' ...
                  'EdgeDamagePct,DamagedLengthPx,VisiblePerimeterPx,MaxTearDepthPx,' ...
                  'TopEdgeStatus,RightEdgeStatus,BottomEdgeStatus,LeftEdgeStatus,Reason'];
        fprintf(fid, '%s\n', header);
    end

    % Extract fields
    src = clean_csv_str(result.input_info.source_path);
    status = result.status;
    cat = result.classification.category;
    conf = result.classification.confidence;
    
    if result.damage.is_reliable
        dam_pct = sprintf('%.2f', result.damage.damage_percentage);
    else
        dam_pct = 'N/A';
    end
    
    dam_len = sprintf('%.1f', result.damage.damaged_edge_length_px);
    perim   = sprintf('%.1f', result.damage.total_perimeter_px);
    
    if isfield(result, 'edges') && result.edges.is_valid
        max_depth = sprintf('%.1f', result.edges.max_defect_depth);
        top_st    = result.edges.edges(1).status;
        right_st  = result.edges.edges(2).status;
        bot_st    = result.edges.edges(3).status;
        left_st   = result.edges.edges(4).status;
    else
        max_depth = 'N/A';
        top_st = 'N/A'; right_st = 'N/A'; bot_st = 'N/A'; left_st = 'N/A';
    end

    reason = clean_csv_str(result.classification.reason);

    row = sprintf('"%s","%s","%s","%s","%s",%.2f,"%s",%s,%s,%s,"%s","%s","%s","%s","%s"', ...
        timestamp_str, file_prefix, src, status, cat, conf, dam_pct, ...
        dam_len, perim, max_depth, top_st, right_st, bot_st, left_st, reason);

    fprintf(fid, '%s\n', row);
    fclose(fid);
end

function s = clean_csv_str(str)
    s = strrep(str, '"', '""');
    s = strrep(s, newline, ' ');
    s = strrep(s, sprintf('\r'), '');
end

%% Helper: Pure MATLAB JSON Serializer for Result Struct
function json = serialize_result_json(result, timestamp_str)
    lines = {};
    lines{end+1} = '{';
    lines{end+1} = sprintf('  "timestamp": "%s",', timestamp_str);
    lines{end+1} = sprintf('  "source_image": "%s",', escape_json(result.input_info.source_path));
    lines{end+1} = sprintf('  "status": "%s",', result.status);
    lines{end+1} = sprintf('  "execution_time_sec": %.4f,', result.execution_time_sec);
    
    % Classification
    lines{end+1} = '  "classification": {';
    lines{end+1} = sprintf('    "category": "%s",', result.classification.category);
    lines{end+1} = sprintf('    "confidence": %.3f,', result.classification.confidence);
    lines{end+1} = sprintf('    "reason": "%s",', escape_json(result.classification.reason));
    lines{end+1} = sprintf('    "is_definitive": %s', bool_str(result.classification.is_definitive));
    lines{end+1} = '  },';

    % Damage Metrics
    lines{end+1} = '  "damage_metrics": {';
    lines{end+1} = sprintf('    "is_reliable": %s,', bool_str(result.damage.is_reliable));
    if result.damage.is_reliable
        lines{end+1} = sprintf('    "edge_damage_percentage": %.2f,', result.damage.damage_percentage);
    else
        lines{end+1} = '    "edge_damage_percentage": null,';
    end
    lines{end+1} = sprintf('    "display_text": "%s",', result.damage.display_text);
    lines{end+1} = sprintf('    "damaged_edge_length_px": %.1f,', result.damage.damaged_edge_length_px);
    lines{end+1} = sprintf('    "total_visible_perimeter_px": %.1f,', result.damage.total_perimeter_px);
    lines{end+1} = sprintf('    "note_area_damage_pct": %.2f', result.damage.note_area_damage_pct);
    lines{end+1} = '  },';

    % Boundary Quality
    lines{end+1} = '  "boundary_quality": {';
    lines{end+1} = sprintf('    "status": "%s",', result.boundary.status);
    lines{end+1} = sprintf('    "confidence": %.3f,', result.boundary.confidence);
    lines{end+1} = sprintf('    "solidity": %.3f,', result.boundary.solidity);
    lines{end+1} = sprintf('    "aspect_ratio": %.3f,', result.boundary.aspect_ratio);
    lines{end+1} = sprintf('    "message": "%s"', escape_json(result.boundary.message));
    lines{end+1} = '  },';

    % Per Edge Analysis
    lines{end+1} = '  "edge_analysis": [';
    if isfield(result, 'edges') && result.edges.is_valid
        for i = 1:length(result.edges.edges)
            e = result.edges.edges(i);
            comma = ',';
            if i == length(result.edges.edges), comma = ''; end
            lines{end+1} = sprintf('    {"edge": "%s", "status": "%s", "nominal_len_px": %.1f, "damaged_len_px": %.1f, "max_depth_px": %.1f, "defects": %d}%s', ...
                e.name, e.status, e.nominal_length, e.damaged_length, e.max_defect_depth, e.defect_count, comma);
        end
    end
    lines{end+1} = '  ]';
    lines{end+1} = '}';
    
    json = strjoin(lines, newline);
end

function s = escape_json(str)
    s = strrep(str, '\', '\\');
    s = strrep(s, '"', '\"');
    s = strrep(s, newline, ' ');
    s = strrep(s, sprintf('\r'), '');
end

function b = bool_str(val)
    if val, b = 'true'; else, b = 'false'; end
end
