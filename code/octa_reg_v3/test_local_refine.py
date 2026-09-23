"""Safety and image-evidence contracts for local montage polishing."""
import numpy as np
import unittest
from scipy import ndimage as ndi
from octa_reg_v3.local_refine import adjusted,motion,prepare,pair_points,evidence,CENTER,run

def test_rotation_is_about_field_center_and_does_not_change_scale():
    t=.7;base=np.array([[np.cos(t),-np.sin(t),2400.],[np.sin(t),np.cos(t),-1700.],[0,0,1.]])
    result=adjusted(base,[1.,3.,4.])
    np.testing.assert_allclose(result[:2,:2].T@result[:2,:2],np.eye(2),atol=1e-12)
    np.testing.assert_allclose(result[:2,:2]@CENTER+result[:2,2]-(base[:2,:2]@CENTER+base[:2,2]),[3,4],atol=1e-10)
    delta=motion(base,result)
    assert abs(delta['center_shift_px']-5)<1e-10
    assert abs(delta['rotation_deg']-1)<1e-10
    assert delta['max_corner_shift_px']<11.31

def test_hard_bound_geometry_includes_rotation_at_corners():
    base=np.eye(3)
    for angle in [-1.,0.,1.]:
        for direction in np.linspace(0,2*np.pi,25):
            m=adjusted(base,[angle,8*np.cos(direction),8*np.sin(direction)])
            d=motion(base,m)
            assert d['center_shift_px']<=8+1e-10
            assert d['max_corner_shift_px']<14.307

def test_heldout_image_evidence_prefers_known_small_shift():
    rng=np.random.default_rng(42);im=ndi.gaussian_filter(rng.normal(size=(512,512)),2)
    im=(im-im.min())/(im.max()-im.min())
    def scan(x):
        s=dict(image=x,valid=np.ones(x.shape,bool),vessel=np.zeros(x.shape,bool));prepare(s);return s
    a=scan(im);b=scan(ndi.shift(im,(3,-4),order=1,mode='reflect'))
    identity=np.eye(3);mb=np.eye(3);mb[:2,2]=[4,-3]
    tr,va=pair_points(a,b,identity)
    assert set(map(tuple,tr)).isdisjoint(set(map(tuple,va)))
    initial=evidence(a,b,identity,identity,va)
    aligned=evidence(a,b,identity,mb,va)
    assert aligned['score']>.98
    assert aligned['score']>initial['score']+.3

def test_requested_25_pixel_5_degree_bounds_use_center_translation():
    base=np.array([[1.,0.,1200.],[0.,1.,-340.],[0.,0.,1.]])
    for angle in [-5.,5.]:
        for direction in np.linspace(0,2*np.pi,25):
            m=adjusted(base,[angle,25*np.cos(direction),25*np.sin(direction)])
            d=motion(base,m)
            assert abs(d['center_shift_px']-25)<1e-9
            assert abs(abs(d['rotation_deg'])-5)<1e-9
            assert d['max_corner_shift_px']<56.53
            np.testing.assert_allclose(m[:2,:2].T@m[:2,:2],np.eye(2),atol=1e-12)

def test_invalid_limits_rejected_before_any_io():
    for px,deg in [(0,5),(-1,5),(25,0),(float('nan'),5)]:
        with unittest.TestCase().assertRaises(ValueError):run('unused-source','unused-output',px,deg)

def load_tests(loader,tests,pattern):
    return unittest.TestSuite(unittest.FunctionTestCase(fn) for name,fn in globals().items() if name.startswith('test_'))
