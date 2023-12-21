import networkx as nx
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# Crea un grafo di esempio
G = nx.complete_graph(5)

# Posizionamento 3D casuale dei nodi
pos = nx.random_layout(G, dim=3)

# Crea la figura 3D
fig = plt.figure(figsize=(8, 8))
ax = fig.add_subplot(111, projection='3d')

# Disegna il grafo
nx.draw(G, pos, ax=ax, with_labels=True, font_weight='bold', node_size=700, node_color='skyblue')

# Mostra la figura interattiva
plt.show()