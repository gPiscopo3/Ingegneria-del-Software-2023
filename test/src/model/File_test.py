# AI test suite generated for File.py

import pickle
from datetime import datetime
from src.model.User import User  # Assicurati di importare correttamente il modulo User dalla posizione corretta
from src.model.File import File  # Assumendo che la classe File sia definita in un modulo chiamato File


# Test suite per la classe File
class TestFile:
    def test_initialization(self):
        file = File("test_identifier")
        assert file.identifier == "test_identifier"
        assert file.modified_by == []

    def test_add_edit(self):
        file = File("test_identifier")
        user = User("test_user", "test_user")
        date = datetime(2023, 12, 1)

        file.add_edit(date, user)
        assert file.modified_by == [(date, user)]

    def test_add_edit_same_second_keeps_both(self):
        # due autori che modificano il file nello stesso secondo: nessuna modifica va persa
        file = File("test_identifier")
        alice, bob = User(1, "alice"), User(2, "bob")
        date = datetime(2023, 12, 1, 10, 0, 0)

        file.add_edit(date, alice)
        file.add_edit(date, bob)
        file.sort_edits()
        assert sorted(author.username for _, author in file.modified_by) == ["alice", "bob"]

    def test_sort_edits(self):
        file = File("test_identifier")
        user1 = User("user1", "test_user1")
        user2 = User("user2", "test_user2")
        user3 = User("user3", "test_user3")
        date1, date2, date3 = datetime(2023, 12, 1), datetime(2023, 12, 2), datetime(2023, 12, 3)

        file.add_edit(date2, user2)
        file.add_edit(date1, user1)
        file.add_edit(date3, user3)

        file.sort_edits()
        assert file.modified_by == [(date3, user3), (date2, user2), (date1, user1)]

    def test_print_edits(self, capsys):  # Utilizzo di capsys per catturare l'output della funzione print
        file = File("test_identifier")
        user = User("test_user", "test_user1")
        date = datetime(2023, 12, 25)

        file.add_edit(date, user)
        file.print_edits()

        captured = capsys.readouterr()
        expected_output = "test_identifier\n2023-12-25T00:00:00Z - test_user1\n-------\n"
        assert captured.out == expected_output

    def test_str_representation(self):
        file = File("test_identifier")
        assert str(file) == "File: [identifier= test_identifier, ModifiedBy={}]"

        # Aggiungi una modifica per il file
        user = User("user_id", "username")
        date = datetime(2023, 12, 26)
        file.add_edit(date, user)

        # Verifica la rappresentazione in stringa dopo l'aggiunta della modifica
        expected_output = f"File: [identifier= test_identifier, ModifiedBy={{{date}: {user}}}]"
        assert str(file) == expected_output

    def test_equality(self):
        file1 = File("test_identifier")
        file2 = File("test_identifier")
        assert file1 == file2

        # Verifica l'ineguaglianza tra due oggetti File con identificatori diversi
        file3 = File("different_identifier")
        assert file1 != file3

        # Verifica l'ineguaglianza con un oggetto di un'altra classe
        assert file1 != "not_a_file_object"

    def test_hash_consistent_with_equality(self):
        # file uguali (stesso identificatore) devono avere lo stesso hash anche con modifiche diverse
        file1, file2 = File("test_identifier"), File("test_identifier")
        file1.add_edit(datetime(2023, 12, 1), User(1, "alice"))
        assert file1 == file2
        assert hash(file1) == hash(file2)
        assert len({file1, file2}) == 1

    def test_unpickle_version_1_dict(self):
        # file .graphapp salvati con la versione 1: modified_by era un dict {data: autore}
        user = User(1, "alice")
        old = File("a.py")
        old.modified_by = {datetime(2023, 12, 1): user, datetime(2023, 12, 3): user}
        loaded = pickle.loads(pickle.dumps(old))
        assert isinstance(loaded.modified_by, list)
        assert [(date, author.username) for date, author in loaded.modified_by] == \
               [(datetime(2023, 12, 3), "alice"), (datetime(2023, 12, 1), "alice")]
