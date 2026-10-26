"""Build energy features and future-energy labels, using a three-sample (15 s) forecast horizon."""
from pathlib import Path
import pandas as pd

OUT = Path(__file__).resolve().parent / 'results'
INITIAL_ENERGY = 100.0
CRITICAL_ENERGY = 45.0  # experimental project-specific threshold, not physical failure
HORIZON_SAMPLES = 3    # 15 s if energy logged every 5 s


def features(energy):
    df = energy.sort_values(['node_id','time']).copy()
    prev_energy = df.groupby('node_id')['energy'].shift(1)
    prev_time = df.groupby('node_id')['time'].shift(1)
    dt = (df.time-prev_time).replace(0, pd.NA)
    df['energy_decay'] = ((prev_energy-df.energy)/dt).fillna(0).clip(lower=0)
    df['energy_consumed'] = (INITIAL_ENERGY - df.energy).clip(lower=0)
    return df


def main():
    p = OUT/'energy250.csv'
    if not p.exists():
        raise SystemExit('Missing energy250.csv — run simulation250.tcl first.')
    energy = pd.read_csv(p)
    expected = {'time','node_id','energy'}
    if not expected.issubset(energy.columns):
        raise SystemExit('Energy CSV is missing expected columns.')
    df = features(energy)
    df['future_energy'] = df.groupby('node_id')['energy'].shift(-HORIZON_SAMPLES)
    labeled = df.dropna(subset=['future_energy']).copy()
    labeled['failure_risk'] = (labeled.future_energy < CRITICAL_ENERGY).astype(int)
    labeled.to_csv(OUT/'ml_dataset.csv', index=False)
    print('Dataset:', len(labeled), 'rows; class counts:', labeled.failure_risk.value_counts().to_dict())
    print('Label = future energy < 45 J after 3 energy-sample intervals.')


if __name__ == '__main__':
    main()
