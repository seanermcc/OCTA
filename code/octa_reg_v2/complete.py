"""Search missing graph connections using full vessel curves and ONH seeds."""
from .run import load,OUT,read,write
from .curves import match
from .assemble import solve,edges

def main():
    scans=load();poses,_,_=solve(scans,edges())
    missing=[i for i,s in enumerate(scans) if not s['excluded'] and i not in poses]
    anchors=[6,2,3,7,8,14,18,25]
    for i in missing:
        for j in anchors:
            if i==j:continue
            a,b=sorted((i,j));path=OUT/'curve_pairs'/f'{a:02d}_{b:02d}.json'
            if path.exists():continue
            r=dict(a=a,b=b,**match(scans[a],scans[b]));write(path,r)
            print(a,b,{k:r[k] for k in ['accepted','score','support','dice','corr','alternative_margin']},flush=True)
    poses,ee,q=solve(scans,edges())
    print('CONNECTED',len(poses),'MISSING',[i for i,s in enumerate(scans) if not s['excluded'] and i not in poses],flush=True)

if __name__=='__main__':main()
