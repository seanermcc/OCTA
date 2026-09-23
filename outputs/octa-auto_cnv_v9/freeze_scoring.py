"""Pin scoring implementation before any held-out or gallery result inspection."""
from common import *
import ast
for p in HERE.glob('*.py'):ast.parse(p.read_text(encoding='utf-8-sig'),filename=str(p))
files=['candidates.py','deliver.py','verify_release.py']
out=HERE/'data/scoring_implementation.json'
record=dict(protocol_sha256=sha(HERE/'data/protocol.json'),files=[fingerprint(HERE/n) for n in files],policy='implementation frozen before held-out candidate extraction/evaluation and before gallery predictions; hyperparameters are the previously frozen protocol')
if out.exists():
 for fp in read(out)['files']:verify(fp)
else:write(out,record)
print('Python syntax valid; scoring implementation frozen')
