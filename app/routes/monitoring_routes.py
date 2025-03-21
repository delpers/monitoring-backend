from fastapi import FastAPI, APIRouter, HTTPException
from app.services.http_service import HTTPService
from app.services.dns_service import DNSService
from app.services.ssl_service import SSLService
from app.services.domain_service import GetDomainInfo
from app.services.monitoring_service import MonitoringService
from app.services.response_time_service import get_response_time
from app.services.error_page_service import ErrorPageService
import requests

# Création du routeur pour les routes de monitoring
app = FastAPI()
router = APIRouter()

# Initialisation des services
http_service = HTTPService()
dns_service = DNSService()
ssl_service = SSLService()
domain_service = GetDomainInfo()
monitoring_service = MonitoringService()


# Route pour récupérer la liste des domaines depuis une API externe
@router.get("/domains")
def get_domains():
    data = http_service.get_domains()
    if not data:
        return {"error": "Impossible de récupérer les données"}
    return data


# Route pour vérifier les enregistrements DNS d'un domaine
@router.get("/dns/{domain}")
def check_dns(domain: str):
    result = dns_service.check_dns(domain)
    return result


# Route pour vérifier la validité du certificat SSL d'un domaine
@router.get("/ssl/{domain}")
def check_ssl(domain: str):
    result = ssl_service.check_ssl(domain)
    return result


# Route pour vérifier les informations d'un domaine (date de création et d'expiration)
@router.get("/domain/{domain}")
async def check_domain(domain: str):
    domain_info = await domain_service.get_info(domain)
    return domain_info


# Route pour vérifier le statut HTTP d'un domaine
@router.get("/monitoring/{domain}")
def check_monitoring(domain: str):
    result = monitoring_service.check_status(domain)
    return result


# Route pour vérifier le temps de réponse d'un domaine
@router.get("/response_time/{domain}")
def check_response_time(domain: str):
    response_time = get_response_time(domain)  # Utilise la fonction get_response_time
    if response_time is not None:
        return {"domain": domain, "response_time": response_time}
    else:
        return {"error": f"Impossible de mesurer le temps de réponse pour {domain}"}


# Route pour vérifier les pages d'un domaine pour des erreurs (codes HTTP >= 400)
@router.get("/error_pages/{domain}")
async def check_error_pages(domain: str):
    error_page_service = ErrorPageService(domain)
    await error_page_service.get_all_pages_from_sitemap()
    errors = await error_page_service.check_error_pages()

    if errors:
        return {"errors": errors}
    else:
        return {"message": "Aucune erreur trouvée"}


# **Route de Ping Service** (nouvelle ajoutée)
@router.get("/ping/{domain}")
def ping_domain(domain: str):
    """Route pour vérifier la disponibilité du domaine"""
    try:
        url = f"http://{domain}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return {"status": "available"}
        else:
            raise HTTPException(
                status_code=503,
                detail=f"{domain} est injoignable (code HTTP: {response.status_code})",
            )
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=503, detail=f"{domain} est injoignable. Erreur: {str(e)}"
        )
