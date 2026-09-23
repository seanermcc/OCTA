"""CPU-only candidate fitting, isolated from the torch OpenMP runtime."""
from common import *
from candidates import fit_scorer

if __name__=='__main__':
 examples=read(HERE/'development/scorer_examples.json')['records']
 scorer=fit_scorer(examples,dict(role='Model 3 deployment scorer; three animal-excluded fits on expanded 101-scan supervision',protocol_sha256=sha(HERE/'data/protocol.json'),independent_evaluation=False))
 write(HERE/'bundles/v9_m3/scorer.json',scorer)
 print(json.dumps(dict(stage='Candidate scorer complete',training_examples=scorer['training_examples'],class_counts=scorer['class_counts'])),flush=True)
