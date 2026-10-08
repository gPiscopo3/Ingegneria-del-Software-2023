import csv
import os
import tempfile
import zipfile
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, Optional

import networkx as nx
import numpy as np
import scipy.io
import scipy.sparse

from src.i18n import tr
from src.logic.Filters import collaborations_in_range, communications_in_range
from src.model.File import File
from src.model.User import User

# esportazione del grafo e dei dati grezzi per l'analisi in R (igraph, statnet), MATLAB e Python (NetworkX)

TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"  # ISO 8601, UTC

# tipi di grafo, anche nei nomi dei file e nei metadati esportati: sempre in inglese, qualunque sia la lingua
# dell'interfaccia, perché gli script di analisi non dipendano dalla lingua di chi ha esportato
KINDS = ("collaboration", "communication", "composite")

DEFINITIONS = {
    "collaboration": ("undirected edge between two developers who modified at least one common file in the "
                      "interval",
                      "number of files modified by both"),
    "communication": ("directed edge source -> target: source replied (comment, review, commit in a PR) after "
                      "a contribution by target in the same issue or pull request",
                      "number of replies"),
    "composite": ("undirected edge: union of collaborations and communications (type = collaboration, "
                  "communication or both)",
                  "weight = weight_collaboration + weight_communication (communications summed in both directions)"),
}


def collaboration_weights(files: Dict[str, File], start: datetime, end: datetime) -> Counter:
    # stesse regole di create_graph: per ogni file, ogni coppia di sviluppatori che lo hanno modificato
    weights = Counter()
    for pairs in collaborations_in_range(start, end, files.values()):
        for a, b in pairs:
            weights[tuple(sorted((a.username, b.username)))] += 1
    return weights


def communication_weights(users: Dict[int, User], start: datetime, end: datetime) -> Counter:
    # stesse regole di create_graph_communication: un arco sender -> receiver per ogni risposta
    weights = Counter()
    for sender, receivers in communications_in_range(start, end, users.values()).items():
        for receiver in receivers:
            weights[(sender.username, receiver.username)] += 1
    return weights


def github_ids(files: Optional[Dict[str, File]], users: Optional[Dict[int, User]]) -> Dict[str, int]:
    ids = {}
    for file in (files or {}).values():
        for author in file.modified_by.values():
            ids[author.username] = author.identifier
    for user in (users or {}).values():
        ids[user.username] = user.identifier
        for receivers in user.communications.values():
            for receiver in receivers:
                ids[receiver.username] = receiver.identifier
    return ids


def build_export_graph(kind: str, files: Optional[Dict[str, File]], users: Optional[Dict[int, User]],
                       start: datetime, end: datetime):
    if kind not in KINDS:
        raise ValueError(f"unknown graph type: {kind}")
    if kind == "communication":
        g = nx.DiGraph()
        for (source, target), weight in communication_weights(users, start, end).items():
            g.add_edge(source, target, weight=weight)
    elif kind == "collaboration":
        g = nx.Graph()
        for (a, b), weight in collaboration_weights(files, start, end).items():
            g.add_edge(a, b, weight=weight)
    else:
        g = nx.Graph()
        collaborations = collaboration_weights(files, start, end)
        communications = Counter()
        for (source, target), weight in communication_weights(users, start, end).items():
            communications[tuple(sorted((source, target)))] += weight  # i due versi sommati
        for pair in set(collaborations) | set(communications):
            collaboration, communication = collaborations.get(pair, 0), communications.get(pair, 0)
            edge_type = "both" if collaboration and communication else (
                "collaboration" if collaboration else "communication")
            g.add_edge(*pair, weight=collaboration + communication, weight_collaboration=collaboration,
                       weight_communication=communication, type=edge_type)

    ids = github_ids(files, users)
    for node in g.nodes:
        attributes = g.nodes[node]
        attributes["github_id"] = int(ids[node]) if node in ids else -1
        attributes["degree"] = g.degree(node)
        attributes["strength"] = g.degree(node, weight="weight")
        if g.is_directed():
            attributes["in_degree"] = g.in_degree(node)
            attributes["out_degree"] = g.out_degree(node)
    return g


def graph_info(kind: str, owner: str, repo: str, start: datetime, end: datetime, directed: bool) -> Dict[str, str]:
    edge_definition, weight_definition = DEFINITIONS[kind]
    return {
        "repository": f"{owner}/{repo}",
        "graph_type": kind,
        "directed": "true" if directed else "false",
        "interval_start": start.strftime(TIMESTAMP_FORMAT),
        "interval_end": end.strftime(TIMESTAMP_FORMAT),
        "edge_definition": edge_definition,
        "weight_definition": weight_definition,
        "exported_at": datetime.now(timezone.utc).strftime(TIMESTAMP_FORMAT),
        "source": "GraphApp: GitHub REST API (issues, pull requests, comments, reviews) and git clone (commits)",
    }


def _node_columns(g):
    columns = ["github_id", "degree", "strength"]
    return columns + (["in_degree", "out_degree"] if g.is_directed() else [])


def _edge_columns(g):
    if any("type" in data for _, _, data in g.edges(data=True)):
        return ["weight", "weight_collaboration", "weight_communication", "type"]
    return ["weight"]


def write_nodes_edges_csv(g, nodes_path: str, edges_path: str):
    nodes = list(g.nodes)
    with open(nodes_path, "w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        columns = _node_columns(g)
        writer.writerow(["id", "name"] + columns)
        for index, node in enumerate(nodes, start=1):
            writer.writerow([index, node] + [g.nodes[node][c] for c in columns])
    with open(edges_path, "w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        columns = _edge_columns(g)
        writer.writerow(["source", "target"] + columns)
        for source, target, data in g.edges(data=True):
            writer.writerow([source, target] + [data[c] for c in columns])


def write_graphml(g, path: str, info: Dict[str, str]):
    g = g.copy()
    g.graph.update(info)  # provenienza e definizioni come attributi del grafo
    nx.write_graphml(g, path, encoding="utf-8")


def write_mat(g, path: str, info: Dict[str, str]):
    nodes = list(g.nodes)
    index = {node: i for i, node in enumerate(nodes)}
    n = len(nodes)

    def adjacency(attribute):
        rows, cols, values = [], [], []
        for source, target, data in g.edges(data=True):
            value = data.get(attribute, 0)
            if not value:
                continue
            rows.append(index[source])
            cols.append(index[target])
            values.append(float(value))
            if not g.is_directed() and source != target:  # MATLAB graph() richiede A simmetrica
                rows.append(index[target])
                cols.append(index[source])
                values.append(float(value))
        return scipy.sparse.csc_matrix((values, (rows, cols)), shape=(n, n))

    names = np.empty((n, 1), dtype=object)
    names[:, 0] = nodes
    edges = list(g.edges(data=True))
    data = {
        "A": adjacency("weight"),
        "names": names,
        "github_ids": np.array([[g.nodes[node]["github_id"]] for node in nodes], dtype=np.int64).reshape(n, 1),
        "directed": np.array([[g.is_directed()]]),
        "source": np.array([index[s] + 1 for s, _, _ in edges], dtype=np.int64).reshape(-1, 1),  # indici 1-based
        "target": np.array([index[t] + 1 for _, t, _ in edges], dtype=np.int64).reshape(-1, 1),
        "weight": np.array([d["weight"] for _, _, d in edges], dtype=float).reshape(-1, 1),
        "info": info,
    }
    if "type" in _edge_columns(g):
        data["A_collaboration"] = adjacency("weight_collaboration")
        data["A_communication"] = adjacency("weight_communication")
    scipy.io.savemat(path, data, do_compression=True)


def write_edits_csv(files: Dict[str, File], start: datetime, end: datetime, path: str) -> int:
    # rete bipartita sviluppatore-file con data: una riga per ogni modifica di un file nell'intervallo
    rows = sorted((date, author.username, author.identifier, file.identifier)
                  for file in files.values() for date, author in file.modified_by.items() if start <= date <= end)
    with open(path, "w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerow(["developer", "developer_id", "file", "timestamp"])
        for date, developer, developer_id, file in rows:
            writer.writerow([developer, developer_id, file, date.strftime(TIMESTAMP_FORMAT)])
    return len(rows)


def write_interactions_csv(users: Dict[int, User], start: datetime, end: datetime, path: str) -> int:
    # rete temporale delle comunicazioni: una riga per ogni risposta source -> target nell'intervallo
    rows = sorted((date, user.username, user.identifier, receiver.username, receiver.identifier)
                  for user in users.values() for date, receivers in user.communications.items()
                  if start <= date <= end for receiver in receivers)
    with open(path, "w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerow(["source", "source_id", "target", "target_id", "timestamp"])
        for date, source, source_id, target, target_id in rows:
            writer.writerow([source, source_id, target, target_id, date.strftime(TIMESTAMP_FORMAT)])
    return len(rows)


# file prodotti da ciascuna modalità di esportazione (aggiunti al prefisso scelto dall'utente);
# l'estensione dell'immagine dipende dal formato scelto
EXPORT_SUFFIXES = {
    "csv": ["_nodes.csv", "_edges.csv"],
    "graphml": [".graphml"],
    "mat": [".mat"],
    "edits": ["_edits.csv"],
    "interactions": ["_interactions.csv"],
    "image": [".{image_format}"],
}
IMAGE_FORMATS = ("png", "svg", "pdf")


def file_names(keys, prefix: str, image_format: str = "png"):
    return [prefix + suffix.format(image_format=image_format)
            for key in EXPORT_SUFFIXES if key in keys for suffix in EXPORT_SUFFIXES[key]]


# nomi creati nella cartella: un unico .zip se le modalità sono più di una, altrimenti i file singoli
def output_names(keys, prefix: str, image_format: str = "png"):
    return [prefix + ".zip"] if len(keys) > 1 else file_names(keys, prefix, image_format)


def _image_format(context: Dict) -> str:
    image_format = context.get("image_format", "png")
    if image_format not in IMAGE_FORMATS:
        raise ValueError(f"unsupported image format: {image_format}")
    return image_format


def _write_all(context: Dict, keys, base: str):
    start, end = context["start"], context["end"]
    if "image" in keys:
        # il disegno arriva dall'interfaccia (stessa disposizione del grafo mostrato): qui nessuna dipendenza da Qt
        context["draw_image"](base + "." + _image_format(context))
    if any(k in keys for k in ("csv", "graphml", "mat")):
        g = build_export_graph(context["kind"], context["files"], context["users"], start, end)
        info = graph_info(context["kind"], context["owner"], context["repo"], start, end, g.is_directed())
        if "csv" in keys:
            write_nodes_edges_csv(g, base + "_nodes.csv", base + "_edges.csv")
        if "graphml" in keys:
            write_graphml(g, base + ".graphml", info)
        if "mat" in keys:
            write_mat(g, base + ".mat", info)
    if "edits" in keys:
        write_edits_csv(context["files"], start, end, base + "_edits.csv")
    if "interactions" in keys:
        write_interactions_csv(context["users"], start, end, base + "_interactions.csv")


# context: owner, repo, kind, start, end, files, users del grafo mostrato; ritorna i percorsi creati
def export_files(context: Dict, keys, directory: str, prefix: str):
    keys = [key for key in EXPORT_SUFFIXES if key in keys]
    if not keys:
        raise ValueError(tr("export.select_one"))
    names = file_names(keys, prefix, _image_format(context) if "image" in keys else "png")
    if len(keys) == 1:
        _write_all(context, keys, os.path.join(directory, prefix))
        return [os.path.join(directory, name) for name in names]

    # più modalità: tutto in un unico zip, scritto a parte e poi rinominato per non lasciare file troncati
    zip_path = os.path.join(directory, prefix + ".zip")
    with tempfile.TemporaryDirectory(prefix="graphapp-export-") as work:
        _write_all(context, keys, os.path.join(work, prefix))
        partial = zip_path + ".part"
        try:
            with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for name in names:
                    archive.write(os.path.join(work, name), arcname=name)
            os.replace(partial, zip_path)
        finally:
            if os.path.exists(partial):
                os.remove(partial)
    return [zip_path]
