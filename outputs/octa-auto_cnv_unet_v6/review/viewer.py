"""Original B/C prediction ratings with separate, explicitly attributed error evidence."""
from v5_editor import *
from loader import SampleCache,KEYS,ReviewStore
from datetime import datetime,timezone

class Window(Window):
    def __init__(self,start=0,manual=False,autoload=True,review_directory=None,cache=None):
        self.model_key='B_267';self.paused=False;self.session_id=uuid.uuid4().hex
        self.review_directory=Path(review_directory or REVIEW)
        self.session_directory=self.review_directory/'sessions'
        self.cache=cache or SampleCache();self.pending_future=None
        self.session_events=[];self.session_seconds={};self.last_activity=time.monotonic();self.last_flush=time.monotonic()
        self.review_clock_started=False;self.comparison_masks={};self.timing_comparison='Comparison off'
        self._records={};self._completion={}
        super().__init__(start,manual,False)
        self.setWindowTitle('CNV review · original B / C predictions · v6');self.resize(1680,1060)
        self.addToolBarBreak();bar=self.addToolBar('Models and review queue');bar.setMovable(False)
        bar.addWidget(W.QLabel(' Original model '));self.experiment=W.QComboBox();self.experiment.addItems(['B','C']);bar.addWidget(self.experiment)
        bar.addWidget(W.QLabel(' Seed '));self.seed=W.QComboBox();self.seed.addItems(['267','268','269']);bar.addWidget(self.seed)
        self.experiment.currentTextChanged.connect(self.model_changed);self.seed.currentTextChanged.connect(self.model_changed)
        self.compare=W.QComboBox();self.compare.addItems(['Comparison off','B vs C at this seed','Seeds within this experiment','All six disagreements']);bar.addWidget(self.compare)
        self.compare.currentIndexChanged.connect(self.comparison_changed)
        self.filter=W.QComboBox();self.filter.addItems(['All acquisitions','Disagreements','Unrated at this seed','Possible misses (reference proxy)','Fixed random sample','No suggestions (any model)','Low support / artifacts / edges','No suggestions (all six)']);bar.addWidget(self.filter)
        self.filter.currentIndexChanged.connect(self.apply_filter)
        self.pause=bar.addAction('Pause timer');self.pause.setCheckable(True);self.pause.toggled.connect(self.pause_changed)
        self.legend=W.QLabel('Orange: original predictions · green: human edits · cyan: optional manual reference · magenta: predicted by only some compared models, not correctness')
        self.legend.setWordWrap(True);self.centralWidget().layout().insertWidget(0,self.legend)
        side=self.region_list.parentWidget();side.setMinimumWidth(315);side.setMaximumWidth(390);sv=side.layout()
        self.rating_box=W.QGroupBox('Rate ORIGINAL suggestions');ratings=W.QVBoxLayout(self.rating_box)
        self.rating_seed=W.QLabel();ratings.addWidget(self.rating_seed)
        self.rating_checks={}
        for ex in 'BC':
            for value in ('acceptable','unacceptable'):
                box=W.QCheckBox(f'{ex} {value}');self.rating_checks[(ex,value)]=box;ratings.addWidget(box)
                box.toggled.connect(lambda checked,e=ex,v=value:self.rating_changed(e,v,checked))
        guide=W.QLabel('Accept adequate detection and extent. Reject meaningful misses, false suggestions or gross extent errors. Skip cosmetic edits. Leave unset if undecided.');guide.setWordWrap(True);guide.setMinimumHeight(58);ratings.addWidget(guide)
        self.rating_progress=W.QLabel();self.rating_progress.setWordWrap(True);ratings.addWidget(self.rating_progress)
        sv.insertWidget(0,self.rating_box)
        self.manual_check=W.QCheckBox('Show manual annotations');self.manual_check.setChecked(False)
        self.manual_check.setToolTip('Read-only references; hiding them never means negative tissue.')
        sv.insertWidget(1,self.manual_check);self.manual_check.toggled.connect(self.manual_changed)
        self.auto_check.setText('Show original suggestions')
        self.attribution=W.QComboBox();self.attribution.addItems(['Miss: displayed model only','Miss: both B and C at this seed'])
        sv.addWidget(self.attribution)
        self.confirm_miss=W.QPushButton('Confirm missed CNV');sv.addWidget(self.confirm_miss);self.confirm_miss.clicked.connect(self.confirm_missed)
        self.correct_button=W.QPushButton('Confirm gross outline correction');sv.addWidget(self.correct_button);self.correct_button.clicked.connect(self.confirm_correction)
        self.correct_button.setToolTip('Applies to the selected suggestion’s own model and seed; cosmetic edits need no rejection.')
        self.notes.setMaximumHeight(50);self.region_list.setMinimumHeight(80);self.region_list.setMaximumHeight(110)
        self.rating_box.setFixedHeight(275)
        for position,widget in enumerate((self.attribution,self.confirm_miss,self.correct_button),2):
            sv.removeWidget(widget);sv.insertWidget(position,widget)
        sv.setSizeConstraint(W.QLayout.SizeConstraint.SetMinimumSize)
        side.setParent(None);scroll=W.QScrollArea();scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(340);scroll.setMaximumWidth(415);scroll.setWidget(side)
        self.top.insertWidget(2,scroll);self.top.setSizes([600,600,350])
        self.scan_choice.setEditable(True);self.scan_choice.setInsertPolicy(W.QComboBox.InsertPolicy.NoInsert)
        self.scan_choice.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        # Keep editing available, with inspecting/rating and explicit misses/removals first.
        for toolbar in self.findChildren(W.QToolBar):
            for action in toolbar.actions():
                if action.text()=='Add CNV':action.setText('Add missed CNV')
                elif action.text()=='Remove':action.setText('Delete false suggestion')
                elif action.text()=='Keep CNV':action.setText('Confirm outline')
                elif action.text()=='Finish scan':action.setText('Finish this review')
        self.poll=Q.QTimer(self);self.poll.setInterval(50);self.poll.timeout.connect(self.poll_load)
        self.refresh_scan_labels();self.sync_ratings()
        W.QApplication.instance().installEventFilter(self)
        if autoload:Q.QTimer.singleShot(0,lambda:self.load_scan(start))

    def untouched_manual(self):return []  # References are never list items or editable regions.

    def visible_regions(self):
        if not self.store:return []
        return [(i,r) for i,r in enumerate(self.store.regions)
            if (not r.seed_ids or r.id.split(':')[0]==self.model_key)
            and (r.decision!='rejected' or self.show_removed.isChecked())
            and (self.auto_check.isChecked() or not r.seed_ids or self.store.persistent(r))]

    def displayed(self):
        if not self.store or not self.auto_check.isChecked():return []
        return [self.store.output(k)['source'] for k in dict.fromkeys([self.model_key,*self.comparison_masks])]

    def log_event(self,action,**details):
        self.session_events.append(dict(action=action,at=datetime.now(timezone.utc).isoformat(),
            scan_id=self.scan.scan_id if self.scan else None,model=self.model_key,
            comparison=self.compare.currentText() if hasattr(self,'compare') else 'off',
            displayed_outputs=self.displayed(),**details))

    def eventFilter(self,obj,event):
        if event.type() in (Q.QEvent.Type.MouseButtonPress,Q.QEvent.Type.KeyPress,Q.QEvent.Type.Wheel):
            now=time.monotonic()
            if not self.review_clock_started:self.previous_tick=now
            self.review_clock_started=True;self.last_activity=now
        elif event.type()==Q.QEvent.Type.MouseMove and self.review_clock_started:self.last_activity=time.monotonic()
        return super().eventFilter(obj,event)

    def record_time(self):
        now=time.monotonic();dt=min(now-self.previous_tick,2.)
        if self.scan is not None and self.review_clock_started and self.isActiveWindow() and not self.loading and not self.paused and now-self.last_activity<60:
            self.review_seconds+=dt;key=f'{self.scan.scan_id}/{self.model_key}/{self.timing_comparison}'
            self.session_seconds[key]=self.session_seconds.get(key,0.)+dt
        self.previous_tick=now
        if now-self.last_flush>=10:
            try:self.flush_session()
            except OSError as exc:
                self.last_flush=now;self.statusBar().showMessage(f'Session log not saved: {exc}. Work remains in memory.')

    def flush_session(self):
        if not self.session_events and not self.session_seconds:return
        write(self.session_directory/f'{self.session_id}.json',dict(session=self.session_id,events=self.session_events,
            active_seconds_by_scan_and_model=self.session_seconds,
            clock='First input, focus, unpaused, <60 seconds idle; capped 2 second intervals; loading and prefetch excluded',
            interpretation='Observed browsing duration, not model performance or time saved.'))
        self.last_flush=time.monotonic()

    def pause_changed(self,value):
        self.record_time();self.paused=value;self.log_event('pause' if value else 'resume');self.previous_tick=time.monotonic()

    def queue_after(self,index):
        return [self.visits[i]['scan_id'] for i in range(index+1,len(self.visits))
            if not self.scan_choice.view().isRowHidden(i) and self._completed(self.visits[i]['scan_id'])][:2]

    def _completed(self,sid):
        if sid not in self._completion:
            p=HERE/'records'/f'{sid}.json';self._completion[sid]=p.exists() and read(p).get('status')=='completed'
        return self._completion[sid]

    def load_scan(self,index):
        if not 0<=index<len(self.visits):return
        sid=self.visits[index]['scan_id']
        if not self._completed(sid):self.statusBar().showMessage('Inference unavailable; see all_samples/scan_status.csv.');return
        if not self.save_all():return
        self.record_time();self.flush_session();self.pending=index;self.loading=True
        self.centralWidget().setEnabled(False);self.load_started=time.perf_counter()
        self.cache.plan([sid,*self.queue_after(index)])
        self.pending_future=self.cache.request(sid);self.poll.start()
        self.statusBar().showMessage('Loading native images and frozen predictions…')

    def poll_load(self):
        if not self.pending_future or not self.pending_future.done():return
        future=self.pending_future;self.pending_future=None;self.poll.stop()
        try:
            scan=future.result();store=ReviewStore(self.review_directory/'regions',scan,self.model_key)
            self.loaded((scan,store));self.statusBar().showMessage(f'Loaded in {time.perf_counter()-self.load_started:.2f} s · rate original B/C suggestions at this seed')
        except Exception as exc:
            self.load_failed(f'{type(exc).__name__}: {exc}')

    def loaded(self,result):
        self.comparison_masks={};self.model_key=result[1].model
        super().loaded(result)
        # Loading never starts the human clock, including prefetched acquisitions.
        self.review_clock_started=False;self.previous_tick=time.monotonic()
        self.last_activity=time.monotonic();self.attribution.setCurrentIndex(0)
        self.log_event('opened acquisition');self.comparison_changed();self.refresh_scan_labels();self.schedule_prefetch()
        self.tool_hint.setText('Inspect predictions, rate B/C, delete false suggestions or add a clear miss. Esc: inspect.')

    def schedule_prefetch(self):
        if not self.scan:return
        next_ids=self.queue_after(self.index);self.cache.plan([self.scan.scan_id,*next_ids])
        for sid in next_ids:self.cache.request(sid,prefetch=True)

    def step_scan(self,step):
        index=self.index+step
        while 0<=index<len(self.visits):
            if not self.scan_choice.view().isRowHidden(index) and self._completed(self.visits[index]['scan_id']):self.load_scan(index);return
            index+=step
        self.statusBar().showMessage('End of the selected review queue.')

    def model_changed(self,*args):
        desired=self.experiment.currentText()+'_'+self.seed.currentText()
        if desired==self.model_key:return
        if self.loading or not self.save_all():
            ex,seed=self.model_key.split('_')
            for widget,value in ((self.experiment,ex),(self.seed,seed)):
                widget.blockSignals(True);widget.setCurrentText(value);widget.blockSignals(False)
            return
        self.record_time()
        if self.store:self.store.switch(desired)
        self.model_key=desired;self.selected=-1;self.reference=-1;self.attribution.setCurrentIndex(0)
        self.comparison_changed();self.sync_ratings()
        if self.store:self.refresh_regions();self.log_event('switched model or seed')
        if self.filter.currentIndex()==2:self.apply_filter(navigate=False)

    def comparison_changed(self,*args):
        self.record_time();self.comparison_masks={};self.timing_comparison=self.compare.currentText()
        if self.store:
            ex,seed=self.model_key.split('_');mode=self.compare.currentIndex()
            keys=[('C' if ex=='B' else 'B')+'_'+seed] if mode==1 else [f'{ex}_{s}' for s in (267,268,269)] if mode==2 else KEYS if mode==3 else []
            self.comparison_masks={k:self.store.output(k)['mask'] for k in keys if k!=self.model_key}
            self.log_event('comparison display');self.render_maps()

    def suggestions_changed(self,visible):
        super().suggestions_changed(visible)
        if self.store:self.log_event('suggestions displayed',visible=visible)

    def manual_changed(self,value):
        if self.store:self.render_maps();self.log_event('manual overlay displayed',visible=value)

    def render_maps(self):
        super().render_maps()
        if self.scan is None:return
        for canvas in (self.structural,self.second):
            if self.auto_check.isChecked():self.mask_overlay(canvas,self.store.proposal_mask,'#ffbb55')
            if self.manual_check.isChecked():
                self.mask_overlay(canvas,self.scan.manual_mask,'#4ce0ff')
                for attr,color in (('reference_uncertain','#b9b5ff'),('reference_removed','#92969c')):
                    mask=getattr(self.scan,attr,None)
                    if mask is not None:self.mask_overlay(canvas,mask,color)
            if self.comparison_masks and self.auto_check.isChecked():
                stack=np.stack([self.store.proposal_mask,*self.comparison_masks.values()]);different=stack.any(0)&~stack.all(0)
                self.mask_overlay(canvas,different,'#ff55df')

    def sync_ratings(self):
        if not hasattr(self,'rating_checks'):return
        seed=self.seed.currentText();self.rating_seed.setText(f'Seed {seed} · matching B / C outputs')
        ratings=self.store.ratings if self.store else {}
        for (ex,value),box in self.rating_checks.items():
            box.blockSignals(True);box.setChecked(ratings.get(f'{ex}_{seed}',{}).get('value')==value);box.blockSignals(False)
        n=sum(ratings.get(f'{ex}_{seed}',{}).get('value') is not None for ex in 'BC')
        total=sum(v.get('value') is not None for v in ratings.values())
        self.rating_progress.setText(f'Model ratings: {n}/2 at this seed · {total}/6 for acquisition\nUnset = unreviewed. Each checkbox can be cleared.')

    def rating_changed(self,ex,value,checked):
        if not self.store or self.loading:self.sync_ratings();return
        key=f'{ex}_{self.seed.currentText()}'
        if not checked and self.store.ratings.get(key,{}).get('value')!=value:return
        self.checkpoint();self.store.rate(key,value if checked else None,self.displayed());self.edited();self.save_all()

    def snapshot(self):
        return copy.deepcopy((self.store.regions,self.store.scan_review,self.store.ratings,self.store.active_error_ids,self.selected))

    def checkpoint(self):
        self.undo_stack.append(self.snapshot());self.redo_stack.clear()
        if len(self.undo_stack)>40:self.undo_stack.pop(0)

    def history(self,source,target):
        if self.store is None or not source:return
        target.append(self.snapshot());before=copy.deepcopy(self.store.ratings);old_errors=list(self.store.active_error_ids)
        regions,state,ratings,errors,selected=source.pop()
        self.store.regions=regions;self.store.scan_review=state;self.store.ratings=ratings;self.store.active_error_ids=errors
        uid=regions[selected].id if 0<=selected<len(regions) else None
        self.store.switch(self.model_key);self.selected=next((i for i,r in enumerate(self.store.regions) if r.id==uid),-1);self.reference=-1
        self.store.event('undo' if source is self.undo_stack else 'redo',ratings_before=before,ratings_after=ratings,
            active_errors_before=old_errors,active_errors_after=errors)
        self.refresh_regions();self.save_all()

    def ensure_region(self):
        self.reference=-1;r=super().ensure_region()
        if r.origin=='hand drawn in v5':r.origin='hand drawn in v6 original prediction review'
        return r

    def add_cnv(self):
        super().add_cnv()
        self.tool_hint.setText('Paint the missed CNV, choose its model attribution, then Confirm missed CNV. Esc: inspect.')

    def error_keys(self):
        seed=self.seed.currentText()
        return [f'{ex}_{seed}' for ex in 'BC'] if self.attribution.currentIndex()==1 else [self.model_key]

    def stroke(self,points,operation):
        before=self.current_region();was_rejected=bool(before and before.decision=='rejected')
        super().stroke(points,operation);r=self.current_region()
        if r and points and r.decision=='rejected' and r.seed_ids and not was_rejected:
            self.store.error('false suggestion',r,[r.id.split(':')[0]],self.displayed());self.refresh_regions();self.save_all()

    def remove(self):
        r=self.current_region()
        if r is None or r.decision=='rejected':return
        super().remove()
        if r.seed_ids:self.store.error('false suggestion',r,[r.id.split(':')[0]],self.displayed())
        else:self.store.event('human draft/lesion removed',region_id=r.id)
        self.refresh_regions();self.save_all()

    def classify(self,category):
        r=self.current_region()
        if r is None:return
        if category=='Full Lesion' and not r.seed_ids and r.origin=='hand drawn in v6 original prediction review':
            self.confirm_missed();return
        super().classify(category)
        self.store.event('outline confirmation' if category=='Full Lesion' else 'uncertain region',region_id=r.id,
            model=self.model_key,changes_model_rating=False)
        self.save_all()

    def confirm_missed(self):
        r=self.current_region()
        if r is None or r.seed_ids or not r.mask.any():
            self.statusBar().showMessage('Add and paint a missed CNV first; select its human footprint.');return
        keys=self.error_keys();footprint=r.record()['runs']
        keys=[k for k in keys if not any(e['id'] in self.store.active_error_ids and e['action']=='missed lesion'
            and e.get('region_id')==r.id and e.get('acquisition_model')==k and e['footprints']['human_runs']==footprint for e in self.store.review_events)]
        if not keys:return
        self.checkpoint();r.category='Full Lesion';r.decision='approved';r.event('explicit missed CNV confirmation',models=keys)
        self.store.error('missed lesion',r,keys,self.displayed());self.edited();self.save_all()

    def confirm_correction(self):
        r=self.current_region()
        if r is None or not r.seed_ids or np.array_equal(r.mask,r.core):
            self.statusBar().showMessage('Edit a suggestion’s outline first, then explicitly confirm the gross correction.');return
        self.checkpoint();r.category='Full Lesion';r.decision='approved';r.event('explicit gross outline correction')
        self.store.error('gross outline correction',r,[r.id.split(':')[0]],self.displayed());self.edited();self.save_all()

    def update_summary(self):
        if self.store is None:return
        super().update_summary();self.sync_ratings()
        human=[r for r in self.store.regions if self.store.persistent(r)]
        drafts=sum(r.decision=='unreviewed' for r in human)
        self.summary.setText(f'Lesion edits: {len(human)} saved/draft regions · {drafts} unresolved\n'
            +('Review finished (ratings may be unset)' if self.store.scan_review.get('rating_review_finished') else 'Review in progress')
            +'\nNo whole-field training labels are created.')

    def save_all(self):
        if self.store is None:return True
        try:
            self.record_time();self.store.save();self.flush_session();self.update_summary();self.refresh_scan_labels();return True
        except Exception as exc:W.QMessageBox.critical(self,'Could not save; work remains in memory',str(exc));return False

    def finish_scan(self,confirmed=False):
        if self.store is None:return
        self.checkpoint()
        self.store.scan_review=dict(status='review_finished',rating_review_finished=True,whole_field_checked=False,
            reviewed_absence=False,at=datetime.now(timezone.utc).isoformat(),unreviewed_tissue='unknown')
        self.store.event('finished rating review',unset_ratings_allowed=True,drafts_allowed=True,whole_field_labels=False)
        self.save_all();self.refresh_regions()

    def read_review(self,sid):
        if self.store and self.store.scan.scan_id==sid:
            return dict(model_ratings=self.store.ratings,scan_review=self.store.scan_review)
        p=self.review_directory/'regions'/f'{sid}_regions.json'
        stamp=p.stat().st_mtime_ns if p.exists() else None
        if self._records.get(sid,(None,None))[0]!=stamp or sid not in self._records:self._records[sid]=(stamp,read(p) if stamp else {})
        return self._records[sid][1]

    def refresh_scan_labels(self):
        if not hasattr(self,'scan_choice'):return
        for i,r in enumerate(self.visits):
            data=self.read_review(r['scan_id']);n=sum(v.get('value') is not None for v in data.get('model_ratings',{}).values())
            state=f'{n}/6 ratings' if self._completed(r['scan_id']) else 'inference unavailable'
            day=str(r.get('days_post_laser') if r.get('days_post_laser') is not None else r['day_label'])
            self.scan_choice.setItemText(i,f"{r['animal']} {r['eye']} · {r['session_date']} {day} · repeat {r['scan_no']} {r['acq_time']} · {state}")
            self.scan_choice.setItemData(i,r['scan_id'],Qt.ItemDataRole.ToolTipRole)

    def apply_filter(self,*args,navigate=True):
        queue_path=HERE/'comparison/review_queue.json';queue=read(queue_path) if queue_path.exists() else []
        qmap={r['scan_id']:r for r in queue};mode=self.filter.currentIndex();first=None
        for i,r in enumerate(self.visits):
            sid=r['scan_id'];q=qmap.get(sid,{})
            ratings=self.read_review(sid).get('model_ratings',{})
            unrated=any(ratings.get(f'{ex}_{self.seed.currentText()}',{}).get('value') is None for ex in 'BC')
            show=mode==0 or mode==1 and q.get('disagreement_pixels',0)>0 or mode==2 and unrated or mode==3 and q.get('possible_misses_proxy',0)>0 or mode==4 and q.get('fixed_random_sample',False) or mode==5 and q.get('any_model_no_suggestions',False) or mode==6 and q.get('support_artifact_edge_priority',False) or mode==7 and q.get('all_models_no_suggestions',False)
            self.scan_choice.view().setRowHidden(i,not show)
            if show and self._completed(sid) and first is None:first=i
        active_index=self.pending if self.loading else self.index
        if navigate and first is not None and (self.scan is None and not self.loading or self.scan_choice.view().isRowHidden(active_index)):
            self.load_scan(first)
        elif self.loading:
            self.cache.plan([self.visits[self.pending]['scan_id'],*self.queue_after(self.pending)])
        else:self.schedule_prefetch()

    def closeEvent(self,event):
        if self.save_all():
            self.poll.stop();self.cache.close();self.flush_session();self.tick.stop()
            W.QApplication.instance().removeEventFilter(self);event.accept()
        else:event.ignore()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--scan');parser.add_argument('--model',choices=KEYS,default='B_267')
    parser.add_argument('--review-directory',type=Path);parser.add_argument('--verify-launch',action='store_true');args=parser.parse_args()
    app=W.QApplication([]);gui.configure_app(app)
    # Avoid two simultaneous writers to the same active review root.
    directory=args.review_directory or (REVIEW/'verification/launcher_records' if args.verify_launch else REVIEW);dest(directory/'.review.lock')
    lock=Q.QLockFile(str(directory/'.review.lock'));lock.setStaleLockTime(0)
    if not lock.tryLock(0):W.QMessageBox.information(None,'Review already open','A review window already uses this record directory.');return 1
    visits=selected();start=next((i for i,r in enumerate(visits) if r['scan_id']==args.scan),0)
    window=Window(start,autoload=False,review_directory=directory);ex,seed=args.model.split('_')
    window.experiment.setCurrentText(ex);window.seed.setCurrentText(seed)
    if args.verify_launch:
        def verify_launch():
            assert not window.manual_check.isChecked() and not window.store.ratings
            assert len(window.rating_checks)==4 and not window.store.path.exists()
            window.fit_all();window.grab().save(str(REVIEW/'verification/launcher.png'))
            write(REVIEW/'verification/launcher.json',dict(passed=True,scan_id=window.scan.scan_id,
                model=window.model_key,manual_default_off=True,isolated_records=True,human_evaluation=False))
            window.close();app.quit()
        window.ready.connect(lambda:Q.QTimer.singleShot(1000,verify_launch))
        Q.QTimer.singleShot(90000,app.quit)
    window.show();Q.QTimer.singleShot(0,lambda:window.load_scan(start));return app.exec()

if __name__=='__main__':raise SystemExit(main())
