import whois
from datetime import datetime

class GetDomainInfo:
    @staticmethod
    def get_info(domain: str):
        try:
            # Utilisation de la bibliothèque whois pour récupérer les informations du domaine
            domain_info = whois.whois(domain)
            
            # Extraction de la date d'enregistrement (date de création) et de la date d'expiration
            creation_date = domain_info.creation_date
            expiration_date = domain_info.expiration_date
            
            # Formattage des dates pour les rendre lisibles
            if isinstance(creation_date, list):
                creation_date = creation_date[0]  # Parfois c'est une liste, on prend la première date
            
            if isinstance(expiration_date, list):
                expiration_date = expiration_date[0]  # Pareil pour l'expiration

            result = {
                "domain": domain,
                "status": "active" if domain_info.status else "inactive",
                "creation_date": creation_date.strftime("%Y-%m-%dT%H:%M:%S") if creation_date else "N/A",
                "expiration_date": expiration_date.strftime("%Y-%m-%dT%H:%M:%S") if expiration_date else "N/A",
            }
            
            return result
        except Exception as e:
            return {"error": str(e)}
