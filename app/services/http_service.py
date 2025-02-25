# app/services/http_service.py

import requests
from config.settings import API_URL

class HTTPService:
    def __init__(self):
        self.api_url = API_URL  # Récupère l'URL depuis settings.py

    def get_domains(self):
        try:
            response = requests.get(self.api_url)  # Effectue l'appel à l'API externe
            response.raise_for_status()  # Vérifie que la requête a réussi (code 200)
            return response.json()  # Retourne les données JSON
        except requests.exceptions.RequestException as e:
            print(f"Erreur lors de la récupération des données : {e}")
            return None
