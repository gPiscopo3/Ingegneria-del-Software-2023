from logic import DataManagement
from datetime import datetime
from datetime import timedelta

'''
TOKEN = "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"

users = DataManagement.get_communications_since("fullmoonlullaby", "test", datetime.today() -
                                                timedelta(days=30), TOKEN)

for user in users.values():
    user.print_communications()


files = DataManagement.get_collaborations_since("fullmoonlullaby", "test", datetime.today() -
                                                timedelta(days=14), TOKEN)

for file in files.values():
    file.print_edits()
'''
'''
from logic import DataManagement

import datetime

from src.logic.Filters import collaborations_in_range

TOKEN = "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"

files = DataManagement.get_collaborations_since("apache", "commons-io",
                                                datetime.datetime(2023, 11, 18), TOKEN)

edges = collaborations_in_range(datetime.datetime(2023, 11, 18),
                                datetime.datetime(2023, 12, 6), files)

for edge in edges:
    for user in edge:
        print(user[0].username, user[1].username)
'''


import networkx as nx
import matplotlib.pyplot as plt

# Creazione del primo grafo
G1 = nx.Graph()
G1.add_edges_from([(1, 2), (2, 3)])

# Creazione del secondo grafo
G2 = nx.Graph()
G2.add_edges_from([(3, 4), (4, 5)])

# Composizione dei due grafi
G_compose = nx.compose(G1, G2)

# Visualizzazione del grafo composto
pos = nx.spring_layout(G_compose)
nx.draw(G_compose, pos, with_labels=True, font_weight='bold', node_color='skyblue', edge_color='gray', width=2)

# Visualizza il grafo composto
plt.show()


