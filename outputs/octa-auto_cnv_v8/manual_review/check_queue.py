"""Read every queued optical provider without creating annotation records."""
from common import *
from loader import load_scan

if __name__=='__main__':
    results=[]
    for a in read(HERE/'queue/queue.json')['acquisitions']:
        start=time.monotonic();scan=load_scan(a)
        results.append(dict(scan_id=a['scan_id'],shape=list(scan.images.shape),
            projection_error_db=scan.alignment_max_error_db,seconds=round(time.monotonic()-start,2)))
        print(f'{len(results)}/30 {a["scan_id"]}: valid',flush=True)
        del scan
    atomic(HERE/'verification/all_providers.json',dict(passed=True,at=now(),acquisitions=results))
