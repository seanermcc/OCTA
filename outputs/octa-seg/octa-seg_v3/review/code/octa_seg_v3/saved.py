"""Read-only index of new and historical journals, without manufacturing review work."""
from pathlib import Path
from functools import lru_cache
from PySide6 import QtCore, QtGui, QtWidgets
from .common import OUT, V3, read


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
        self.flagged = QtWidgets.QCheckBox('Flagged/shared')
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
        for col, width in ((1,105),(2,145),(3,140),(4,60)):
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
            and (not self.flagged.isChecked() or r['meta'].get('for_review') or r['meta'].get('especially_ambiguous'))]
        self.table.setRowCount(len(self.rows))
        for row, r in enumerate(self.rows):
            stamp = QtCore.QDateTime.fromSecsSinceEpoch(int(r['time'])).toString('yyyy-MM-dd HH:mm') if r['time'] else 'Historical'
            for col, value in enumerate([r['scan_id'], r['bscan'], r['status'], stamp,
                    '★' if r['meta'].get('for_review') or r['meta'].get('especially_ambiguous') else '', r['meta'].get('notes', '')[:100]]):
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
