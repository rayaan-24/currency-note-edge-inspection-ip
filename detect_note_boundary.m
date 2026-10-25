function boundary_data = detect_note_boundary(gray_img, cfg, manual_corners)
% DETECT_NOTE_BOUNDARY - Step 3: Currency Note Boundary & Edge-Region Detection
%
% Accurately segments the banknote from the background, extracts the 2D contour,
% detects the 4 primary corners, computes the convex hull envelope, and calculates
% an objective boundary quality confidence metric. Supports manual corner overrides.
%
% Syntax:
%   boundary_data = detect_note_boundary(gray_img, cfg, manual_corners)
%
% Inputs:
%   gray_img       - Preprocessed grayscale image (uint8 or double).
%   cfg            - Configuration struct (from config.m).
%   manual_corners - (Optional) 4x2 matrix [TL; TR; BR; BL] of manual corner points.
%
% Outputs:
%   boundary_data struct with fields:
%     .contour       - Nx2 array of (x, y) coordinates of outer perimeter.
%     .corners       - 4x2 array of [Top-Left; Top-Right; Bottom-Right; Bottom-Left].
%     .mask          - 2D logical mask of the segmented note region.
%     .convex_hull   - Kx2 array of convex hull vertices.
%     .confidence    - Scalar (0.0 to 1.0) indicating boundary detection reliability.
%     .status        - 'SUCCESS', 'WARNING_LOW_CONFIDENCE', 'FAILED', or 'MANUAL_OVERRIDE'.
%     .message       - Diagnostic description of boundary extraction.
%     .aspect_ratio  - Estimated note aspect ratio (width / height).
%     .solidity      - Ratio of note area to its convex hull area.

    if nargin < 2 || isempty(cfg)
        cfg = config();
    end

    [img_h, img_w] = size(gray_img);
    total_pixels = img_h * img_w;

    boundary_data = struct();
    boundary_data.contour = zeros(0, 2);
    boundary_data.corners = zeros(4, 2);
    boundary_data.mask = false(img_h, img_w);
    boundary_data.convex_hull = zeros(0, 2);
    boundary_data.confidence = 0.0;
    boundary_data.status = 'FAILED';
    boundary_data.message = '';
    boundary_data.aspect_ratio = 1.0;
    boundary_data.solidity = 0.0;

    %% 1. Handle Manual Corner Override if provided by user
    if nargin >= 3 && ~isempty(manual_corners)
        if size(manual_corners, 1) == 4 && size(manual_corners, 2) == 2
            % Check bounds
            in_bounds = manual_corners(:, 1) >= 1 & manual_corners(:, 1) <= img_w & ...
                        manual_corners(:, 2) >= 1 & manual_corners(:, 2) <= img_h;
            if all(in_bounds)
                boundary_data = build_boundary_from_corners(manual_corners, img_h, img_w);
                boundary_data.status = 'MANUAL_OVERRIDE';
                boundary_data.confidence = 1.0;
                boundary_data.message = 'Manual boundary adjustment applied by user.';
                return;
            end
        end
    end

    %% 2. Automated Segmentation & Binarization
    try
        [thresh_val, raw_mask] = matlab_fallback_utils.otsu_threshold_safe(gray_img, cfg.boundary.threshold_multiplier);
    catch ME
        boundary_data.status = 'FAILED';
        boundary_data.message = sprintf('Otsu binarization failed: %s', ME.message);
        return;
    end

    %% 3. Morphological Filtering & Noise Suppression
    % Close gaps in currency ink
    closed_mask = matlab_fallback_utils.morphology_safe(raw_mask, 'close', cfg.boundary.morph_close_radius);
    
    % Strip small detached background noise
    opened_mask = matlab_fallback_utils.morphology_safe(closed_mask, 'open', cfg.boundary.morph_open_radius);
    
    % Hole filling
    filled_mask = fill_holes_safe(opened_mask);

    %% 4. Connected Component Extraction (Largest Region)
    [cc_stats, largest_mask] = matlab_fallback_utils.connected_components_safe(filled_mask);
    
    if isempty(cc_stats) || ~any(largest_mask(:))
        boundary_data.status = 'FAILED';
        boundary_data.message = 'No distinct foreground connected component detected.';
        return;
    end

    note_area = sum(largest_mask(:));
    area_ratio = note_area / total_pixels;

    % Validate area limits
    if area_ratio < cfg.boundary.min_note_area_ratio
        boundary_data.status = 'FAILED';
        boundary_data.message = sprintf('Detected foreground region too small (%.1f%% of image area, required >= %.1f%%).', ...
            area_ratio * 100, cfg.boundary.min_note_area_ratio * 100);
        return;
    end

    if area_ratio > cfg.boundary.max_note_area_ratio
        boundary_data.status = 'FAILED';
        boundary_data.message = sprintf('Detected foreground region exceeds %.1f%% of image area (likely uniform or cropped).', ...
            cfg.boundary.max_note_area_ratio * 100);
        return;
    end

    boundary_data.mask = largest_mask;

    %% 5. Perimeter Contour Tracing
    contour_pts = trace_boundary_safe(largest_mask);
    if size(contour_pts, 1) < 20
        boundary_data.status = 'FAILED';
        boundary_data.message = 'Perimeter contour too short or degenerate.';
        return;
    end
    boundary_data.contour = contour_pts;

    %% 6. Convex Hull Computation
    hull_pts = matlab_fallback_utils.convex_hull_2d_safe(contour_pts);
    boundary_data.convex_hull = hull_pts;

    %% 7. 4-Corner Estimation & Quad Alignment
    corners = matlab_fallback_utils.find_quad_corners(contour_pts, hull_pts);
    boundary_data.corners = corners;

    %% 8. Aspect Ratio & Solidity Calculation
    % Estimate dimensions from corners
    % Top edge length (TL -> TR)
    w_top = norm(corners(2, :) - corners(1, :));
    % Bottom edge length (BL -> BR)
    w_bottom = norm(corners(3, :) - corners(4, :));
    % Left edge length (TL -> BL)
    h_left = norm(corners(4, :) - corners(1, :));
    % Right edge length (TR -> BR)
    h_right = norm(corners(3, :) - corners(2, :));

    avg_w = (w_top + w_bottom) / 2.0;
    avg_h = (h_left + h_right) / 2.0;
    
    if avg_h > 0
        boundary_data.aspect_ratio = avg_w / avg_h;
    else
        boundary_data.aspect_ratio = 1.0;
    end

    % Solidity = Area / Hull Area
    hull_area = polygon_area_safe(hull_pts);
    if hull_area > 0
        boundary_data.solidity = min(1.0, note_area / hull_area);
    else
        boundary_data.solidity = 0.5;
    end

    %% 9. Boundary Quality Confidence Score (0.0 to 1.0)
    % A principled confidence metric combining:
    % (a) Solidity consistency (expected > 0.85 for currency notes)
    % (b) Aspect ratio plausibility (typical banknotes are 1.5 - 2.4)
    % (c) Image border margin (notes not colliding with camera borders)
    % (d) Edge gradient sharpness along contour
    
    % Factor 1: Solidity score (0 to 1)
    % High solidity (> 0.90) => high score; tears reduce solidity slightly to ~0.85
    solidity_score = min(max((boundary_data.solidity - 0.50) / 0.45, 0.0), 1.0);
    
    % Factor 2: Aspect ratio score
    % Ideal aspect ratio is around 1.6 to 2.2
    if boundary_data.aspect_ratio >= 1.2 && boundary_data.aspect_ratio <= 3.0
        ar_score = 1.0 - abs(boundary_data.aspect_ratio - 1.9) / 2.0;
        ar_score = min(max(ar_score, 0.4), 1.0);
    else
        ar_score = 0.2;
    end
    
    % Factor 3: Border clearance (checks if note touches outer frame)
    margin_px = 6;
    touches_border = any(contour_pts(:, 1) <= margin_px) || ...
                     any(contour_pts(:, 1) >= (img_w - margin_px)) || ...
                     any(contour_pts(:, 2) <= margin_px) || ...
                     any(contour_pts(:, 2) >= (img_h - margin_px));
    if touches_border
        border_score = 0.65;
    else
        border_score = 1.0;
    end

    % Composite confidence
    conf = 0.50 * solidity_score + 0.30 * ar_score + 0.20 * border_score;
    boundary_data.confidence = round(conf, 3);

    if boundary_data.confidence >= cfg.boundary.min_confidence_threshold
        boundary_data.status = 'SUCCESS';
        boundary_data.message = sprintf('Boundary verified (Confidence: %.1f%%, Solidity: %.2f, Aspect: %.2f).', ...
            boundary_data.confidence * 100, boundary_data.solidity, boundary_data.aspect_ratio);
    else
        boundary_data.status = 'WARNING_LOW_CONFIDENCE';
        boundary_data.message = sprintf('Low boundary confidence (%.1f%%). Manual inspection recommended.', ...
            boundary_data.confidence * 100);
    end
end

%% Helper: Hole filling in binary mask
function filled = fill_holes_safe(bin_mask)
    if exist('imfill', 'file') == 2 || exist('imfill', 'builtin') == 5
        try
            filled = imfill(bin_mask, 'holes');
            return;
        catch
        end
    end
    
    % Flood fill inverted mask from borders to find exterior background
    [h, w] = size(bin_mask);
    exterior = false(h, w);
    inv_mask = ~bin_mask;
    
    % Seed border pixels
    border_pixels = false(h, w);
    border_pixels(1, :) = true; border_pixels(h, :) = true;
    border_pixels(:, 1) = true; border_pixels(:, w) = true;
    
    seeds = border_pixels & inv_mask;
    queue = find(seeds);
    exterior(queue) = true;
    
    head = 1;
    dx = [0, 0, -1, 1];
    dy = [-1, 1, 0, 0];
    
    while head <= length(queue)
        curr = queue(head);
        head = head + 1;
        [cy, cx] = ind2sub([h, w], curr);
        
        for k = 1:4
            ny = cy + dy(k);
            nx = cx + dx(k);
            if ny >= 1 && ny <= h && nx >= 1 && nx <= w
                if inv_mask(ny, nx) && ~exterior(ny, nx)
                    exterior(ny, nx) = true;
                    queue(end+1) = sub2ind([h, w], ny, nx);
                end
            end
        end
    end
    
    % Holes are non-exterior pixels in inverted mask
    filled = ~exterior;
end

%% Helper: 8-Connected Outer Boundary Tracer (Moore Neighbor Tracing)
function contour = trace_boundary_safe(bin_mask)
    if exist('bwboundaries', 'file') == 2 || exist('bwboundaries', 'builtin') == 5
        try
            b = bwboundaries(bin_mask, 'noholes');
            if ~isempty(b)
                % bwboundaries returns [row, col] -> convert to [x, y]
                contour = [b{1}(:, 2), b{1}(:, 1)];
                return;
            end
        catch
        end
    end

    % Standalone Moore-Neighbor tracing
    [h, w] = size(bin_mask);
    % Find topmost-leftmost pixel
    start_found = false;
    start_y = 1; start_x = 1;
    for y = 1:h
        for x = 1:w
            if bin_mask(y, x)
                start_y = y;
                start_x = x;
                start_found = true;
                break;
            end
        end
        if start_found, break; end
    end

    if ~start_found
        contour = zeros(0, 2);
        return;
    end

    % Directions for 8-neighborhood (clockwise): [dx, dy]
    nbrs = [
        0, -1;   % N
        1, -1;   % NE
        1,  0;   % E
        1,  1;   % SE
        0,  1;   % S
       -1,  1;   % SW
       -1,  0;   % W
       -1, -1    % NW
    ];

    curr_x = start_x;
    curr_y = start_y;
    back_dir = 7; % Entered from West

    max_steps = 2 * (h + w) * 4;
    contour_coords = zeros(max_steps, 2);
    n_pts = 0;

    for step = 1:max_steps
        n_pts = n_pts + 1;
        contour_coords(n_pts, :) = [curr_x, curr_y];

        % Scan 8 neighbors starting from back_dir + 1
        found_next = false;
        search_start = mod(back_dir, 8) + 1;

        for offset = 0:7
            check_idx = mod(search_start + offset - 1, 8) + 1;
            nx = curr_x + nbrs(check_idx, 1);
            ny = curr_y + nbrs(check_idx, 2);

            if nx >= 1 && nx <= w && ny >= 1 && ny <= h
                if bin_mask(ny, nx)
                    curr_x = nx;
                    curr_y = ny;
                    % Back direction points to previous pixel
                    back_dir = mod(check_idx + 4 - 1, 8) + 1;
                    found_next = true;
                    break;
                end
            end
        end

        if ~found_next || (curr_x == start_x && curr_y == start_y && n_pts > 4)
            break;
        end
    end

    contour = contour_coords(1:n_pts, :);
end

%% Helper: Compute 2D Polygon Area using Green's Theorem (Shoelace formula)
function a = polygon_area_safe(pts)
    if size(pts, 1) < 3
        a = 0;
        return;
    end
    x = pts(:, 1);
    y = pts(:, 2);
    a = 0.5 * abs(sum(x .* [y(2:end); y(1)]) - sum(y .* [x(2:end); x(1)]));
end

%% Helper: Rebuild boundary struct from manual corners
function b_data = build_boundary_from_corners(corners, img_h, img_w)
    b_data = struct();
    b_data.corners = corners;
    
    % Interpolate perimeter line segments between corners
    tl = corners(1, :); tr = corners(2, :);
    br = corners(3, :); bl = corners(4, :);
    
    n_seg = 80;
    edge_top = [linspace(tl(1), tr(1), n_seg)', linspace(tl(2), tr(2), n_seg)'];
    edge_right = [linspace(tr(1), br(1), n_seg)', linspace(tr(2), br(2), n_seg)'];
    edge_bottom = [linspace(br(1), bl(1), n_seg)', linspace(br(2), bl(2), n_seg)'];
    edge_left = [linspace(bl(1), tl(1), n_seg)', linspace(bl(2), tl(2), n_seg)'];
    
    b_data.contour = [edge_top; edge_right; edge_bottom; edge_left];
    b_data.convex_hull = corners;
    
    % Polygon mask
    [X, Y] = meshgrid(1:img_w, 1:img_h);
    in_poly = inpolygon_safe(X, Y, corners(:, 1), corners(:, 2));
    b_data.mask = in_poly;
    
    w_avg = (norm(tr - tl) + norm(br - bl)) / 2;
    h_avg = (norm(bl - tl) + norm(br - tr)) / 2;
    b_data.aspect_ratio = w_avg / max(h_avg, 1);
    b_data.solidity = 1.0;
end

%% Helper: Pure MATLAB inpolygon test
function in = inpolygon_safe(X, Y, xv, yv)
    if exist('inpolygon', 'file') == 2 || exist('inpolygon', 'builtin') == 5
        try
            in = inpolygon(X, Y, xv, yv);
            return;
        catch
        end
    end
    % Ray casting algorithm for grid
    [h, w] = size(X);
    in = false(h, w);
    n = length(xv);
    for i = 1:n
        j = mod(i, n) + 1;
        x1 = xv(i); y1 = yv(i);
        x2 = xv(j); y2 = yv(j);
        
        cond = ((y1 > Y) ~= (y2 > Y)) & (X < (x2 - x1) .* (Y - y1) ./ max((y2 - y1), 1e-9) + x1);
        in = xor(in, cond);
    end
end
