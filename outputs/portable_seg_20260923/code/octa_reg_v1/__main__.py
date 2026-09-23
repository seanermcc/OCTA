import argparse
from pathlib import Path
from . import CONFIG
from .io import DEFAULT_OUT,DEFAULT_INVENTORY,DEFAULT_EXPORT
from .pipeline import run,inventory_only

def main():
    p=argparse.ArgumentParser(description='Vessel-only physical rigid registration; no CNV inputs')
    p.add_argument('command',choices=['inventory','run','report'])
    p.add_argument('--output',type=Path,default=DEFAULT_OUT)
    p.add_argument('--inventory',type=Path,default=DEFAULT_INVENTORY)
    p.add_argument('--vessel-export',type=Path,default=DEFAULT_EXPORT)
    p.add_argument('--eye',help='Bounded smoke selection, e.g. TS165_OD')
    p.add_argument('--workers',type=int,choices=[1,2],default=2)
    args=p.parse_args();cfg=dict(CONFIG,workers=args.workers)
    if args.command=='inventory':inventory_only(args.output,args.inventory,args.vessel_export,cfg)
    elif args.command=='run':
        run(args.output,args.inventory,args.vessel_export,cfg,args.eye)
        from .io import read
        if read(args.output/'status.json')['status']=='failed':raise SystemExit(1)
    else:
        from .report import report
        report(args.output)

if __name__=='__main__':main()
