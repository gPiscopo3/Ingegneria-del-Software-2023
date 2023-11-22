from APICalls import get_collaborations_since
from logic import Filters, APICalls

files = get_collaborations_since("2023-11-09T00:00:00Z", "tensorflow", "tensorflow", "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")

#collaborations_in_range("")

'''


from matplotlib import pyplot as plt

import networkx as nx

from logic import get_issues
import networkx as nx
from matplotlib import pyplot as plt

from logic import get_issues


# Funzione per creare un grafo interattivo delle comunicazioni tra gli utenti
def create_interactive_graph(owner, repo_name):
    all_users = get_issues(owner, repo_name)

    # Crea un grafo diretto
    communication_graph = nx.DiGraph()

    # Aggiungi nodi e archi al grafo basandoti sulle comunicazioni degli utenti
    for username, user in all_users.items():
        communication_graph.add_node(username)  # Aggiungi nodo per l'utente corrente
        for communication_date, communication in user.comms.items():
            sender = communication.sender
            for receiver in communication.receivers:
                communication_graph.add_edge(sender, receiver, date=communication_date)

    # Visualizza il grafo
    pos = nx.spring_layout(communication_graph)  # Posiziona i nodi in modo da rendere il grafo più leggibile
    nx.draw(communication_graph, pos, with_labels=True, node_size=700, node_color='skyblue', font_size=10,
            font_color='black', font_weight='bold', width=2, edge_color='gray', connectionstyle="arc3,rad=-0.3")
    plt.show()

# Esempio di utilizzo della funzione
owner = "fullmoonlullaby"
repo_name = "test"
create_interactive_graph(owner, repo_name)

'''