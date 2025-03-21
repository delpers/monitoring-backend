import ssl
import socket
from datetime import datetime


class SSLService:
    def __init__(self):
        pass

    def check_ssl(self, domain: str):
        """
        Vérifie le certificat SSL d'un domaine.
        """
        result = {}
        try:
            # Connexion SSL
            context = ssl.create_default_context()
            with socket.create_connection((domain, 443)) as conn:
                with context.wrap_socket(conn, server_hostname=domain) as ssl_socket:
                    # Récupérer les informations du certificat SSL
                    cert = ssl_socket.getpeercert()

                    # Fonction de transformation sécurisée pour les sujets et émetteurs
                    def safe_dict(cert_field):
                        """Transforme une liste de tuples en un dictionnaire"""
                        return (
                            {item[0]: item[1] for item in cert_field}
                            if isinstance(cert_field, list)
                            else {}
                        )

                    # Extraire subject et issuer de manière sécurisée
                    subject_dict = safe_dict(cert.get("subject", []))
                    issuer_dict = safe_dict(cert.get("issuer", []))

                    # Dates de validité du certificat
                    notBefore = cert["notBefore"]
                    notAfter = cert["notAfter"]
                    serialNumber = cert.get("serialNumber")

                    # Convertir les dates de validité en format lisible
                    notBefore = datetime.strptime(notBefore, "%b %d %H:%M:%S %Y GMT")
                    notAfter = datetime.strptime(notAfter, "%b %d %H:%M:%S %Y GMT")
                    current_time = datetime.utcnow()

                    # Vérifier si le certificat est valide
                    if notBefore <= current_time <= notAfter:
                        status = "Certificat SSL valide"
                    else:
                        status = "Certificat SSL expiré"

                    # Ajouter les informations au résultat
                    result["status"] = status
                    result["subject"] = subject_dict.get("commonName", "N/A")
                    result["issuer"] = issuer_dict.get("commonName", "N/A")
                    result["valid_from"] = notBefore
                    result["valid_until"] = notAfter
                    result["serialNumber"] = serialNumber
                    result["issued_on"] = notBefore  # Date d'achat (émission)
                    result["expires_on"] = notAfter  # Date d'expiration
                    return {"domain": domain, "ssl_info": result}

        except ssl.SSLError as e:
            return {"domain": domain, "status": "SSL Error", "message": str(e)}
        except socket.error as e:
            return {"domain": domain, "status": "Unreachable", "message": str(e)}
        except Exception as e:
            return {"domain": domain, "status": "Error", "message": str(e)}
