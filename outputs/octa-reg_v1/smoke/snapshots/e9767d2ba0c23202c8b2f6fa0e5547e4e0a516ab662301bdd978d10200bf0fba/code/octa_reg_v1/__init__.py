"""Frozen vessel-supported registration experiment. No CNV or layer inputs."""
from control_map_v1 import DEFAULTS as LEGACY_DEFAULTS

VERSION = 'octa-reg_v1'
CONFIG = {k: v for k, v in LEGACY_DEFAULTS.items() if k.startswith(('registration_', 'onh_', 'convergence_', 'branch_')) and 'buffer' not in k}
CONFIG.update(seed=1701, bootstrap_samples=100, cnv_mode='off', cnv_snapshot=None,
              field_um=1460., workers=2, feature_proximity_um=35.,
              orb_n_keypoints=1200, orb_fast_threshold=.04,
              descriptor_exclusion_dilation_pixels=20, descriptor_patch_pixels=31,
              descriptor_max_ratio=.75, ransac_min_samples=3, ransac_max_trials=1500,
              intensity_percentiles=[2, 98], junction_radius_um=30.,
              junction_dilation_pixels=2, cycle_limit_um=45.,
              coordinate_convention='pixel centers: x=A-line*dx, y=B-scan*dy; x right, y down',
              anatomical_directions='unknown', transform_model='physical rigid',
              preprocessing='nonfinite + explicit exclusions/uncertainty + assessable reviewed ONH interior')
