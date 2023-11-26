import requests

CLIENT_ID = "Iv1.d557ebb9ed145302"  # relativo all'app, non all'utente


# sono i due metodi che verranno usati per autenticarsi, i metodi singolarmente funzionano ma serve una parte di
# interazione con l'utente da implementare


# metodo eseguito in automatico all'avvio dell'app e restituisce valori utili per l'autenticazione:
#   verification_uri: URL che l'utente dovrà clickare per autenticarsi via browser (NON si può implementare tramite
#                     API github, quindi non possiamo metterlo diretto nell'app)
#   user_code: codice che l'utente dovrà inserire all'url per autenticarsi
#   device_code: codice da passare per ottenere l'access token
def get_user_code():
    response = requests.post("https://github.com/login/device/code?client_id=" + CLIENT_ID)
    params = dict(param.split('=') for param in response.text.split('&'))
    return params


# dopo aver fatto i passaggi necessari via browser, l'utente clickerà un tasto che farà eseguire questo metodo
def get_access_token(device_code: str):
    query_string = ("client_id=" + CLIENT_ID + "&device_code=" + device_code +
                    "&grant_type=urn:ietf:params:oauth:grant-type:device_code")
    response = requests.post("https://github.com/login/oauth/access_token?" + query_string)
    params = dict(param.split('=') for param in response.text.split('&'))
    if "access_token" in params:
        return params["access_token"]

    # se l'utente clicka il tasto senza aver fatto i passaggi necessari via browser, non c'è un access token e questo
    # metodo ritorna una stringa vuota (servirà far apparire un messaggio d'errore e non cambiare schermata)
    else:
        return ""
