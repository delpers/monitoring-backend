from fastapi import Request

def get_public_ip(request: Request):
    try:
        # 📌 Priorité à l'en-tête 'X-Forwarded-For' (derrière un proxy)
        ip = request.headers.get('x-forwarded-for')
        if ip:
            # 🔄 Gérer plusieurs IP et prendre la première non vide
            ip = [i.strip() for i in ip.split(',') if i.strip()][0]
        else:
            # 📌 Fallback sur l'IP directe du client
            ip = request.client.host

        # 🛡️ Vérifier que l'IP n'est pas vide ou invalide
        if not ip:
            raise ValueError("IP introuvable")

        return {"ip": ip}

    except Exception as e:
        print(f"❌ Erreur lors de la récupération de l'IP publique : {e}")
        return {"error": "Unable to retrieve IP"}
