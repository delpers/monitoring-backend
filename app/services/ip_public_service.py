# app/services/ip_public_service.py

import requests

def get_public_ip():
    try:
        # Utilisation d'un service comme ipify pour obtenir l'IP publique
        response = requests.get("https://api.ipify.org?format=json")
        response.raise_for_status()  # Vérifie que la requête a réussi
        data = response.json()
        return data.get("ip")
    except requests.exceptions.RequestException as e:
        # En cas d'erreur lors de la récupération
        print(f"Erreur lors de la récupération de l'IP publique: {e}")
        return None
