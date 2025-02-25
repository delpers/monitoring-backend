# app/services/monitoring_service.py

import requests

class MonitoringService:
    def __init__(self):
        pass

    def check_status(self, domain: str):
        """
        Vérifie si le domaine est en ligne via HTTP.
        """
        try:
            response = requests.get(f"http://{domain}")
            return {"domain": domain, "status_code": response.status_code, "status": "online" if response.status_code == 200 else "offline"}
        except requests.exceptions.RequestException:
            return {"domain": domain, "status": "offline"}
