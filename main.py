from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.monitoring_routes import router as monitoring_router  # Import du routeur de monitoring
from app.routes.agents_ip_routes import router as agents_ip_router  # Import du routeur des agents

# Charger les variables d'environnement (si besoin)
import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Créer l'application FastAPI
app = FastAPI()

# Ajouter la configuration CORS
origins = [
    "http://localhost",  # Ajoutez ici l'URL de votre frontend en développement
    "http://localhost:3000",
    "https://fragmastering.com",
    "*",  # Autorise toutes les origines (prenez garde en production, il est préférable de restreindre les origines)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Autoriser les origines spécifiées
    allow_credentials=True,
    allow_methods=["*"],  # Autoriser toutes les méthodes HTTP
    allow_headers=["*"],  # Autoriser tous les en-têtes
)

# Ajouter le routeur de monitoring sous le préfixe "/services"
app.include_router(monitoring_router, prefix="/services")

# Ajouter le routeur des agents sous le préfixe "/*"
app.include_router(agents_ip_router)
