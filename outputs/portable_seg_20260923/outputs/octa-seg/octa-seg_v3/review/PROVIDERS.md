# Review provider contract 1

The read-only adapter is `code/octa_seg_v3/providers.py`. Existing v1/v2 native canonical image/prediction caches remain supported. The current supported anatomy is **5-8surf-pr**, including the photoreceptor composite and outer-RPE meaning. Different anatomy is never matched by boundary index. `ANATOMY` specifies names, definitions, order and named thickness endpoints; manifests must equal this validated definition. Extending to a genuinely different anatomical convention requires a new validated adapter.

## Publish a compatible release

Place `review_provider.json` directly in a release folder under project `outputs`, `outputs/octa-seg`, or `review/providers`. Publish data first, manifest second, and `REVIEW_PROVIDER_COMPLETE.json` **last**, atomically. The completion file contains `manifest_sha256`, the SHA-256 of the exact manifest bytes. Until this marker matches, the release is not eligible.

Required manifest fields:

* `format`: `octa-review-provider-1`; `status`: `complete`.
* `version`, `checkpoint_identity`, `provenance`, and `state_availability` (explicitly describe unavailable state outputs).
* `kind`: `context` or `surfaces`; `scans`: per-scan records.
* Each scan carries `scan_id`, original `source_volume`, `shape` `[native B-scans, native A-lines]`, `axis_order` `B-scan,A-line`, `orientation` `native-enface;vitreous-at-depth-zero`, `crop_offset` in full canonical depth, `retina_band` in the source convention, and `spacing_um` `[B-scan, A-line, depth]`. Current spacing is `[1460/NB, 1460/NX, 1.12]`.

### Context masks

Each scan adds a relative `file` path and its exact `sha256`. The NPZ contains native boolean masks; no transpose, resizing or shift is inferred. Manifest `masks` entries each contain `name`, `definition`, `array`:

| name | exact definition |
|---|---|
| cnv | CNV enface footprint |
| vessel | major vessel enface footprint |
| onh | optic nerve head enface footprint |

Missing optional masks are allowed. Every supplied mask is validated before that scan's context is installed. Human drafts/uncertainty/absence and saved masks take precedence. Provider version/hash and contextual exposure remain separate from layer model inputs. Filesystem checks are polled every 10 seconds, debounced by 750 ms; app activation and manual Refresh also refresh context. A rejected provider is described in the context status.

### Surface releases

Set `adapter` to `octa-measurements-cache-1` and `anatomy` to the exact `ANATOMY` object exported by `providers.py`. Each scan adds `directory` and `sha256` entries for `prepared.json`, `geometry.npz`, and `measurements.npz`. The cache schema is the existing v1/v2 native schema:

* `prepared.json`: `scan_id`, `images` path to canonical `[B-scan, depth, A-line]` NPY, explicit fresh-orientation provenance, and original `source` identity.
* `geometry.npz`: `label_offset` and `retina_band`.
* `measurements.npz`: `raw_position_branch` `[B-scan,boundary,A-line]`; `probabilities` `[B-scan,boundary,2,A-line]`; `entropy`; native `vessel` and `shadow`; `label_offset`; exact `surface_names`.

New unreviewed cases select completed compatible entries. A saved case resolves its recorded provider before loading and checks model identity, including prediction and calibration hashes. Frozen shared queues do the same. There is no automatic or implicit adoption of new predictions into saved human work.

## Existing integrations and limits

* Existing vessel proposals: established `load_enface` / vessel proposal loader, with saved human work taking precedence.
* Automatic ONH: the actual completed `outputs/octo-vessel_onh_v2` schema was inspected. Its final marker, per-scan record, source/native shape/retina band, prediction hash, model hash and NPZ scan identity are validated. Three real scans exercised the adapter. It is opt-in experimental context because the release reports false ONH detections and explicitly declines promotion over frozen v1.
* Final v9 CNV context: `cnv_context.py` reads `octa-auto_cnv_v9/final_correction/dataset/manifest.json`, validates acquisition/source/native geometry against the v9 Model 3 acquisition index, and verifies confirmed target hashes, scan IDs, axes and known/ignored pixels. Live `final_correction/review/regions/<scan_id>.json` saves supersede exports, including drafts and explicit absence; unsure/excluded pixels are not pink CNV. Pending acquisitions use their exact selected assessment reference with pending status, while deferred/poor-image cases suppress old CNV footprints. Invalid current sources suppress stale CNV and report the error. Manifest, current correction and target changes participate in automatic refresh. This is read-only display context, separate from manual B-scan lesion labels.
* Older saved CNV region records: v5, then v4, then v3, for scans outside the final v9 dataset. Native row intervals, source identity and revision are validated. Rejected regions are omitted; retained drafts/uncertainty remain explicitly identified as saved context, not approved labels.
* The independent CNV U-Net v6 workflow does not publish this review-provider contract. It is **not silently imported**. Its publisher can emit the sealed context manifest above without changing this GUI. The generic adapter was exercised with compatible, incomplete and incompatible synthetic releases.

All providers are read-only. Optional context never changes frozen layer predictions, existing annotations, review assignments or training roles.
