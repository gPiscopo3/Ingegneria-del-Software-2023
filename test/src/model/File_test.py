# AI test suite generated for File.py

from datetime import datetime
from src.model.User import User  # Assicurati di importare correttamente il modulo User dalla posizione corretta
from src.model.File import File  # Assumendo che la classe File sia definita in un modulo chiamato File


# Test suite per la classe File
class TestFile:
    def test_initialization(self):
        file = File("test_identifier")
        assert file.identifier == "test_identifier"
        assert file.modified_by == {}

    def test_add_edit(self):
        file = File("test_identifier")
        user = User("test_user", "test_user")
        date = datetime.now()

        file.add_edit(date, user)
        assert date in file.modified_by
        assert file.modified_by[date] == user

    def test_sort_edits(self):
        file = File("test_identifier")
        user1 = User("user1", "test_user1")
        user2 = User("user2", "test_user2")
        date1 = datetime.now()
        date2 = datetime.now()

        file.add_edit(date1, user1)
        file.add_edit(date2, user2)

        file.sort_edits()
        dates = list(file.modified_by.keys())
        assert dates == sorted(dates, reverse=True)

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

    def test_hash(self):
        file = File("test_identifier")
        my_dict = {}
        hashable_dict = tuple(sorted(my_dict.items()))
        assert hash(file) == hash(("test_identifier", hashable_dict))
