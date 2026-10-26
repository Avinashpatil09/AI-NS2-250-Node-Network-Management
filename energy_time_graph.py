"""View how average simulated energy falls with time; outputs one PNG."""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
OUT=Path(__file__).resolve().parent/'results'
df=pd.read_csv(OUT/'energy250.csv')
df.groupby('time').energy.mean().plot()
plt.title('Average Energy over Simulation Time')
plt.xlabel('Time (s)')
plt.ylabel('Energy (J)')
plt.tight_layout()
(OUT/'graphs').mkdir(parents=True,exist_ok=True)
plt.savefig(OUT/'graphs'/'energy_vs_time.png',dpi=160)
print('Saved results/graphs/energy_vs_time.png')
