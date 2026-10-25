function viz_data = visualize_damage(img_display, boundary_data, edge_analysis, damage_metric, classification_result, cfg)
% VISUALIZE_DAMAGE - Step 5: Boundary, Defect Mask & Red Overlay Generation
%
% Generates all diagnostic visual representations for the currency note:
%   1. Binary Damage Mask (2D logical array).
%   2. Vivid Red Defect Overlay on the original/normalized RGB image.
%   3. Boundary and Corner Visualization.
%   4. Quad-View Comparison Panel (Original, Grayscale, Boundary, Overlay).
%
% Syntax:
%   viz_data = visualize_damage(img_display, boundary_data, edge_analysis, damage_metric, classification_result, cfg)
%
% Inputs:
%   img_display           - RGB or Grayscale image array.
%   boundary_data         - Struct returned by detect_note_boundary.m.
%   edge_analysis         - Struct returned by analyze_note_edges.m.
%   damage_metric         - Struct returned by calculate_damage_percentage.m.
%   classification_result - Struct returned by classify_note_condition.m.
%   cfg                   - Configuration struct (from config.m).
%
% Outputs:
%   viz_data struct with fields:
%     .damage_mask           - 2D logical mask of damaged edge regions.
%     .overlay_image         - uint8 RGB image with semi-transparent red damage highlight.
%     .boundary_image        - uint8 RGB image with detected boundary contour & 4 corners.
%     .quad_comparison_image - uint8 RGB composite 2x2 multi-panel inspection canvas.
%     .summary_text          - Formatted multi-line text summary.

    if nargin < 6 || isempty(cfg)
        cfg = config();
    end

    % Ensure base image is RGB uint8
    if size(img_display, 3) == 1
        base_rgb = repmat(uint8(img_display), [1, 1, 3]);
    else
        base_rgb = uint8(img_display(:, :, 1:3));
    end
    [img_h, img_w, ~] = size(base_rgb);

    viz_data = struct();
    viz_data.damage_mask = false(img_h, img_w);
    viz_data.overlay_image = base_rgb;
    viz_data.boundary_image = base_rgb;
    viz_data.quad_comparison_image = base_rgb;
    viz_data.summary_text = '';

    %% 1. Generate Binary Damage Mask
    dam_mask = false(img_h, img_w);
    if ~isempty(edge_analysis) && edge_analysis.is_valid
        for i = 1:length(edge_analysis.edges)
            e = edge_analysis.edges(i);
            if ~isempty(e.defect_points)
                pts = e.defect_points;
                for p = 1:size(pts, 1)
                    px = round(pts(p, 1));
                    py = round(pts(p, 2));
                    % Dilate defect points by brush radius 4 for visibility
                    r_brush = 4;
                    for dy = -r_brush:r_brush
                        for dx = -r_brush:r_brush
                            ny = py + dy; nx = px + dx;
                            if ny >= 1 && ny <= img_h && nx >= 1 && nx <= img_w
                                if (dx^2 + dy^2) <= r_brush^2
                                    dam_mask(ny, nx) = true;
                                end
                            end
                        end
                    end
                end
            end
        end
    end
    viz_data.damage_mask = dam_mask;

    %% 2. Generate Vivid Red Defect Overlay Image
    overlay = base_rgb;
    alpha = cfg.viz.overlay_alpha;
    red_color = uint8(round(cfg.viz.defect_overlay_color * 255));
    green_color = uint8(round(cfg.viz.intact_edge_color * 255));

    % Paint intact edges green (subtle highlight)
    if ~isempty(edge_analysis) && edge_analysis.is_valid
        for i = 1:length(edge_analysis.edges)
            e = edge_analysis.edges(i);
            if ~isempty(e.intact_points)
                pts = e.intact_points;
                for p = 1:size(pts, 1)
                    px = round(pts(p, 1));
                    py = round(pts(p, 2));
                    if py >= 1 && py <= img_h && px >= 1 && px <= img_w
                        overlay(py, px, 1) = uint8(double(overlay(py, px, 1)) * (1 - 0.3) + double(green_color(1)) * 0.3);
                        overlay(py, px, 2) = uint8(double(overlay(py, px, 2)) * (1 - 0.3) + double(green_color(2)) * 0.3);
                        overlay(py, px, 3) = uint8(double(overlay(py, px, 3)) * (1 - 0.3) + double(green_color(3)) * 0.3);
                    end
                end
            end
        end
    end

    % Paint damaged regions vivid semi-transparent RED
    [dam_r, dam_c] = find(dam_mask);
    for idx = 1:length(dam_r)
        r = dam_r(idx); c = dam_c(idx);
        overlay(r, c, 1) = uint8(double(overlay(r, c, 1)) * (1 - alpha) + double(red_color(1)) * alpha);
        overlay(r, c, 2) = uint8(double(overlay(r, c, 2)) * (1 - alpha) + double(red_color(2)) * alpha);
        overlay(r, c, 3) = uint8(double(overlay(r, c, 3)) * (1 - alpha) + double(red_color(3)) * alpha);
    end

    % Draw solid red outline around damaged clusters for maximum contrast
    dam_boundary = dam_mask & ~matlab_fallback_utils.morphology_safe(dam_mask, 'erode', 1);
    [b_r, b_c] = find(dam_boundary);
    for idx = 1:length(b_r)
        overlay(b_r(idx), b_c(idx), :) = red_color;
    end

    viz_data.overlay_image = overlay;

    %% 3. Generate Boundary & Corner Visualization Image
    b_img = base_rgb;
    if ~isempty(boundary_data) && ~strcmp(boundary_data.status, 'FAILED')
        % Draw outer contour in vivid yellow
        if ~isempty(boundary_data.contour)
            c_pts = boundary_data.contour;
            for p = 1:size(c_pts, 1)
                cx = round(c_pts(p, 1)); cy = round(c_pts(p, 2));
                if cy >= 1 && cy <= img_h && cx >= 1 && cx <= img_w
                    b_img(cy, cx, 1) = 255;
                    b_img(cy, cx, 2) = 235;
                    b_img(cy, cx, 3) = 20;
                end
            end
        end

        % Draw estimated quadrilateral envelope (dashed line between 4 corners)
        if size(boundary_data.corners, 1) == 4
            c_quad = boundary_data.corners;
            quad_loop = [c_quad; c_quad(1, :)];
            for k = 1:4
                b_img = draw_line_safe(b_img, quad_loop(k, :), quad_loop(k+1, :), [255, 60, 220], true);
            end

            % Highlight 4 corners as bright cyan circular discs
            corner_col = uint8(round(cfg.viz.corner_color * 255));
            for k = 1:4
                cx = round(c_quad(k, 1)); cy = round(c_quad(k, 2));
                b_img = draw_circle_safe(b_img, cx, cy, 7, corner_col, [0, 0, 0]);
            end
        end
    end
    viz_data.boundary_image = b_img;

    %% 4. Generate 2x2 Multi-Panel Quad Inspection Canvas
    % Panel 1: Original Image
    % Panel 2: Preprocessed Grayscale (converted to 3-channel)
    % Panel 3: Boundary & Corners
    % Panel 4: Red Damage Overlay
    
    panel1 = annotate_panel(base_rgb, '1. Original Image');
    
    gray_3ch = repmat(uint8(matlab_fallback_utils.rgb2gray_safe(base_rgb)), [1, 1, 3]);
    panel2 = annotate_panel(gray_3ch, '2. Preprocessed Grayscale');
    
    conf_str = sprintf('3. Boundary (Conf: %.0f%%)', boundary_data.confidence * 100);
    panel3 = annotate_panel(b_img, conf_str);
    
    status_str = '4. Overlay';
    if ~isempty(classification_result) && ~isempty(damage_metric)
        status_str = sprintf('4. %s (Damage: %s)', classification_result.category, damage_metric.display_text);
    end
    panel4 = annotate_panel(overlay, status_str);

    % Assemble 2x2 composite
    top_half = [panel1, panel2];
    bottom_half = [panel3, panel4];
    viz_data.quad_comparison_image = [top_half; bottom_half];

    %% 5. Generate Text Summary
    lines = {};
    lines{end+1} = '=== Currency Note Edge Inspection Summary ===';
    if ~isempty(classification_result)
        lines{end+1} = sprintf('Classification: %s (Confidence: %.1f%%)', ...
            classification_result.category, classification_result.confidence * 100);
        lines{end+1} = sprintf('Reason: %s', classification_result.reason);
    end
    if ~isempty(damage_metric)
        lines{end+1} = sprintf('Edge Damage Percentage: %s', damage_metric.display_text);
        lines{end+1} = sprintf('Total Damaged Length: %.1f px | Total Visible Perimeter: %.1f px', ...
            damage_metric.damaged_edge_length_px, damage_metric.total_perimeter_px);
        lines{end+1} = sprintf('Note Surface Area Loss: %.2f%%', damage_metric.note_area_damage_pct);
    end
    if ~isempty(edge_analysis) && edge_analysis.is_valid
        lines{end+1} = '--- Individual Edge Measurements ---';
        for i = 1:length(edge_analysis.edges)
            e = edge_analysis.edges(i);
            lines{end+1} = sprintf('  [%s Edge] Status: %-7s | Damaged: %5.1f px | Max Depth: %4.1f px | Defects: %d', ...
                e.name, e.status, e.damaged_length, e.max_defect_depth, e.defect_count);
        end
    end
    viz_data.summary_text = strjoin(lines, newline);
end

%% Helper: Draw line between two points
function img = draw_line_safe(img, p1, p2, color_rgb, is_dashed)
    [h, w, ~] = size(img);
    dist = norm(p2 - p1);
    n_steps = max(2, round(dist * 1.5));
    xs = round(linspace(p1(1), p2(1), n_steps));
    ys = round(linspace(p1(2), p2(2), n_steps));

    col = uint8(color_rgb);
    for k = 1:n_steps
        if is_dashed && mod(floor(k / 6), 2) == 1
            continue;
        end
        x = xs(k); y = ys(k);
        if y >= 1 && y <= h && x >= 1 && x <= w
            img(y, x, :) = col;
            % 2px thickness
            if y < h, img(y+1, x, :) = col; end
            if x < w, img(y, x+1, :) = col; end
        end
    end
end

%% Helper: Draw filled circle with border
function img = draw_circle_safe(img, cx, cy, radius, fill_col, border_col)
    [h, w, ~] = size(img);
    for dy = -radius:radius
        for dx = -radius:radius
            d2 = dx^2 + dy^2;
            if d2 <= radius^2
                ny = cy + dy; nx = cx + dx;
                if ny >= 1 && ny <= h && nx >= 1 && nx <= w
                    if d2 >= (radius - 1)^2
                        img(ny, nx, :) = uint8(border_col);
                    else
                        img(ny, nx, :) = uint8(fill_col);
                    end
                end
            end
        end
    end
end

%% Helper: Annotate top banner onto panel
function panel = annotate_panel(panel_img, title_str)
    panel = panel_img;
    [h, w, ~] = size(panel);
    banner_h = 28;
    
    % Draw dark header bar at top
    panel(1:banner_h, :, 1) = 28;
    panel(1:banner_h, :, 2) = 32;
    panel(1:banner_h, :, 3) = 40;
    
    % Draw separator line
    panel(banner_h, :, 1) = 80;
    panel(banner_h, :, 2) = 140;
    panel(banner_h, :, 3) = 220;

    % Simple 5x7 bitmap font rendering for banner text (pure MATLAB)
    panel = render_ascii_text(panel, 12, 8, title_str, [240, 245, 255]);
end

%% Helper: Minimal embedded ASCII font renderer (pure MATLAB)
function img = render_ascii_text(img, start_x, start_y, txt, color_rgb)
    [h, w, ~] = size(img);
    col = uint8(color_rgb);
    curr_x = start_x;

    % Simple 5x7 font pattern definitions for key ASCII characters
    for i = 1:length(txt)
        ch = txt(i);
        glyph = get_char_glyph(ch);
        [gh, gw] = size(glyph);
        
        for gy = 1:gh
            for gx = 1:gw
                if glyph(gy, gx)
                    px = curr_x + gx; py = start_y + gy;
                    if py >= 1 && py <= h && px >= 1 && px <= w
                        img(py, px, :) = col;
                    end
                end
            end
        end
        curr_x = curr_x + gw + 2;
        if curr_x >= w - 10, break; end
    end
end

function g = get_char_glyph(c)
    % 5x7 binary character bitmaps
    switch c
        case '1', g = [0 1 0; 1 1 0; 0 1 0; 0 1 0; 0 1 0; 0 1 0; 1 1 1];
        case '2', g = [1 1 1; 0 0 1; 0 0 1; 1 1 1; 1 0 0; 1 0 0; 1 1 1];
        case '3', g = [1 1 1; 0 0 1; 0 0 1; 1 1 1; 0 0 1; 0 0 1; 1 1 1];
        case '4', g = [1 0 1; 1 0 1; 1 0 1; 1 1 1; 0 0 1; 0 0 1; 0 0 1];
        case 'O', g = [0 1 1 0; 1 0 0 1; 1 0 0 1; 1 0 0 1; 1 0 0 1; 1 0 0 1; 0 1 1 0];
        case 'G', g = [0 1 1 1; 1 0 0 0; 1 0 0 0; 1 0 1 1; 1 0 0 1; 1 0 0 1; 0 1 1 0];
        case 'T', g = [1 1 1 1 1; 0 0 1 0 0; 0 0 1 0 0; 0 0 1 0 0; 0 0 1 0 0; 0 0 1 0 0; 0 0 1 0 0];
        case 'F', g = [1 1 1 1; 1 0 0 0; 1 1 1 0; 1 0 0 0; 1 0 0 0; 1 0 0 0; 1 0 0 0];
        case 'B', g = [1 1 1 0; 1 0 0 1; 1 1 1 0; 1 0 0 1; 1 0 0 1; 1 0 0 1; 1 1 1 0];
        case '.', g = [0; 0; 0; 0; 0; 1; 1];
        case '%', g = [1 0 1; 0 0 1; 0 1 0; 1 0 0; 1 0 1; 0 0 0; 0 0 0];
        case ':', g = [0; 1; 0; 0; 1; 0; 0];
        case '-', g = [0 0 0; 0 0 0; 0 0 0; 1 1 1; 0 0 0; 0 0 0; 0 0 0];
        case '(', g = [0 1; 1 0; 1 0; 1 0; 1 0; 1 0; 0 1];
        case ')', g = [1 0; 0 1; 0 1; 0 1; 0 1; 0 1; 1 0];
        case ' ', g = zeros(7, 3);
        otherwise
            % Generic fallback character box
            g = [1 1 1 1; 1 0 0 1; 1 0 0 1; 1 0 0 1; 1 0 0 1; 1 0 0 1; 1 1 1 1];
    end
end
