# app/services/response_time_service.py
import requests
import time
from typing import Optional

def get_response_time(url: str) -> Optional[float]:
    """
    Cette fonction mesure le temps de réponse pour un URL donné.
    
    :param url: L'URL du site à surveiller
    :return: Le temps de réponse en secondes, ou None si une erreur se produit
    """
    try:
        # Vérifier si l'URL commence par 'http:// ou https://', sinon ajouter 'http://'
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "http://" + url
        
        start_time = time.time()  # Enregistre l'heure avant la requête
        response = requests.get(url)  # Envoie la requête HTTP GET
        
        # Si la requête échoue ou le statut HTTP n'est pas 2xx, une exception sera levée
        response.raise_for_status()  # Vérifie que la réponse est correcte (status 200)
        
        end_time = time.time()  # Enregistre l'heure après la réponse
        
        # Retourner le temps de réponse en secondes
        return round(end_time - start_time, 2)
    except requests.exceptions.RequestException as e:
        # Log des erreurs pour déboguer
        print(f"Erreur lors de la connexion à {url}: {e}")
        return None
