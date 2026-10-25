function result = main(input_image_path)
% MAIN - Currency Note Edge Quality Inspection (CLI & Octave Entry Point)
%
% Replaces the legacy desktop uifigure with a lightweight, 100% GNU Octave
% and MATLAB compatible command-line and programmatic interface.
%
% Syntax:
%   result = main()
%   result = main(input_image_path)
%
% Examples:
%   main('dataset/test_images/synthetic_good_01.png')
%   main('dataset/test_images/synthetic_torn_corner_02.png')
%
% When launched without arguments, it analyzes the primary sample note
% and prints a comprehensive diagnostic inspection report.

    % Ensure project root is in Octave / MATLAB load path
    proj_dir = fileparts(mfilename('fullpath'));
    if ~isempty(proj_dir)
        addpath(proj_dir);
    end

    cfg = config();

    if nargin < 1 || isempty(input_image_path)
        input_image_path = fullfile(proj_dir, 'dataset', 'test_images', 'synthetic_good_01.png');
        if ~exist(input_image_path, 'file')
            generate_synthetic_test_images(fullfile(proj_dir, 'dataset', 'test_images'));
        end
    end

    fprintf('=================================================================\n');
    fprintf('        CURRENCY NOTE EDGE QUALITY INSPECTION PIPELINE           \n');
    fprintf('=================================================================\n');
    fprintf('Input Note: %s\n\n', input_image_path);

    % Execute core image processing pipeline
    result = process_currency_note(input_image_path, cfg);

    % Export result artifacts (PNG overlays, mask, JSON, CSV)
    export_paths = export_results(result, cfg.paths.results_dir, cfg);

    % Display diagnostic summary
    fprintf('STATUS:         %s\n', result.status);
    fprintf('CLASSIFICATION: %s (Confidence: %.1f%%)\n', ...
        result.classification.category, result.classification.confidence * 100);
    fprintf('DAMAGE METRIC:  %s\n', result.damage.display_text);
    fprintf('SURFACE LOSS:   %.2f%%\n', result.damage.note_area_damage_pct);
    fprintf('EXECUTION TIME: %.4f seconds\n\n', result.execution_time_sec);
    fprintf('DECISION REASON:\n  %s\n\n', result.classification.reason);

    if isfield(result, 'edges') && result.edges.is_valid
        fprintf('INDIVIDUAL EDGE BREAKDOWN:\n');
        fprintf('  %-8s | %-8s | %-12s | %-14s | %-8s\n', 'Edge', 'Status', 'Damaged (px)', 'Max Depth (px)', 'Defects');
        fprintf('  ------------------------------------------------------------\n');
        for i = 1:length(result.edges.edges)
            e = result.edges.edges(i);
            fprintf('  %-8s | %-8s | %12.1f | %14.1f | %8d\n', ...
                e.name, e.status, e.damaged_length, e.max_defect_depth, e.defect_count);
        end
        fprintf('\n');
    end

    fprintf('EXPORTED ARTIFACTS:\n');
    if isfield(export_paths, 'overlay_path')
        fprintf('  - Overlay:  %s\n', export_paths.overlay_path);
    end
    if isfield(export_paths, 'mask_path')
        fprintf('  - Mask:     %s\n', export_paths.mask_path);
    end
    if isfield(export_paths, 'report_json_path')
        fprintf('  - JSON:     %s\n', export_paths.report_json_path);
    end
    if isfield(export_paths, 'summary_csv_path')
        fprintf('  - CSV Log:  %s\n', export_paths.summary_csv_path);
    end
    fprintf('=================================================================\n');

end
