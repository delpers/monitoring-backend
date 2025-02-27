import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.services_api import app  # Assurez-vous que app est bien importé depuis services_api

# Définir les origines autorisées
# Ajoutez le protocole HTTP ou HTTPS pour que CORS fonctionne correctement
ALLOWED_ORIGINS = [
    "https://fragmastering.com",  # pour les demandes HTTPS
    "http://fragmastering.com",   # pour les demandes HTTP (si nécessaire)
]

# Configurer CORS correctement
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # Autoriser les origines spécifiées
    allow_credentials=True,  # Changez cela en True si vous souhaitez permettre les cookies
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
    expose_headers=["Content-Type"],
    max_age=86400,  # Cache préflight pour 24 heures
)

# Démarrer le serveur avec uvicorn
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, reload=True)
