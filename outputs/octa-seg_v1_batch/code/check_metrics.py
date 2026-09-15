"""Small adversarial checks of finite masks, adjacent pairs and geometry."""
from qc import *

def run_checks():
    x=np.array([[1.,2.,np.nan],[5.,9.,20.]])
    mask=np.array([[True,True,True],[True,False,True]])
    r=describe(x,mask)
    assert r['native_n']==6 and r['eligible_n']==5 and r['finite_native_n']==5 and r['finite_eligible_n']==4
    assert r['aline_abs_jump_n']==1 and r['aline_abs_jump_median']==1
    assert r['bscan_abs_jump_n']==1 and r['bscan_abs_jump_median']==4
    assert r['median']==3.5 and r['mad']==2.0
    assert describe(x,np.zeros_like(mask))['coverage_eligible_pct'] is None
    a=np.array([[[10.,5.],[np.nan,15.],[9.,20.]]])
    g=geometry(a,0,0,20,np.ones((1,2),bool),'')
    assert g['native_crossing_n']==1 and g['native_crossing_comparable_n']==2
    g=geometry(a,2,0,20,np.ones((1,2),bool),'')
    assert g['native_out_of_crop_n']==1
    assert stats([np.nan])['n']==0 and stats([np.nan])['mean'] is None
    write(OUT/'verification/metric_checks.json',dict(passed=True,checks=['finite and eligible denominators differ correctly','no interpolation across missing adjacent endpoints','image exclusions remove pairs','unscaled MAD','zero-denominator missingness','nonadjacent crossings through missing boundary','out-of-crop finite denominator']))
    print('Metric checks passed')

if __name__=='__main__':run_checks()
