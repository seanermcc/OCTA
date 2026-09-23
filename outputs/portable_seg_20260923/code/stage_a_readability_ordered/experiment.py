"""Bounded dev-only readability experiment. Run via the dated access guard."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import random
import time
import numpy as np
import torch
from eight_surface.labels import load_label
from eight_surface.config import SURFACE_NAMES, LAYER_DEFS
from stage_a.common import DEFAULT, OUT, output_dir, write_json, write_csv, fingerprint, verify, digest
from stage_a.data import Dataset
from stage_a.model import decode
from stage_a.train import load_checkpoint
from .readability import ReadabilityUNet, ReadabilityHead, readability_targets, masked_readability_loss
from .ordered import decode_ordered, gated_raw, crossing_flags, REASONS
from stage_a_readability import _column_features

RUN = OUT / 'stage_a/20260908_v5_readability_ordered'
BASE = OUT / 'stage_a/20260908_v4_longtrain'
CHECKPOINT = BASE / 'dev_seed20260908/best.pt'
SEED = 20260909
GRID = [.50, .70, .80, .85, .90, .95, .98, .99, 1.]


def read_npz(path):
    with np.load(path, allow_pickle=False) as data:
        return {k: data[k] for k in data.files}


def old_inventory():
    # Metadata only for old artifacts, including locked data; never open their contents.
    roots = [OUT / 'stage_a' / n for n in ('20260908_v2', '20260908_v3_readability', '20260908_v4_longtrain')]
    return {str(p): [p.stat().st_size, p.stat().st_mtime_ns]
            for root in roots for p in root.rglob('*') if p.is_file()}


def prepare():
    output_dir(RUN)
    if (RUN / 'prepared.json').exists():
        raise FileExistsError('Prepared experiment already exists')
    write_json(RUN / 'old_inventory_before.json', old_inventory())
    datasets = {s: Dataset(DEFAULT, s, eligible_only=False) for s in ('train', 'validation')}
    records = [dict(r, split=s) for s, data in datasets.items() for r in data.records]
    backbone, ck = load_checkpoint(CHECKPOINT, 'cuda')
    assert ck['epoch'] == 124 and ck['identity'] == datasets['train'].identity
    model = ReadabilityUNet(backbone).cuda().eval()
    audits, slopes, entropies, simple_train = [], [[] for _ in range(8)], [[] for _ in range(8)], []
    features_dir = output_dir(RUN / 'cache')
    output_dir(RUN / 'logits_validation')
    protected = [fingerprint(DEFAULT / n) for n in ('manifest.json', 'partitions.json', 'cache_manifest.json')]
    protected.append(fingerprint(CHECKPOINT))
    for index, r in enumerate(records):
        data = datasets[r['split']]
        entry = data.cache['entries'][r['key']]
        verify(r['label'])
        protected.extend([r['label'], r['targets_fingerprint'], entry['file']])
        human = load_label(r['label']['path'])
        target = read_npz(r['targets'])
        cached = read_npz(entry['file']['path'])
        rt, rw, rs = readability_targets(human, target['valid'])
        strict, _, _ = readability_targets(human, target['valid'], 'strict')
        assert np.array_equal(human['region_excluded'], (target['reason_bits'] & 32).any(0))
        offset = entry['label_offset']
        image = torch.from_numpy(cached['x']).unsqueeze(0).cuda()
        with torch.no_grad():
            logits, _, features = model.extract(image)
            rows, entropy = decode(logits)
        raw, entropy = rows[0].cpu().numpy(), entropy[0].cpu().numpy()
        # Exact same old computation and old scope/shadow/crossing reasons.
        baseline_path = (BASE / ('eval_train' if r['split'] == 'train' else 'dev_seed20260908/eval_validation') / (r['key'] + '.npz'))
        old = read_npz(baseline_path)
        current = gated_raw(raw, target['scope'], target['shadow'])
        if not np.array_equal(raw - offset, old['rows']) or not np.array_equal(entropy, old['entropy']) or not np.array_equal(current['reason_bits'], old['reason_bits']):
            raise AssertionError('Epoch-124 reproduction changed: ' + r['key'])
        band = data.manifest['sources'][r['scan_id']]['label_band']
        signal = _column_features(cached['x'][0], offset, offset + band[1] - band[0])
        simple = np.column_stack([entropy.mean(0), entropy.max(0), signal[:, 8], signal[:, 5]])
        np.savez_compressed(features_dir / (r['key'] + '.npz'), features=features[0].cpu().numpy(),
            raw_rows=raw, entropy=entropy, readability_target=rt, readability_weight=rw,
            readability_source=rs, simple_features=simple, x=cached['x'], truth=cached['rows'],
            valid=cached['valid'], scope=target['scope'], shadow=target['shadow'],
            human_excluded=human['region_excluded'], label_offset=np.array(offset),
            vitreous_high=cached['vitreous_high'], target_reason_bits=target['reason_bits'])
        if r['split'] == 'validation':
            np.save(RUN / 'logits_validation' / (r['key'] + '.npy'), logits[0].cpu().numpy())
        else:
            simple_train.append(simple)
            for k in range(8):
                v = cached['valid'][k]
                adjacent = v[1:] & v[:-1]
                slopes[k].extend(abs(np.diff(cached['rows'][k]))[adjacent].tolist())
                entropies[k].extend(entropy[k, v].tolist())
        audits.append(dict(key=r['key'], split=r['split'], animal=r['animal'], verdict=r['verdict'],
            qc_group=r['qc_group'], scope_status=r['scope_status'], format=human['label_format_version'],
            local_provenance=human['local_provenance_available'], seconds_active=human['seconds_active'],
            n_strokes=human['n_strokes'], weak_positive=int((rs == 3).sum()), strong_positive=int((rs == 2).sum()),
            explicit_negative=int((rt == 0).sum()), unknown=int((rt < 0).sum()),
            strict_positive=int((strict == 1).sum()), supported_surface_columns=int(cached['valid'].sum()),
            total_columns=len(rt)))
        print(f'prepare {index+1}/{len(records)} {r["key"]}', flush=True)
    simple_train = np.concatenate(simple_train).astype(float)
    measured = [dict(surface=name, n_adjacent=len(s), slope_median=float(np.median(s)),
        slope_p95=float(np.quantile(s, .95)), slope_p99=float(np.quantile(s, .99)),
        slope_max=float(np.max(s)), n_entropy=len(e), entropy_p995=float(np.quantile(e, .995)))
        for name, s, e in zip(SURFACE_NAMES, slopes, entropies)]
    config = dict(entropy_cap=[row['entropy_p995'] for row in measured],
        continuity_scale_px=[max(2., row['slope_p99']) for row in measured],
        continuity_weight=.15, continuity_truncation=4., max_log_drop=float(np.log(20)), gap_px=1,
        sweeps='one forward and one backward; coordinate descent; no global optimality claim')
    plan = dict(seed=SEED, epochs=40, steps_per_epoch=48, optimizer='AdamW', lr=.0003, weight_decay=.0001,
        batch_size=1, gradient_clip=5., head_hidden=32, input_channels=160,
        sampling='uniform training animal with known columns, then uniform known-label B-scan',
        augmentation='horizontal flip of cached features and readability targets together',
        loss='known-column class-macro BCE; explicit exclusion weight 1; legacy positive proxy weight .25; unknown 0',
        loss_weights=dict(readability=1., boundary_update=0., region_update=0.),
        selection='minimum animal-macro validation readability loss over fixed 40 epochs; earliest exact tie',
        initialization='all epoch-124 boundary-model parameters copied and FROZEN; only 1-D context head new',
        decision='no extension and no hyperparameter search',
        display_coverage=.95, coverage_grid=GRID, threshold='training positive-proxy quantiles only; no production threshold',
        decoder=config, simple_mean=simple_train.mean(0).tolist(), simple_sd=(simple_train.std(0)+1e-9).tolist(),
        experimental=True, validated=False)
    write_json(RUN / 'PRESPECIFIED_PLAN.json', plan)
    write_csv(RUN / 'annotation_audit.csv', audits)
    write_csv(RUN / 'continuity_measurements_train.csv', measured)
    write_json(RUN / 'protected_fingerprints.json', protected)
    write_json(RUN / 'prepared.json', dict(records=records, identity=datasets['train'].identity,
        checkpoint=fingerprint(CHECKPOINT), formats=dict(Counter(r['format'] for r in audits)),
        plan_sha256=fingerprint(RUN / 'PRESPECIFIED_PLAN.json'), baseline_exact_bscans=len(records),
        scientific_versions=dict(torch=torch.__version__, numpy=np.__version__),
        totals={s: {k: sum(r[k] for r in audits if r['split'] == s)
            for k in ('weak_positive','strong_positive','explicit_negative','unknown','strict_positive','supported_surface_columns','total_columns')}
            for s in datasets}))


def train():
    if (RUN / 'head_last.pt').exists():
        raise FileExistsError('Completed training preserved; choose a new experiment')
    prepared = json.loads((RUN / 'prepared.json').read_text())
    plan = json.loads((RUN / 'PRESPECIFIED_PLAN.json').read_text())
    verify(prepared['plan_sha256'])
    torch.manual_seed(plan['seed']); random.seed(plan['seed']); np.random.seed(plan['seed'])
    torch.cuda.manual_seed_all(plan['seed'])
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    head = ReadabilityHead(plan['input_channels'], plan['head_hidden']).cuda()
    optimizer = torch.optim.AdamW(head.parameters(), lr=plan['lr'], weight_decay=plan['weight_decay'])
    by_split = defaultdict(list)
    for r in prepared['records']:
        d = read_npz(RUN / 'cache' / (r['key']+'.npz'))
        if not (d['readability_target'] >= 0).any():
            continue
        item = dict(record=r, **{k: torch.from_numpy(d[k]).unsqueeze(0).cuda()
                    for k in ('features','readability_target','readability_weight')})
        by_split[r['split']].append(item)
    groups = defaultdict(list)
    for item in by_split['train']:
        groups[item['record']['animal']].append(item)
    animals = sorted(groups)
    def loss(item, flip=False):
        f, y, w = [item[k] for k in ('features','readability_target','readability_weight')]
        if flip:
            f, y, w = [t.flip(-1) for t in (f,y,w)]
        return masked_readability_loss(head(f), y, w)
    best, history, events = float('inf'), [], []
    start = time.monotonic()
    for epoch in range(1, plan['epochs']+1):
        head.train(); sampled=[]
        for _ in range(plan['steps_per_epoch']):
            animal = random.choice(animals); item = random.choice(groups[animal])
            optimizer.zero_grad(set_to_none=True)
            value = loss(item, random.random() < .5)
            if not torch.isfinite(value):
                raise FloatingPointError('Nonfinite readability loss')
            value.backward()
            if not all(torch.isfinite(p.grad).all() for p in head.parameters() if p.grad is not None):
                raise FloatingPointError('Nonfinite head gradient')
            grad = float(torch.nn.utils.clip_grad_norm_(head.parameters(), plan['gradient_clip']))
            if grad <= 0:
                raise ValueError('No head gradients')
            optimizer.step(); sampled.append(float(value.detach()))
            events.append(dict(step=len(events)+1, epoch=epoch, animal=animal,
                key=item['record']['key'], loss=sampled[-1], gradient_norm=grad))
        head.eval(); validation=defaultdict(list); training=defaultdict(list)
        with torch.no_grad():
            for name, dest in [('train',training),('validation',validation)]:
                for item in by_split[name]:
                    dest[item['record']['animal']].append(float(loss(item)))
        macro = lambda d: float(np.mean([np.mean(v) for v in d.values()]))
        v = macro(validation)
        row = dict(epoch=epoch, step=len(events), sampled_training_loss=float(np.mean(sampled)),
            train_macro_loss=macro(training), validation_macro_loss=v,
            validation_by_animal={a:float(np.mean(vals)) for a,vals in validation.items()})
        history.append(row)
        state = dict(head=head.state_dict(), optimizer=optimizer.state_dict(), epoch=epoch, step=len(events),
            validation_macro_loss=v, config=plan, source_checkpoint=prepared['checkpoint'],
            identity=prepared['identity'], experimental=True, validated=False)
        if v < best:
            best = v; torch.save(state, RUN / 'head_best.pt')
        torch.save(state, RUN / 'head_last.pt')
        write_json(RUN / 'training_history.json', history)
        print(json.dumps(row), flush=True)
    torch.save(head.state_dict(), RUN / 'head_roundtrip.pt')
    restored = ReadabilityHead(plan['input_channels'], plan['head_hidden']).cuda().eval()
    restored.load_state_dict(torch.load(RUN / 'head_roundtrip.pt', weights_only=True))
    with torch.no_grad():
        f=by_split['train'][0]['features']
        assert torch.equal(head(f), restored(f))
    write_csv(RUN / 'training_steps.csv', events)
    write_json(RUN / 'training_complete.json', dict(seconds=time.monotonic()-start, steps=len(events),
        epochs=len(history), best_epoch=min(history, key=lambda r:r['validation_macro_loss'])['epoch'],
        best_loss=best, head_parameters=sum(p.numel() for p in head.parameters()),
        checkpoint_roundtrip_exact=True, boundary_parameters_updated=0,
        peak_cuda_bytes=torch.cuda.max_memory_allocated(), plan_unchanged=fingerprint(RUN/'PRESPECIFIED_PLAN.json')==prepared['plan_sha256']))


def scores(prepared, plan):
    ck = torch.load(RUN / 'head_best.pt', map_location='cpu', weights_only=True)
    head = ReadabilityHead(plan['input_channels'], plan['head_hidden']).cuda().eval()
    head.load_state_dict(ck['head'])
    values = {}
    for r in prepared['records']:
        d = read_npz(RUN / 'cache' / (r['key']+'.npz'))
        with torch.no_grad():
            readable = head(torch.from_numpy(d['features']).unsqueeze(0).cuda()).sigmoid()[0].cpu().numpy()
        z = (d['simple_features']-np.asarray(plan['simple_mean']))/np.asarray(plan['simple_sd'])
        simple = z[:,0]+z[:,1]-z[:,2]+z[:,3]
        values[r['key']] = dict(data=d, learned=1.-readable, simple=simple)
    return values


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','train','evaluate','verify'])
    args=parser.parse_args(); torch.set_num_threads(4)
    if args.action == 'prepare': prepare()
    elif args.action == 'train': train()
    elif args.action == 'evaluate':
        from .evaluate import run
        run()
    else:
        prepared=json.loads((RUN/'prepared.json').read_text())
        protected=json.loads((RUN/'protected_fingerprints.json').read_text())
        for fp in protected: verify(fp)
        before=json.loads((RUN/'old_inventory_before.json').read_text())
        after=old_inventory()
        changed=[p for p,st in before.items() if after.get(p)!=st]
        if changed: raise AssertionError(changed)
        write_json(RUN/'integrity_complete.json',dict(allowed_fingerprints_verified=len(protected),
            old_artifacts_unchanged=len(before), old_artifacts_added=len(set(after)-set(before)),
            original_checkpoint_unchanged=fingerprint(CHECKPOINT)==prepared['checkpoint'],
            locked_contents_hashed=False, final_test_data_read=False, repeatability_data_read=False,
            human_labels_written=False, frozen_definitions_modified=False))


if __name__ == '__main__': main()
