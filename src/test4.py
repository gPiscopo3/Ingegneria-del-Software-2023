from src.logic import APICalls
import datetime
from collections import Counter

from src.logic.Filters import communications_in_range, create_directed_edges
from src.logic.Pull_issue_request import pulls_json

from src.logic.DataManagement import get_communications_since

TOKEN = "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"
header = {"Authorization": "Bearer " + TOKEN}
dt = datetime.datetime(2023, 12, 1)

# res = APICalls.get_pulls_since("tensorflow", "tensorflow", dt, TOKEN)
#
# for pull in res:
#     print(pull)

# res = pulls_json("tensorflow", "tensorflow", dt, TOKEN)
# for pull in res:
#     print(pull)

res = get_communications_since("tensorflow", "tensorflow", dt, TOKEN)
# for user_id, user in res.items():
#     print(user_id)
#     for data, set_utenti in user.communications.items():
#         print("ha comunicato in data: " + str(data) + " con gli utenti: ")
#         for u in set_utenti:
#             print(u.username)
#     print()

res2 = communications_in_range(datetime.datetime(2023, 11, 1), datetime.datetime(2023, 12, 15), res)

for user, list_user in res2.items():
    print(user.username)
    for receiver in list_user:
        print(receiver.username)
    print()

print("**************")

lista_archi_diretti = create_directed_edges(res2)
#print(lista_archi_diretti)
# for tupla in lista_archi_diretti:
#     print(tupla[0].username)
#     print(tupla[1].username)
#     print()

conteggi_totali = Counter(lista_archi_diretti)
#print(conteggi_totali)
for coppia, conteggio in conteggi_totali.items():
    print(f"{coppia[0].username, coppia[1].username}: {conteggio} volte")


