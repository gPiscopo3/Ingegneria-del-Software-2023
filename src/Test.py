from logic import DataManagement
from datetime import datetime
from datetime import timedelta


TOKEN = "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"

users = DataManagement.get_communications_since("fullmoonlullaby", "test", datetime.today() -
                                                timedelta(days=30), TOKEN)

for user in users.values():
    user.print_communications()


files = DataManagement.get_collaborations_since("fullmoonlullaby", "test", datetime.today() -
                                                timedelta(days=14), TOKEN)

for file in files.values():
    file.print_edits()

