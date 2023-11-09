from src.model.User import User
from src.model.Communication import Communication
from typing import Dict, Set
import requests
import datetime


TOKEN = "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"


# TO DO: adattarla bene alle pull requests, per ora prende solo i commenti e non va bene
# con le issue funziona bene
def get_communications(owner: str, repo_name: str, communication_type: str):

    # conterrà tutti gli utenti che hanno avuto comunicazioni in una qualsiasi issue
    # in pratica, conterrà tutti i nodi del grafo
    all_users: Dict[str, User] = {}

    # è un buffer che serve a tener traccia degli utenti che hanno commentato, viene pulito per ogni issue
    previous_comments_usernames: Set[str] = set()

    starting_date = (datetime.datetime.now() - datetime.timedelta(days=7))
    header = {"Authorization": "Bearer " + TOKEN}

    # prendo tutte le issue di un certo repo che hanno ricevuto commenti negli ultimi 30 giorni, ordinate per data
    response = requests.get(
        'https://api.github.com/repos/' + owner + '/' + repo_name + '/' + communication_type +
        '?state=all&sort=updated&direction=desc&since=' + starting_date.strftime("%Y-%m-%dT%H:%M:%SZ"), headers=header)

    if response.status_code == 200:
        for issue in response.json():

            # per ogni issue prendo tutti i commenti, ordinati per data
            response = requests.get(
                'https://api.github.com/repos/' + owner + '/' + repo_name + '/' + communication_type + '/' +
                str(issue["number"]) + '/comments?state=all&sort=created&direction=asc', headers=header)

            if response.status_code == 200:
                previous_comments_usernames.clear()

                # booleano che indica se ignorare l'issue perché non è avvenuta nessuna comunicazione
                # (es. issue senza commenti, issue commentata unicamente dalla persona che l'ha creata)
                communication_happened = False

                # ignoro le issue senza commenti
                if len(response.json()) > 0:

                    # se c'è almeno un commento creato da un utente diverso da chi ha creato l'issue salvo l'utente
                    # sia nel buffer che come nodo del grafo e pongo communication_happened=True
                    issue_creator = issue["user"]["login"]
                    for comment in response.json():
                        if comment["user"]["login"] != issue_creator:
                            communication_happened = True
                            if all_users.get(issue_creator) is None:
                                all_users[issue_creator] = User(issue_creator)
                            previous_comments_usernames.add(issue_creator)
                            break

                if communication_happened:
                    for comment in response.json():
                        created_date = datetime.datetime.strptime(comment["created_at"], "%Y-%m-%dT%H:%M:%SZ")

                        # per ogni commento mi salvo l'utente che lo ha generato
                        comment_author = comment["user"]["login"]
                        if all_users.get(comment_author) is None:
                            all_users[comment_author] = User(comment_author)

                        # solo se il commento è creato nell'ultimo mese e se c'è almeno un commento precedente
                        # controllo e salvo le comunicazioni generate dal commento
                        if created_date >= starting_date:
                            communication = Communication(all_users[comment_author], created_date, communication_type)
                            # questo ciclo serve a cancellare la comunicazione dell'autore del commento con se stesso
                            for username in previous_comments_usernames:
                                if username != comment_author:
                                    communication.receivers.append(all_users[username])
                            # se la comunicazione non ha ricevitori (es. commento a se stessi) non la salvo
                            if len(communication.receivers) > 0:
                                all_users[comment_author].communications[created_date] = communication

                        previous_comments_usernames.add(comment_author)

            else:
                print(response.status_code)

    else:
        print(response.status_code)

    # per ogni utente ordina le comunicazioni dalla più recente alla più vecchia
    for key in all_users:
        all_users[key].communications = dict(sorted(all_users[key].communications.items(), reverse=True))

    return all_users
