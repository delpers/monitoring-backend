import requests
from fastapi import Request

IPINFO_API_KEY = "8ac58b80584dd3"  # Remplacez par votre token API ipinfo.io

def get_public_ip(request: Request):
    try:
        # Vérifier d'abord l'en-tête 'x-forwarded-for' pour les IP derrière un proxy
        ip = request.headers.get('x-forwarded-for')
        if ip:
            # Si plusieurs IP sont présentes (séparées par des virgules), on prend la première
            ip = ip.split(',')[0].strip()
        else:
            # Sinon, utiliser l'IP directe du client (souvent le proxy lui-même)
            ip = request.client.host
        
        # Effectuer une requête à l'API ipinfo pour récupérer les informations de l'IP
        response = requests.get(f"https://ipinfo.io/{ip}/json?token={IPINFO_API_KEY}")
        data = response.json()

        # Récupérer la ville, l'ISP et l'ASN
        city = data.get("city", "Inconnue")
        isp = data.get("org", "Inconnu")  # org contient généralement l'ISP ou l'AS
        asn = data.get("asn", {}).get("asn", "Inconnu")  # ASN peut être dans la clé 'asn'

        return {
            "ip": ip,
            "city": city,
            "isp": isp,
            "asn": asn
        }
    
    except Exception as e:
        print(f"Erreur lors de la récupération de l'IP publique ou des informations : {e}")
        return None
