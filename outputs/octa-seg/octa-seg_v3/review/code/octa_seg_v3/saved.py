"""Read-only index of new and historical journals, without manufacturing review work."""
from pathlib import Path
from functools import lru_cache
from PySide6 import QtCore, QtGui, QtWidgets
from .common import OUT, V3, ROOT, read
from . import common
DATA_ROOT = getattr(common, "DATA_ROOT", ROOT)


def describe(path, legacy=False):
    path = Path(path)
    stat = path.stat()
    return _describe(str(path), legacy, stat.st_mtime_ns, stat.st_size)


@lru_cache(maxsize=4096)
def _describe(path, legacy, mtime, size):
    record = read(path)
    events = record['events'][:record['cursor']]
    meta = {}
    status = 'Legacy' if legacy else 'Draft'
    work = False
    for event in events:
        if event['action'] == 'migrate_cnv_distinctions':
            continue  # Layer confirmation is unchanged; new lesion definitions remain unconfirmed.
        if event['action'] == 'case_metadata':
            if ('data_role' in event['values'] and event['values']['data_role'] != meta.get('data_role', 'development')
                    and status in ('Confirmed', 'Needs reconfirmation')):
                status = 'Needs reconfirmation'
            meta.update(event['values'])
        else:
            work = True
            if event['action'] == 'confirm_bscan' and event.get('contract') == 'whole-bscan-confirmation-1':
                status = 'Confirmed'
            elif status in ('Confirmed', 'Needs reconfirmation'):
                status = 'Needs reconfirmation'
    if legacy:
        status = 'Legacy'
    boundary_times = [e.get('timestamp', 0) for e in events if e['action'] != 'case_metadata']
    return dict(path=str(path), scan_id=record['scan_id'], bscan=int(record['bscan']), reviewer=record['reviewer_id'],
        status=status, work=work, meta=meta, time=max(boundary_times, default=0), model_id=record['model_id'],
        source=record['source'], legacy=legacy)


def index(reviewer, output=None, include_tags=False):
    rows = {}
    roots = [(V3 / 'reviewers' / reviewer, True), (Path(output or OUT / 'reviewers' / reviewer), False)]
    for root, legacy in roots:
        for path in sorted((root / 'journals').glob('*.json')):
            entry = describe(path, legacy)
            key = (entry['scan_id'], entry['bscan'])
            # A new journal supersedes its historical view even after undoing all work.
            rows[key] = entry
    return sorted((r for r in rows.values() if r['work'] or include_tags), key=lambda r: (r['scan_id'], r['bscan']))


def sharing(record):
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


class SharedBrowser(QtWidgets.QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle('Shared / starred samples · independent review')
        self.resize(950, 480)
        layout = QtWidgets.QVBoxLayout(self)
        hint = QtWidgets.QLabel('All confirmed lead B-scans are shared automatically, along with manually shared cases. ★ means explicitly starred as ambiguous; Shared has no star. '
            'Opening a case uses your reviewer ID and your own boundary edits.')
        hint.setWordWrap(True); layout.addWidget(hint)
        filters = QtWidgets.QHBoxLayout()
        self.owner = QtWidgets.QComboBox()
        owners = {'lead', window.reviewer}
        for root in (OUT / 'reviewers', V3 / 'reviewers'):
            if root.exists(): owners.update(p.name for p in root.iterdir() if p.is_dir())
        self.owner.addItems(sorted(owners)); self.owner.setCurrentText('lead')
        filters.addWidget(QtWidgets.QLabel('Shared by:')); filters.addWidget(self.owner)
        self.search = QtWidgets.QLineEdit(); self.search.setPlaceholderText('Filter by animal or scan')
        filters.addWidget(self.search)
        self.unfinished = QtWidgets.QCheckBox('Not yet confirmed by me'); filters.addWidget(self.unfinished)
        layout.addLayout(filters)
        self.kind = QtWidgets.QComboBox(); self.kind.addItems(['All shared', 'Starred only', 'Shared without star'])
        filters.addWidget(self.kind)
        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(['Animal / scan', 'Native B-scan', 'Sharing', 'My review status'])
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(1, 120); self.table.setColumnWidth(2, 130); self.table.setColumnWidth(3, 190)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self.open_current); layout.addWidget(self.table)
        buttons = QtWidgets.QHBoxLayout()
        self.open_button = QtWidgets.QPushButton('Open under my reviewer ID')
        self.open_button.clicked.connect(self.open_current); buttons.addWidget(self.open_button)
        refresh = QtWidgets.QPushButton('Refresh shared samples'); refresh.clicked.connect(self.refresh); buttons.addWidget(refresh)
        layout.addLayout(buttons)
        self.summary = QtWidgets.QLabel(); self.summary.setWordWrap(True); layout.addWidget(self.summary)
        self.owner.currentTextChanged.connect(self.refresh)
        self.search.textChanged.connect(self.refresh); self.unfinished.toggled.connect(self.refresh)
        self.kind.currentIndexChanged.connect(self.refresh)
        self.refresh()

    def refresh(self, *_):
        owner = self.owner.currentText()
        cases = shared_cases(owner, self.window.entries, self.window.output if owner == self.window.reviewer else None)
        own = {(r['scan_id'], r['bscan']): r['status'] for r in index(self.window.reviewer, self.window.output)}
        term = self.search.text().strip().lower()
        self.rows = [r for r in cases if term in r['scan_id'].lower()
            and (self.kind.currentIndex() == 0 or r['starred'] == (self.kind.currentIndex() == 1))
            and (not self.unfinished.isChecked() or own.get((r['scan_id'], r['bscan'])) != 'Confirmed')]
        self.table.setRowCount(len(self.rows))
        for i, row in enumerate(self.rows):
            status = own.get((row['scan_id'], row['bscan']), 'Not started')
            if status == 'Draft': status = 'Started (draft)'
            for col, value in enumerate((row['scan_id'], row['bscan'], '★ Starred' if row['starred'] else 'Shared', status)):
                self.table.setItem(i, col, QtWidgets.QTableWidgetItem(str(value)))
        self.open_button.setEnabled(bool(self.rows))
        self.summary.setText(f'{len(self.rows)} matching B-scans in {len({r["scan_id"] for r in self.rows})} volumes '
            f'available here · {sum(r["starred"] for r in self.rows)} starred / {sum(not r["starred"] for r in self.rows)} shared without star · shared by {owner} · saving as {self.window.reviewer}. '
            'Previous/Next selected B-scan follows this filtered list after opening a case.')
        if self.rows: self.table.selectRow(0)

    def open_current(self, *_):
        selected = self.table.currentRow()
        if selected >= 0:
            self.window.use_shared_cases(self.rows, selected)


class Browser(QtWidgets.QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle('My saved reviews · resume or discuss')
        self.resize(1000, 520)
        layout = QtWidgets.QVBoxLayout(self)
        filters = QtWidgets.QHBoxLayout()
        self.search = QtWidgets.QLineEdit(); self.search.setPlaceholderText('Search animal, scan or notes')
        self.status = QtWidgets.QComboBox(); self.status.addItems(['Any status', 'Draft', 'Confirmed', 'Needs reconfirmation', 'Legacy'])
        self.category = QtWidgets.QComboBox(); self.category.addItems(['Any category', 'cnv', 'onh', 'artifact', 'clear'])
        self.volume = QtWidgets.QCheckBox('This volume')
        self.flagged = QtWidgets.QCheckBox('Shared / starred')
        for widget in (self.search, self.status, self.category, self.volume, self.flagged): filters.addWidget(widget)
        layout.addLayout(filters)
        line = QtWidgets.QHBoxLayout()
        self.owner = QtWidgets.QComboBox(); self.owner.addItem(window.reviewer)
        owners = set()
        for root in (OUT / 'reviewers', V3 / 'reviewers'):
            if root.exists(): owners.update(p.name for p in root.iterdir() if p.is_dir())
        self.owner.addItems(sorted(owners - {window.reviewer}))
        line.addWidget(QtWidgets.QLabel('Review owner:')); line.addWidget(self.owner)
        self.discussion = QtWidgets.QCheckBox('Discussion mode · read only, exposure recorded')
        line.addWidget(self.discussion); line.addStretch(); layout.addLayout(line)
        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['Animal / scan', 'Native B-scan', 'Status', 'Last review', 'Shared', 'Notes'])
        for col, width in ((1,105),(2,145),(3,140),(4,100)):
            self.table.setColumnWidth(col,width)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.doubleClicked.connect(self.open_current)
        layout.addWidget(self.table)
        row = QtWidgets.QHBoxLayout()
        for title, fn in [('Open saved review', self.open_current), ('Resume last', self.resume_last),
                          ('Previous saved review', lambda: self.step(-1)), ('Next saved review', lambda: self.step(1)),
                          ('Next unfinished', self.next_unfinished), ('Refresh list', self.refresh)]:
            button = QtWidgets.QPushButton(title); button.clicked.connect(fn); row.addWidget(button)
        layout.addLayout(row)
        self.summary = QtWidgets.QLabel(); layout.addWidget(self.summary)
        self.search.textChanged.connect(self.refresh)
        for widget in (self.status, self.category, self.owner): widget.currentIndexChanged.connect(self.refresh)
        for widget in (self.volume, self.flagged): widget.toggled.connect(self.refresh)
        self.refresh()

    def refresh(self, *_):
        owner = self.owner.currentText()
        other = owner != self.window.reviewer
        if other: self.discussion.setChecked(True)
        self.discussion.setEnabled(not other)
        rows = index(owner, self.window.output if not other else None)
        term = self.search.text().lower()
        self.rows = [r for r in rows if (not term or term in (r['scan_id'] + ' ' + r['meta'].get('notes', '')).lower())
            and (self.status.currentIndex() == 0 or r['status'] == self.status.currentText())
            and (self.category.currentIndex() == 0 or self.category.currentText() in r['meta'].get('categories', []))
            and (not self.volume.isChecked() or self.window.volume and r['scan_id'] == self.window.volume.scan.scan_id)
            and (not self.flagged.isChecked() or sharing(r)[0])]
        self.table.setRowCount(len(self.rows))
        for row, r in enumerate(self.rows):
            stamp = QtCore.QDateTime.fromSecsSinceEpoch(int(r['time'])).toString('yyyy-MM-dd HH:mm') if r['time'] else 'Historical'
            for col, value in enumerate([r['scan_id'], r['bscan'], r['status'], stamp,
                    '★ Starred' if sharing(r)[1] else ('Shared' if sharing(r)[0] else ''), r['meta'].get('notes', '')[:100]]):
                self.table.setItem(row, col, QtWidgets.QTableWidgetItem(str(value)))
        self.summary.setText(f'{len(self.rows)} matching saved reviews · {sum(r["status"] == "Confirmed" for r in rows)} confirmed / {len(rows)} saved for {owner}')
        if self.rows: self.table.selectRow(0)

    def open_current(self, *_):
        selected = self.table.currentRow()
        if selected >= 0:
            self.window.open_saved(self.rows[selected], self.discussion.isChecked())

    def step(self, direction):
        if self.rows:
            self.table.selectRow(max(0, min(len(self.rows)-1, self.table.currentRow()+direction)))
            self.open_current()

    def resume_last(self):
        if self.rows:
            self.table.selectRow(max(range(len(self.rows)), key=lambda k: (self.rows[k]['time'], self.rows[k]['scan_id'], self.rows[k]['bscan'])))
            self.open_current()

    def next_unfinished(self):
        start = self.table.currentRow()+1
        for k in list(range(start, len(self.rows))) + list(range(start)):
            if self.rows[k]['status'] != 'Confirmed':
                self.table.selectRow(k); self.open_current(); return
