"""Decision-layer only: suggest a nearby lower-risk alternative, NOT actual NS2 rerouting."""
from pathlib import Path
import math
import pandas as pd

OUT=Path(__file__).resolve().parent/'results'


def main():
    df=pd.read_csv(OUT/'final_node_predictions.csv')
    xy=pd.read_csv(OUT/'positions250.csv')
    df=df.merge(xy,on='node_id')
    eligible=df[df.risk_level=='LOW']
    rows=[]
    for p in df.itertuples():
        if p.risk_level!='HIGH':
            rows.append({'node_id':p.node_id,'action':'MONITOR','alternative_node_id':''})
            continue
        options=eligible[eligible.node_id!=p.node_id]
        if options.empty:
            rows.append({'node_id':p.node_id,'action':'NO_LOW_RISK_ALTERNATIVE','alternative_node_id':''})
            continue
        distances=(options.x-p.x)**2+(options.y-p.y)**2
        replacement=int(options.loc[distances.idxmin(),'node_id'])
        rows.append({'node_id':p.node_id,'action':'SUGGEST_LOWER_RISK_NODE','alternative_node_id':replacement})
    pd.DataFrame(rows).to_csv(OUT/'preventive_actions.csv',index=False)
    counts=pd.DataFrame(rows).action.value_counts().to_dict()
    print('Preventive DECISION only (does not modify NS2 routes):',counts)


if __name__=='__main__':
    main()
