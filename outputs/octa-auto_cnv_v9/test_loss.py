"""Isolated Torch arithmetic test: avoid mixing two vendor CPU OpenMP runtimes."""
import unittest,torch
from models import masked_loss
class LossTests(unittest.TestCase):
 def test_unknown_is_zero_gradient(self):
  z=torch.tensor([[[2.,3.],[float('nan'),float('nan')]]],requires_grad=True);y=torch.tensor([[[1.,0.],[float('nan'),float('nan')]]]);k=torch.tensor([[[1.,1.],[0.,0.]]]);loss=masked_loss(z,y,k,1);self.assertTrue(torch.isfinite(loss));loss.backward();self.assertEqual(float(z.grad[0,1].abs().sum()),0.)
if __name__=='__main__':unittest.main()
