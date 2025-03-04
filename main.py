from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.monitoring_routes import router as monitoring_router  # Import du routeur de monitoring
from app.routes.agents_ip_routes import router as agents_ip_router  # Import du routeur des agents
from app.routes.monitoring_ws_routes import router as ws_router  # ✅ Import de la route WebSocket
import asyncio  # ✅ Import pour gérer les tâches asynchrones

# Charger les variables d'environnement
import os
from dotenv import load_dotenv
load_dotenv()

# Créer l'application FastAPI
app = FastAPI()

# Ajouter la configuration CORS
origins = [
    "http://localhost",        # URL de votre frontend en développement
    "http://localhost:3000",
    "https://*.gitpod.io",
    "https://delpers-moinitoringfron-195vwqytq46.ws-eu118.gitpod.io",
    "*",                       # Autorise toutes les origines (attention en production)
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


