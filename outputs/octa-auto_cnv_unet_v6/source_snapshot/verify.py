"""Contract tests plus a real tiny-set overfit before the bounded pilot."""
from common import *
from dataset import export_target,automatic_thickness,tensor_inputs
from model import UNet,masked_loss,infer
from train import configure,Sampler
from metrics import score,match,PROTOCOL
import torch
import unittest

class Contracts(unittest.TestCase):
    def test_unknown_gradients_and_negative_loss(self):
        z=torch.zeros((2,16,16),requires_grad=True);t=torch.zeros_like(z);k=torch.ones_like(z,dtype=torch.bool)
        k[:,0]=False;t[0,2:5,2:5]=1
        loss=masked_loss(z,t,k);loss.backward()
        self.assertTrue((z.grad[:,0]==0).all());self.assertGreater(float(z.grad[1,1:].abs().sum()),0)
        self.assertEqual(float(masked_loss(z,t,k&False)),0)
    def test_label_contract(self):
        visit=dict(scan_id='x',source=str(HERE/'synthetic.mat'))
        mask=np.zeros((512,512),bool);mask[3:20,8:28]=True
        region=dict(id='p',runs=encode(mask),reviewed_runs=encode(mask),bscan_indices=list(range(3,20)),
                    decision='approved',category='Full Lesion',classification_complete=True,events=[dict(action='explicit CNV review',category='Full Lesion')])
        record=dict(scan_id='x',source_volume=visit['source'],native_shape=[512,512],axis_order='B-scan,A-line',regions=[region])
        a,_=export_target(record,visit);self.assertEqual(int(a['known'].sum()),int(mask.sum()))
        record['scan_review']=dict(status='complete',whole_field_checked=True,confirmed_cnv_count=1,uncertainty_region_ids=[],reviewed_absence=False)
        a,_=export_target(record,visit);self.assertTrue(a['known'].all())
        region['reviewed_runs']=[];a,info=export_target(record,visit);self.assertFalse(a['target'].any());self.assertFalse(info['complete'])
        a,_=export_target(None,visit);self.assertFalse(a['known'].any())
        with self.assertRaises(ValueError):decode([[512,0,1]])
    def test_thickness_and_fill(self):
        rows=np.broadcast_to(np.arange(8)[None,:,None]*10+100,(2,8,4)).copy().astype(float)
        g=dict(label_offset=100,shadow=np.zeros((2,4),bool));g['shadow'][0,0]=True
        cal=[dict(supported=False) for _ in range(8)]
        t,reason,e=automatic_thickness(rows,np.zeros((2,8,2,4)),g,cal,100)
        self.assertTrue(np.isnan(t[:,0,0]).all());self.assertAlmostEqual(float(t[0,1,1]),78.4,places=3)
        d=dict(optical=np.ones((2,2,4)),thickness_um=t,availability=np.isfinite(t),shadow=g['shadow'])
        stats={n:dict(center=[0]*c,scale=[1]*c) for n,c in [('optical',2),('thickness_um',8)]}
        x=tensor_inputs(d,stats,'C');self.assertEqual(x.shape[0],19);self.assertTrue((x[11:,0,0]==0).all());self.assertTrue((x[2:10,0,0]==0).all())
    def test_matching_and_empty(self):
        self.assertEqual(len(match(np.array([[.9,.11],[.11,0]]),.1)),2)
        shape=(32,32);zero=np.zeros(shape,bool)
        d=dict(known=~zero,target=zero,instances=np.zeros((0,*shape),bool),availability=np.ones((8,*shape),bool),shadow=zero,vessel=zero,low_signal=zero)
        result,_=score(zero,d,True);self.assertIsNone(result['known_dice']);self.assertEqual(result['false_positives'],0)
        p=zero.copy();p[1:4,1:4]=True;result,_=score(p,d,True);self.assertEqual(result['false_positives'],1)
        d['known'][1:4,1:4]=False;result,_=score(p,d,True);self.assertEqual(result['false_positives'],0)
    def test_architecture_and_blending(self):
        for c in (2,11,19):
            net=UNet(c);self.assertEqual(tuple(net(torch.zeros(1,c,32,32)).shape),(1,32,32))
        class Constant(torch.nn.Module):
            def forward(self,x):return x[:,0]*0
        p=infer(Constant(),np.ones((2,512,512),np.float32),torch.device('cpu'))
        self.assertTrue(np.allclose(p,.5))

def run():
    configure(267)
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Contracts)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():raise RuntimeError('Contract verification failed')
    write(HERE/'evaluation/protocol.json',PROTOCOL)
    m=read(HERE/'data/manifest.json');stats=read(HERE/'data/normalization.json')
    ds=[]
    for r in m['scans']:
        if r['split']=='train' and r['audit']['positive_pixels']+r['audit']['negative_pixels']>0:
            d=npz(HERE/'data'/f"{r['scan_id']}.npz");d['input']=tensor_inputs(d,stats,'A');ds.append(d)
    sampler=Sampler(ds,267);fixed=[sampler.tile(True,False),sampler.tile(False,False)]
    device=torch.device('cuda' if torch.cuda.is_available() else 'cpu');net=UNet(2).to(device)
    x,y,k=[torch.from_numpy(np.stack([r[i] for r in fixed])).to(device) for i in range(3)]
    optim=torch.optim.AdamW(net.parameters(),lr=.001,weight_decay=.0001);losses=[]
    for step in range(800):
        net.train();optim.zero_grad();z=net(x);loss=masked_loss(z,y,k);loss.backward();optim.step();losses.append(float(loss.detach()))
        if step%100==0:progress('Tiny-set overfit',step=step,loss=losses[-1])
    p=net(x).sigmoid().detach();pred=p>.5
    tp=float((pred&y&k).sum());den=float(((pred&k).sum()+(y&k).sum()))
    tiny_dice=2*tp/den
    check=dict(contract_tests=result.testsRun,passed=tiny_dice>=.85 and losses[-1]<=.35*losses[0],initial_loss=losses[0],final_loss=losses[-1],tiny_known_dice=tiny_dice,
               steps=800,device=str(device),losses=losses,tiles=[r[3] for r in fixed],
               peak_gpu_allocated_bytes=torch.cuda.max_memory_allocated() if device.type=='cuda' else None)
    write(HERE/'verification/preflight.json',check)
    if tiny_dice<.85 or losses[-1]>.35*losses[0]:raise RuntimeError('Tiny-set did not overfit sufficiently')
    progress('Preflight passed',tiny_dice=tiny_dice,final_loss=losses[-1])

if __name__=='__main__':run()
