import networkx as nx
import matplotlib.pyplot as plt

# Crea due grafi di esempio (g1 e g2)
g1 = nx.Graph()
g1.add_edges_from([(1, 2), (2, 3), (3, 4)])

g2 = nx.Graph()
g2.add_edges_from([(2, 5), (1,2), (3, 6), (4, 7)])

# Unisci i due grafi mantenendo i nodi uguali
merged_graph = nx.compose(g1, g2)

# Assegna colori diversi agli archi di g1 e g2
edge_colors = []
for edge in merged_graph.edges:
    if edge in g1.edges and edge in g2.edges:
        # Arco presente in entrambi i grafi
        edge_colors.append('purple')
    elif edge in g1.edges:
        # Arco presente solo in g1
        edge_colors.append('blue')
    elif edge in g2.edges:
        # Arco presente solo in g2
        edge_colors.append('red')

# Disegna il grafo unificato con colori diversi per g1 e g2
nx.draw(merged_graph, with_labels=True, edge_color=edge_colors)
plt.show()
