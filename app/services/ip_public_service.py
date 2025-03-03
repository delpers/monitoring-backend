import requests

def get_public_ip():
    try:
        response = requests.get('https://api.ipify.org?format=json')
        ip = response.json().get("ip")
        return ip
    except Exception as e:
        print(f"Erreur lors de la récupération de l'IP publique : {e}")
        return None
