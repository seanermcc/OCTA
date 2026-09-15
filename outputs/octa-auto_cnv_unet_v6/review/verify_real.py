"""Measured recovery, alignment, prefetch and GUI checks on isolated review records."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from common import *
import tempfile,importlib.util,gc,shutil
from loader import load_data,SampleCache,memory_bytes,ReviewStore
from viewer import Window,W,Q,gui

def run():
    app=W.QApplication.instance() or W.QApplication([]);gui.configure_app(app)
    def fail_dialog(parent,title,message,*args):raise RuntimeError(title+': '+message)
    W.QMessageBox.critical=fail_dialog
    visits=selected();chosen=[next(r for r in visits if r['scan_id']==sid) for sid in
        ('TS267_OD_2025-02-19_D0_s02_112013','TS267_OD_2025-04-16_D56_s01_100746')]
    chosen.append(next(r for r in visits if read(HERE/'inputs'/f"{r['scan_id']}.json").get('new_acquisition_upstream')))
    spec=importlib.util.spec_from_file_location('baseline_batch',HERE/'batch.py');baseline=importlib.util.module_from_spec(spec);spec.loader.exec_module(baseline)
    # Baseline may announce recovery as batch progress. Benchmark must not write any batch artifacts.
    baseline.progress=lambda *a,**k:None
    results=[]
    with tempfile.TemporaryDirectory(dir=dest(REVIEW/'verification/real_records/.keep').parent) as tmp:
        directory=Path(tmp)
        for j,r in enumerate(chosen):
            sid=r['scan_id'];print('Baseline:',sid,flush=True)
            assert (HERE/'inputs'/f'{sid}.npz').exists()
            t=time.perf_counter();old,meta,images=baseline.recover_inputs(r,verify_all=False);seconds=time.perf_counter()-t
            t=time.perf_counter();scan=load_data(sid);uncached=time.perf_counter()-t
            for attr,key in (('structural_enface','optical'),('octa','optical')):
                np.testing.assert_array_equal(getattr(scan,attr),old[key][0 if attr=='structural_enface' else 1])
            np.testing.assert_array_equal(scan.thickness,old['thickness_um'])
            np.testing.assert_array_equal(scan.endpoints,old['endpoints_crop_px'])
            assert np.array_equal(scan.images,images)
            del old,images;gc.collect()
            index=next(i for i,v in enumerate(visits) if v['scan_id']==sid)
            store=ReviewStore(directory/str(j)/'regions',scan)
            cache=SampleCache();w=Window(index,autoload=False,review_directory=directory/str(j),cache=cache)
            # Capture and exercise real GUI without scheduling unrelated sources during timing.
            w.schedule_prefetch=lambda:None;w.loaded((scan,store));w.show();app.processEvents();w.fit_all()
            w.navigate(213,347,False);assert w.row_spin.value()==213 and w.col==347
            w.compare.setCurrentIndex(1);w.manual_check.setChecked(False);app.processEvents()
            w.grab().save(str(dest(REVIEW/'verification'/f'real_{j}_original.png')))
            w.manual_check.setChecked(True);app.processEvents();w.grab().save(str(dest(REVIEW/'verification'/f'real_{j}_manual.png')))
            w.mode.setCurrentIndex(1);w.layer.setCurrentIndex(2)
            top,bottom=w.displayed_boundaries;np.testing.assert_allclose((bottom-top)*1.12,scan.thickness[2,213],equal_nan=True)
            w.grab().save(str(dest(REVIEW/'verification'/f'real_{j}_bscan.png')))
            t=time.perf_counter()
            for ex in 'BC':
                for seed in ('267','268','269'):w.experiment.setCurrentText(ex);w.seed.setCurrentText(seed)
            switches=time.perf_counter()-t
            assert not store.ratings and not store.path.exists();assert all(kind=='region' for kind,k in w.entries)
            w.rating_checks['B','acceptable'].setChecked(True);w.rating_checks['C','unacceptable'].setChecked(True)
            w.add_cnv();w.diameter.setValue(3);w.stroke([(16,16),(27,16),(27,27),(16,27),(16,16)],'cnv_brush_add')
            w.confirm_missed();uid=w.current_region().id;w.finish_scan();w.close();app.processEvents()
            reopened=ReviewStore(directory/str(j)/'regions',scan,'B_267')
            assert reopened.ratings['B_269']['value']=='acceptable' and reopened.ratings['C_269']['value']=='unacceptable'
            assert any(x.id==uid for x in reopened.regions) and not reopened.scan_review['whole_field_checked']
            results.append(dict(scan_id=sid,old_uncached_recovery_seconds=seconds,new_uncached_recovery_seconds=uncached,
                six_switches_including_render_seconds=switches,identical_native_images_and_maps=True,
                estimated_cache_MiB=memory_bytes(scan)/1024**2,isolated_save_reopen=True))
            print(results[-1],flush=True)
            w.deleteLater();app.processEvents();del scan,store,reopened,w;gc.collect()
            fixture=(directory/str(j)).resolve();assert fixture.is_relative_to(directory.resolve());shutil.rmtree(fixture)
        # Real asynchronous rolling queue: current acquisition followed by the next two in a filtered order.
        queue=[r['scan_id'] for r in chosen];cache=SampleCache();cache.plan(queue)
        ticks=[];timer=Q.QTimer();timer.setInterval(25);timer.timeout.connect(lambda:ticks.append(time.perf_counter()));timer.start()
        before=set(directory.rglob('*_regions.json'))
        t=time.perf_counter();first=cache.request(queue[0])
        while not first.done():app.processEvents();time.sleep(.005)
        first.result();current_seconds=time.perf_counter()-t
        futures=[cache.request(sid,prefetch=True) for sid in queue[1:]]
        start=time.perf_counter()
        while any(f is not None and not f.done() for f in futures):app.processEvents();time.sleep(.005)
        prefetch_seconds=time.perf_counter()-start
        for f in futures:
            if f is not None:f.result()
        warmed=[]
        for sid in queue:
            t=time.perf_counter();scan=cache.request(sid).result();warmed.append(dict(scan_id=sid,lookup_seconds=time.perf_counter()-t))
        assert before==set(directory.rglob('*_regions.json'))
        timer.stop();stats=copy_stats=dict(cache.stats);cached=list(cache.cache)
        gaps=np.diff(ticks)
        cache.close()
        report=dict(passed=True,human_evaluation=False,measurements=results,
            method='One before/after pass in this process; OS disk caches are uncontrolled. Switch times include rendering, source lookup times do not.',
            prefetch=dict(filtered_queue=queue,current_load_seconds=current_seconds,next_two_seconds=prefetch_seconds,
                cached_acquisitions=cached,warm_lookups=warmed,stats=stats,qt_event_ticks=len(ticks),
                max_event_tick_gap_seconds=float(gaps.max()) if len(gaps) else None,no_review_records_created=True))
        write(REVIEW/'verification/real_verification.json',report);print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':run()
