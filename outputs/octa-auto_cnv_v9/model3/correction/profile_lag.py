"""Read-only timing of saved-review progress and isolated report generation."""
from common import *
from review_store import progress
import cProfile, pstats, io

def main():
    queue=read(HERE/'queue/queue.json')['acquisitions']
    profile=cProfile.Profile();profile.enable();start=time.perf_counter()
    result=progress(queue);progress_s=time.perf_counter()-start
    from measure import run
    start=time.perf_counter();summary=run(output=HERE/'verification/performance_baseline/reports')
    report_s=time.perf_counter()-start;profile.disable()
    out=io.StringIO();pstats.Stats(profile,stream=out).sort_stats('cumtime').print_stats(18)
    destination(HERE/'verification/performance_baseline/profile.txt').write_text(out.getvalue())
    data=dict(progress_seconds=progress_s,report_seconds=report_s,progress=result,
              saved_scans=sum((HERE/'review/regions'/(a['scan_id']+'.json')).exists() for a in queue))
    atomic(HERE/'verification/performance_baseline/timing.json',data)
    print(json.dumps(data),flush=True);print(out.getvalue(),flush=True)

if __name__=='__main__':main()
