from fastapi import Request

def get_public_ip(request: Request):
    try:
        # ✅ Vérifier d'abord l'en-tête 'x-forwarded-for' pour les IP derrière un proxy
        ip = request.headers.get('x-forwarded-for')
        if ip:
            # Si plusieurs IP sont présentes (séparées par des virgules), on prend la première
            return ip.split(',')[0].strip()
        
        # ❌ Sinon, utiliser l'IP directe du client (souvent le proxy lui-même)
        return request.client.host
    except Exception as e:
        print(f"Erreur lors de la récupération de l'IP publique : {e}")
        return None
