"""One node-by-node table: energy, ML risk, packet metrics and preventive decision."""
from pathlib import Path
import pandas as pd

OUT=Path(__file__).resolve().parent/'results'


def main():
    risk=pd.read_csv(OUT/'final_node_predictions.csv')
    net=pd.read_csv(OUT/'node_network_analysis.csv')
    merged=risk.merge(net,on='node_id',how='left')
    for c in ['packets_sent','packets_received','packets_lost','packet_loss_pct','mean_delay_s']:
        merged[c]=merged[c].fillna(0)
    actions=OUT/'preventive_actions.csv'
    if actions.exists():
        decisions=pd.read_csv(actions)
        merged=merged.merge(decisions[['node_id','action','alternative_node_id']],on='node_id',how='left')
    else:
        merged['action']='NOT_EVALUATED'
        merged['alternative_node_id']=''
    merged.to_csv(OUT/'final_integrated_results.csv',index=False)
    print('Wrote final_integrated_results.csv for',len(merged),'nodes')


if __name__=='__main__':
    main()
