# AI Generated Test Suite for User.py

from datetime import datetime
from src.model.User import User  # Assicurati di importare correttamente la classe User dalla posizione corretta


# Test suite per la classe User
class TestUser:
    def test_initialization(self):
        user = User("test_id", "test_username")
        assert user.identifier == "test_id"
        assert user.username == "test_username"
        assert user.communications == {}

    def test_update_communication(self):
        user = User("test_id", "test_username")
        receiver1 = User("receiver_id_1", "receiver1")
        receiver2 = User("receiver_id_2", "receiver2")
        date = datetime.now()

        user.update_communication(date, {receiver1, receiver2})
        assert date in user.communications
        assert receiver1 in user.communications[date]
        assert receiver2 in user.communications[date]

    def test_sort_communications(self):
        user = User("test_id", "test_username")
        receiver1 = User("receiver_id_1", "receiver1")
        receiver2 = User("receiver_id_2", "receiver2")
        date1 = datetime.now()
        date2 = datetime.now()

        user.update_communication(date1, {receiver1})
        user.update_communication(date2, {receiver2})

        user.sort_communications()
        dates = list(user.communications.keys())
        assert dates == sorted(dates, reverse=True)

    def test_print_communications(self, capsys):  # Utilizzo di capsys per catturare l'output della funzione print
        user = User("test_id", "test_username")
        receiver = User("receiver_id", "receiver")
        date = datetime(2023, 12, 25)

        user.update_communication(date, {receiver})
        user.print_communications()

        captured = capsys.readouterr()
        expected_output = "Sender: test_username\n \n2023-12-25 00:00:00\nreceiver\n \n-------\n"
        assert captured.out == expected_output

    def test_str_representation(self):
        user = User("test_id", "test_username")
        assert str(user) == "User: [identifier= test_id, username= test_username]"
