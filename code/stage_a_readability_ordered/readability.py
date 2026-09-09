"""Experimental whole-column head; never supplies boundary-position targets.

Legacy positives are explicitly weak review proxies, not recovered local strokes.
The strict policy is available to expose the absence of local positive evidence.
"""
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from eight_surface.config import CASCADE_VERSION


def readability_targets(record, valid, legacy_policy="review_proxy"):
    if legacy_policy not in ("review_proxy", "strict"):
        raise ValueError("Unknown legacy readability policy")
    valid = np.asarray(valid, bool)
    if valid.ndim != 2 or valid.shape[0] != 8:
        raise ValueError("Expected eight boundary masks")
    width = valid.shape[1]
    excluded = np.asarray(record["region_excluded"], bool)
    if excluded.shape != (width,):
        raise ValueError("Readability width mismatch")
    # -1 unknown, 0 explicit unusable, 1 reviewed usable proxy.
    target = np.full(width, -1, np.int8)
    weight = np.zeros(width, np.float32)
    source = np.zeros(width, np.uint8)  # 0 unknown, 1 explicit exclusion, 2 local, 3 legacy proxy
    if record.get("cascade_version") != CASCADE_VERSION:
        return target, weight, source
    positive = np.zeros(width, bool)
    if record.get("local_provenance_available", False):
        # Local 'no' never becomes a whole-column negative. Defaults are unknown.
        from eight_surface.provenance import record_visibility, record_reliability, MARK_YES
        vis, rel = record_visibility(record), record_reliability(record)
        positive = (vis == MARK_YES).all(0) & (rel == MARK_YES).all(0)
        positive &= record["verdict"] in ("accepted", "corrected")
        positive &= valid.all(0)  # retain scope/finite/position eligibility safeguards
        target[positive], weight[positive], source[positive] = 1, 1., 2
    elif legacy_policy == "review_proxy":
        # Multiple independent whole-surface corrections and substantive review
        # support a WEAK image-readability proxy. They do not certify local drawing.
        substantive = (record["verdict"] == "corrected"
                       and record.get("seconds_active", 0) >= 30
                       and record.get("n_strokes", 0) >= 8)
        flags = (np.asarray(record["surface_edited"], bool)
                 & np.asarray(record["surface_visible"], bool)
                 & np.asarray(record["surface_reliable"], bool)
                 & ~np.asarray(record["surface_displaced"], bool))
        positive = valid.all(0) & substantive & flags.all()
        target[positive], weight[positive], source[positive] = 1, .25, 3
    # Explicit exclusions are valid evidence regardless of B-scan verdict.
    # Absence of a mark, rejection, shadow, scope and missing labels are NOT negatives.
    target[excluded], weight[excluded], source[excluded] = 0, 1., 1
    return target, weight, source


def masked_readability_loss(logits, target, weight):
    """Class-macro BCE on known columns, with legacy positive reliability=.25.

    Unknowns produce exactly zero gradient. Class means avoid majority-class
    domination; a class absent in an image is omitted, never synthesized.
    """
    if logits.shape != target.shape or logits.shape != weight.shape:
        raise ValueError("Readability loss shape mismatch")
    known = target >= 0
    if not known.any():
        return logits.sum() * 0
    clean = torch.where(known, target, torch.zeros_like(target)).float()
    ce = F.binary_cross_entropy_with_logits(logits, clean, reduction="none")
    terms = [(ce[target == c] * weight[target == c]).mean()
             for c in (0, 1) if (target == c).any()]
    return torch.stack(terms).mean()


class ReadabilityHead(nn.Module):
    """Depth-resolved image/decoder context, with a 57-column receptive field."""
    def __init__(self, channels=160, hidden=32):
        super().__init__()
        self.channels, self.hidden = channels, hidden
        self.net = nn.Sequential(nn.Conv1d(channels, hidden, 9, padding=4), nn.SiLU(),
            nn.Conv1d(hidden, hidden, 9, padding=8, dilation=2), nn.SiLU(),
            nn.Conv1d(hidden, hidden, 9, padding=16, dilation=4), nn.SiLU(),
            nn.Conv1d(hidden, 1, 1))

    def forward(self, features):
        return self.net(features)[:, 0]


class ReadabilityUNet(nn.Module):
    """Frozen epoch-124 encoder/decoder and both old heads; only new head learns.

    Pool 8 decoder channels into 16 axial bins and raw normalized intensity into
    32 bins. Depth profiles preserve vertical attenuation and normal dark bands;
    lateral convolutions see contrast/structural changes, not just darkness.
    """
    def __init__(self, boundary_model, head=None):
        super().__init__()
        self.backbone = boundary_model
        self.backbone.requires_grad_(False)
        self.head = head or ReadabilityHead(boundary_model.base * 16 + 32)

    def extract(self, image):
        with torch.no_grad():
            x, skips = image, []
            for encoder in self.backbone.enc:
                x = encoder(x)
                skips.append(x)
                x = F.avg_pool2d(x, 2)
            x = self.backbone.bridge(x)
            for decoder, skip in zip(self.backbone.dec, reversed(skips)):
                x = decoder(torch.cat([F.interpolate(x, size=skip.shape[-2:],
                    mode="bilinear", align_corners=False), skip], 1))
            width = image.shape[-1]
            features = torch.cat([F.adaptive_avg_pool2d(x, (16, width)).flatten(1, 2),
                F.adaptive_avg_pool2d(image, (32, width)).flatten(1, 2)], 1)
            return self.backbone.boundary(x), self.backbone.region(x), features

    def forward(self, image):
        boundaries, regions, features = self.extract(image)
        return boundaries, regions, self.head(features)


def load_readability_model(head_checkpoint, device="cpu"):
    """Restore the opt-in model, verifying the exact frozen boundary checkpoint.

    Returns logits and an uncalibrated readability score; no rejection threshold
    is automatically activated. The head checkpoint carries its source identity.
    """
    from stage_a.common import verify
    from stage_a.train import load_checkpoint
    ck = torch.load(head_checkpoint, map_location="cpu", weights_only=True)
    verify(ck["source_checkpoint"])
    backbone, original = load_checkpoint(ck["source_checkpoint"]["path"], device)
    if original["identity"] != ck["identity"]:
        raise ValueError("Boundary/head dataset identity mismatch")
    head = ReadabilityHead(ck["config"]["input_channels"], ck["config"]["head_hidden"])
    head.load_state_dict(ck["head"])
    model = ReadabilityUNet(backbone, head).to(device).eval()
    return model, ck
