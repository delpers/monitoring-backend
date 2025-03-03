import os
from dotenv import load_dotenv

# Charger les variables d'environnement depuis un fichier .env
load_dotenv()

# URL de l'API que tu utilises
API_URL = "https://api.npoint.io/de6179cea0603dbd1e85"

# Paramètres de connexion MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")  # Tu peux le charger depuis un .env si nécessaire

# Clé secrète pour la gestion des tokens
SECRET_KEY = os.getenv("SECRET_KEY", "your_default_secret_key")  # Remplace par la clé réelle ou une variable d'environnement
