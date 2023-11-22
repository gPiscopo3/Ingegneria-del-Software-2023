from datetime import datetime
from itertools import combinations
from typing import List, Dict, Set
from model.File import File
from model.User import User


def communications_in_range(start: datetime, end: datetime, users: List[User]):
    adjacency_map: Dict[User, Set[User]] = dict()
    for sender in users:
        adjacency_map[sender] = set()
        for date, receivers in sender.communications.items():
            if start <= date <= end:
                adjacency_map[sender].update(receivers)
    return adjacency_map


def collaborations_in_range(start: datetime, end: datetime, files: List[File]):
    edges = []
    for file in files:
        collaborators = set()
        for commit_date, author in file.modifiedBy.items():
            if start <= commit_date <= end:
                collaborators.add(author)
        if len(collaborators) > 1:
            all_pairs = list(combinations(collaborators, 2))
            edges.append(all_pairs)
    return list(set(tuple(sorted(coppia)) for coppia in edges))