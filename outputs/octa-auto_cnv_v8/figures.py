from common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
def run():
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for i,ax in enumerate(axes,1):
        rows=[json.loads(s) for s in (HERE/f'model{i}/training.jsonl').read_text().splitlines()]
        ax.plot([r['epoch'] for r in rows],[r['mean_fit_loss'] for r in rows],color='#bb4f3e' if i==1 else '#326ba8',lw=1.6)
        ax.set(title=f'Model {i}: training fit diagnostic',xlabel='Scheduled epoch',ylabel='Mean sampled-patch training loss');ax.grid(alpha=.2)
    fig.suptitle('Fixed 100-epoch fits · no validation or checkpoint selection',fontsize=13)
    fig.savefig(dest(HERE/'reports/training_diagnostics.png'),dpi=170);plt.close(fig)
if __name__=='__main__':run()
