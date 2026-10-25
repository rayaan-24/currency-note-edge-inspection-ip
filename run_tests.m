function test_summary = run_tests()
% RUN_TESTS - Comprehensive Automated Test Suite for Image Processing Pipeline
%
% Executes 11 unit and integration tests validating the correctness, mathematical
% precision, error handling, and file export of the Currency Note Edge Quality
% Inspection algorithms:
%
%   Test 1:  Valid RGB image input processing.
%   Test 2:  Grayscale 2D image input processing.
%   Test 3:  Invalid image input & error resilience.
%   Test 4:  Uniform blank image failure-mode handling.
%   Test 5:  Clean synthetic rectangular note (Good note validation).
%   Test 6:  Synthetic note with missing corner tear (Torn corner validation).
%   Test 7:  Synthetic note with top edge notched tear (Edge tear validation).
%   Test 8:  Synthetic note with vertical fold crease (Folded note validation).
%   Test 9:  Synthetic note with high surface texture wear (Old/Worn validation).
%   Test 10: Damage percentage formula unit tests & edge cases (divide-by-zero).
%   Test 11: Exported output file generation (PNG, JSON, CSV).
%
% Syntax:
%   test_summary = run_tests()
%
% Outputs:
%   test_summary struct with passed/failed counts, timing, and detailed log.

    fprintf('=================================================================\n');
    fprintf('       CURRENCY NOTE EDGE INSPECTION: AUTOMATED TEST SUITE       \n');
    fprintf('=================================================================\n\n');

    cfg = config();
    test_dir = fullfile(fileparts(mfilename('fullpath')), 'dataset', 'test_images');

    % Ensure synthetic benchmark images exist
    if ~exist(fullfile(test_dir, 'synthetic_good_01.png'), 'file')
        fprintf('Generating synthetic seed benchmark images for testing...\n');
        generate_synthetic_test_images(test_dir);
    end

    tests = {
        @() test_1_valid_rgb(),                      'Test 1: Valid RGB Input Processing';
        @() test_2_grayscale_input(),                'Test 2: Grayscale 2D Input Processing';
        @() test_3_invalid_input(),                  'Test 3: Invalid Input Error Handling';
        @() test_4_uniform_image(test_dir),          'Test 4: Uniform Blank Canvas Handling';
        @() test_5_clean_note(test_dir),             'Test 5: Clean Note Verification (Good)';
        @() test_6_torn_corner(test_dir),            'Test 6: Missing Corner Detection (Torn)';
        @() test_7_torn_edge(test_dir),              'Test 7: Top Edge Notch Detection (Torn)';
        @() test_8_folded_note(test_dir),            'Test 8: Vertical Fold Crease Detection';
        @() test_9_worn_note(test_dir),              'Test 9: Surface Texture Wear (Old/Worn)';
        @() test_10_damage_calc_math(cfg),           'Test 10: Damage Percentage Formula Math';
        @() test_11_export_pipeline(test_dir, cfg),  'Test 11: Output Artifact Export Pipeline'
    };

    total_tests = size(tests, 1);
    passed_count = 0;
    failed_count = 0;
    test_results = struct('name', {}, 'status', {}, 'message', {}, 'duration', {});

    t_suite_start = tic;

    for i = 1:total_tests
        test_fn = tests{i, 1};
        test_name = tests{i, 2};
        
        fprintf('[RUNNING] %s ... ', test_name);
        t_start = tic;
        
        try
            [ok, msg] = test_fn();
            t_dur = toc(t_start);
            if ok
                fprintf('PASSED (%.3fs)\n', t_dur);
                passed_count = passed_count + 1;
                status_str = 'PASSED';
            else
                fprintf('FAILED (%.3fs) -> %s\n', t_dur, msg);
                failed_count = failed_count + 1;
                status_str = 'FAILED';
            end
        catch ME
            t_dur = toc(t_start);
            fprintf('ERROR (%.3fs) -> %s\n', t_dur, ME.message);
            failed_count = failed_count + 1;
            status_str = 'ERROR';
            msg = ME.message;
        end

        test_results(i).name = test_name;
        test_results(i).status = status_str;
        test_results(i).message = msg;
        test_results(i).duration = t_dur;
    end

    total_time = toc(t_suite_start);

    fprintf('\n=================================================================\n');
    fprintf('TEST SUITE COMPLETE: %d/%d Passed, %d Failed (Total Time: %.2fs)\n', ...
        passed_count, total_tests, failed_count, total_time);
    fprintf('=================================================================\n\n');

    test_summary = struct();
    test_summary.total = total_tests;
    test_summary.passed = passed_count;
    test_summary.failed = failed_count;
    test_summary.duration_sec = total_time;
    test_summary.details = test_results;
end

%% Test 1: Valid RGB Input
function [ok, msg] = test_1_valid_rgb()
    % Create simple 400x600 synthetic RGB array in memory
    img = uint8(40 * ones(400, 600, 3));
    img(100:300, 100:500, :) = 200; % bright rectangle note
    res = process_currency_note(img);
    
    if ~strcmp(res.status, 'SUCCESS') && ~strcmp(res.status, 'WARNING')
        ok = false; msg = 'Pipeline did not return SUCCESS or WARNING status.'; return;
    end
    if isempty(res.preprocessed.gray_image)
        ok = false; msg = 'Preprocessed grayscale image was not generated.'; return;
    end
    ok = true; msg = '';
end

%% Test 2: Grayscale 2D Input
function [ok, msg] = test_2_grayscale_input()
    img_gray = uint8(35 * ones(400, 600));
    img_gray(100:300, 100:500) = 210;
    res = process_currency_note(img_gray);
    
    if isempty(res.preprocessed.gray_image)
        ok = false; msg = 'Failed to process 2D grayscale matrix input.'; return;
    end
    ok = true; msg = '';
end

%% Test 3: Invalid Input Error Handling
function [ok, msg] = test_3_invalid_input()
    % Test non-existent file
    res = process_currency_note('non_existent_file_xyz_12345.png');
    if ~strcmp(res.status, 'ERROR')
        ok = false; msg = 'Expected ERROR status on missing file, but got different status.'; return;
    end
    if ~strcmp(res.classification.category, 'Needs Manual Inspection')
        ok = false; msg = 'Expected "Needs Manual Inspection" for invalid file.'; return;
    end
    ok = true; msg = '';
end

%% Test 4: Uniform Blank Canvas Handling
function [ok, msg] = test_4_uniform_image(test_dir)
    p = fullfile(test_dir, 'synthetic_uniform_06.png');
    if ~exist(p, 'file')
        % Generate blank in memory
        img = uint8(50 * ones(500, 800, 3));
    else
        img = p;
    end
    res = process_currency_note(img);
    
    if ~strcmp(res.boundary.status, 'FAILED')
        ok = false; msg = 'Boundary detection should have failed on uniform blank canvas.'; return;
    end
    if ~strcmp(res.damage.display_text, 'Unable to estimate reliably')
        ok = false; msg = 'Damage display text should be "Unable to estimate reliably".'; return;
    end
    ok = true; msg = '';
end

%% Test 5: Clean Note Verification (Good)
function [ok, msg] = test_5_clean_note(test_dir)
    p = fullfile(test_dir, 'synthetic_good_01.png');
    res = process_currency_note(p);
    
    if ~strcmp(res.classification.category, 'Good')
        ok = false; msg = sprintf('Expected Good category, got %s', res.classification.category); return;
    end
    if res.damage.damage_percentage > 2.0
        ok = false; msg = sprintf('Clean note damage percentage (%.2f%%) exceeded 2.0%%', res.damage.damage_percentage); return;
    end
    ok = true; msg = '';
end

%% Test 6: Missing Corner Detection (Torn)
function [ok, msg] = test_6_torn_corner(test_dir)
    p = fullfile(test_dir, 'synthetic_torn_corner_02.png');
    res = process_currency_note(p);
    
    if ~strcmp(res.classification.category, 'Torn')
        ok = false; msg = sprintf('Expected Torn category, got %s', res.classification.category); return;
    end
    if res.damage.damage_percentage <= 0.0
        ok = false; msg = 'Damage percentage must be > 0.0 for missing corner.'; return;
    end
    if res.edges.max_defect_depth < 6.0
        ok = false; msg = sprintf('Defect depth (%0.1f) lower than expected tear notch.', res.edges.max_defect_depth); return;
    end
    ok = true; msg = '';
end

%% Test 7: Top Edge Notch Detection (Torn)
function [ok, msg] = test_7_torn_edge(test_dir)
    p = fullfile(test_dir, 'synthetic_torn_edge_03.png');
    res = process_currency_note(p);
    
    if ~strcmp(res.classification.category, 'Torn')
        ok = false; msg = sprintf('Expected Torn category, got %s', res.classification.category); return;
    end
    % Top edge should be marked DAMAGED
    top_edge = res.edges.edges(1);
    if ~strcmp(top_edge.status, 'DAMAGED')
        ok = false; msg = 'Top edge was expected to be DAMAGED.'; return;
    end
    ok = true; msg = '';
end

%% Test 8: Vertical Fold Crease Detection
function [ok, msg] = test_8_folded_note(test_dir)
    p = fullfile(test_dir, 'synthetic_folded_04.png');
    res = process_currency_note(p);
    
    if ~strcmp(res.classification.category, 'Folded')
        ok = false; msg = sprintf('Expected Folded category, got %s', res.classification.category); return;
    end
    if ~res.classification.indicators.has_fold
        ok = false; msg = 'Fold indicator boolean was false.'; return;
    end
    ok = true; msg = '';
end

%% Test 9: Surface Texture Wear (Old/Worn)
function [ok, msg] = test_9_worn_note(test_dir)
    p = fullfile(test_dir, 'synthetic_worn_05.png');
    res = process_currency_note(p);
    
    if ~strcmp(res.classification.category, 'Old/Worn')
        ok = false; msg = sprintf('Expected Old/Worn category, got %s', res.classification.category); return;
    end
    if res.classification.indicators.wear_index < 15.0
        ok = false; msg = sprintf('Wear index (%.1f) too low for worn note.', res.classification.indicators.wear_index); return;
    end
    ok = true; msg = '';
end

%% Test 10: Damage Percentage Formula Math
function [ok, msg] = test_10_damage_calc_math(cfg)
    % 10a. Zero perimeter protection
    dummy_b = struct('status', 'SUCCESS', 'confidence', 0.9, 'solidity', 0.95);
    dummy_e = struct('is_valid', true, 'total_visible_perimeter', 0.0, 'total_damaged_length', 0.0, 'edges', []);
    d1 = calculate_damage_percentage(dummy_e, dummy_b, cfg);
    if d1.is_reliable || ~isnan(d1.damage_percentage)
        ok = false; msg = 'Zero perimeter should return unreliable and NaN percentage.'; return;
    end

    % 10b. Clean edge: 0 damaged out of 1000 perimeter -> 0.00%
    dummy_e2 = struct('is_valid', true, 'total_visible_perimeter', 1000.0, 'total_damaged_length', 0.0, 'edges', []);
    d2 = calculate_damage_percentage(dummy_e2, dummy_b, cfg);
    if ~d2.is_reliable || abs(d2.damage_percentage - 0.0) > 1e-3
        ok = false; msg = 'Expected 0.00% damage on clean perimeter.'; return;
    end

    % 10c. 10% damaged: 100px damaged out of 900 intact + 100 damaged = 1000 total -> 10.00%
    dummy_e3 = struct('is_valid', true, 'total_visible_perimeter', 900.0, 'total_damaged_length', 100.0, 'edges', []);
    d3 = calculate_damage_percentage(dummy_e3, dummy_b, cfg);
    if abs(d3.damage_percentage - 10.00) > 1e-2
        ok = false; msg = sprintf('Expected 10.00%% damage, got %.2f%%', d3.damage_percentage); return;
    end

    ok = true; msg = '';
end

%% Test 11: Output Artifact Export Pipeline
function [ok, msg] = test_11_export_pipeline(test_dir, cfg)
    p = fullfile(test_dir, 'synthetic_good_01.png');
    res = process_currency_note(p);
    
    temp_results = fullfile(fileparts(mfilename('fullpath')), 'results');
    export_paths = export_results(res, temp_results, cfg);
    
    if ~isfield(export_paths, 'overlay_path') || ~exist(export_paths.overlay_path, 'file')
        ok = false; msg = 'Overlay PNG was not exported.'; return;
    end
    if ~isfield(export_paths, 'mask_path') || ~exist(export_paths.mask_path, 'file')
        ok = false; msg = 'Mask PNG was not exported.'; return;
    end
    if ~isfield(export_paths, 'report_json_path') || ~exist(export_paths.report_json_path, 'file')
        ok = false; msg = 'JSON Report was not exported.'; return;
    end
    if ~isfield(export_paths, 'summary_csv_path') || ~exist(export_paths.summary_csv_path, 'file')
        ok = false; msg = 'Summary CSV was not exported.'; return;
    end

    ok = true; msg = '';
end
