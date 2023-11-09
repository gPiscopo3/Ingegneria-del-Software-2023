from src.model.User import User
from src.model.Communication import Communication
from typing import Dict, Set
import requests as r
import datetime


TOKEN = "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"


def get_issues(owner: str, repo_name: str):

    # conterrà tutti gli utenti che hanno avuto comunicazioni in una qualsiasi issue
    # in pratica, conterrà tutti i nodi del grafo
    all_users: Dict[str, User] = {}

    # è un buffer che serve a tener traccia degli utenti che hanno commentato, viene pulito per ogni issue
    previous_comments_usernames: Set[str] = set()

    starting_date = (datetime.datetime.now() - datetime.timedelta(days=30))
    header = {"Authorization": "Bearer " + TOKEN}

    # prendo tutte le issue di un certo repo che hanno ricevuto commenti negli ultimi 30 giorni, ordinate per data
    response = r.get(
        'https://api.github.com/repos/' + owner + '/' + repo_name + '/issues?state=all&sort=updated&direction=desc'
        '&since=' + starting_date.strftime("%Y-%m-%dT%H:%M:%SZ"), headers=header)

    if response.status_code == 200:
        for i in response.json():

            # per ogni issue prendo tutti i commenti, ordinati per data
            response = r.get(
                'https://api.github.com/repos/' + owner + '/' + repo_name + '/issues/' + str(i["number"]) + '/comments'
                '?state=all&sort=created&direction=asc',
                headers=header)

            if response.status_code == 200:
                previous_comments_usernames.clear()

                # se l'issue ha almeno un commento controllo le comunicazioni avvenute, se ne ha zero la ignoro
                # TO DO: ignorare le issue create e commentate unicamente dalla stessa persona
                if len(response.json()) > 0:

                    # salvo l'utente che ha creato l'issue sia nel buffer che come nodo del grafo
                    username = i["user"]["login"]
                    if all_users.get(username) is None:
                        all_users[username] = User(username)
                    previous_comments_usernames.add(username)

                    for c in response.json():
                        created_date = datetime.datetime.strptime(c["created_at"], "%Y-%m-%dT%H:%M:%SZ")

                        # per ogni commento mi salvo l'utente che lo ha generato
                        username = c["user"]["login"]
                        if all_users.get(username) is None:
                            all_users[username] = User(username)

                        # solo se il commento è creato nell'ultimo mese e se c'è almeno un commento precedente
                        # controllo e salvo le comunicazioni generate dal commento
                        if created_date >= starting_date:
                            communication = Communication(all_users[username], created_date, 'issue')
                            # questo ciclo serve a cancellare la comunicazione dell'autore del commento con se stesso
                            for u in previous_comments_usernames:
                                if u != username:
                                    communication.receivers.append(all_users[u])
                            all_users[username].comms[created_date] = communication

                        previous_comments_usernames.add(username)

            else:
                print(response.status_code)

    else:
        print(response.status_code)

    return all_users
