from fastapi import APIRouter, HTTPException, Depends, Header, Body
import jwt
import datetime
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import requests

# Charger les variables d'environnement
load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
MONGO_URI = os.getenv("MONGO_URI")

# Connexion à MongoDB
client = AsyncIOMotorClient(MONGO_URI)
db = client.monitoring_db
agents_collection = db.agents  # Collection des agents (nouvelle collection)

# Créer un routeur pour les services
router = APIRouter()

# Fonction pour obtenir l'IP publique
def get_public_ip():
    try:
        # Utilisation d'un service comme ipify pour obtenir l'IP publique
        response = requests.get("https://api.ipify.org?format=json")
        response.raise_for_status()  # Vérifie que la requête a réussi
        data = response.json()
        return data.get("ip")
    except requests.exceptions.RequestException as e:
        # En cas d'erreur lors de la récupération
        print(f"Erreur lors de la récupération de l'IP publique: {e}")
        return None

# Route pour obtenir l'IP publique
@router.get("/ip")
async def public_ip():
    ip = get_public_ip()  # Appel à la fonction qui récupère l'IP
    if ip:
        return {"ip": ip}
    return {"error": "Unable to fetch public IP"}

# Vérification du token
def verify_token(authorization: str = Header(...)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Token missing")
    
    try:
        token = authorization.split(" ")[1]
        decoded_token = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return decoded_token
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Modèle pour enregistrer un agent
class Agent(BaseModel):
    agent_id: str
    ip: str
    user_agent: str
    domain: str
    date_added: datetime.datetime = datetime.datetime.utcnow()

# Route pour enregistrer un agent
@router.post("/register/")
async def register_agent(agent: Agent, token: dict = Depends(verify_token)):
    try:
        agent_data = {
            "agent_id": agent.agent_id,
            "ip": agent.ip,
            "user_agent": agent.user_agent,
            "domain": agent.domain,
            "date_added": agent.date_added
        }
        result = await agents_collection.insert_one(agent_data)
        return {"status": "success", "agent_id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'enregistrement de l'agent: {str(e)}")

# Modèle pour mettre à jour un agent
class UpdateAgent(BaseModel):
    ip: str
    user_agent: str

# Route pour mettre à jour un agent
@router.put("/update/{agent_id}")
async def update_agent(agent_id: str, agent_data: UpdateAgent, token: dict = Depends(verify_token)):
    try:
        # Vérifier si l'agent existe dans la base de données
        if not ObjectId.is_valid(agent_id):
            raise HTTPException(status_code=400, detail="Agent ID invalide")

        agent_obj_id = ObjectId(agent_id)
        existing_agent = await agents_collection.find_one({"_id": agent_obj_id})

        if not existing_agent:
            raise HTTPException(status_code=404, detail="Agent non trouvé")

        # Mise à jour des informations de l'agent
        update_result = await agents_collection.update_one(
            {"_id": agent_obj_id},
            {"$set": {
                "ip": agent_data.ip,
                "user_agent": agent_data.user_agent
            }}
        )

        if update_result.modified_count == 0:
            raise HTTPException(status_code=400, detail="Aucune modification effectuée")

        return {"status": "success", "message": "Agent mis à jour"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la mise à jour de l'agent: {str(e)}")

# Route pour récupérer les agents par domaine
@router.get("/agents/{domain}")
async def get_agents_by_domain(domain: str):
    try:
        # Accédez à la collection 'agents' sous monitoring_db
        agents = await agents_collection.find({"domain": domain}).to_list(100)

        if not agents:
            return {"status": "success", "agents": []}

        # Conversion des ObjectId en string pour le JSON
        for agent in agents:
            agent["_id"] = str(agent["_id"])

        return {"status": "success", "agents": agents}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération des agents: {str(e)}")

