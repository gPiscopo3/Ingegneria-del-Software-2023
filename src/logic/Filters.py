from datetime import datetime
from itertools import combinations
from typing import List, Dict
from src.model.File import File
from src.model.User import User


def communications_in_range(start: datetime, end: datetime, users: List[User]):
    try:
        adjacency_map: Dict[User, List[User]] = dict()
        for sender in users:
            adjacency_map[sender] = list()
            for date, receivers in sender.communications.items():
                if start <= date <= end:
                    for rec in receivers:
                        adjacency_map[sender].append(rec)
        return adjacency_map
    except TypeError:
        print("TypeError: wrong type")


def collaborations_in_range(start: datetime, end: datetime, files: List[File]):
    try:
        edges = []
        for file in files:
            collaborators = set()
            for commit_date, author in file.modified_by.items():
                if start <= commit_date <= end:
                    collaborators.add(author)
            if len(collaborators) > 1:
                all_pairs = list(combinations(collaborators, 2))
                edges.append(all_pairs)
        return edges
    except TypeError:
        print("TypeError: wrong type")
