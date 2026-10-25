function generated_files = generate_synthetic_test_images(output_dir)
% GENERATE_SYNTHETIC_TEST_IMAGES - Generates ground-truth geometric test images
%
% This MATLAB function generates clearly labeled synthetic currency note test images
% for algorithm unit testing, regression testing, and course demonstrations.
%
% Outputs:
%   generated_files - Cell array of absolute paths to generated image files.
%
% Note:
%   These images are synthetic geometric models designed to validate edge
%   detection accuracy, tear measurement precision, fold detection, and
%   failure-mode robustness. They are explicitly NOT real banknote photographs.

    if nargin < 1 || isempty(output_dir)
        output_dir = fullfile(fileparts(mfilename('fullpath')), 'dataset', 'test_images');
    end
    
    if ~exist(output_dir, 'dir')
        mkdir(output_dir);
    end
    
    img_w = 800;
    img_h = 500;
    note_w = 580;
    note_h = 280;
    
    x0 = floor((img_w - note_w) / 2);
    y0 = floor((img_h - note_h) / 2);
    x1 = x0 + note_w;
    y1 = y0 + note_h;
    
    generated_files = {};

    %% Base background generator
    function bg = make_background()
        bg = zeros(img_h, img_w, 3, 'uint8');
        % Dark charcoal desk background with subtle horizontal grain
        for r = 1:img_h
            val = uint8(36 + mod(r * 7, 9));
            bg(r, :, 1) = val;
            bg(r, :, 2) = val + 4;
            bg(r, :, 3) = val + 10;
        end
    end

    %% Internal security graphics painter
    function img = paint_note_graphics(img, x_start, x_end, y_start, y_end)
        % Security border
        m = 16;
        bx0 = x_start + m; bx1 = x_end - m;
        by0 = y_start + m; by1 = y_end - m;
        
        border_col = uint8([155, 185, 165]);
        img(by0:by0+2, bx0:bx1, 1) = border_col(1);
        img(by0:by0+2, bx0:bx1, 2) = border_col(2);
        img(by0:by0+2, bx0:bx1, 3) = border_col(3);
        
        img(by1-2:by1, bx0:bx1, 1) = border_col(1);
        img(by1-2:by1, bx0:bx1, 2) = border_col(2);
        img(by1-2:by1, bx0:bx1, 3) = border_col(3);
        
        img(by0:by1, bx0:bx0+2, 1) = border_col(1);
        img(by0:by1, bx0:bx0+2, 2) = border_col(2);
        img(by0:by1, bx0:bx0+2, 3) = border_col(3);
        
        img(by0:by1, bx1-2:bx1, 1) = border_col(1);
        img(by0:by1, bx1-2:bx1, 2) = border_col(2);
        img(by0:by1, bx1-2:bx1, 3) = border_col(3);
        
        % Vertical dashed security thread
        th_x = x_start + 240;
        for ty = (y_start + 20):16:(y_end - 20)
            img(ty:ty+8, th_x-1:th_x+1, 1) = 110;
            img(ty:ty+8, th_x-1:th_x+1, 2) = 135;
            img(ty:ty+8, th_x-1:th_x+1, 3) = 120;
        end
    end

    %% 1. Clean Good Note (synthetic_good_01.png)
    img1 = make_background();
    base_color = uint8([190, 218, 198]);
    img1(y0:y1, x0:x1, 1) = base_color(1);
    img1(y0:y1, x0:x1, 2) = base_color(2);
    img1(y0:y1, x0:x1, 3) = base_color(3);
    img1 = paint_note_graphics(img1, x0, x1, y0, y1);
    
    p1 = fullfile(output_dir, 'synthetic_good_01.png');
    imwrite(img1, p1);
    generated_files{end+1} = p1;

    %% 2. Torn Corner Note (synthetic_torn_corner_02.png)
    img2 = make_background();
    img2(y0:y1, x0:x1, 1) = base_color(1);
    img2(y0:y1, x0:x1, 2) = base_color(2);
    img2(y0:y1, x0:x1, 3) = base_color(3);
    
    % Clip off top-right corner with triangular tear notch
    notch_w = 65;
    notch_h = 55;
    bg_ref = make_background();
    for r = y0:(y0 + notch_h)
        cut_w = floor(notch_w * (1 - (r - y0) / notch_h));
        if cut_w > 0
            c_start = x1 - cut_w;
            img2(r, c_start:x1, :) = bg_ref(r, c_start:x1, :);
        end
    end
    img2 = paint_note_graphics(img2, x0, x1, y0, y1);
    
    p2 = fullfile(output_dir, 'synthetic_torn_corner_02.png');
    imwrite(img2, p2);
    generated_files{end+1} = p2;

    %% 3. Torn Top Edge Note (synthetic_torn_edge_03.png)
    img3 = make_background();
    img3(y0:y1, x0:x1, 1) = base_color(1);
    img3(y0:y1, x0:x1, 2) = base_color(2);
    img3(y0:y1, x0:x1, 3) = base_color(3);
    
    % Irregular notched tear along top edge
    tear_center_x = x0 + 260;
    tear_radius_x = 35;
    tear_depth_y = 28;
    for c = (tear_center_x - tear_radius_x):(tear_center_x + tear_radius_x)
        dist_x = abs(c - tear_center_x) / tear_radius_x;
        curr_depth = floor(tear_depth_y * (1 - dist_x^1.6));
        if curr_depth > 0
            img3(y0:(y0 + curr_depth), c, :) = bg_ref(y0:(y0 + curr_depth), c, :);
        end
    end
    img3 = paint_note_graphics(img3, x0, x1, y0, y1);
    
    p3 = fullfile(output_dir, 'synthetic_torn_edge_03.png');
    imwrite(img3, p3);
    generated_files{end+1} = p3;

    %% 4. Folded Note (synthetic_folded_04.png)
    img4 = make_background();
    img4(y0:y1, x0:x1, 1) = base_color(1);
    img4(y0:y1, x0:x1, 2) = base_color(2);
    img4(y0:y1, x0:x1, 3) = base_color(3);
    img4 = paint_note_graphics(img4, x0, x1, y0, y1);
    
    % Strong vertical fold crease
    fold_x = floor((x0 + x1) / 2);
    % Dark valley
    img4(y0:y1, fold_x-1:fold_x, 1) = uint8(base_color(1) * 0.55);
    img4(y0:y1, fold_x-1:fold_x, 2) = uint8(base_color(2) * 0.55);
    img4(y0:y1, fold_x-1:fold_x, 3) = uint8(base_color(3) * 0.55);
    % Bright ridge specular
    img4(y0:y1, fold_x+1:fold_x+2, 1) = uint8(min(255, double(base_color(1)) * 1.25));
    img4(y0:y1, fold_x+1:fold_x+2, 2) = uint8(min(255, double(base_color(2)) * 1.25));
    img4(y0:y1, fold_x+1:fold_x+2, 3) = uint8(min(255, double(base_color(3)) * 1.25));
    
    p4 = fullfile(output_dir, 'synthetic_folded_04.png');
    imwrite(img4, p4);
    generated_files{end+1} = p4;

    %% 5. Old / Worn Note (synthetic_worn_05.png)
    img5 = make_background();
    worn_base = uint8([175, 185, 165]);
    img5(y0:y1, x0:x1, 1) = worn_base(1);
    img5(y0:y1, x0:x1, 2) = worn_base(2);
    img5(y0:y1, x0:x1, 3) = worn_base(3);
    
    % Add synthetic surface aging noise and contrast degradation
    rng(42);
    noise_pattern = int16(randn(y1 - y0 + 1, x1 - x0 + 1) * 18);
    for ch = 1:3
        patch = int16(img5(y0:y1, x0:x1, ch)) + noise_pattern;
        patch = uint8(min(max(patch, 0), 255));
        img5(y0:y1, x0:x1, ch) = patch;
    end
    
    p5 = fullfile(output_dir, 'synthetic_worn_05.png');
    imwrite(img5, p5);
    generated_files{end+1} = p5;

    %% 6. Uniform Blank Canvas (Failure mode testing)
    img6 = uint8(50 * ones(img_h, img_w, 3));
    p6 = fullfile(output_dir, 'synthetic_uniform_06.png');
    imwrite(img6, p6);
    generated_files{end+1} = p6;

    fprintf('Successfully generated %d synthetic benchmark test images in %s\n', ...
        length(generated_files), output_dir);
end
