"""Release the structural fit once every training volume is ready."""
from common import *
def run():
    records=read(HERE/'data/manifest.json')['records'];deadline=time.time()+4*3600
    while True:
        missing=[r['scan_id'] for r in records if not (HERE/'cache'/r['scan_id']/'manifest.json').exists()]
        if not missing:break
        if time.time()>deadline:raise TimeoutError('Structural training cache not ready: '+str(missing))
        time.sleep(5)
    train=[read(HERE/'cache'/r['scan_id']/'manifest.json') for r in records]
    for r,m in zip(records,train):
        assert m['scan_id']==r['scan_id'] and m['native_shape']==[512,1024,512]
    a=np.concatenate([np.asarray(x['normalization_sample']) for x in train]);q=np.percentile(a,[25,50,75])
    stats=read(HERE/'data/normalization_enface.json')
    stats['structural']=dict(center=float(q[1]),scale=float(max((q[2]-q[0])/1.349,.001)),sample='regular 16 B-scan x 8 depth x 8 lateral stride; training volumes only')
    path=HERE/'data/normalization_structural.json'
    if path.exists():assert read(path)==stats
    else:write(path,stats)
    progress('Structural training normalization ready',training_volumes=len(train))
if __name__=='__main__':run()
