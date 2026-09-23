from common import *
protocol=read(HERE/'data/protocol.json');protocol['microbatch']=4
protocol['batching_deviation']=dict(reason='Synthetic same-GPU benchmark: batch4 about 2.3x faster; 517 MB peak allocation fits available GPU. GroupNorm and per-tile mean loss preserve effective-batch mathematics; AMP arithmetic may differ.',evidence=fingerprint(HERE/'verification/batch_benchmark.log'),prior_incomplete_fit='verification/superseded_microbatch1',policy='All reported fits restart fresh with batch4; no evaluation predictions inspected before amendment')
write(HERE/'data/protocol.json',protocol)
m=read(HERE/'data/supervision.json');m['protocol_sha256']=sha(HERE/'data/protocol.json');m['selection_sha256']=sha(HERE/'data/selection.json');write(HERE/'data/supervision.json',m)
write(HERE/'data/batching_amendment.json',protocol['batching_deviation'])
