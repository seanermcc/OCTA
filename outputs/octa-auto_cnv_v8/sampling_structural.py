"""Structural-only sampling: no access to v6, optical projections or thickness."""
from common import *
from models import structural_patch
from collections import defaultdict,Counter

def row_windows(mask):
    sums=np.pad(mask.astype('int32'),((0,0),(1,0))).cumsum(1)
    return sums[:,256:]-sums[:,:-256]

class Sampler:
    def __init__(self,manifest,stats,model):
        assert model==2
        self.stats=stats['structural'];self.data={};self.pools=defaultdict(lambda:defaultdict(list));self.counts=Counter()
        for r in manifest['records']:
            sid=r['scan_id'];z=npz(r['target_file']['path']);p=z['target'];known=z['known']
            positives=row_windows(p);background=row_windows(known&~p)
            coords=dict(positive=np.argwhere(positives>0),background=np.argwhere((positives==0)&(background>0)))
            self.data[sid]=dict(volume=np.load(HERE/'cache'/sid/'structural.npy',mmap_mode='r'),target=p,known=known,coords=coords)
            for kind,positions in coords.items():
                if len(positions):self.pools[r['animal']][kind].append(sid)
        self.animals=sorted(self.pools)
        if any(not self.pools[a]['positive'] or not self.pools[a]['background'] for a in self.animals):raise ValueError('Animal missing structural positive/background pool')
    def sample(self,rng,kind):
        if kind not in ('positive','background'):raise ValueError('Structural model uses only positive/background sampling')
        animal=rng.choice(self.animals);sid=rng.choice(self.pools[animal][kind]);e=self.data[sid]
        coords=e['coords'][kind];row,x=coords[rng.integers(len(coords))]
        image=structural_patch(e['volume'],int(row),int(x),self.stats);target=e['target'][row,x:x+256].copy();known=e['known'][row,x:x+256].copy()
        if rng.random()<.5:image=image[:,:,::-1].copy();target=target[::-1].copy();known=known[::-1].copy()
        if rng.random()<.5:image=image[::-1].copy()
        image=image*rng.uniform(.95,1.05)+rng.uniform(-.1,.1)
        if kind=='background':assert not target.any()
        self.counts['animal:'+animal]+=1;self.counts['scan:'+sid]+=1;self.counts['actual:'+kind]+=1;self.counts['requested:'+kind]+=1
        return np.ascontiguousarray(image,dtype=np.float32),np.ascontiguousarray(target,dtype=np.float32),np.ascontiguousarray(known,dtype=np.float32)
