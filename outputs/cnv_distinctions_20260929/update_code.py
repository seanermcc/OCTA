"""Archive and update each installed reviewer without replacing portable/Mac adapters."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path('D:/Projects/octa')
REL = Path('outputs/octa-seg/octa-seg_v3/review/code/octa_seg_v3')
ROOTS = [ROOT, Path('F:/octa/Full/_Project'), Path('F:/octa/Mac_Boundary_Reviewer/project')]
FILES = ['lesions.py', 'feedback.py', 'lesion_tools.py', 'controls.py', 'label_gui.py', 'gui.py']

def replace(s, old, new, count=1):
    if s.count(old) != count:
        raise RuntimeError(f'Expected {count} occurrences, found {s.count(old)}: {old[:100]}')
    return s.replace(old, new)

def transform(name, s):
    if name == 'lesions.py':
        s = replace(s, "DEFINITION_VERSION = 'cnv-lesion-tentative-1'", "LEGACY_VERSION = 'cnv-lesion-tentative-1'\nDEFINITION_VERSION = 'cnv-core-full-2'")
        s = replace(s, 'DEFINITIONS = {', 'LEGACY_DEFINITIONS = {')
        s = replace(s, 'DEFINITION_VERSIONS = {DEFINITION_VERSION: DEFINITIONS}', '''CORE_DEFINITION = 'CNV-Core is defined as the region where RPE is non-traceable with a loss of contrast (dark) blood-vessel invasion from the RPE'
FULL_DEFINITION = 'Full-CNV Lesion is defined by regions where the RPE is clearly disrupted, and this should not depend on the hyper-reflective dots above the RPE'
DEFINITIONS = {'CNV-Core': CORE_DEFINITION, 'Full-CNV Lesion (RPE-Disrupt)': FULL_DEFINITION,
               'CNV edge': LEGACY_DEFINITIONS['CNV edge'], 'Hyper_Ref': LEGACY_DEFINITIONS['Hyper_Ref']}
DEFINITION_VERSIONS = {LEGACY_VERSION: LEGACY_DEFINITIONS, DEFINITION_VERSION: DEFINITIONS}
REGION_KEYS = ('cnv_core', 'cnv_full')
REGION_COLORS = {'cnv_core': '#ac6beb', 'cnv_full': '#31dfd2'}
MIGRATION_ACTION = 'migrate_cnv_distinctions'
LEGACY_MAPPING = {'lead': 'cnv_core', 'shichu': 'cnv_full'}


def region_union(state):
    return state['cnv_region'] | state['cnv_core'] | state['cnv_full']


def migrate(state, event):
    kind = event.get('destination')
    if (kind not in REGION_KEYS or event.get('lesion_definition') != DEFINITION_VERSION
            or event.get('from_definition') != LEGACY_VERSION
            or LEGACY_MAPPING.get(event.get('reviewer_id')) != kind
            or any(state[k].any() for k in REGION_KEYS)):
        raise ValueError('Invalid explicit CNV category migration')
    if event.get('legacy_region_runs') != runs(state['cnv_region']):
        raise ValueError('CNV migration does not match the original footprint')
    state[kind][:] = state['cnv_region']
    state['cnv_region'][:] = False
''')
        s = replace(s, "ACTIONS = {'cnv_region', 'cnv_edge', 'cnv_edge_mark', 'hyper_ref'}", "ACTIONS = {'cnv_region', 'cnv_core', 'cnv_full', 'cnv_edge', 'cnv_edge_mark', 'hyper_ref', MIGRATION_ACTION}")
        s = replace(s, 'return dict(cnv_region=np.zeros(width, bool),', 'return dict(cnv_core=np.zeros(width, bool), cnv_full=np.zeros(width, bool),\n                cnv_region=np.zeros(width, bool),')
        s = replace(s, 'def snapshot(state):\n    return dict(', 'def snapshot(state, version=DEFINITION_VERSION):\n    result = dict(')
        s = replace(s, "shape=list(state['hyper_ref'].shape))", "shape=list(state['hyper_ref'].shape))\n    if version != LEGACY_VERSION:\n        result.update({k: runs(state[k]) for k in REGION_KEYS})\n    return result")
        s = replace(s, 'def digest(state):\n    return hashlib.sha256(json.dumps(snapshot(state),', 'def digest(state, version=DEFINITION_VERSION):\n    return hashlib.sha256(json.dumps(snapshot(state, version),')
        s = replace(s, "if action == 'cnv_region':\n        state['cnv_region'][lo:hi] = not erase", "if action in ('cnv_region', *REGION_KEYS):\n        if action in REGION_KEYS and event['lesion_definition'] != DEFINITION_VERSION:\n            raise ValueError('New CNV categories require their explicit definitions')\n        state[action][lo:hi] = not erase")
        s = s.replace("~state['cnv_region']", '~region_union(state)').replace("usable & state['cnv_region']", 'usable & region_union(state)').replace("(state['cnv_region'] | (edge_state == 1))", '(region_union(state) | (edge_state == 1))')
        s = replace(s, "return dict(cnv_region=state['cnv_region'].copy(), cnv_region_known=usable,", "return dict(cnv_core=state['cnv_core'].copy(), cnv_full=state['cnv_full'].copy(),\n                cnv_core_known=usable.copy(), cnv_full_known=usable.copy(),\n                cnv_region=state['cnv_region'].copy(), cnv_region_known=usable,")
    elif name == 'feedback.py':
        s = replace(s, "~lesion['cnv_region']", '~L.region_union(lesion)')
        s = replace(s, "        if action == 'case_metadata':", """        if action == L.MIGRATION_ACTION:
            L.migrate(lesion, event)
            lesion_definition = L.DEFINITION_VERSION
            # A category rename does not re-confirm a new definition or a new absence.
            # Existing layer geometry and its human confirmation remain intact.
            lesion_confirmation = None
            continue
        if action == 'case_metadata':""")
        s = replace(s, 'L.digest(lesion)', 'L.digest(lesion, version)')
        s = replace(s, 'L.snapshot(lesion)', 'L.snapshot(lesion, version)')
        s = replace(s, "    targets.update(L.targets(r['lesions'], lesion_eligible, r['excluded'], effective_shadow, vessel))", """    targets.update(L.targets(r['lesions'], lesion_eligible, r['excluded'], effective_shadow, vessel))
    if not r['lesion_confirmation'] or r['lesion_confirmation'].get('lesion_definition') != L.DEFINITION_VERSION:
        targets['cnv_core_known'][:] = False
        targets['cnv_full_known'][:] = False""")
        s = replace(s, "'cnv_region_known', 'cnv_edge_known', 'cnv_edge_valid', 'hyper_ref_known'):", "'cnv_region_known', 'cnv_core_known', 'cnv_full_known', 'cnv_edge_known', 'cnv_edge_valid', 'hyper_ref_known'):")
    elif name == 'lesion_tools.py':
        s = replace(s, "[('cnv_region', 'CNV region'), ('cnv_edge', 'CNV edge'), ('hyper_ref', 'Hyper_Ref')]", "[('cnv_core', 'CNV-Core'), ('cnv_full', 'Full-CNV Lesion (RPE-Disrupt)'), ('cnv_edge', 'CNV edge'), ('hyper_ref', 'Hyper_Ref')]")
        s = replace(s, "        self.buttons['cnv_region'].setToolTip('Left-drag across the lesion: mark full-depth columns. Ctrl+drag clears. Separate from image exclusion and automatic CNV context.')", """        for key, definition in [('cnv_core', L.CORE_DEFINITION), ('cnv_full', L.FULL_DEFINITION)]:
            self.buttons[key].setToolTip(definition + '\\nLeft-drag marks full-depth columns. Erase (E) or Ctrl+drag clears only this category.')
            self.buttons[key].setStyleSheet('QPushButton {color:' + L.REGION_COLORS[key] + ';} QPushButton:checked {background:#394553; border:2px solid ' + L.REGION_COLORS[key] + ';}')""")
        s = replace(s, "        self.region_item.setZValue(4)", """        self.region_item.setZValue(4)
        self.region_item.setToolTip('Historical CNV region (not yet migrated)')
        self.region_items = {}
        for key in L.REGION_KEYS:
            item = scene.addPath(QtGui.QPainterPath())
            color = QtGui.QColor(L.REGION_COLORS[key]); color.setAlpha(34)
            item.setBrush(color)
            pen = QtGui.QPen(QtGui.QColor(L.REGION_COLORS[key]), 1.3)
            pen.setCosmetic(True)
            item.setPen(pen); item.setZValue(5)
            item.setData(0, key)
            item.setToolTip(L.CORE_DEFINITION if key == 'cnv_core' else L.FULL_DEFINITION)
            self.region_items[key] = item""")
        s = s.replace('[self.region_item, self.mask_item,', '[self.region_item, *self.region_items.values(), self.mask_item,')
        s = s.replace("mode == 'cnv_region'", 'mode in L.REGION_KEYS').replace("mode in ('cnv_region', 'hyper_ref')", "mode in (*L.REGION_KEYS, 'hyper_ref')").replace("g['mode'] in ('cnv_region', 'retinal_erase')", "g['mode'] in (*L.REGION_KEYS, 'retinal_erase')")
        s = replace(s, '        self.region_item.setPath(path)', """        self.region_item.setPath(path)
        for key, item in self.region_items.items():
            path = QtGui.QPainterPath()
            for lo, hi in L.runs(state[key]):
                path.addRect(lo-.5, 0, hi-lo, state['hyper_ref'].shape[0])
            item.setPath(path)""")
        s = s.replace('CNV region, CNV edge', 'CNV-Core, Full-CNV, CNV edge')
    elif name == 'controls.py':
        start = s.index('    e.cnv_hint = QtWidgets.QLabel(')
        end = s.index('    paint_row = QtWidgets.QHBoxLayout()', start)
        s = s[:start] + '''    e.cnv_hint = QtWidgets.QLabel(L.CORE_DEFINITION + '<br><br>' + L.FULL_DEFINITION)
    e.cnv_info = info_button(e.cnv_hint, 'CNV-Core and Full-CNV Lesion definitions')
    cnv_row = QtWidgets.QHBoxLayout()
    cnv_row.setSpacing(4)
    cnv_row.addWidget(e.lesion_tools.buttons['cnv_core'])
    cnv_row.addWidget(e.lesion_tools.buttons['cnv_full'], 1)
    cnv_row.addWidget(e.cnv_info)
    layout.addLayout(cnv_row)
    layout.addWidget(e.cnv_hint)
    context_row = QtWidgets.QHBoxLayout()
    context_row.addWidget(e.lesion_tools.buttons['cnv_edge'])
    e.show_auto_cnv = QtWidgets.QCheckBox('Show auto-CNV (pink)')
    e.show_auto_cnv.setObjectName('show_auto_cnv')
    e.show_auto_cnv.setChecked(True)
    e.show_auto_cnv.setToolTip('Show or hide the separate octa-auto_CNV overlay in the B-scan and en-face view. Display only; no annotations change.')
    e.show_auto_cnv.toggled.connect(e.redraw_surfaces)
    context_row.addWidget(e.show_auto_cnv)
    layout.addLayout(context_row)
''' + s[end:]
        s = s.replace('CNV region', 'CNV-Core / Full-CNV').replace('marked CNV-Core / Full-CNV', 'union of the marked CNV-Core / Full-CNV regions')
        s = replace(s, "'QToolButton {border-radius:11px; font-weight:bold;}", "'QToolButton {border:1px solid #aabccc; border-radius:11px; padding:0px; font-weight:bold;}")
        # Qt maps ControlModifier to Command on Mac. Use native text throughout the new panel.
        s = replace(s, '    return button\n', '    return button\n', 1)
    elif name == 'label_gui.py':
        s = replace(s, '        dock.setMinimumWidth(300)\n        dock.setMaximumWidth(355)', '        dock.setMinimumWidth(440)\n        dock.setMaximumWidth(485)')
        s = replace(s, '        if self._lesion is not None:', '        if self._lesion is not None and self.show_auto_cnv.isChecked():')
        s = replace(s, "Saved en-face CNV footprint at this native B-scan, projected through the full displayed depth.", "Separate octa-auto_CNV footprint at this native B-scan, projected through the full displayed depth.")
        # Migrate on opening pre-update Mac/local journals through the same authoritative writer.
        s = replace(s, '        self._loading = False\n        self.recompute()', '''        if not self.read_only:
            self.journal.migrate_cnv(self.volume.data['raw_position_branch'][self.row], self.offset, self.pack.images.shape[1])
        self._loading = False
        self.recompute()''')
        s = replace(s, '    @property\n    def events(self):', '''    def migrate_cnv(self, baseline, offset, depth):
        """User-authorized schema migration; never fabricate a stroke or confirmation."""
        kind = L.LEGACY_MAPPING.get(self.data['reviewer_id'])
        if not kind or not self.events or any(e['action'] == L.MIGRATION_ACTION or
                e.get('lesion_definition') == L.DEFINITION_VERSION for e in self.events):
            return False
        before = resolve(self.events, baseline, offset, depth)
        event = dict(id=uuid.uuid4().hex, timestamp=time.time(), action=L.MIGRATION_ACTION,
                     reviewer_id=self.data['reviewer_id'], from_definition=L.LEGACY_VERSION,
                     lesion_definition=L.DEFINITION_VERSION, destination=kind,
                     legacy_region_runs=L.runs(before['lesions']['cnv_region']),
                     reason='User requested lead CNV Region -> CNV-Core; shichu CNV Region -> Full-CNV; opposite category empty.')
        after = resolve(self.events + [event], baseline, offset, depth)
        for key in ('positions', 'trace', 'reliability', 'anatomy', 'approved', 'excluded'):
            if not np.array_equal(before[key], after[key], equal_nan=True):
                raise ValueError('CNV migration must not change layer annotations')
        self.change(event)
        return True

    @property
    def events(self):''')
        s = replace(s, "            proposed['cursor'] = max(0, min(len(proposed['events']), proposed['cursor'] + direction))", """            # The schema transition is an undo floor; original revisions remain in history/archive.
            floor = max((i + 1 for i, ev in enumerate(proposed['events']) if ev['action'] == L.MIGRATION_ACTION), default=0)
            proposed['cursor'] = max(floor, min(len(proposed['events']), proposed['cursor'] + direction))""")
        # Mac labels in all tooltips and buttons without changing physical modifiers.
        s = replace(s, '        build(self)\n', '''        build(self)
        if os.sys.platform == 'darwin':
            for widget in self.body.findChildren(QtWidgets.QWidget):
                widget.setToolTip(widget.toolTip().replace('Ctrl', 'Command').replace('Alt', 'Option'))
                if isinstance(widget, (QtWidgets.QLabel, QtWidgets.QAbstractButton)):
                    widget.setText(widget.text().replace('Ctrl', 'Command').replace('Alt', 'Option'))
''')
    elif name == 'gui.py':
        s = replace(s, 'CNV region: left-drag marks full-depth columns', 'CNV-Core / Full-CNV: left-drag marks each category independently')
        s = replace(s, 'Manual region: purple · edge: pink · dots: gold', 'CNV-Core: purple · Full-CNV: cyan · auto-CNV: pink<br>CNV edge: pale pink · dots: gold')
        if "GESTURES = GESTURES.replace('Ctrl', 'Command')" not in s:
            s = replace(s, 'def configure_v3_app(app):', "import sys\nif sys.platform == 'darwin':\n    GESTURES = GESTURES.replace('Ctrl', 'Command').replace('Alt', 'Option')\n\n\ndef configure_v3_app(app):")
        s = replace(s, "        self.navigator = Navigator('Volume navigator')", "        self.editor.show_auto_cnv.toggled.connect(lambda _: self.update_map())\n        self.navigator = Navigator('Volume navigator')")
        s = replace(s, '            self.navigator.set_annotations(cnv, vessel, onh, edge)', '            self.navigator.set_annotations(cnv if self.editor.show_auto_cnv.isChecked() else np.zeros_like(cnv), vessel, onh, edge)')
        s = replace(s, "Pink outline + light fill: CNV · blue: vessel · green: ONH", "Pink: auto-CNV (independent toggle) · blue: vessel · green: ONH")
    return s

def main():
    changes = []
    for root in ROOTS:
        for name in FILES:
            path = root / REL / name
            old = path.read_text(encoding='utf-8')
            new = transform(name, old)
            compile(new, str(path), 'exec')
            changes.append((root, path, new))
    # Validate every transformation before changing any installed file.
    records = []
    for root, path, new in changes:
        archive_root = ROOT / 'outputs/archived/cnv_gui_before_20260929' if root == ROOT else Path('F:/octa/archived/cnv_gui_before_20260929') / ('mac' if 'Mac_Boundary_Reviewer' in str(root) else 'windows')
        backup = archive_root / path.relative_to(root)
        if backup.exists():
            raise RuntimeError(f'Archive already exists: {backup}')
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        assert hashlib.sha256(backup.read_bytes()).hexdigest() == sha
        path.write_text(new, encoding='utf-8', newline='\n')
        records.append(dict(path=str(path), archive=str(backup), before_sha256=sha,
                            after_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    (ROOT / 'outputs/cnv_distinctions_20260929/code_update.json').write_text(json.dumps(records, indent=2))
    print(f'Archived and updated {len(records)} source files')

if __name__ == '__main__':
    main()
