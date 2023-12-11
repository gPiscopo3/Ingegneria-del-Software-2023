from src.logic import APICalls
import datetime

from src.logic.DataManagement import get_communications_since

TOKEN = "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"
header = {"Authorization": "Bearer " + TOKEN}
dt = datetime.datetime(2023, 12, 1)

# res = APICalls.get_pulls_since("tensorflow", "tensorflow", dt, TOKEN)
#
# for pull in res:
#     print(pull)

res = get_communications_since("tensorflow", "tensorflow", dt, TOKEN)
for user_id, user in res.items():  # ordina per data (discendente) le comunicazioni di ogni utente
    print(user_id)
    for data, set_utenti in user.communications.items():
        print("ha comunicato in data: " + str(data) + " con gli utenti: ")
        for u in set_utenti:
            print(u.username)
    print()
