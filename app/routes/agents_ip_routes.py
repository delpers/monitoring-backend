from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Header, Body, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import jwt
import datetime
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional, List
import traceback
from bson import ObjectId, json_util
from app.services.ip_public_service import get_public_ip
import asyncio
import json

# Liste des connexions WebSocket actives
active_connections: List[WebSocket] = []

# Charger les variables d'environnement
load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
MONGO_URI = os.getenv("MONGO_URI")

# Connexion à MongoDB
client = AsyncIOMotorClient(MONGO_URI)
db = client.monitoring_db
visits_collection = db.visits
ip_collection = db.ip_logs  # Collection pour les logs d'IP

app = FastAPI()
router = APIRouter()

# 📌 Modèles Pydantic
class TokenRequest(BaseModel):
    domain: str
    user_id: str  

class UserVisit(BaseModel):
    ip: str
    user_agent: str
    date_entree: datetime.datetime
    date_sortie: Optional[datetime.datetime] = None
    domain: str
    tracking_user_analytics: str  # Identifiant utilisateur unique

class VisitUpdateData(BaseModel):
    date_sortie: datetime.datetime
    domain: str

# Route pour obtenir l'IP publique
@router.get("/agents/ip")
async def public_ip(request: Request):
    ip = get_public_ip(request)  # Appel à la fonction modifiée avec request comme paramètre
    if ip:
        return {"ip": ip["ip"]}  # Extraire l'adresse IP de l'objet renvoyé par get_public_ip
    return {"error": "Unable to fetch public IP"}

# Route pour générer un token
@router.post("/agents/generate-token/")
async def generate_token(request: TokenRequest):
    try:
        full_user_id = f"{request.domain}_user_{request.user_id}"
        payload = {
            "user_id": full_user_id,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        
        # Handle different versions of PyJWT
        if isinstance(token, bytes):
            token = token.decode('utf-8')
            
        return {"token": token}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur de génération du token: {str(e)}")

# 🔐 Vérification du token JWT
def verify_token(authorization: str = Header(...)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token manquant ou mal formaté")
    
    try:
        token = authorization.split("Bearer ")[1]  # Extraction après "Bearer "
        decoded_token = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return decoded_token
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expiré")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invalide")

# Route WebSocket pour les connexions en temps réel
@router.websocket("/ws/visits")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            # Attendre un message du client (si nécessaire)
            data = await websocket.receive_text()
            print(f"Message reçu: {data}")
            # Vous pouvez gérer les messages du client ici, si besoin
            # Par exemple, vérifier un domaine ou envoyer des informations spécifiques.
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        print("Client déconnecté")

# Fonction pour convertir automatiquement ObjectId en chaînes lors de la sérialisation
def custom_json_serializer(obj):
    if isinstance(obj, ObjectId):
        return str(obj)  # Convert ObjectId to string
    if hasattr(obj, 'isoformat'):  # More robust check for datetime-like objects
        return obj.isoformat()  # Convert datetime to ISO format string
    raise TypeError(f"Type {type(obj)} not serializable")

# Fonction pour envoyer une mise à jour en temps réel sur toutes les connexions actives
async def notify_visits_change(visit_data: dict):
    message = json.dumps({
        "event": "new_visit",
        "data": visit_data
    }, default=custom_json_serializer)  # Utilisation du sérialiseur personnalisé

    # Envoyer un message à toutes les connexions actives
    for connection in active_connections:
        try:
            await connection.send_text(message)
        except Exception as e:
            print(f"Erreur lors de l'envoi du message: {e}")

# 🚀 Enregistrement d'une nouvelle visite
@router.post("/agents/visit/")
async def track_visit(visit: UserVisit, token: dict = Depends(verify_token)):
    try:
        print("✅ Enregistrement d'une nouvelle visite:", visit.dict())

        # Insérer la visite en MongoDB
        visit_data = {
            "ip": visit.ip,
            "user_agent": visit.user_agent,
            "date_entree": visit.date_entree,
            "date_sortie": visit.date_sortie,
            "domain": visit.domain,
            "tracking_user_analytics": visit.tracking_user_analytics
        }

        # Check if the visit already exists
        existing_visit = await visits_collection.find_one({
            "domain": visit.domain,
            "tracking_user_analytics": visit.tracking_user_analytics,
            "date_sortie": None  # Ensuring the visit is still active
        })

        if existing_visit:
            raise HTTPException(status_code=400, detail="La visite est déjà en cours pour cet utilisateur.")

        result = await visits_collection.insert_one(visit_data)

        # Ajouter l'IP au suivi des logs par domaine
        ip_data = {
            "ip": visit.ip,
            "user_agent": visit.user_agent,
            "date_entree": visit.date_entree,
            "date_sortie": visit.date_sortie,
            "tracking_user_analytics": visit.tracking_user_analytics
        }

        await ip_collection.update_one(
            {"domain": visit.domain},
            {"$push": {"ips": ip_data}},
            upsert=True
        )

        # Notifier les connexions WebSocket actives
        await notify_visits_change(visit_data)

        return {
            "status": "success",
            "visit_id": str(result.inserted_id),
            "tracking_user_analytics": visit.tracking_user_analytics
        }
    except Exception as e:
        error_details = traceback.format_exc()
        print("❌ Erreur lors de l'enregistrement de la visite:", error_details)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'insertion: {str(e)}")

# Modifier la mise à jour pour s'assurer que le datetime est correctement converti
@router.put("/agents/visit/update/")
async def update_visit_exit(
    visit_id: str,
    visit_update: VisitUpdateData = Body(...),
    token: dict = Depends(verify_token)
):
    try:
        print("📡 Mise à jour d'une visite avec visit_id:", visit_id)
        print("📡 Données reçues:", visit_update.dict())

        object_id = ObjectId(visit_id)

        # Debug print of datetime
        print("🕒 Date de sortie reçue:", visit_update.date_sortie)
        print("🕒 Type de date de sortie:", type(visit_update.date_sortie))

        # Ensure datetime is UTC
        if visit_update.date_sortie.tzinfo is None:
            visit_update.date_sortie = visit_update.date_sortie.replace(tzinfo=datetime.timezone.utc)

        # Alternative update method with explicit UTC conversion
        update_result = await visits_collection.update_one(
            {"_id": object_id, "domain": visit_update.domain},
            {"$set": {"date_sortie": visit_update.date_sortie}}
        )

        print("📊 Résultat de la mise à jour:", update_result.modified_count)

        if update_result.modified_count == 0:
            raise HTTPException(status_code=400, detail="Mise à jour impossible")

        # Notify WebSocket clients
        updated_visit = await visits_collection.find_one({"_id": object_id})
        await notify_visits_change({
            "event": "update_exit",
            "data": updated_visit
        })

        return {"status": "success", "message": "Sortie mise à jour"}
    except Exception as e:
        error_details = traceback.format_exc()
        print("❌ Erreur complète lors de la mise à jour:")
        print(error_details)
        raise HTTPException(status_code=500, detail=f"Erreur MongoDB: {str(e)}")

@router.put("/agents/visit/update/{visit_id}")
async def update_visit_exit(
    visit_id: str,
    visit_update: VisitUpdateData = Body(...),
    token: dict = Depends(verify_token)
):
    try:
        print("📡 Mise à jour d'une visite avec visit_id:", visit_id)
        print("📡 Données reçues:", visit_update.dict())

        # Conversion de visit_id en ObjectId
        object_id = ObjectId(visit_id)

        # Assurez-vous que la date de sortie est en UTC
        if visit_update.date_sortie.tzinfo is None:
            visit_update.date_sortie = visit_update.date_sortie.replace(tzinfo=datetime.timezone.utc)

        # Mise à jour de la visite
        update_result = await visits_collection.update_one(
            {"_id": object_id, "domain": visit_update.domain},
            {"$set": {"date_sortie": visit_update.date_sortie}}
        )

        if update_result.modified_count == 0:
            raise HTTPException(status_code=400, detail="Mise à jour impossible")

        # Récupérer la visite mise à jour
        updated_visit = await visits_collection.find_one({"_id": object_id})
        
        # Notifier les connexions WebSocket des mises à jour
        await notify_visits_change({
            "event": "update_exit",
            "data": updated_visit
        })

        return {"status": "success", "message": "Sortie mise à jour"}
    except Exception as e:
        print(f"❌ Erreur lors de la mise à jour: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la mise à jour: {str(e)}")

# 🧐 Endpoint pour récupérer les visites
@router.get("/agents/visits/{domain}")
async def get_visits_by_domain(domain: str):
    try:
        # Accédez à la collection 'visits' sous monitoring_db
        visits_collection = db.visits

        # Filtrer les visites par domaine
        visits = await visits_collection.find({"domain": domain}).to_list(100)

        # Si aucune visite n'est trouvée
        if not visits:
            return {"status": "success", "visits": []}

        # Conversion des ObjectId en string pour le JSON
        for visit in visits:
            visit["_id"] = str(visit["_id"])

        return {"status": "success", "visits": visits}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération des visites: {str(e)}")
