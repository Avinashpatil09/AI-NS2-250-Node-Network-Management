"""Predict risk at the final sampled moment of each node (15-sec extrapolative forecast)."""
from pathlib import Path
import joblib
import pandas as pd
from create_ml_dataset import features
from train_model import FEATURES

OUT = Path(__file__).resolve().parent/'results'


def main():
    model = joblib.load(OUT/'failure_prediction_model.pkl')
    df = features(pd.read_csv(OUT/'energy250.csv'))
    last = df.sort_values('time').groupby('node_id').tail(1).sort_values('node_id').copy()
    prob = model.predict_proba(last[FEATURES])
    positive = list(model.classes_)
    last['failure_probability'] = prob[:,positive.index(1)] if 1 in positive else 0.0
    last['risk_level'] = pd.cut(last.failure_probability,[-0.001,0.35,0.70,1.001],
                                labels=['LOW','MEDIUM','HIGH'],right=False)
    last[['node_id','time','energy','energy_decay','energy_consumed',
          'failure_probability','risk_level']].to_csv(OUT/'final_node_predictions.csv',index=False)
    print('Latest snapshot risk categories:',last.risk_level.value_counts().to_dict())


if __name__ == '__main__':
    main()
