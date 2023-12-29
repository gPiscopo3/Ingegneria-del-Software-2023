from datetime import datetime
from typing import Dict
from src.model.User import User


class File:
    def __init__(self, identifier):
        self.identifier: str = identifier
        self.modified_by: Dict[datetime, User] = {}

    def add_edit(self, date, author):
        self.modified_by[date] = author

    def sort_edits(self):
        self.modified_by = dict(sorted(self.modified_by.items(), reverse=True))

    def print_edits(self):
        print(self.identifier)
        for date, author in self.modified_by.items():
            print(date.strftime("%Y-%m-%dT%H:%M:%SZ") + " - " + author.username)
        print("-------")

    def __str__(self):
        return "File: [identifier= " + self.identifier + ", ModifiedBy={" + ";".join([f"{chiave}: {valore}" for chiave,
            valore in self.modified_by.items()]) + "}]"

    def __eq__(self, other):
        if isinstance(other, File):
            return self.identifier == other.identifier
        return False

    def __hash__(self):
        hashable_modifiedy_by = tuple(sorted(self.modified_by.items()))
        return hash((self.identifier, hashable_modifiedy_by))
