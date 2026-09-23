from common import *
p=HERE/'gallery/app.js';s=p.read_text(encoding='utf8')
old='${current.session_date} · ${current.day_label}`;'
new='${current.session_date} · ${displayDay(current)}`;'
assert old in s;s=s.replace(old,new)
s=s.replace('function fmt(n,d=0)',"function displayDay(a){const actual=String(a.days_post_laser??'').trim();return actual&&Number.isFinite(Number(actual))?'Day '+actual+' (nominal '+a.day_label+')':a.day_label+' · nominal'}\nfunction fmt(n,d=0)")
s=s.replace('${current.quality_note}`;',"${current.quality_note}${current.source_folder_differs_from_index?' · folder/index day discrepancy; see provenance':''}`;")
tmp=p.with_suffix('.tmp');tmp.write_text(s,encoding='utf8');os.replace(tmp,p)
ids={r['scan_id'] for r in read(HERE/'data/supervision.json')['records']};rows=[r for r in read(EXPORT/'manifest.json')['records'] if r['scan_id'] in ids]
coverage=dict(total=len(rows),vessel_reviewed=sum(r['vessel_reviewed'] for r in rows),onh_reviewed=sum(r['onh_reviewed'] for r in rows),onh_nonempty=sum(r['onh_pixels']>0 for r in rows),onh_reviewed_absence=sum(r['onh_reviewed'] and r['onh_pixels']==0 for r in rows),onh_unknown_empty=sum(not r['onh_reviewed'] and r['onh_pixels']==0 for r in rows))
write(HERE/'reports/context_coverage.json',coverage);print(json.dumps(coverage))
