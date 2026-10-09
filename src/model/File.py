from datetime import datetime
from typing import List, Tuple
from src.model.User import User


class File:
    def __init__(self, identifier):
        self.identifier: str = identifier
        # lista e non dict per data: due modifiche nello stesso secondo restano entrambe
        self.modified_by: List[Tuple[datetime, User]] = []

    def add_edit(self, date, author):
        self.modified_by.append((date, author))

    def sort_edits(self):
        self.modified_by.sort(key=lambda edit: edit[0], reverse=True)

    def print_edits(self):
        print(self.identifier)
        for date, author in self.modified_by:
            print(date.strftime("%Y-%m-%dT%H:%M:%SZ") + " - " + author.username)
        print("-------")

    def __str__(self):
        return "File: [identifier= " + self.identifier + ", ModifiedBy={" + ";".join([f"{chiave}: {valore}" for chiave,
            valore in self.modified_by]) + "}]"

    def __eq__(self, other):
        if isinstance(other, File):
            return self.identifier == other.identifier
        return False

    def __hash__(self):
        # coerente con __eq__: file uguali devono avere lo stesso hash
        return hash(self.identifier)

    def __setstate__(self, state):
        # file salvati con la versione 1 del formato: modified_by era un dict {data: autore}
        if isinstance(state.get("modified_by"), dict):
            state["modified_by"] = sorted(state["modified_by"].items(), key=lambda edit: edit[0], reverse=True)
        self.__dict__.update(state)
