function [gray_img, normalized_img, orig_img, info] = preprocess_note(input_source, cfg)
% PREPROCESS_NOTE - Step 1 & 2: Input Validation, Normalization & Denoising
%
% Implements Step 1 (Image Input) and Step 2 (Preprocessing) of the Currency
% Note Edge Quality Inspection pipeline.
%
% Syntax:
%   [gray_img, normalized_img, orig_img, info] = preprocess_note(input_source, cfg)
%
% Inputs:
%   input_source - File path string (PNG, JPG, BMP, TIF) OR image array (RGB/Gray).
%   cfg          - Configuration struct (from config.m, optional).
%
% Outputs:
%   gray_img       - Preprocessed 2D grayscale image (denoised, contrast enhanced).
%   normalized_img - Resized RGB or Grayscale image preserving aspect ratio.
%   orig_img       - Unmodified original image array.
%   info           - Metadata struct containing dimensions, scale factor, dynamic range.

    if nargin < 2 || isempty(cfg)
        cfg = config();
    end

    info = struct();
    info.is_valid = false;
    info.error_message = '';
    info.source_path = '';

    %% Step 1: Input Loading & Validation
    if ischar(input_source) || isstring(input_source)
        file_path = char(input_source);
        info.source_path = file_path;
        
        if ~exist(file_path, 'file')
            info.error_message = sprintf('File not found: %s', file_path);
            error('preprocess_note:FileNotFound', '%s', info.error_message);
        end
        
        try
            orig_img = imread(file_path);
        catch ME
            info.error_message = sprintf('Unable to read image file: %s (%s)', file_path, ME.message);
            error('preprocess_note:ReadError', '%s', info.error_message);
        end
    elseif isnumeric(input_source) || islogical(input_source)
        orig_img = input_source;
        info.source_path = '<matrix_input>';
    else
        info.error_message = 'Invalid input_source type. Expected filepath string or image matrix.';
        error('preprocess_note:InvalidType', '%s', info.error_message);
    end

    % Check dimensions
    if isempty(orig_img) || ndims(orig_img) < 2
        info.error_message = 'Image array is empty or has fewer than 2 dimensions.';
        error('preprocess_note:EmptyImage', '%s', info.error_message);
    end

    % Strip alpha channel if 4 channels (RGBA)
    if size(orig_img, 3) == 4
        orig_img = orig_img(:, :, 1:3);
    end

    orig_h = size(orig_img, 1);
    orig_w = size(orig_img, 2);
    orig_channels = size(orig_img, 3);
    
    info.original_size = [orig_h, orig_w, orig_channels];
    info.original_class = class(orig_img);

    %% Step 2: Normalization (Aspect-Ratio Preserving Scaling)
    target_w = cfg.preproc.target_width;
    if orig_w ~= target_w && target_w > 0
        scale = target_w / orig_w;
        new_h = max(1, round(orig_h * scale));
        new_w = target_w;
        
        % Check if imresize is available, otherwise use bilinear interpolation
        if exist('imresize', 'file') == 2 || exist('imresize', 'builtin') == 5
            try
                normalized_img = imresize(orig_img, [new_h, new_w]);
            catch
                normalized_img = resize_bilinear(orig_img, new_h, new_w);
            end
        else
            normalized_img = resize_bilinear(orig_img, new_h, new_w);
        end
        info.scale_factor = scale;
    else
        normalized_img = orig_img;
        info.scale_factor = 1.0;
    end
    
    [norm_h, norm_w, norm_c] = size(normalized_img);
    info.normalized_size = [norm_h, norm_w, norm_c];

    %% Convert to Grayscale
    if norm_c >= 3
        raw_gray = matlab_fallback_utils.rgb2gray_safe(normalized_img);
    else
        raw_gray = normalized_img;
    end
    raw_gray_u8 = uint8(raw_gray);

    %% Denoising via Gaussian Smoothing Filter
    sigma = cfg.preproc.denoise_sigma;
    ksize = cfg.preproc.filter_kernel_size;
    denoised_gray = matlab_fallback_utils.gaussian_filter_safe(raw_gray_u8, sigma, ksize);

    %% Selective Contrast Enhancement
    % We compute dynamic range and contrast standard deviation.
    % Only enhance if contrast is compressed to avoid boosting noise.
    gray_double = double(denoised_gray) / 255.0;
    p_low = prctile_safe(gray_double(:), 3);
    p_high = prctile_safe(gray_double(:), 97);
    dynamic_range = p_high - p_low;
    
    info.dynamic_range = dynamic_range;
    info.mean_intensity = mean(gray_double(:));

    if cfg.preproc.enable_contrast_enhancement && dynamic_range < 0.85
        % Contrast stretch
        stretched = (gray_double - p_low) / max(dynamic_range, 1e-4);
        stretched = min(max(stretched, 0.0), 1.0);
        gray_img = uint8(round(stretched * 255.0));
        info.contrast_enhanced = true;
    else
        gray_img = denoised_gray;
        info.contrast_enhanced = false;
    end

    info.is_valid = true;
end

%% Helper: Pure MATLAB Bilinear Image Resizing
function resized = resize_bilinear(src, new_h, new_w)
    [old_h, old_w, channels] = size(src);
    src_d = double(src);
    resized_d = zeros(new_h, new_w, channels);
    
    scale_y = old_h / new_h;
    scale_x = old_w / new_w;
    
    [X_new, Y_new] = meshgrid((0.5:(new_w-0.5)) * scale_x + 0.5, ...
                              (0.5:(new_h-0.5)) * scale_y + 0.5);
    
    X_new = min(max(X_new, 1), old_w);
    Y_new = min(max(Y_new, 1), old_h);
    
    x1 = floor(X_new); x2 = min(x1 + 1, old_w);
    y1 = floor(Y_new); y2 = min(y1 + 1, old_h);
    
    wx = X_new - x1;
    wy = Y_new - y1;
    
    for c = 1:channels
        ch = src_d(:, :, c);
        q11 = ch(sub2ind([old_h, old_w], y1, x1));
        q12 = ch(sub2ind([old_h, old_w], y2, x1));
        q21 = ch(sub2ind([old_h, old_w], y1, x2));
        q22 = ch(sub2ind([old_h, old_w], y2, x2));
        
        top = (1 - wx) .* q11 + wx .* q21;
        bottom = (1 - wx) .* q12 + wx .* q22;
        resized_d(:, :, c) = (1 - wy) .* top + wy .* bottom;
    end
    
    if isa(src, 'uint8')
        resized = uint8(round(min(max(resized_d, 0), 255)));
    else
        resized = resized_d;
    end
end

%% Helper: Percentile estimation without requiring Statistics Toolbox
function val = prctile_safe(data, p)
    s = sort(data(:));
    n = length(s);
    if n == 0
        val = 0;
        return;
    end
    rank = (p / 100.0) * (n - 1) + 1;
    r_floor = floor(rank);
    r_ceil = ceil(rank);
    if r_floor == r_ceil
        val = s(r_floor);
    else
        weight = rank - r_floor;
        val = (1 - weight) * s(r_floor) + weight * s(r_ceil);
    end
end
