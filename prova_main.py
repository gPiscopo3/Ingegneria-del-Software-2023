from src.logic.DataManagement import get_collaborations_since
from src.logic.Filters import collaborations_in_range
from datetime import datetime
from datetime import timedelta
from collections import Counter

token = ""

files = get_collaborations_since("tensorflow", "tensorflow", datetime.now() - timedelta(days=2), token)
result = collaborations_in_range(datetime.now() - timedelta(days=2), datetime.now(), files)
print(type(result))

lista_trasformata = [
    [tuple(sorted((coppia[0], coppia[1]), key=lambda x: x.username)) for coppia in lista]
    for lista in result
]

conteggi_totali = Counter([item for sublist in lista_trasformata for item in sublist])

print("Occorrenze delle coppie di oggetti:")
for coppia, conteggio in conteggi_totali.items():
    if conteggio > 1:
        print(f"{coppia[0].username, coppia[1].username}: {conteggio} volte")

print(type(conteggi_totali))
