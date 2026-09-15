"""Release integrity checks and focused regression tests beyond the training preflight."""
from common import *
from dataset import split,tensor_inputs
from train import Sampler,configure
from model import UNet,masked_loss
from metrics import score
import torch
import copy
import unittest
from io import BytesIO

class MoreContracts(unittest.TestCase):
    def test_augmentations_keep_masks_aligned_and_resume(self):
        mask=np.zeros((512,512),bool);mask[130:190,180:240]=True
        d=dict(target=mask,known=np.ones_like(mask),input=np.stack([mask,mask,mask]).astype('float32'))
        sampler=Sampler([d],267);state=copy.deepcopy(sampler.rng.bit_generator.state)
        batch,coords=sampler.batch(4)
        np.testing.assert_array_equal(batch[0][:,2].astype(bool),batch[1])
        sampler.rng.bit_generator.state=state;again,again_coords=sampler.batch(4)
        for a,b in zip(batch,again):np.testing.assert_array_equal(a,b)
        self.assertEqual(coords,again_coords)
    def test_instances_merges_and_ignored_borders(self):
        a=np.zeros((32,32),bool);b=a.copy();a[5:12,5:12]=True;b[5:12,16:23]=True
        t=a|b;k=np.ones_like(t);pred=t.copy();pred[7:9,12:16]=True
        d=dict(known=k,target=t,instances=np.stack([a,b]),availability=np.ones((8,32,32),bool),shadow=~k,vessel=~k,low_signal=~k)
        s,detail=score(pred,d,True)
        self.assertEqual(s['merges'],1);self.assertEqual(s['matched'],1);self.assertEqual(s['additions_proxy'],1)
        d['known'][4:6,5:12]=False;d['target'] &= d['known'];d['instances'] &= d['known'][None]
        s,detail=score(a,d,True)
        self.assertIsNone(detail['matches'][0]['border_mean_um'])
    def test_optimizer_roundtrip(self):
        configure(71);net=UNet(2);optimizer=torch.optim.AdamW(net.parameters(),lr=.001,weight_decay=.0001)
        x=torch.randn(2,2,32,32);t=torch.rand(2,32,32)>.8;k=torch.ones_like(t)
        def step(n,o):
            o.zero_grad();loss=masked_loss(n(x),t,k);loss.backward();o.step()
        step(net,optimizer)
        stream=BytesIO();torch.save(dict(model=net.state_dict(),optimizer=optimizer.state_dict()),stream);stream.seek(0)
        ck=torch.load(stream,weights_only=False);other=UNet(2);other.load_state_dict(ck['model']);op=torch.optim.AdamW(other.parameters());op.load_state_dict(ck['optimizer'])
        step(net,optimizer);step(other,op)
        for a,b in zip(net.parameters(),other.parameters()):torch.testing.assert_close(a,b,rtol=0,atol=0)

def run():
    configure(267);result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(MoreContracts))
    if not result.wasSuccessful():raise RuntimeError('Regression tests failed')
    m=read(HERE/'data/manifest.json');stats=read(HERE/'data/normalization.json');visits={};n=0
    for r in m['scans']:
        visits.setdefault(r['session_date'],set()).add(r['split']);assert r['split']==split(r)
        verify(r['dataset']);d=npz(r['dataset']['path'])
        assert d['target'].shape==d['known'].shape==(512,512)
        assert not (d['target']&~d['known']).any()
        assert np.array_equal(d['availability'],np.isfinite(d['thickness_um']))
        assert np.isnan(d['thickness_um'][:,d['shadow']]).all()
        for ex,c in [('A',2),('B',11),('C',19)]:assert tensor_inputs(d,stats,ex).shape==(c,512,512)
        n+=1
    assert all(len(x)==1 for x in visits.values())
    fingerprints=[];models=[]
    for ex in 'ABC':
        for seed in [267,268,269]:
            out=HERE/f'experiment_{ex}'
            if seed!=267:out=out/f'seed_{seed}'
            if not (out/'complete.json').exists():continue
            config=read(out/'config.json');ck=torch.load(out/'last.pt',map_location='cpu',weights_only=False)
            assert ck['config']==config and config['manifest_sha256']==sha(HERE/'data/manifest.json')
            assert config['model_code_sha256']==sha(HERE/'model.py') and config['training_code_sha256']==sha(HERE/'train.py')
            assert ck['optimizer']['state'] and ck['sampler_rng'] and ck['torch_rng'].numel()>0
            for r in m['scans']:
                sid=r['scan_id'];a=npz(out/'scores'/f'{sid}.npz');pred=npz(out/'predictions'/f'{sid}.npz')
                assert a['score'].shape==(512,512) and np.isfinite(a['score']).all() and np.min(a['score'])>=0 and np.max(a['score'])<=1
                assert np.array_equal(pred['mask'],a['score']>=float(pred['threshold']))
                assert np.array_equal(pred['candidate_labels']>0,pred['mask'])
            models.append(dict(experiment=ex,seed=seed,epochs=read(out/'complete.json')['epochs']))
            fingerprints.append(sha(out/'best.pt'))
    assert len(set(fingerprints))==len(fingerprints)
    unchanged=all(sha(p)==h for p,h in m['annotation_hashes'].items());assert unchanged
    write(HERE/'verification/release_checks.json',dict(passed=True,additional_contract_tests=result.testsRun,
        scans_verified=n,models=models,distinct_checkpoints=len(set(fingerprints)),original_annotation_files_unchanged=unchanged,
        no_human_review_yet=not (HERE/'review/human_observations.jsonl').exists()))
    progress('Release verification passed',scans=n,models=len(models))

if __name__=='__main__':run()
