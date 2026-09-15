"""Read actual GUI records; never produce or modify an annotation."""
from common import *
from collections import Counter,defaultdict

def run():
    rows=[];actions=Counter();seconds=defaultdict(float)
    for path in (HERE/'review/regions').glob('*_regions.json'):
        a=read(path);r=a['regions'];ctx=a['review_context']
        rows.append(dict(scan_id=a['scan_id'],whole_field_complete=a['scan_review'].get('whole_field_checked',False),
            confirmed_lesions=sum(x['decision']=='approved' and x['category']=='Full Lesion' for x in r),
            unsure=sum(x['decision']=='approved' and x['category']=='Other' for x in r),drafts=sum(x['decision']=='unreviewed' for x in r),
            rejected=sum(x['decision']=='rejected' for x in r),assisted=ctx.get('assisted_annotation',False),visible_models=';'.join(ctx.get('visible_models',[])),
            source_record=str(path),record_sha256=sha(path)))
    actual={'addition confirmed','removal','confirmed lesion removal','outline correction confirmed','acceptance'}
    for path in (HERE/'review/sessions').glob('*.json'):
        a=read(path)
        for event in a['events']:
            if event['action'] in actual:actions[(event['scan_id'],event['model'],event['action'])]+=1
        for key,value in a['active_seconds_by_scan_and_model'].items():seconds[key]+=value
    csv_write(HERE/'review/observed_decisions.csv',rows)
    csv_write(HERE/'review/observed_interactions.csv',[dict(scan_id=k[0],visible_model=k[1],action=k[2],count=v) for k,v in sorted(actions.items())])
    csv_write(HERE/'review/active_time.csv',[dict(scan_model_comparison=k,seconds=v) for k,v in sorted(seconds.items())])
    report=f'''# Human review status

Saved acquisitions with explicit human work: {len(rows)}.
Whole fields explicitly completed: {sum(r['whole_field_complete'] for r in rows)}.

{'Human evaluation is pending. No human review findings or time savings are claimed.' if not rows else 'These are actual assisted GUI review records, separate from automatic comparisons and independent validation.'}

Observed interaction counts come only from explicit GUI actions and retain visible-model attribution. Counts may include actions later undone; current decisions are reported separately. Drafts and Unsure regions are not confirmed CNV labels. Only explicit whole-field completion supplies reviewed background.

Active time starts at the first interaction and excludes pauses, loss of focus, loading, and idle intervals after 60 seconds. Comparison mode is retained. These times do not constitute a controlled B/C or seed comparison, and no time saving is inferred.
'''
    dest(HERE/'review/HUMAN_REVIEW_STATUS.md').write_text(report,encoding='utf-8')
    print('Human review summaries:',len(rows),'saved acquisitions',flush=True)

if __name__=='__main__':run()
