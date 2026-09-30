"""Update shared selection without editing human journals or Mac save adapters."""
from pathlib import Path
import hashlib
import json
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REL = Path('outputs/octa-seg/octa-seg_v3/review/code/octa_seg_v3')
WINDOWS = Path('F:/octa/Full/_Project')
MAC = Path('F:/octa/Mac_Boundary_Reviewer/project')
roots = [ROOT, WINDOWS, MAC]
for i, root in enumerate(roots):
    for name in ('saved.py', 'gui.py'):
        dst = HERE/'before'/str(i)/name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists(): shutil.copy2(root/REL/name, dst)

s = (HERE/'before/1/saved.py').read_text(encoding='utf-8')
s = s.replace('from .common import OUT, V3, read', 'from .common import OUT, V3, ROOT, read\nfrom . import common\nDATA_ROOT = getattr(common, "DATA_ROOT", ROOT)')
start = s.index('def shared_cases(')
end = s.index('\n\nclass SharedBrowser', start)
s = s[:start] + '''def sharing(record):
    """Sharing is selection metadata; a star means explicitly ambiguous only."""
    meta = record['meta']
    starred = bool(meta.get('especially_ambiguous'))
    automatic = record['reviewer'] == 'lead' and record['status'] == 'Confirmed'
    return automatic or bool(meta.get('for_review')) or starred, starred


def shared_index(owner, output=None):
    # Mac's own journals stay local. Other reviewers' current selections come
    # from the drive, not the stale first-launch copy in Mac Documents.
    if output is None and DATA_ROOT != ROOT:
        drive = DATA_ROOT / 'Reviews/reviewers' / owner
        if drive.is_dir():
            output = drive
    return index(owner, output, include_tags=True)


def shared_cases(owner, entries, output=None):
    """Selection identities and star only: no answers, masks, notes or categories."""
    providers = {entry['scan_id']: entry['directory'] for entry in entries}
    result = []
    for record in shared_index(owner, output):
        shared, starred = sharing(record)
        if record['scan_id'] not in providers or not shared:
            continue
        result.append(dict(scan_id=record['scan_id'], bscan=record['bscan'],
            provider=record['source'].get('provider') or providers[record['scan_id']],
            model_id=record['model_id'], data_role=record['meta'].get('data_role', 'development'),
            starred=starred))
    return result
''' + s[end:]
s = s.replace('Lists B-scans marked “For review” or starred as ambiguous by the selected reviewer. ',
              'All confirmed lead B-scans are shared automatically, along with manually shared cases. '
              '★ means explicitly starred as ambiguous; Shared has no star. ')
s = s.replace("self.table = QtWidgets.QTableWidget(0, 3)", "self.kind = QtWidgets.QComboBox(); self.kind.addItems(['All shared', 'Starred only', 'Shared without star'])\n        filters.addWidget(self.kind)\n        self.table = QtWidgets.QTableWidget(0, 4)")
s = s.replace("['Animal / scan', 'Native B-scan', 'My review status']", "['Animal / scan', 'Native B-scan', 'Sharing', 'My review status']")
s = s.replace('self.table.setColumnWidth(2, 190)', 'self.table.setColumnWidth(2, 130); self.table.setColumnWidth(3, 190)')
s = s.replace('Refresh shared flags', 'Refresh shared samples')
s = s.replace('self.search.textChanged.connect(self.refresh); self.unfinished.toggled.connect(self.refresh)',
              'self.search.textChanged.connect(self.refresh); self.unfinished.toggled.connect(self.refresh)\n        self.kind.currentIndexChanged.connect(self.refresh)')
s = s.replace("self.rows = [r for r in cases if term in r['scan_id'].lower()", "self.rows = [r for r in cases if term in r['scan_id'].lower()\n            and (self.kind.currentIndex() == 0 or r['starred'] == (self.kind.currentIndex() == 1))")
s = s.replace("for col, value in enumerate((row['scan_id'], row['bscan'], own.get((row['scan_id'], row['bscan']), 'Not reviewed'))):",
              "status = own.get((row['scan_id'], row['bscan']), 'Not started')\n            if status == 'Draft': status = 'Started (draft)'\n            for col, value in enumerate((row['scan_id'], row['bscan'], '★ Starred' if row['starred'] else 'Shared', status)):")
s = s.replace("f'available here · shared by {owner} · saving as {self.window.reviewer}. '",
              "f'available here · {sum(r[\"starred\"] for r in self.rows)} starred / {sum(not r[\"starred\"] for r in self.rows)} shared without star · shared by {owner} · saving as {self.window.reviewer}. '")
s = s.replace("QtWidgets.QCheckBox('Flagged/shared')", "QtWidgets.QCheckBox('Shared / starred')")
s = s.replace("and (not self.flagged.isChecked() or r['meta'].get('for_review') or r['meta'].get('especially_ambiguous'))", "and (not self.flagged.isChecked() or sharing(r)[0])")
s = s.replace("'★' if r['meta'].get('for_review') or r['meta'].get('especially_ambiguous') else ''", "'★ Starred' if sharing(r)[1] else ('Shared' if sharing(r)[0] else '')")
s = s.replace('(4,60)', '(4,100)')
compile(s, 'saved.py', 'exec')
for root in roots:
    (root/REL/'saved.py').write_text(s, encoding='utf-8', newline='\n')
    g = (HERE/'before'/str(roots.index(root))/'gui.py').read_text(encoding='utf-8')
    if 'class SharedBrowser' not in (HERE/'before'/str(roots.index(root))/'saved.py').read_text(encoding='utf-8'):
        g = g.replace('from .saved import index as saved_index, Browser', 'from .saved import index as saved_index, Browser, SharedBrowser')
        g = g.replace('        self.saved_browser = None', '        self.shared_browser = None\n        self.saved_browser = None')
        source = (HERE/'before/1/gui.py').read_text(encoding='utf-8')
        a = source.index('        self.shared_button = ')
        b = source.index('\n', source.index('        layout.addWidget(self.shared_button)', a))
        anchor = '        self.review_legend.setWordWrap(True); layout.addWidget(self.review_legend)'
        assert anchor in g
        g = g.replace(anchor, anchor+'\n'+source[a:b])
        a = source.index('    def show_shared(')
        b = source.index('    def open_saved(', a)
        g = g.replace('    def open_saved(', source[a:b]+'    def open_saved(', 1)
    g = g.replace('Filter the lead reviewer’s shared or starred B-scans and open them independently under your own ID',
                  'All confirmed lead B-scans plus explicitly shared cases; stars mark ambiguity. Open independently under your own ID')
    # Strip display-only sharing metadata before creating an independent queue.
    g = g.replace('self.queue = [dict(row) for row in rows]', "self.queue = [{k: v for k, v in row.items() if k != 'starred'} for row in rows]")
    compile(g, str(root/REL/'gui.py'), 'exec')
    (root/REL/'gui.py').write_text(g, encoding='utf-8', newline='\n')
report = {str(root):{n:hashlib.sha256((root/REL/n).read_bytes()).hexdigest() for n in ('saved.py','gui.py')} for root in roots}
(HERE/'code_update.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
