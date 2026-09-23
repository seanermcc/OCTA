from common import *
from legacy import tensor_inputs
from models import structural_patch
from collections import defaultdict,Counter

def windows(mask,height,width):
    integral=np.pad(mask.astype('int32'),((1,0),(1,0))).cumsum(0).cumsum(1)
    return integral[height:,width:]-integral[:-height,width:]-integral[height:,:-width]+integral[:-height,:-width]

class Sampler:
    def __init__(self,manifest,stats,model):
        self.model=model;self.stats=stats;self.data={};self.pools=defaultdict(lambda:defaultdict(list));self.counts=Counter()
        for r in manifest['records']:
            sid=r['scan_id'];z=npz(r['target_file']['path']);p=z['target'];k=z['known'];h=256 if model==1 else 1
            pc=windows(p,h,256);bc=windows(k&~p,h,256)
            v6=npz(HERE/'cache'/sid/'v6.npz')['mask'].astype(bool)
            hc=windows(v6&k&~p,h,256)
            coords=dict(positive=np.argwhere(pc>0),background=np.argwhere((pc==0)&(bc>0)),hard=np.argwhere((pc==0)&(bc>0)&(hc>0)))
            entry=dict(record=r,target=p,known=k,coords=coords)
            if model==1:entry['input']=tensor_inputs(npz(HERE/'cache'/sid/'enface.npz'),stats,'C')
            else:entry['volume']=np.load(HERE/'cache'/sid/'structural.npy',mmap_mode='r')
            self.data[sid]=entry
            for kind,c in coords.items():
                if len(c):self.pools[r['animal']][kind].append(sid)
        self.animals=sorted(self.pools)
        if any(not self.pools[a]['positive'] or not self.pools[a]['background'] for a in self.animals):raise ValueError('Animal missing eligible positive/background sampling pool')
    def sample(self,rng,kind):
        animal=rng.choice(self.animals);requested=kind
        if not self.pools[animal][kind]:kind='background';self.counts['hard_fallback']+=1
        sid=rng.choice(self.pools[animal][kind]);e=self.data[sid];coords=e['coords'][kind];y,x=coords[rng.integers(len(coords))]
        if self.model==1:
            image=e['input'][:,y:y+256,x:x+256].copy();target=e['target'][y:y+256,x:x+256].copy();known=e['known'][y:y+256,x:x+256].copy()
            if rng.random()<.5:image=image[:,:,::-1].copy();target=target[:,::-1].copy();known=known[:,::-1].copy()
        else:
            image=structural_patch(e['volume'],int(y),int(x),self.stats['structural']);target=e['target'][y,x:x+256].copy();known=e['known'][y,x:x+256].copy()
            if rng.random()<.5:image=image[:,:,::-1].copy();target=target[::-1].copy();known=known[::-1].copy()
            if rng.random()<.5:image=image[::-1].copy()
            image=image*rng.uniform(.95,1.05)+rng.uniform(-.1,.1)
        if kind in ('background','hard'):assert not target.any()
        self.counts['animal:'+animal]+=1;self.counts['scan:'+sid]+=1;self.counts['actual:'+kind]+=1;self.counts['requested:'+requested]+=1
        return np.ascontiguousarray(image,dtype=np.float32),np.ascontiguousarray(target,dtype=np.float32),np.ascontiguousarray(known,dtype=np.float32)
