from logic import DataManagement
from datetime import datetime
from datetime import timedelta


TOKEN = "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"

users = DataManagement.get_communications_since("fullmoonlullaby", "test", datetime.today() -
                                                timedelta(days=30), TOKEN)

for user in users.values():
    user.print_communications()


files = DataManagement.get_collaborations_since("fullmoonlullaby", "test", datetime.today() -
                                                timedelta(days=7), TOKEN)

for file in files.values():
    file.print_edits()

