function damage_metric = calculate_damage_percentage(edge_analysis, boundary_data, cfg)
% CALCULATE_DAMAGE_PERCENTAGE - Step 6: Edge Damage Metric Computation
%
% Precisely computes the percentage of the banknote's visible perimeter that is
% damaged, torn, or missing, according to the specified formula:
%
%   Edge damage percentage = (estimated damaged edge length / estimated total visible note perimeter) * 100
%
% Robustness features:
%   - Handles division-by-zero safely.
%   - If boundary detection failed or confidence is inadequate, returns 'Unable to estimate reliably'
%     rather than fabricating a false number.
%   - Distinguishes edge length damage from total 2D note surface area loss.
%   - Discloses clearly that results are algorithmic computer vision estimates.
%
% Syntax:
%   damage_metric = calculate_damage_percentage(edge_analysis, boundary_data, cfg)
%
% Inputs:
%   edge_analysis - Struct returned by analyze_note_edges.m.
%   boundary_data - Struct returned by detect_note_boundary.m.
%   cfg           - Configuration struct (from config.m).
%
% Outputs:
%   damage_metric struct with fields:
%     .is_reliable            - Boolean indicating if calculation is mathematically valid.
%     .damage_percentage      - Numeric value (0.0 to 100.0) or NaN if unreliable.
%     .display_text           - Formatted string for UI display (e.g., '14.25%' or 'Unable to estimate reliably').
%     .damaged_edge_length_px - Total measured damaged edge span (pixels).
%     .total_perimeter_px     - Total visible note perimeter (pixels).
%     .note_area_damage_pct   - Separate surface area loss percentage (distinguished from edge damage).
%     .per_edge_breakdown     - Struct containing Top, Right, Bottom, Left damage percentages.
%     .disclaimer             - Standard academic computer vision disclaimer.

    if nargin < 3 || isempty(cfg)
        cfg = config();
    end

    damage_metric = struct();
    damage_metric.is_reliable = false;
    damage_metric.damage_percentage = NaN;
    damage_metric.display_text = 'Unable to estimate reliably';
    damage_metric.damaged_edge_length_px = 0.0;
    damage_metric.total_perimeter_px = 0.0;
    damage_metric.note_area_damage_pct = 0.0;
    damage_metric.per_edge_breakdown = struct();
    damage_metric.disclaimer = 'Algorithmic estimate derived from 2D digital image processing. Not an official central bank grading standard or legal tender certification.';

    %% 1. Guard against failed or degenerate boundary
    if isempty(boundary_data) || strcmp(boundary_data.status, 'FAILED') || ...
       isempty(edge_analysis) || ~edge_analysis.is_valid
        return;
    end

    total_vis_perim = edge_analysis.total_visible_perimeter + edge_analysis.total_damaged_length;
    total_dam_len   = edge_analysis.total_damaged_length;

    % Division by zero protection
    if total_vis_perim <= 1e-4
        damage_metric.display_text = 'Unable to estimate reliably (Zero perimeter)';
        return;
    end

    %% 2. Calculate Edge Damage Percentage
    % Formula: (damaged_length / total_visible_perimeter) * 100
    raw_pct = (total_dam_len / total_vis_perim) * 100.0;
    clamped_pct = min(max(raw_pct, 0.0), 100.0);
    rounded_pct = round(clamped_pct, 2);

    damage_metric.is_reliable = true;
    damage_metric.damage_percentage = rounded_pct;
    damage_metric.display_text = sprintf('%.2f%%', rounded_pct);
    damage_metric.damaged_edge_length_px = round(total_dam_len, 1);
    damage_metric.total_perimeter_px = round(total_vis_perim, 1);

    %% 3. Separate 2D Note Area Loss Calculation
    % Distinguish perimeter damage from planar area damage to prevent user confusion
    if boundary_data.solidity > 0 && boundary_data.solidity <= 1.0
        area_loss = (1.0 - boundary_data.solidity) * 100.0;
        damage_metric.note_area_damage_pct = round(min(max(area_loss, 0.0), 100.0), 2);
    else
        damage_metric.note_area_damage_pct = 0.0;
    end

    %% 4. Per-Edge Breakdown
    breakdown = struct();
    for i = 1:length(edge_analysis.edges)
        e = edge_analysis.edges(i);
        e_nom = max(e.nominal_length, 1e-4);
        e_dam_pct = round((e.damaged_length / e_nom) * 100.0, 2);
        
        switch lower(e.name)
            case 'top',    breakdown.top_damage_pct = e_dam_pct;
            case 'right',  breakdown.right_damage_pct = e_dam_pct;
            case 'bottom', breakdown.bottom_damage_pct = e_dam_pct;
            case 'left',   breakdown.left_damage_pct = e_dam_pct;
        end
    end
    damage_metric.per_edge_breakdown = breakdown;

end
