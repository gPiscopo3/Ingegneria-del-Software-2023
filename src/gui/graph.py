from collections import Counter
from typing import Dict
from PyQt6.QtWidgets import QWidget, QVBoxLayout
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
import networkx as nx
from datetime import datetime
from src.logic.DataManagement import get_collaborations_since, get_communications_since
from src.logic.Filters import collaborations_in_range, communications_in_range


def create_graph(owner: str, repo_name: str, starting_date: datetime, token: str, datai: datetime, dataf: datetime,
                 files: dict):
    if files is None:
        files = get_collaborations_since(owner, repo_name, starting_date, token)
    collaborations = collaborations_in_range(datai, dataf, files)
    # print(collaborations)

    lista_trasformata = [
        [tuple(sorted((coppia[0], coppia[1]), key=lambda x: x.username)) for coppia in lista]
        for lista in collaborations
    ]

    conteggi_totali = Counter([item for sublist in lista_trasformata for item in sublist])

    G = nx.Graph()

    # print("Occorrenze delle coppie di oggetti:")
    for coppia, conteggio in conteggi_totali.items():

        if conteggio > 0:
            G.add_edge(coppia[0].username, coppia[1].username, weight=conteggio)
            print(f"{coppia[0].username, coppia[1].username}: {conteggio} volte")

    # Creazione di un grafo non diretto

    return G, files


def create_graph_communication(owner: str, repo_name: str, starting_date: datetime, token: str, datai: datetime,
                               dataf: datetime, all_users):
    if all_users is None:
        all_users = get_communications_since(owner, repo_name, starting_date, token)
    communications = communications_in_range(datai, dataf, all_users)  # mappa di adiacenza : Dict[User, List[User]]
    lista_archi_diretti = create_directed_edges(communications)
    conteggi_totali = Counter(lista_archi_diretti)
    G = nx.DiGraph()
    for coppia, conteggio in conteggi_totali.items():

        if conteggio > 0:
            G.add_edge(coppia[0].username, coppia[1].username, weight=conteggio)
            print(f"{coppia[0].username, coppia[1].username}: {conteggio} volte")

    return G, all_users


class GraphWidget(QWidget):
    def __init__(self, G, flag: int, edge_color: []):
        super().__init__()

        self.initUI(G, flag, edge_color)

    def initUI(self, G, flag, edge_color):
        # Creazione di un layout verticale per il widget
        layout = QVBoxLayout(self)

        # Creazione della figura per il grafo
        fig, ax = plt.subplots()
        canvas = FigureCanvasQTAgg(fig)
        layout.addWidget(canvas)

        labels = nx.get_edge_attributes(G, 'weight')

        # Disegno del grafo sulla figura
        pos = nx.circular_layout(G, scale=1.0)
        if flag == 1:
            nx.draw(G, pos, with_labels=True, ax=ax, node_size=170, node_color='skyblue', font_size=8)
            nx.draw_networkx_edge_labels(G, pos, edge_labels=labels)  # Aggiungi etichette degli archi
        if flag == 2:
            nx.draw(G, pos, with_labels=True, ax=ax, node_size=170, node_color='skyblue', font_size=8,
                    connectionstyle='arc3, rad = 0.05')
            nx.draw_networkx_edge_labels(G, pos, edge_labels=labels, font_size=8,
                                         label_pos=0.4)  # Aggiungi etichette degli archi
        if flag == 3:
            #labels = ['comunicazioni', 'collaborazioni', 'entrambe']
            nx.draw(G, pos, with_labels=True, ax=ax, node_size=170, edge_color=edge_color, font_size=8)
            legend_labels = ['Comunicazioni', 'Collaborazioni', 'Composito']
            colors = {'Comunicazioni': 'red', 'Collaborazioni': 'blue', 'Composito': 'purple'}
            legend_handles = [
                plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=colors[label], markersize=10, label=label)
                for label in legend_labels]
            plt.legend(handles=legend_handles, title="Tipi di collegamenti", loc='upper left')
            #
            # # Aggiungi una leggenda statica
            # legend_x = 1.2  # Posizione x della leggenda
            # legend_y = 0.9  # Posizione y della leggenda
            #
            # for label in legend_labels:
            #     plt.text(legend_x, legend_y, label, color=colors[label], ha='left', va='center')
            #     plt.fill_between([legend_x - 0.1, legend_x + 0.1], legend_y - 0.05, legend_y + 0.05,
            #                      color=colors[label])
        # Aggiunta del canvas al layout
        layout.addWidget(canvas)


def create_composite_graph(owner: str, repo_name: str, starting_date: datetime, token: str, datai: datetime,
                           dataf: datetime,
                           files: dict, all_users):
    g1, files = create_graph(owner, repo_name, starting_date, token, datai, dataf,
                             files)
    g2, all_users = create_graph_communication(owner, repo_name, starting_date, token, datai,
                                               dataf, all_users)

    g2 = g2.to_undirected()

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

    return merged_graph, files, all_users, edge_colors


def create_directed_edges(adj_map: Dict):
    edges = []
    for user, list_user in adj_map.items():
        for receiver in list_user:
            tup = (user, receiver)
            edges.append(tup)
    return edges
