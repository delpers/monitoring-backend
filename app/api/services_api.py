# app/api/services_api.py

from fastapi import FastAPI
from app.services.http_service import HTTPService
from app.services.dns_service import DNSService
from app.services.ssl_service import SSLService
from app.services.domain_service import GetDomainInfo
from app.services.monitoring_service import MonitoringService

app = FastAPI()

# Initialiser les services
http_service = HTTPService()
dns_service = DNSService()
ssl_service = SSLService()
domain_service = GetDomainInfo()
monitoring_service = MonitoringService()

@app.get("/services/domains")
def get_domains():
    """
    Récupère la liste des domaines depuis l'API externe.
    """
    data = http_service.get_domains()
    if not data:
        return {"error": "Impossible de récupérer les données"}
    return data

@app.get("/services/dns/{domain}")
def check_dns(domain: str):
    """
    Vérifie les enregistrements DNS pour un domaine.
    """
    result = dns_service.check_dns(domain)
    return result

@app.get("/services/ssl/{domain}")
def check_ssl(domain: str):
    """
    Vérifie la validité du certificat SSL pour un domaine.
    """
    result = ssl_service.check_ssl(domain)
    return result

@app.get("/services/domain/{domain}")
async def check_domain(domain: str):
    """
    Vérifie les informations du domaine : date de création et date d'expiration
    """
    domain_info = GetDomainInfo.get_info(domain)
    return domain_info

@app.get("/services/monitoring/{domain}")
def check_monitoring(domain: str):
    """
    Vérifie le statut HTTP d'un domaine.
    """
    result = monitoring_service.check_status(domain)
    return result
