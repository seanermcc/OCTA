"""Evaluate withheld explicit evidence, retaining policy/footprint/learning distinctions."""
from .common import *
from quality_pilot.metrics import stats

def compare(snapshot,current=ROUND):
    m=read(Path(snapshot)/'manifest.json');results=[];interaction=[]
    mechanical=[]
    for sid in SCANS:
        old=npz(ROUND/'volumes'/sid/'measurements.npz');new=npz(Path(current)/'volumes'/sid/'measurements.npz')
        for k,name in enumerate(new['surface_names']):
            previous_solid=np.isfinite(old['reported_positions'][:,k]);now=np.isfinite(new['reported_positions'][:,k])
            mechanical.append(dict(scan_id=sid,boundary=str(name),previous_solid_fraction=previous_solid.mean(),current_solid_fraction=now.mean(),
               previous_solid_retained_fraction=float(now[previous_solid].mean()) if previous_solid.any() else None,
               **{f'position_change_{key}':val for key,val in stats(np.abs(new['raw_position_branch'][:,k]-old['raw_position_branch'][:,k])*1.12).items()},
               interpretation='mechanical differences, not good-boundary retention without human assessment'))
    table(Path(current)/'reports/round_mechanical_comparison.csv',mechanical)
    for r in m['records']:
        t=npz(r['targets']['path']);b=r['bscan'];sid=r['scan_id']
        es=r['events'];approvals=sum(e['action']=='approve_position' for e in es);corrections=sum(e['action']=='correct' for e in es)
        interaction.append(dict(key=r['key'],role=r['role'],review_seconds=r['review_seconds'],candidate_approval_events=approvals,correction_events=corrections,
            candidate_event_fraction=approvals/max(1,approvals+corrections),interpretation='event rate; not population candidate accuracy'))
        if r['role']!='assessment':continue
        for name,folder in [('previous',ROUND),('current',Path(current))]:
            d=npz(folder/'volumes'/sid/'measurements.npz')
            for k,boundary in enumerate(d['surface_names']):
                solid=np.isfinite(d['reported_positions'][b,k]);bad=t['reliability_target'][k]==0;good=t['reliability_target'][k]==1
                for sensitivity,valid in [('manual_only',t['manual_valid'][k]),('manual_plus_approved',t['manual_valid'][k]|t['approved_valid'][k])]:
                    err=np.abs(d['raw_position_branch'][b,k,valid]-t['rows'][k,valid])*1.12
                    results.append(dict(key=r['key'],boundary=str(boundary),model=name,sensitivity=sensitivity,
                       bad_columns=int(bad.sum()),false_solid_fraction=float(solid[bad].mean()) if bad.any() else None,
                       good_columns=int(good.sum()),good_retention=float(solid[good].mean()) if good.any() else None,
                       **{f'position_error_{key}':val for key,val in stats(err).items()}))
    table(Path(current)/'reports/assessment_comparison.csv',results);table(Path(current)/'reports/review_effort.csv',interaction)
    write(Path(current)/'reports/assessment_status.json',dict(assessment_records=sum(r['role']=='assessment' for r in m['records']),
        status='development assessment only' if results else 'pending withheld human assessment',provider_promoted=False,
        ancestry='all-label initialization; no animal-excluded generalization claim'))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('snapshot',type=Path);p.add_argument('--current',type=Path,default=ROUND);a=p.parse_args();compare(a.snapshot,a.current)
