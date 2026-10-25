function cfg = config()
% CONFIG - Central configuration parameters for Currency Note Edge Inspection
%
% This function returns a structured configuration object containing all
% adjustable thresholds, morphological parameters, edge tolerance settings,
% and classification rules used throughout the image processing pipeline.
%
% Usage:
%   cfg = config();
%
% All parameters are documented with units and recommended tuning ranges.

    cfg = struct();

    %% 1. Preprocessing Parameters
    % Target width to which notes are normalized while preserving aspect ratio.
    % 800px provides an optimal balance between edge precision and computational speed on modest hardware.
    cfg.preproc.target_width = 800;
    
    % Gaussian smoothing filter standard deviation (pixels).
    % Suppresses high-frequency sensor noise without blurring structural edges.
    cfg.preproc.denoise_sigma = 1.2;
    
    % Kernel size for Gaussian filter (odd integer).
    cfg.preproc.filter_kernel_size = 5;
    
    % Enable adaptive contrast enhancement (imadjust / histogram stretching).
    cfg.preproc.enable_contrast_enhancement = true;
    
    % Saturation limits for contrast adjustment [low_in, high_in].
    cfg.preproc.contrast_stretch_limits = [0.03, 0.97];

    %% 2. Boundary and Note Detection Parameters
    % Method for segmentation: 'otsu' (global optimal) or 'adaptive'
    cfg.boundary.binarize_method = 'otsu';
    
    % Multiplier for Otsu threshold (values < 1.0 make segmentation more sensitive to dark notes)
    cfg.boundary.threshold_multiplier = 0.95;
    
    % Minimum ratio of note area to overall image area.
    % Prevents picking up small background artifacts.
    cfg.boundary.min_note_area_ratio = 0.12;
    
    % Maximum ratio of note area to overall image area.
    % If note exceeds 98%, image is likely uniform or cropped too tightly.
    cfg.boundary.max_note_area_ratio = 0.96;
    
    % Structuring element radius for morphological closing (bridges currency ink gaps)
    cfg.boundary.morph_close_radius = 5;
    
    % Structuring element radius for morphological opening (removes small detached noise)
    cfg.boundary.morph_open_radius = 3;
    
    % Minimum boundary confidence (0.0 to 1.0) required for automated processing
    cfg.boundary.min_confidence_threshold = 0.55;

    %% 3. Edge Analysis Parameters
    % Orthogonal deviation tolerance (pixels).
    % Deviations smaller than this are considered natural currency paper roughness.
    cfg.edge.defect_tolerance_px = 4.0;
    
    % Minimum defect depth (pixels) to qualify as an intentional tear or notch.
    cfg.edge.tear_depth_threshold_px = 7.0;
    
    % Minimum continuous defect span along edge (pixels) to ignore point noise.
    cfg.edge.min_defect_length_px = 10.0;
    
    % Sampling step (pixels) along the perimeter contour.
    cfg.edge.contour_sample_step = 2;

    %% 4. Classification Rules & Thresholds
    % Maximum edge damage percentage to qualify as 'Good'
    cfg.classify.good_max_damage_pct = 2.0;
    
    % Minimum edge damage percentage to classify as 'Torn'
    cfg.classify.torn_min_damage_pct = 2.0;
    
    % Minimum individual defect depth (px) that triggers 'Torn' classification
    cfg.classify.torn_min_defect_depth_px = 8.0;
    
    % Fold detection: Minimum directional gradient contrast for crease line
    cfg.classify.fold_gradient_threshold = 28.0;
    
    % Fold detection: Minimum span of crease across note dimension (50%)
    cfg.classify.fold_min_length_ratio = 0.48;
    
    % Old/Worn detection: High-frequency texture roughness threshold (std deviation of gradient)
    cfg.classify.worn_roughness_threshold = 17.5;
    
    % Old/Worn detection: Contrast fading index threshold (lower dynamic range across body)
    cfg.classify.worn_contrast_fade_threshold = 0.42;

    %% 5. Visualization Settings
    % Defect highlight overlay color in RGB [Red, Green, Blue] normalized (0 to 1)
    cfg.viz.defect_overlay_color = [1.0, 0.15, 0.15]; % Vivid red
    
    % Intact edge color in RGB normalized
    cfg.viz.intact_edge_color = [0.15, 0.85, 0.25]; % Green
    
    % Detected corners highlight color in RGB
    cfg.viz.corner_color = [0.0, 0.85, 1.0]; % Cyan
    
    % Alpha transparency for overlay (0.0 transparent, 1.0 fully opaque)
    cfg.viz.overlay_alpha = 0.45;
    
    % Line width for drawing boundary overlays
    cfg.viz.boundary_line_width = 3;

    %% 6. File & Directory Paths
    cfg.paths.dataset_dir = 'dataset';
    cfg.paths.results_dir = 'results';
    cfg.paths.overlays_dir = fullfile(cfg.paths.results_dir, 'overlays');
    cfg.paths.masks_dir = fullfile(cfg.paths.results_dir, 'masks');
    cfg.paths.boundaries_dir = fullfile(cfg.paths.results_dir, 'boundaries');
    cfg.paths.reports_dir = fullfile(cfg.paths.results_dir, 'reports');
    cfg.paths.summary_csv = fullfile(cfg.paths.results_dir, 'summary.csv');

end
