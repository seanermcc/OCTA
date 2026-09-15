"""Read current review records; report explicit ratings without inferring model quality."""
from common import *
from collections import Counter

def run():
    records=[read(p) for p in (REVIEW/'regions').glob('*_regions.json')]
    ratings=Counter();errors=Counter();old_regions=0;finished=0
    for rec in records:
        old_regions+=len(rec.get('regions',[]));finished+=bool(rec.get('scan_review',{}).get('rating_review_finished'))
        for key,value in rec.get('model_ratings',{}).items():
            if value.get('value') is not None:ratings[key+'/'+value['value']]+=1
        for event in rec.get('review_events',[]):
            if event['id'] in rec.get('active_error_ids',[]):errors[event['action']]+=1
    result=dict(saved_acquisitions=len(records),saved_region_records=old_regions,explicit_model_ratings=dict(ratings),
        active_error_evidence=dict(errors),finished_reviews=finished,
        interpretation='Human evaluation remains pending beyond explicit saved user decisions; historical Keep actions are not model ratings.')
    write(REVIEW/'review_summary.json',result)
    (dest(REVIEW/'HUMAN_REVIEW_STATUS.md')).write_text(
        '# Human review status\n\n'
        f'Saved acquisitions: **{len(records)}**. Saved region decisions/drafts: **{old_regions}**.\n\n'
        f'Explicit original-model ratings: **{sum(ratings.values())}**. Finished new reviews: **{finished}**.\n\n'
        'Human evaluation remains pending except for real user decisions already saved. '
        'The two reviews present at migration retain their original decisions and history. '
        'Historical Keep/Remove actions were not converted into new model ratings. '
        'All verification interactions used isolated test directories.\n\n'
        'Unset ratings and unreviewed tissue remain unknown. No training export, threshold changes, or retraining occur.\n',encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':run()
