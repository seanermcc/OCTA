"""Instrument all sampler reads; only supervision and structural volumes allowed."""
from common import *
import sampling_structural as ss
def run():
    target=np.zeros((512,512),bool);target[100:130,100:130]=True
    volume=np.broadcast_to(np.arange(1024,dtype=np.float32)[None,:,None],(512,1024,512))
    accessed=[];original_npz=ss.npz;original_load=np.load
    def labels(path):
        assert str(path)=='SYNTHETIC_TARGET';accessed.append('supervision')
        return dict(target=target,known=np.ones_like(target))
    def load(path,**kw):
        assert Path(path).name=='structural.npy';accessed.append('structural_volume');return volume
    try:
        ss.npz=labels;np.load=load
        sampler=ss.Sampler(dict(records=[dict(scan_id='SYNTHETIC_ONLY',animal='TEST',target_file=dict(path='SYNTHETIC_TARGET'))]),dict(structural=dict(center=0,scale=1024)),2)
        rng=np.random.default_rng(267)
        for kind in ['positive','background']*10:
            image,y,k=sampler.sample(rng,kind)
            assert image.shape==(5,1024,256) and y.shape==k.shape==(256,)
            assert (image[:,-1,:]>image[:,0,:]).all(), 'Axial orientation reversed'
        assert accessed==['supervision','structural_volume']
    finally:ss.npz=original_npz;np.load=original_load
    write(HERE/'verification/structural_isolation.json',dict(passed=True,read_types=accessed,input_shape=[5,1024,256],no_axial_augmentation=True,no_v6_optical_thickness_or_candidate_reads=True))
    print('Structural sampler read isolation and axial augmentation checks passed',flush=True)
if __name__=='__main__':run()
