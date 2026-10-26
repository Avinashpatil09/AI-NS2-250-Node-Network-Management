"""Train a Random Forest using node-held-out train/test splits to reduce leakage."""
from pathlib import Path
import json
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
from sklearn.model_selection import GroupShuffleSplit

OUT = Path(__file__).resolve().parent/'results'
FEATURES = ['energy','energy_decay','energy_consumed']


def main():
    df = pd.read_csv(OUT/'ml_dataset.csv')
    if df.empty:
        raise SystemExit('Dataset is empty: run a longer NS2 simulation.')
    X,y = df[FEATURES],df.failure_risk.astype(int)
    split = GroupShuffleSplit(n_splits=1,test_size=0.2,random_state=42)
    train_idx,test_idx = next(split.split(X,y,groups=df.node_id))
    model = RandomForestClassifier(n_estimators=200,max_depth=12,min_samples_leaf=2,
                                   class_weight='balanced_subsample',random_state=42,n_jobs=-1)
    model.fit(X.iloc[train_idx],y.iloc[train_idx])
    pred = model.predict(X.iloc[test_idx])
    data = {
        'training_rows':len(train_idx),'test_rows':len(test_idx),
        'training_nodes':int(df.iloc[train_idx].node_id.nunique()),
        'test_nodes':int(df.iloc[test_idx].node_id.nunique()),
        'train_classes':sorted(map(int,y.iloc[train_idx].unique())),
        'test_classes':sorted(map(int,y.iloc[test_idx].unique())),
        'accuracy':float(accuracy_score(y.iloc[test_idx],pred)),
        'confusion_matrix_0_1':confusion_matrix(y.iloc[test_idx],pred,labels=[0,1]).tolist(),
        'classification_report':classification_report(y.iloc[test_idx],pred,labels=[0,1],
                                                       output_dict=True,zero_division=0),
        'feature_importance':dict(zip(FEATURES,map(float,model.feature_importances_))),
        'warning':'Labels were constructed from simulated future energy; high test accuracy does not validate real-world node failure prediction.'
    }
    if len(data['train_classes'])<2:
        data['warning'] += ' Only one training class present: classifier cannot distinguish failure-risk classes; increase simulation duration or adjust *documented* simulation assumptions.'
    joblib.dump(model, OUT/'failure_prediction_model.pkl')
    (OUT/'model_metrics.json').write_text(json.dumps(data,indent=2))
    print('Random Forest trained. Node-held-out accuracy:',round(data['accuracy'],4))
    print('Train classes:',data['train_classes'],'Test classes:',data['test_classes'])
    print('Confusion matrix [0,1]:',data['confusion_matrix_0_1'])


if __name__=='__main__':
    main()
