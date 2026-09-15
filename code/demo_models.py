"""Launch existing review applications without retraining or changing releases."""
from pathlib import Path
import argparse
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs'
V2 = OUT / 'octa-seg/octa-seg_v2'
V3 = OUT / 'octa-seg/octa-seg_v3'
CHOICES = {
    '1': ('Layer review v3 (current)', V3, ['-m', 'octa_seg_v3.gui'], V3 / 'catalog.json'),
    '2': ('Layer review v2 (previous workflow)', V2, ['-m', 'octa_seg_v2.gui'], V2 / 'manifest.json'),
    '3': ('CNV v6: original B/C predictions', OUT / 'octa-auto_cnv_unet_v6/review', ['viewer.py'], OUT / 'octa-auto_cnv_unet_v6/all_samples/FINAL_VERIFIED.json'),
    '4': ('Vessel / ONH v1 correction queue', OUT / 'octo-vessel_onh_v1', ['app.py'], OUT / 'octa-vessel_seg_v1-batch/inventory.json'),
    '5': ('Vessel / ONH v2 comparison gallery', OUT / 'octo-vessel_onh_v2', None, OUT / 'octo-vessel_onh_v2/index.html'),
    '6': ('Thickness viewer: completed 314-scan batch', OUT / 'octa-seg_v1_batch', ['code/batch.py', 'thick'], OUT / 'octa-seg_v1_batch/thick/volumes.json'),
    '7': ('CNV v6 offline comparison gallery', OUT / 'octa-auto_cnv_unet_v6/all_samples/comparison', None, OUT / 'octa-auto_cnv_unet_v6/all_samples/comparison/index.html'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('choice', nargs='?', choices=CHOICES)
    parser.add_argument('--check', action='store_true', help='Check runtime and local demo entry files; open no GUI')
    args = parser.parse_args()
    if args.check:
        failed = False
        for key, (label, folder, command, required) in CHOICES.items():
            okay = folder.is_dir() and required.is_file()
            failed |= not okay
            print(f'{key}: {"OK" if okay else "MISSING"} - {label}\n   {required}')
        probe = subprocess.run([sys.executable, '-B', '-c',
            'import numpy, h5py, scipy, skimage, matplotlib, pandas, PySide6; '
            'print("Review runtime imports: OK")'])
        print('Entry-file checks do not verify every referenced image or checkpoint. Open your selected demo before the meeting.')
        return int(failed or probe.returncode != 0)
    key = args.choice
    if key is None:
        print('\nOCTA model demonstrations\n')
        for number, (label, *_rest) in CHOICES.items():
            print(f'{number}. {label}')
        key = input('\nChoose 1-7 (Enter to exit): ').strip()
        if not key:
            return 0
        if key not in CHOICES:
            print('Please choose a number from 1 to 7.')
            return 1
    label, folder, command, required = CHOICES[key]
    if not required.is_file():
        print(f'Missing local demo asset: {required}\nSee DEMO_GUIDE.md. A GitHub clone does not include the dataset.')
        return 1
    print(f'Opening {label}', flush=True)
    if command is None:
        os.startfile(str(required))
        return 0
    env = os.environ.copy()
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PYTHONPATH'] = os.pathsep.join(map(str, [V3 / 'code', V2 / 'code', ROOT / 'code']))
    return subprocess.run([sys.executable, '-B', *command], cwd=folder, env=env).returncode


if __name__ == '__main__':
    raise SystemExit(main())
