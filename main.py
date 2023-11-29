import networkx as nx
from matplotlib import pyplot as plt

from logic.APICalls import get_communications_since, get_collaborations_since
import datetime as dt

from logic.Filters import collaborations_in_range

datainizio = dt.datetime(2023, 10, 27)
datai = dt.datetime(2023, 10, 27)
dataf = dt.datetime(2023, 11, 27)

if __name__ == '__main__':
    # utenti= get_communications_since("apache", "commons-io", datainizio, "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")
    # print(utenti)
    files = get_collaborations_since("apache", "commons-io", datainizio, "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")
    print(files)
    collaborations = collaborations_in_range(datai, dataf, files)
    for tupla in collaborations:
        for a in tupla:
            print(a[0], a[1])
            print()

    # Creazione di un grafo non diretto
    G = nx.Graph()

    # Aggiunta degli utenti come nodi
    for tupla in collaborations:
        for a in tupla:
            G.add_edge(a[0].username, a[1].username)

    # Disegno del grafo
    pos = nx.spring_layout(G)  # Layout per il disegno
    nx.draw(G, pos, with_labels=True, font_weight='bold', node_color='skyblue', edge_color='gray')

    # Mostrare il grafo
    plt.show()
