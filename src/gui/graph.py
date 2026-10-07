import math
from collections import Counter
from typing import Dict
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
import networkx as nx
from datetime import datetime
from src.gui.style import matplotlib_colors
from src.logic.DataManagement import get_collaborations_since, get_communications_since
from src.logic.Filters import collaborations_in_range, communications_in_range


def create_graph(owner: str, repo_name: str, starting_date: datetime, token: str, datai: datetime, dataf: datetime,
                 files):
    if files is None:
        files = get_collaborations_since(owner, repo_name, starting_date, token)
    collaborations = collaborations_in_range(datai, dataf, files.values())
    # print(collaborations)

    lista_trasformata = [
        [tuple(sorted((coppia[0], coppia[1]), key=lambda x: x.username)) for coppia in lista]
        for lista in collaborations
    ]

    conteggi_totali = Counter([item for sublist in lista_trasformata for item in sublist])

    G = nx.Graph()

    for coppia, conteggio in conteggi_totali.items():

        if conteggio > 0:
            G.add_edge(coppia[0].username, coppia[1].username, weight=conteggio)

    return G, files


def create_graph_communication(owner: str, repo_name: str, starting_date: datetime, token: str, datai: datetime,
                               dataf: datetime, all_users):
    if all_users is None:
        all_users = get_communications_since(owner, repo_name, starting_date, token)
    communications = communications_in_range(datai, dataf, all_users.values())  # mappa di adiacenza : Dict[User, List[User]]
    lista_archi_diretti = create_directed_edges(communications)
    conteggi_totali = Counter(lista_archi_diretti)
    G = nx.DiGraph()
    for coppia, conteggio in conteggi_totali.items():

        if conteggio > 0:
            G.add_edge(coppia[0].username, coppia[1].username, weight=conteggio)

    return G, all_users


MAX_EDGE_LABELS = 150  # oltre questa soglia le etichette dei pesi renderebbero il grafo illeggibile


class GraphWidget(QWidget):
    def __init__(self, G, flag: int, edge_color: [], dark: bool = True):
        super().__init__()

        self.initUI(G, flag, edge_color, dark)

    def initUI(self, G, flag, edge_color, dark):
        colors = matplotlib_colors(dark)

        # Creazione di un layout verticale per il widget
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Creazione della figura per il grafo (Figure e non pyplot, per non accumulare figure globali)
        fig = Figure(facecolor=colors["background"])
        ax = fig.add_subplot(111)
        ax.set_facecolor(colors["background"])
        ax.set_axis_off()
        canvas = FigureCanvasQTAgg(fig)

        # Toolbar per zoom, spostamento e salvataggio dell'immagine
        toolbar = NavigationToolbar2QT(canvas, self)
        layout.addWidget(toolbar)
        layout.addWidget(canvas)

        if G.number_of_nodes() == 0:
            ax.text(0.5, 0.5, "Nessuna interazione nell'intervallo selezionato", ha='center', va='center',
                    color=colors["text"], fontsize=11, transform=ax.transAxes)
            return

        # Disegno del grafo sulla figura
        pos = nx.spring_layout(G, seed=42, k=2 / math.sqrt(G.number_of_nodes()))
        node_sizes = [300 + 120 * G.degree(n) for n in G.nodes]
        weights = nx.get_edge_attributes(G, 'weight')
        max_weight = max(weights.values(), default=1)
        widths = [1 + 3 * weights.get(e, 1) / max_weight for e in G.edges]

        if flag == 1:
            edge_colors = colors["edge"]
        elif flag == 2:
            edge_colors = colors["communications"]
        else:
            palette_map = {'blue': colors["collaborations"], 'red': colors["communications"],
                           'purple': colors["composite"]}
            edge_colors = [palette_map.get(c, c) for c in edge_color]

        edge_options = dict(ax=ax, width=widths, edge_color=edge_colors, alpha=0.75, node_size=node_sizes)
        if flag == 2:
            edge_options.update(arrows=True, arrowstyle='-|>', arrowsize=12, connectionstyle='arc3, rad = 0.08')
        nx.draw_networkx_edges(G, pos, **edge_options)
        nx.draw_networkx_nodes(G, pos, ax=ax, node_size=node_sizes, node_color=colors["node"],
                               edgecolors=colors["node_border"], linewidths=1.5)
        label_pos = {n: (x, y + 0.045) for n, (x, y) in pos.items()}  # etichette sopra i nodi
        nx.draw_networkx_labels(G, label_pos, ax=ax, font_size=8, font_color=colors["text"],
                                verticalalignment='bottom',
                                bbox=dict(boxstyle='round,pad=0.2', fc=colors["label_bg"], ec='none', alpha=0.8))

        if G.number_of_edges() <= MAX_EDGE_LABELS and flag != 3:
            nx.draw_networkx_edge_labels(G, pos, ax=ax, edge_labels=weights, font_size=7,
                                         font_color=colors["text"], label_pos=0.4 if flag == 2 else 0.5,
                                         bbox=dict(boxstyle='round,pad=0.15', fc=colors["background"], ec='none'))

        if flag == 3:
            legend_labels = {'Collaborazioni': colors["collaborations"], 'Comunicazioni': colors["communications"],
                             'Entrambe': colors["composite"]}
            legend_handles = [Line2D([0], [0], color=color, linewidth=3, label=label)
                              for label, color in legend_labels.items()]
            legend = ax.legend(handles=legend_handles, title="Tipi di collegamenti", loc='best',
                               facecolor=colors["label_bg"], edgecolor=colors["label_bg"], labelcolor=colors["text"])
            legend.get_title().set_color(colors["text"])

        fig.tight_layout()


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
