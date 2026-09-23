"""Read-only preliminary ONH atlas; independent of segmentation and labels."""

VERSION = "control_map_v1.0"
LAYERS = [
    ["Full retina", "ILM", "RPE"], ["RNFL", "ILM", "RNFL_GCL"],
    ["GCL", "RNFL_GCL", "GCL_IPL"], ["IPL", "GCL_IPL", "IPL_INL"],
    ["INL", "IPL_INL", "INL_OPL"], ["OPL", "INL_OPL", "OPL_ONL"],
    ["Photoreceptor composite", "OPL_ONL", "PR_RPE"], ["RPE band", "PR_RPE", "RPE"],
]
CAVEAT = "Preliminary measurements. Image N/S/E/W = D*/V*/N*/T* provisionally; anatomy unconfirmed."

DEFAULTS = dict(
    schema=VERSION, scan_workers=2, field_um=1460., radial_band_um=250., angular_sector_deg=30.,
    grid_um=25., neighborhood_diameter_um=500., local_sigma_floor_um=1.12,
    normal_sigma=3., minimum_neighborhood_fraction=.5, candidate_sigma=4.5,
    candidate_min_area_um2=100., cnv_buffer_diameters=1., vessel_buffer_diameters=.5,
    onh_buffer_diameters=.5, onh_min_arc_deg=150., onh_max_residual_um=25.,
    onh_max_uncertainty_um=150., convergence_min_branches=3,
    branch_min_length_um=100., branch_max_curvature_ratio=.12,
    convergence_max_condition=20., registration_residual_um=15.,
    registration_min_matches=8, registration_min_branch_matches=3,
    registration_min_overlap=.15, registration_min_vessel_dice=.35,
    registration_min_structural_correlation=.25, bootstrap_samples=100, seed=1701,
    orientation=dict(image_north="D*", image_south="V*", image_east="N*", image_west="T*",
                     rotation_deg=0., provisional=True), calibration_overrides={},
)
