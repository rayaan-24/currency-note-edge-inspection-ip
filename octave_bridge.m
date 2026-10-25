function octave_bridge(input_image_path, results_dir)
% OCTAVE_BRIDGE - Dedicated headless bridge between Python FastAPI and GNU Octave
%
% This script is invoked by octave_runner.py to execute the full .m image processing
% pipeline on a specified image and output clean machine-readable JSON to stdout.
%
% Syntax:
%   octave_bridge('path/to/image.png')
%   octave_bridge('path/to/image.png', 'results')

    % Ensure project path is loaded
    proj_dir = fileparts(mfilename('fullpath'));
    if ~isempty(proj_dir)
        addpath(proj_dir);
    end

    % Try loading GNU Octave image package if installed
    try
        pkg load image;
    catch
        % Standalone fallbacks in matlab_fallback_utils will handle processing
    end

    cfg = config();
    if nargin >= 2 && ~isempty(results_dir)
        cfg.paths.results_dir = results_dir;
        cfg.paths.overlays_dir = fullfile(results_dir, 'overlays');
        cfg.paths.masks_dir = fullfile(results_dir, 'masks');
        cfg.paths.boundaries_dir = fullfile(results_dir, 'boundaries');
        cfg.paths.reports_dir = fullfile(results_dir, 'reports');
        cfg.paths.summary_csv = fullfile(results_dir, 'summary.csv');
    end

    try
        % Execute core image processing pipeline
        result = process_currency_note(input_image_path, cfg);
        
        % Export result artifacts
        export_paths = export_results(result, cfg.paths.results_dir, cfg);
        
        % Attach export paths to result struct for python consumption
        result.exported_files = export_paths;

        % Print JSON delimiter block for safe parsing
        fprintf('\n===OCTAVE_JSON_START===\n');
        % Read the generated report JSON or serialize
        if isfield(export_paths, 'report_json_path') && exist(export_paths.report_json_path, 'file')
            fid = fopen(export_paths.report_json_path, 'r');
            if fid ~= -1
                report_content = fread(fid, '*char')';
                fclose(fid);
                fprintf('%s', report_content);
            else
                fprintf('{"error": "Failed to read report JSON file"}');
            end
        else
            fprintf('{"status": "%s", "error": "%s"}', result.status, result.error_message);
        end
        fprintf('\n===OCTAVE_JSON_END===\n');

    catch ME
        fprintf('\n===OCTAVE_JSON_START===\n');
        err_msg = strrep(ME.message, '"', '\"');
        fprintf('{"status": "ERROR", "error": "%s", "classification": {"category": "Needs Manual Inspection", "confidence": 0.0, "reason": "Octave runtime error: %s"}, "damage": {"is_reliable": false, "display_text": "Unable to estimate reliably"}}', err_msg, err_msg);
        fprintf('\n===OCTAVE_JSON_END===\n');
    end
end
