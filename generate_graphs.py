"""Make the nine graphs described in the previous project guide."""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=Path(__file__).resolve().parent/'results'
G=OUT/'graphs'


def save(name,title,xlabel='',ylabel=''):
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.tight_layout()
    plt.savefig(G/name,dpi=160)
    plt.close()


def main():
    G.mkdir(parents=True,exist_ok=True)
    energy=pd.read_csv(OUT/'energy250.csv')
    pred=pd.read_csv(OUT/'final_node_predictions.csv')
    stats=pd.read_csv(OUT/'node_network_analysis.csv')
    xy=pd.read_csv(OUT/'positions250.csv')

    trend=energy.groupby('time').energy.mean()
    trend.plot()
    save('energy_vs_time.png','Average Remaining Node Energy','Time (s)','Energy (J)')

    pred.energy.hist(bins=20)
    save('energy_levels.png','Remaining Energy at Last Snapshot','Energy (J)','Number of nodes')

    pred.energy_decay.hist(bins=20)
    save('energy_decay.png','Instantaneous Energy Consumption Rate','J/s','Number of nodes')

    pred.plot.scatter(x='energy',y='failure_probability',alpha=0.6)
    save('energy_vs_failure.png','Energy vs Predicted Risk Probability','Energy (J)','Predicted risk probability')

    pred.failure_probability.hist(bins=20)
    save('failure_probability.png','Random Forest Risk Probabilities','Probability','Number of nodes')

    pred.risk_level.value_counts().reindex(['LOW','MEDIUM','HIGH'],fill_value=0).plot.bar()
    save('risk_distribution.png','Risk Category Distribution','Category','Number of nodes')

    top=stats.nlargest(min(20,len(stats)),'packet_loss_pct')
    top.plot.bar(x='node_id',y='packet_loss_pct',legend=False)
    save('packet_loss.png','Packet Loss for Top 20 Source Nodes','Source node ID','Packet loss (%)')

    top=stats.nlargest(min(20,len(stats)),'mean_delay_s')
    top.plot.bar(x='node_id',y='mean_delay_s',legend=False)
    save('average_delay.png','App-Layer Mean Delay for Top 20 Source Nodes','Source node ID','Delay (s)')

    merged=xy.merge(pred[['node_id','risk_level']],on='node_id')
    colors={'LOW':'tab:green','MEDIUM':'tab:orange','HIGH':'tab:red'}
    for category, subset in merged.groupby('risk_level'):
        plt.scatter(subset.x,subset.y,label=category,s=20,color=colors.get(category,'gray'))
    plt.legend()
    plt.axis('equal')
    save('network_topology.png','Node Locations (not measured AODV routes)','x (m)','y (m)')

    print('Nine graphs saved in results/graphs/')


if __name__=='__main__':
    main()
