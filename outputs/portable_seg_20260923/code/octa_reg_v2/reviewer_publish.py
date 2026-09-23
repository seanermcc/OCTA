"""Update reviewer assets/visit metadata without rerunning or changing registration."""
import json
from pathlib import Path
import shutil
from .review_server import DEFAULT_ROOT


def visit(info):
    actual = info.get('days_post_laser')
    nominal = str(info.get('day_label') or '').lower()
    if actual not in ('', None):
        day = float(actual)
        label = 'pre' if day < 0 else 'd'+format(day, 'g')
        basis = 'actual days after laser'
    else:
        label = ('pre' if info.get('timepoint_kind') == 'pre_laser' or 'pre' in nominal or 'before' in nominal
                 else 'd0' if nominal == 'laser day' else '6mo' if nominal == '6 mo'
                 else 'wt' if nominal == 'wt' else nominal or '?')
        basis = 'nominal label; actual day unavailable'
    # Long labels get compact per-montage aliases during publication; full value remains in the tooltip.
    return dict(day_label=label, day_basis=basis, nominal_day_label=info.get('day_label'),
                days_post_laser=actual)


def publish(root=DEFAULT_ROOT):
    source = Path(__file__).parent
    count = 0
    for folder in sorted(root.iterdir()):
        path = folder/'montage.json'
        if not path.is_file(): continue
        data = json.loads(path.read_text(encoding='utf-8'))
        registration = folder/'review_registration.json'
        if not registration.exists(): registration = folder/'registration.json'
        infos = {s['scan_id']:s for s in json.loads(registration.read_text(encoding='utf-8'))['scans']}
        long_labels = {}
        for s in data['scans']:
            s.update(visit(infos[s['scan_id']]))
            if len(s['day_label']) > 4:
                full = s['day_label']; long_labels.setdefault(full, 'v'+str(len(long_labels)+1))
                s['day_basis'] += '; full label '+full; s['day_label'] = long_labels[full]
        path.write_text(json.dumps(data, indent=2, allow_nan=False), encoding='utf-8')
        (folder/'data.js').write_text('window.MONTAGE='+json.dumps(data, allow_nan=False)+';', encoding='utf-8')
        for name in ('cohort_viewer.html', 'cohort_viewer.js'):
            shutil.copyfile(source/name, folder/('index.html' if name.endswith('.html') else name))
        (folder/'OPEN_MONTAGE.cmd').write_text('@echo off\ncall "%~dp0..\\OPEN_REVIEWER.cmd" '+folder.name+'\n')
        count += 1
    # Use the stdlib-only server, still launched through the activated project environment.
    launcher = '''@echo off
call D:\\Anaconda\\Scripts\\activate.bat octa
cd /d "%~dp0..\\..\\.."
set PYTHONPATH=%CD%\\code
python -c "import urllib.request,json; assert json.load(urllib.request.urlopen('http://127.0.0.1:8771/api/health', timeout=2))['service']=='octa-reg-v2-review'" >nul 2>&1
if errorlevel 1 start "" /min powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%~dp0START_SERVER.ps1"
if "%~1"=="" (start "" "http://127.0.0.1:8771/index.html") else (start "" "http://127.0.0.1:8771/%~1/index.html")
'''
    (root/'OPEN_REVIEWER.cmd').write_text(launcher)
    (root/'START_SERVER.ps1').write_text('''. D:\\Anaconda\\shell\\condabin\\conda-hook.ps1
conda activate octa
Set-Location ($PSScriptRoot + '\\..\\..\\..')
$env:PYTHONPATH = "$PWD\\code"
python -m octa_reg_v2.review_server
''')
    index = root/'index.html'
    if index.exists():
        page = index.read_text(encoding='utf-8')
        if 'review-status-script' not in page:
            page += '''<script id="review-status-script">
for (const card of document.querySelectorAll('a.card')) {
 const group = card.getAttribute('href').split('/')[0];
 fetch('/api/review/'+group).then(r=>r.ok?r.json():null).then(r=>{
  const badge=document.createElement('p');badge.style.fontWeight='bold';
  badge.textContent=!r?'Review status unavailable':r.montage_confirmed?'✓ Montage confirmed':
   Object.values(r.fields).filter(f=>f.status==='confirmed').length+' fields confirmed · montage pending';
  card.append(badge);
 }).catch(()=>{});
}
</script>'''
            index.write_text(page, encoding='utf-8')
    return count


if __name__ == '__main__': print('Published reviewers:', publish())
