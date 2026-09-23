"""Human web-review decisions, isolated from frozen predictions and training labels."""
from common import *
import threading
from datetime import datetime, timezone

TARGET_POLICY = dict(
    schema='cnv-approved-outline-policy-v2',
    authority='User clarification: both outlines can be correct despite boundary variation; prefer Model 2 for a single shared target.',
    both_confirmed_meaning='both are acceptable; pixel-identical boundaries are not required',
    shared_target_priority=['m2_adjusted', 'm1'],
    eligibility='only explicitly confirmed masks; Model 2 correction flags withhold Model 2 eligibility',
    model_specific_targets='retain each model approval and mask separately for optional model-specific training',
    existing_records='apply this interpretation on read/export; preserve original decisions and immutable history',
    automatic_retraining=False)


def interpret_approval(record):
    """Apply current user-authorized target policy without rewriting a human record."""
    r = dict(record)
    m1 = bool(r['confirm_m1'])
    m2 = bool(r['confirm_m2_adjusted']) and not r['review_model2']
    models = r.get('prediction_contract', {}).get('models', {})
    different = bool(models) and models['m1']['mask_sha256'] != models['m2_adjusted']['mask_sha256']
    if r.get('needs_target_resolution'):
        r['historical_target_resolution_requirement_superseded'] = True
    r.update(interpretation_policy=TARGET_POLICY['schema'], needs_target_resolution=False,
             both_models_accepted=m1 and m2, accepted_outline_variation=m1 and m2 and different,
             preferred_shared_target_model='m2_adjusted' if m2 else 'm1' if m1 else None,
             model_specific_target_models={'m1': 'm1' if m1 else None,
                                          'm2': 'm2_adjusted' if m2 else None})
    return r


class ReviewConflict(ValueError):
    pass


class ReviewStore:
    def __init__(self, gallery, directory):
        self.gallery = Path(gallery)
        self.directory = dest(directory)
        self.data = read(self.gallery / 'data.json')
        self.cases = {a['scan_id']: a for a in self.data['cases']}
        self.lock = threading.RLock()

    def contract(self, sid):
        if sid not in self.cases:
            raise ValueError('Unknown acquisition')
        a = self.cases[sid]
        path = self.gallery / 'assets' / sid / 'candidates.json'
        candidates = read(path)
        models = {}
        for model, key in [('m1', 'm1'), ('m2_adjusted', 'm2')]:
            rows = candidates[key]
            if model == 'm2_adjusted':
                rows = [c for c in rows if c['display_selected']]
            mask = np.zeros((512, 512), bool)
            for c in rows:
                mask |= decode(c['runs'])
            models[model] = dict(candidate_ids=[c['id'] for c in rows],
                                 mask_sha256=hashlib.sha256(mask.tobytes()).hexdigest(),
                                 area_pixels=int(mask.sum()))
        contract = dict(selection_sha256=self.data['selection_sha256'],
                        scan_id=sid, source_identity=a.get('source_identity', 'synthetic'),
                        candidate_file=fingerprint(path), models=models,
                        predictions=a.get('status', []),
                        raw_pixel_threshold=self.data.get('raw_pixel_threshold', .7),
                        adjusted_candidate_threshold=self.data.get('adjusted_candidate_threshold', .5),
                        axis_order='B-scan,A-line', native_shape=[512, 512])
        # The token binds a human decision to the exact displayed prediction version.
        token_data = dict(scan_id=sid, source_identity=contract['source_identity'],
                          selection_sha256=contract['selection_sha256'],
                          candidates_sha256=contract['candidate_file']['sha256'], models=models,
                          thresholds=[contract['raw_pixel_threshold'],contract['adjusted_candidate_threshold']],
                          predictions=[(r['model'],r['prediction']['sha256'],r['checkpoint']['sha256']) for r in contract['predictions']])
        return contract, digest(token_data)

    def _head(self, sid, token):
        path = self.directory / 'decisions' / (sid + '.json')
        if not path.exists():
            return interpret_approval(dict(scan_id=sid, revision=0, confirm_m1=False,
                        confirm_m2_adjusted=False, review_model2=False, notes='', token=token))
        record = read(path)
        if record['token'] != token:
            raise ReviewConflict('Prediction version changed; existing decision requires explicit reconciliation')
        return interpret_approval(record)

    def all(self):
        with self.lock:
            records = {}
            for sid in self.cases:
                _, token = self.contract(sid)
                records[sid] = self._head(sid, token)
            return dict(schema='cnv-v9-web-review-v1', selection_sha256=self.data['selection_sha256'],
                        records=records, scope='whole acquisition per model; explicit human confirmation',
                        training_started=False, training_target_policy=TARGET_POLICY)

    def queue(self, records=None):
        if records is None:
            records = self.all()['records']
        rows = []
        for sid, r in records.items():
            if r['review_model2']:
                a = self.cases[sid]
                rows.append(dict(scan_id=sid, animal=a['animal'], eye=a['eye'],
                                 session_date=a['session_date'], revision=r['revision'],
                                 notes=r['notes'], seed_model='v9_m2_adjusted',
                                 confirmation=False, needs_gui_correction=True,
                                 prediction_contract=r['prediction_contract'],
                                 decision_file=str(self.directory/'decisions'/(sid+'.json'))))
        return dict(schema='cnv-v9-model2-correction-flags-v1', acquisitions=rows,
                    selected_model='v9_m2_adjusted', creates_no_annotations=True,
                    instruction='Seed later GUI drafts from adjusted candidates; retain both raw model alternatives. Human correction and final whole-field confirmation remain required.')

    def save(self, sid, payload):
        fields = {'expected_revision', 'token', 'confirm_m1', 'confirm_m2_adjusted', 'review_model2', 'notes'}
        if not isinstance(payload, dict) or set(payload) != fields:
            raise ValueError('Invalid review fields')
        for key in ('confirm_m1', 'confirm_m2_adjusted', 'review_model2'):
            if type(payload[key]) is not bool:
                raise ValueError('Review checkboxes must be booleans')
        if type(payload['expected_revision']) is not int or payload['expected_revision'] < 0:
            raise ValueError('Invalid revision')
        if not isinstance(payload['notes'], str) or len(payload['notes']) > 4000:
            raise ValueError('Notes must be at most 4000 characters')
        if payload['confirm_m2_adjusted'] and payload['review_model2']:
            raise ValueError('Model 2 cannot be confirmed while it needs correction')
        with self.lock:
            contract, token = self.contract(sid)
            if token != payload['token']:
                raise ReviewConflict('Prediction version changed; reload before reviewing')
            old = self._head(sid, token)
            if old['revision'] != payload['expected_revision']:
                raise ReviewConflict('This review changed in another tab; reload to see its latest state')
            for status in contract['predictions']:
                verify(status['prediction'])
                verify(status['checkpoint'])
            state = {k: payload[k] for k in ('confirm_m1', 'confirm_m2_adjusted', 'review_model2', 'notes')}
            if old['revision'] and all(old[k] == v for k, v in state.items()):
                return old
            record = dict(schema='cnv-v9-web-review-decision-v1', scan_id=sid,
                          revision=old['revision'] + 1, token=token, **state,
                          updated_at=datetime.now(timezone.utc).isoformat(),
                          human_action='explicit browser checkbox/notes save',
                          confirmation_scope='whole field: included CNVs and outlines acceptable with boundary variation; omitted pixels reviewed as background for this model; zero candidates confirms no CNV',
                          unchecked_meaning='unconfirmed, not a negative label',
                          prediction_contract=contract,
                          needs_target_resolution=False,
                          training_exported=False,
                          previous_revision_sha256=sha(self.directory/'decisions'/(sid+'.json')) if old['revision'] else None)
            record = interpret_approval(record)
            history = self.directory / 'history' / sid / f"{record['revision']:06d}.json"
            if history.exists():
                raise ReviewConflict('An interrupted save exists; reconcile its preserved history before continuing')
            write(history, record)
            write(self.directory / 'decisions' / (sid + '.json'), record)
            write(self.directory / 'model2_queue.json', self.queue())
            return record
