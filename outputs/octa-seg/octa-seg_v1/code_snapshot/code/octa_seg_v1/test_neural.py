"""Separate process: the installed Torch and NumPy BLAS OpenMP runtimes conflict."""
import unittest
import torch
from .model import StateNet, evidence, state_loss
from stage_a.model import BoundaryUNet

class Neural(unittest.TestCase):
    def test_state_negative_only_gradient_and_unknown_mask(self):
        torch.set_num_threads(2)
        net=StateNet();f=torch.randn(1,8,27,32);v=torch.zeros(1,32,dtype=torch.bool)
        t=torch.full((1,8,32),-1);r=t.clone();t[0,1,5:10]=0
        loss=state_loss(net(f,v),t,r,v,False);loss.backward()
        self.assertGreater(sum(float(p.grad.abs().sum()) for p in net.parameters()),0)
        self.assertEqual(float(state_loss(net(f,v),r,r,v,False).detach()),0)
    def test_evidence_shapes(self):
        x=torch.randn(1,1,64,32);net=BoundaryUNet()
        f,r,e=evidence(net(x)[0],x)
        self.assertEqual(f.shape,(1,8,27,32));self.assertEqual(StateNet()(f,torch.zeros(1,32)).shape,(1,8,2,32))
    def test_vessel_ablation_ignores_mask(self):
        net=StateNet().eval();f=torch.randn(1,8,27,32)
        self.assertTrue(torch.equal(net(f,torch.ones(1,32),False),net(f,torch.zeros(1,32),False)))

if __name__=="__main__":unittest.main()
