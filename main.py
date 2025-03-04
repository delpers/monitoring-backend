from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.monitoring_routes import router as monitoring_router
from app.routes.agents_ip_routes import router as agents_ip_router
from app.routes.monitoring_ws_routes import router as ws_router
import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Créer l'application FastAPI
app = FastAPI()

# Ajouter la configuration CORS
origins = [
    "http://localhost",        # Frontend local en développement
    "http://localhost:3000",
    "https://*.gitpod.io",
    "*",                       # Autoriser toutes les origines (attention en production)
    "https://monitoring-backend-17d6.onrender.com",  # Ajoutez l'URL de votre frontend dans Render si besoin
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,      # Autoriser les origines spécifiées
    allow_credentials=True,
    allow_methods=["*"],        # Autoriser toutes les méthodes HTTP
    allow_headers=["*"],        # Autoriser tous les en-têtes
)

# Ajouter les routeurs
app.include_router(monitoring_router, prefix="/services")
app.include_router(agents_ip_router)
app.include_router(ws_router)  # Ajoutez votre routeur WebSocket
