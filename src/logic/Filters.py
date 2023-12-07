from datetime import datetime
from itertools import combinations
from typing import List, Dict, Set
from src.model.File import File
from src.model.User import User


def communications_in_range(start: datetime, end: datetime, users: List[User]):
    adjacency_map: Dict[User, Set[User]] = dict()
    for sender in users:
        adjacency_map[sender] = set()
        for date, receivers in sender.communications.items():
            if start <= date <= end:
                adjacency_map[sender].update(receivers)
    return adjacency_map


def collaborations_in_range(start: datetime, end: datetime, files):
    edges = []
    for sha, file in files.items():
        collaborators = set()
        for commit_date, author in file.modified_by.items():
            if start <= commit_date <= end:
                collaborators.add(author)
        if len(collaborators) > 1:
            all_pairs = list(combinations(collaborators, 2))
            edges.append(all_pairs)
    return edges



