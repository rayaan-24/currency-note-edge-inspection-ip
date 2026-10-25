classdef matlab_fallback_utils
    % MATLAB_FALLBACK_UTILS - Toolbox-Independent Image Processing Primitives
    %
    % Provides robust, standalone implementations of essential computer vision
    % and image processing primitives in pure MATLAB. If MATLAB's Image Processing
    % Toolbox is present, these functions transparently leverage high-performance
    % built-ins. If the toolbox is absent, mathematically rigorous base MATLAB
    % matrix algorithms are executed seamlessly.
    %
    % Static Methods:
    %   - rgb2gray_safe
    %   - otsu_threshold_safe
    %   - gaussian_filter_safe
    %   - morphology_safe
    %   - connected_components_safe
    %   - sobel_gradients_safe
    %   - convex_hull_2d_safe
    %   - point_to_segment_dist
    %   - find_quad_corners

    methods (Static)

        %% 1. Safe RGB to Grayscale Conversion
        function gray = rgb2gray_safe(img)
            % Converts an RGB image to grayscale using standard ITU-R BT.601-7 luma.
            if ndims(img) == 2
                gray = img;
                return;
            end
            
            if size(img, 3) >= 3
                if exist('rgb2gray', 'file') == 2 || exist('rgb2gray', 'builtin') == 5
                    try
                        gray = rgb2gray(img(:,:,1:3));
                        return;
                    catch
                        % Fallback to direct matrix computation
                    end
                end
                
                % Standard luma weighting: Y = 0.2989*R + 0.5870*G + 0.1140*B
                r = double(img(:,:,1));
                g = double(img(:,:,2));
                b = double(img(:,:,3));
                y = 0.2989 * r + 0.5870 * g + 0.1140 * b;
                
                if isa(img, 'uint8')
                    gray = uint8(round(min(max(y, 0), 255)));
                elseif isa(img, 'uint16')
                    gray = uint16(round(min(max(y, 0), 65535)));
                else
                    gray = y;
                end
            else
                gray = img(:,:,1);
            end
        end

        %% 2. Otsu Maximum Between-Class Variance Binarization
        function [threshold_val, binary_mask] = otsu_threshold_safe(gray_img, multiplier)
            % Computes global threshold using Nobuyuki Otsu's algorithm (1979).
            if nargin < 2
                multiplier = 1.0;
            end
            
            gray_u8 = uint8(gray_img);
            [h, w] = size(gray_u8);
            total_pixels = h * w;
            
            % Compute 256-bin histogram
            counts = zeros(256, 1);
            for val = 0:255
                counts(val + 1) = sum(gray_u8(:) == val);
            end
            p = counts / total_pixels;
            
            omega = cumsum(p);
            mu = cumsum(p .* (0:255)');
            mu_total = mu(end);
            
            % Maximize between-class variance: sigma_b^2 = (mu_total * omega - mu)^2 / (omega * (1 - omega))
            denominator = omega .* (1.0 - omega);
            numerator = (mu_total * omega - mu).^2;
            
            % Avoid divide-by-zero
            valid = denominator > 1e-12;
            sigma_b_squared = zeros(256, 1);
            sigma_b_squared(valid) = numerator(valid) ./ denominator(valid);
            
            [~, max_idx] = max(sigma_b_squared);
            opt_thresh = (max_idx - 1) / 255.0; % Normalized 0.0 to 1.0
            
            effective_thresh = min(max(opt_thresh * multiplier, 0.05), 0.95);
            thresh_u8 = uint8(round(effective_thresh * 255));
            
            % In currency inspection, notes are typically brighter than dark backdrops.
            % But we verify foreground/background polarities:
            mask_candidate = (gray_u8 >= thresh_u8);
            
            % If candidate mask occupies > 85% or < 15%, check inverted polarity
            area_ratio = sum(mask_candidate(:)) / total_pixels;
            if area_ratio < 0.10 || area_ratio > 0.90
                inverted_mask = (gray_u8 < thresh_u8);
                inv_area = sum(inverted_mask(:)) / total_pixels;
                if inv_area >= 0.15 && inv_area <= 0.85
                    binary_mask = inverted_mask;
                    threshold_val = effective_thresh;
                    return;
                end
            end
            
            binary_mask = mask_candidate;
            threshold_val = effective_thresh;
        end

        %% 3. Gaussian Denoising Filter
        function smoothed = gaussian_filter_safe(img, sigma, ksize)
            % Applies 2D Gaussian smoothing kernel via 2D spatial convolution.
            if nargin < 3
                ksize = max(3, 2 * ceil(2 * sigma) + 1);
            end
            
            % Build 1D Gaussian kernel
            half = floor(ksize / 2);
            x = -half:half;
            gauss_1d = exp(-(x.^2) / (2 * sigma^2));
            gauss_1d = gauss_1d / sum(gauss_1d);
            gauss_2d = gauss_1d' * gauss_1d;
            
            is_u8 = isa(img, 'uint8');
            img_d = double(img);
            
            if exist('imfilter', 'file') == 2 || exist('imfilter', 'builtin') == 5
                try
                    smoothed = imfilter(img_d, gauss_2d, 'replicate');
                    if is_u8, smoothed = uint8(round(smoothed)); end
                    return;
                catch
                end
            end
            
            % Manual 2D convolution with border replication
            pad_img = padarray_safe(img_d, [half, half], 'replicate');
            smoothed_d = conv2(pad_img, gauss_2d, 'valid');
            
            if is_u8
                smoothed = uint8(round(min(max(smoothed_d, 0), 255)));
            else
                smoothed = smoothed_d;
            end
        end

        %% 4. Binary Morphology (Dilation, Erosion, Closing, Opening)
        function result_mask = morphology_safe(bin_mask, op_type, radius)
            % Executes binary morphological operations using spatial structuring elements.
            bin_mask = logical(bin_mask);
            radius = max(1, round(radius));
            
            % Create circular structuring element
            [Y, X] = meshgrid(-radius:radius, -radius:radius);
            se = (X.^2 + Y.^2) <= (radius^2);
            se_count = sum(se(:));
            
            switch lower(op_type)
                case 'dilate'
                    result_mask = dilate_internal(bin_mask, se);
                case 'erode'
                    result_mask = erode_internal(bin_mask, se, se_count);
                case 'close'
                    % Close = Dilate then Erode
                    dilated = dilate_internal(bin_mask, se);
                    result_mask = erode_internal(dilated, se, se_count);
                case 'open'
                    % Open = Erode then Dilate
                    eroded = erode_internal(bin_mask, se, se_count);
                    result_mask = dilate_internal(eroded, se);
                otherwise
                    error('Unsupported morphology operation: %s', op_type);
            end
            
            function d = dilate_internal(m, kernel)
                kh = floor(size(kernel, 1) / 2);
                pad_m = padarray_safe(double(m), [kh, kh], 'replicate');
                conv_res = conv2(pad_m, double(kernel), 'valid');
                d = conv_res >= 1.0;
            end
            
            function e = erode_internal(m, kernel, req_count)
                kh = floor(size(kernel, 1) / 2);
                pad_m = padarray_safe(double(m), [kh, kh], 0);
                conv_res = conv2(pad_m, double(kernel), 'valid');
                e = conv_res >= (req_count - 0.5);
            end
        end

        %% 5. Connected Component Analysis & Largest Region Extraction
        function [cc_stats, largest_mask] = connected_components_safe(bin_mask)
            % 2-Pass Connected Component Labeling (8-connectivity).
            bin_mask = logical(bin_mask);
            [h, w] = size(bin_mask);
            
            if exist('bwconncomp', 'file') == 2 || exist('bwconncomp', 'builtin') == 5
                try
                    cc = bwconncomp(bin_mask, 8);
                    stats = regionprops(cc, 'Area', 'BoundingBox', 'PixelIdxList', 'Centroid');
                    cc_stats = stats;
                    
                    if isempty(stats)
                        largest_mask = false(h, w);
                        return;
                    end
                    
                    areas = [stats.Area];
                    [~, max_idx] = max(areas);
                    largest_mask = false(h, w);
                    largest_mask(stats(max_idx).PixelIdxList) = true;
                    return;
                catch
                end
            end
            
            % Pure MATLAB 2-pass connected components algorithm
            labels = zeros(h, w);
            parent = zeros(h * w / 4 + 100, 1);
            next_label = 1;
            
            function r = find_root(x)
                while parent(x) > 0 && parent(x) ~= x
                    x = parent(x);
                end
                r = x;
            end
            
            function union_labels(a, b)
                ra = find_root(a);
                rb = find_root(b);
                if ra ~= rb
                    parent(rb) = ra;
                end
            end

            for y = 1:h
                for x = 1:w
                    if bin_mask(y, x)
                        neighbors = [];
                        if y > 1 && x > 1 && labels(y-1, x-1) > 0, neighbors(end+1) = labels(y-1, x-1); end
                        if y > 1 && labels(y-1, x) > 0,           neighbors(end+1) = labels(y-1, x);   end
                        if y > 1 && x < w && labels(y-1, x+1) > 0, neighbors(end+1) = labels(y-1, x+1); end
                        if x > 1 && labels(y, x-1) > 0,           neighbors(end+1) = labels(y, x-1);   end
                        
                        if isempty(neighbors)
                            labels(y, x) = next_label;
                            parent(next_label) = next_label;
                            next_label = next_label + 1;
                        else
                            min_lbl = min(neighbors);
                            labels(y, x) = min_lbl;
                            for k = 1:length(neighbors)
                                union_labels(min_lbl, neighbors(k));
                            end
                        end
                    end
                end
            end
            
            % Second pass: resolve roots
            resolved_map = containers.Map('KeyType', 'int32', 'ValueType', 'int32');
            dense_label = 1;
            dense_labels = zeros(h, w);
            
            for y = 1:h
                for x = 1:w
                    lbl = labels(y, x);
                    if lbl > 0
                        root_lbl = int32(find_root(lbl));
                        if ~isKey(resolved_map, root_lbl)
                            resolved_map(root_lbl) = dense_label;
                            dense_label = dense_label + 1;
                        end
                        dense_labels(y, x) = resolved_map(root_lbl);
                    end
                end
            end
            
            num_components = dense_label - 1;
            if num_components == 0
                cc_stats = [];
                largest_mask = false(h, w);
                return;
            end
            
            % Compute areas and pixel lists
            cc_stats = struct('Area', {}, 'BoundingBox', {}, 'PixelIdxList', {}, 'Centroid', {});
            max_area = 0;
            max_idx = 1;
            
            for c = 1:num_components
                pix_indices = find(dense_labels == c);
                area = length(pix_indices);
                [rows, cols] = ind2sub([h, w], pix_indices);
                min_c = min(cols); max_c = max(cols);
                min_r = min(rows); max_r = max(rows);
                
                cc_stats(c).Area = area;
                cc_stats(c).BoundingBox = [min_c, min_r, max_c - min_c + 1, max_r - min_r + 1];
                cc_stats(c).PixelIdxList = pix_indices;
                cc_stats(c).Centroid = [mean(cols), mean(rows)];
                
                if area > max_area
                    max_area = area;
                    max_idx = c;
                end
            end
            
            largest_mask = false(h, w);
            largest_mask(cc_stats(max_idx).PixelIdxList) = true;
        end

        %% 6. Sobel Edge Gradient Filter
        function [grad_mag, grad_x, grad_y] = sobel_gradients_safe(gray_img)
            % Computes horizontal, vertical, and overall gradient magnitudes.
            gray_d = double(gray_img);
            
            hx = [-1, 0, 1; -2, 0, 2; -1, 0, 1];
            hy = [-1, -2, -1; 0, 0, 0; 1, 2, 1];
            
            pad_img = padarray_safe(gray_d, [1, 1], 'replicate');
            grad_x = conv2(pad_img, hx, 'valid');
            grad_y = conv2(pad_img, hy, 'valid');
            grad_mag = sqrt(grad_x.^2 + grad_y.^2);
        end

        %% 7. 2D Convex Hull (Monotone Chain Algorithm)
        function hull_pts = convex_hull_2d_safe(pts)
            % pts is an Nx2 array of [x, y] coordinates.
            % Returns counter-clockwise ordered convex hull vertices.
            if size(pts, 1) <= 3
                hull_pts = pts;
                return;
            end
            
            % Sort points lexicographically by x, then y
            [~, sort_idx] = sortrows(pts, [1, 2]);
            sorted_pts = pts(sort_idx, :);
            
            % Remove duplicate coordinates
            d = diff(sorted_pts, 1, 1);
            duplicate_mask = [false; all(d == 0, 2)];
            sorted_pts(duplicate_mask, :) = [];
            n = size(sorted_pts, 1);
            if n <= 3
                hull_pts = sorted_pts;
                return;
            end
            
            % Cross product of 2D vectors OA and OB: (A.x - O.x)*(B.y - O.y) - (A.y - O.y)*(B.x - O.x)
            function cp = cross_prod(o, a, b)
                cp = (a(1) - o(1)) * (b(2) - o(2)) - (a(2) - o(2)) * (b(1) - o(1));
            end
            
            % Build lower hull
            lower = zeros(n, 2);
            k_low = 0;
            for i = 1:n
                p = sorted_pts(i, :);
                while k_low >= 2 && cross_prod(lower(k_low-1, :), lower(k_low, :), p) <= 0
                    k_low = k_low - 1;
                end
                k_low = k_low + 1;
                lower(k_low, :) = p;
            end
            
            % Build upper hull
            upper = zeros(n, 2);
            k_up = 0;
            for i = n:-1:1
                p = sorted_pts(i, :);
                while k_up >= 2 && cross_prod(upper(k_up-1, :), upper(k_up, :), p) <= 0
                    k_up = k_up - 1;
                end
                k_up = k_up + 1;
                upper(k_up, :) = p;
            end
            
            % Combine (omit last point of each list as it is repeated)
            hull_pts = [lower(1:k_low-1, :); upper(1:k_up-1, :)];
        end

        %% 8. Orthogonal Point-to-Line-Segment Distance
        function [dist, proj_pt, t] = point_to_segment_dist(p, a, b)
            % Computes shortest Euclidean distance from point p to line segment a-b.
            ab = b - a;
            len_sq = sum(ab.^2);
            
            if len_sq < 1e-12
                dist = norm(p - a);
                proj_pt = a;
                t = 0;
                return;
            end
            
            % Projection scalar t = ((p - a) . (b - a)) / |b - a|^2
            t = sum((p - a) .* ab) / len_sq;
            t_clamped = min(max(t, 0.0), 1.0);
            
            proj_pt = a + t_clamped * ab;
            dist = norm(p - proj_pt);
        end

        %% 9. 4-Corner Estimation for Currency Notes
        function corners = find_quad_corners(contour_pts, hull_pts)
            % Detects the 4 primary corners of a rectangular note:
            % [Top-Left; Top-Right; Bottom-Right; Bottom-Left].
            if isempty(contour_pts)
                corners = zeros(4, 2);
                return;
            end
            
            % Strategy: project onto 4 diagonal axes:
            % Top-Left: minimizes (x + y)
            % Bottom-Right: maximizes (x + y)
            % Top-Right: maximizes (x - y)
            % Bottom-Left: minimizes (x - y)
            
            sum_xy = contour_pts(:, 1) + contour_pts(:, 2);
            diff_xy = contour_pts(:, 1) - contour_pts(:, 2);
            
            [~, idx_tl] = min(sum_xy);
            [~, idx_br] = max(sum_xy);
            [~, idx_tr] = max(diff_xy);
            [~, idx_bl] = min(diff_xy);
            
            c_tl = contour_pts(idx_tl, :);
            c_tr = contour_pts(idx_tr, :);
            c_br = contour_pts(idx_br, :);
            c_bl = contour_pts(idx_bl, :);
            
            corners = [c_tl; c_tr; c_br; c_bl];
        end

    end
end

%% Helper function: Safe matrix padding (substitute for padarray)
function out = padarray_safe(A, padsize, padval)
    if ischar(padval) && strcmpi(padval, 'replicate')
        ph = padsize(1);
        pw = padsize(2);
        [h, w] = size(A);
        
        row_idx = [ones(1, ph), 1:h, h * ones(1, ph)];
        col_idx = [ones(1, pw), 1:w, w * ones(1, pw)];
        out = A(row_idx, col_idx);
    else
        val = double(padval);
        ph = padsize(1);
        pw = padsize(2);
        [h, w] = size(A);
        out = val * ones(h + 2*ph, w + 2*pw);
        out(ph+1:ph+h, pw+1:pw+w) = A;
    end
end
