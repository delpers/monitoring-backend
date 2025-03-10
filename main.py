from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.monitoring_routes import router as monitoring_router
from app.routes.agents_ip_routes import router as agents_ip_router
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
    "http://localhost:3001",
    "*",                       # Autoriser toutes les origines (attention en production)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permettre toutes les origines (pour tester uniquement)
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "PUT", "DELETE", "PATCH"],  # Autoriser ces méthodes
    allow_headers=["*"],
)

# Ajouter les routeurs
app.include_router(monitoring_router, prefix="/services")
app.include_router(agents_ip_router)
