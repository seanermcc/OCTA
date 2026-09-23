"""Create an isolated browser test copy; no decisions are written to real animals."""
import json
from pathlib import Path
import shutil
from .review_server import DEFAULT_ROOT


def main():
    root=DEFAULT_ROOT.parent/'reviewer_test'
    folder=root/'TS999_OS';folder.mkdir(parents=True,exist_ok=True)
    data=json.loads((DEFAULT_ROOT/'TS165_OS/montage.json').read_text())
    data['summary']['group']='TS999_OS';data['groups']=['TS999_OS']
    for s in data['scans']:
        s['scan_id']='synthetic-'+str(s['index']);s['animal']='TS999'
        s['day_label']=['pre','d0','d14'][s['index']%3];s['day_basis']='UI TEST ONLY'
    (folder/'montage.json').write_text(json.dumps(data),encoding='utf-8')
    (folder/'data.js').write_text('window.MONTAGE='+json.dumps(data)+';',encoding='utf-8')
    shutil.copytree(DEFAULT_ROOT/'TS165_OS/assets',folder/'assets',dirs_exist_ok=True)
    for src,dest in [('cohort_viewer.html','index.html'),('cohort_viewer.js','cohort_viewer.js')]:
        shutil.copyfile(Path(__file__).with_name(src),folder/dest)
    print(root)


if __name__=='__main__':main()
