from fastapi import FastAPI
from app.services.http_service import HTTPService
from app.services.dns_service import DNSService
from app.services.ssl_service import SSLService
from app.services.domain_service import GetDomainInfo
from app.services.monitoring_service import MonitoringService
from app.services.response_time_service import get_response_time
from app.services.error_page_service import ErrorPageService

# Importer le module pour le monitoring des visites
from app.api.monitoring_agent_api import router as monitoring_agent_router

# Création de l'application FastAPI
app = FastAPI()

# Initialisation des services
http_service = HTTPService()
dns_service = DNSService()
ssl_service = SSLService()
domain_service = GetDomainInfo()
monitoring_service = MonitoringService()

# Enregistrer le routeur de monitoring des visites
app.include_router(monitoring_agent_router)

# Route pour récupérer la liste des domaines depuis une API externe
@app.get("/services/domains")
def get_domains():
    """
    Récupère la liste des domaines depuis l'API externe.
    """
    data = http_service.get_domains()
    if not data:
        return {"error": "Impossible de récupérer les données"}
    return data

# Route pour vérifier les enregistrements DNS d'un domaine
@app.get("/services/dns/{domain}")
def check_dns(domain: str):
    """
    Vérifie les enregistrements DNS pour un domaine.
    """
    result = dns_service.check_dns(domain)
    return result

# Route pour vérifier la validité du certificat SSL d'un domaine
@app.get("/services/ssl/{domain}")
def check_ssl(domain: str):
    """
    Vérifie la validité du certificat SSL pour un domaine.
    """
    result = ssl_service.check_ssl(domain)
    return result

# Route pour vérifier les informations d'un domaine (date de création et d'expiration)
@app.get("/services/domain/{domain}")
async def check_domain(domain: str):
    """
    Vérifie les informations du domaine : date de création et date d'expiration
    """
    domain_info = await domain_service.get_info(domain)
    return domain_info

# Route pour vérifier le statut HTTP d'un domaine
@app.get("/services/monitoring/{domain}")
def check_monitoring(domain: str):
    """
    Vérifie le statut HTTP d'un domaine.
    """
    result = monitoring_service.check_status(domain)
    return result

# Route pour vérifier le temps de réponse d'un domaine
@app.get("/services/response_time/{domain}")
def check_response_time(domain: str):
    """
    Vérifie le temps de réponse d'un domaine.
    """
    response_time = get_response_time(domain)  # Utilise la fonction get_response_time
    if response_time is not None:
        return {"domain": domain, "response_time": response_time}
    else:
        return {"error": f"Impossible de mesurer le temps de réponse pour {domain}"}

# Route pour vérifier les pages d'un domaine pour des erreurs (codes HTTP >= 400)
@app.get("/services/error_pages/{domain}")
async def check_error_pages(domain: str):
    """
    Vérifie toutes les pages d'un domaine pour les erreurs (codes HTTP >= 400).
    """
    # Créer une instance de ErrorPageService pour ce domaine
    error_page_service = ErrorPageService(domain)

    # Récupérer toutes les pages du domaine via le sitemap
    await error_page_service.get_all_pages_from_sitemap()

    # Vérifier les erreurs sur les pages récupérées
    errors = await error_page_service.check_error_pages()

    if errors:
        return {"errors": errors}
    else:
        return {"message": "Aucune erreur trouvée"}
