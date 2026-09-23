"""Pre/post inventory plus full hashes of release code and annotation heads."""
from common import *
def snapshot():
    folders=[p for p in (ROOT/'outputs').iterdir() if p.is_dir() and (p.name.startswith('octa-auto_cnv_') and p!=HERE or p.name in ('cnv_labels','cnv_review_v1'))]
    out={}
    for folder in folders:
        for root,dirs,files in os.walk(folder):
            dirs[:]=[d for d in dirs if d!='__pycache__']
            for name in files:
                p=Path(root)/name;st=p.stat();item=dict(bytes=st.st_size,mtime_ns=st.st_mtime_ns)
                if p.suffix in ('.json','.py','.md','.cmd','.html','.js','.css') or 'cnv_labels' in p.parts:item['sha256']=sha(p)
                out[str(p)]=item
    return out
if __name__=='__main__':
    p=HERE/'verification/preservation_before.json';current=snapshot()
    if '--after' in sys.argv:
        before=read(p);changes=[k for k in set(before)|set(current) if before.get(k)!=current.get(k)]
        write(HERE/'verification/preservation_after.json',dict(unchanged=not changes,files=len(current),changed=changes,scope='All old CNV release files: size/mtime; text/code and original annotation NPZ: additionally SHA256. Consumed predictions and checkpoints independently full-hashed.'))
        if changes:raise RuntimeError('Old release changed: '+str(changes[:10]))
    elif not p.exists():write(p,current)
