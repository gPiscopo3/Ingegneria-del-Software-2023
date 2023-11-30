from PyQt6.QtWidgets import QWidget, QVBoxLayout
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
import networkx as nx
from datetime import datetime
from src.logic.DataManagement import get_collaborations_since
from src.logic.Filters import collaborations_in_range


def create_graph(owner: str, repo_name: str, starting_date: datetime, token: str, datai: datetime, dataf: datetime):
    files = get_collaborations_since(owner, repo_name, starting_date, token)
    collaborations = collaborations_in_range(datai, dataf, files)
    print(collaborations)

    # Creazione di un grafo non diretto
    G = nx.Graph()

    # Aggiunta degli utenti come nodi
    for tupla in collaborations:
        for a in tupla:
            G.add_edge(a[0].username, a[1].username)

    return G


class GraphWidget(QWidget):
    def __init__(self, G):
        super().__init__()

        self.initUI(G)

    def initUI(self, G):
        # Creazione di un layout verticale per il widget
        layout = QVBoxLayout(self)

        # Creazione della figura per il grafo
        fig, ax = plt.subplots()
        canvas = FigureCanvasQTAgg(fig)
        layout.addWidget(canvas)

        # Disegno del grafo sulla figura
        pos = nx.spring_layout(G)  # Puoi cambiare l'algoritmo di posizionamento a seconda delle tue esigenze
        nx.draw(G, pos, with_labels=True, font_weight='bold', ax=ax)

        # Aggiunta del canvas al layout
        layout.addWidget(canvas)
