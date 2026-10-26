"""Draw recorded NS2 node positions, not a measurement of active AODV routes."""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
OUT=Path(__file__).resolve().parent/'results'
df=pd.read_csv(OUT/'positions250.csv')
plt.scatter(df.x,df.y,s=17)
plt.title('NS2 Node Positions (not actual routing links)')
plt.xlabel('x (m)')
plt.ylabel('y (m)')
plt.axis('equal')
plt.tight_layout()
(OUT/'graphs').mkdir(parents=True,exist_ok=True)
plt.savefig(OUT/'graphs'/'network_topology.png',dpi=160)
print('Saved results/graphs/network_topology.png')
