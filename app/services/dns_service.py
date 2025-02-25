import dns.resolver
import logging

logger = logging.getLogger(__name__)

class DNSService:
    def __init__(self):
        pass

    def check_dns(self, domain: str):
        """
        Vérifie différents types d'enregistrements DNS pour un domaine.
        """
        result = {}
        try:
            # Vérification des enregistrements A
            try:
                a_records = dns.resolver.resolve(domain, 'A')
                result["A"] = [ip.address for ip in a_records]
            except dns.resolver.NoAnswer:
                result["A"] = "Aucun enregistrement A trouvé"

            # Vérification des enregistrements MX (serveurs de messagerie)
            try:
                mx_records = dns.resolver.resolve(domain, 'MX')
                result["MX"] = [mx.exchange.to_text() for mx in mx_records]
            except dns.resolver.NoAnswer:
                result["MX"] = "Aucun enregistrement MX trouvé"

            # Vérification des enregistrements CNAME
            try:
                cname_records = dns.resolver.resolve(domain, 'CNAME')
                result["CNAME"] = [cname.target.to_text() for cname in cname_records]
            except dns.resolver.NoAnswer:
                result["CNAME"] = "Aucun enregistrement CNAME trouvé"

            # Vérification des enregistrements TXT
            try:
                txt_records = dns.resolver.resolve(domain, 'TXT')
                result["TXT"] = [txt.strings for txt in txt_records]
            except dns.resolver.NoAnswer:
                result["TXT"] = "Aucun enregistrement TXT trouvé"

            return {"domain": domain, "status": "reachable", "records": result}

        except dns.resolver.NXDOMAIN:
            logger.error(f"Domaine introuvable : {domain}")
            return {"domain": domain, "status": "unreachable", "message": "Domaine introuvable"}
        except dns.resolver.Timeout:
            logger.error(f"Timeout lors de la requête DNS pour le domaine {domain}")
            return {"domain": domain, "status": "timeout", "message": "Échec de la requête DNS"}
        except Exception as e:
            logger.error(f"Erreur inconnue lors de la vérification DNS pour {domain}: {str(e)}")
            return {"domain": domain, "status": "error", "message": str(e)}
