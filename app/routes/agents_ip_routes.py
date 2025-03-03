from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Header, Body
from pydantic import BaseModel
import jwt  # Assurez-vous que PyJWT est installé: pip install PyJWT
import datetime
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional
import traceback
from bson import ObjectId
from app.services.ip_public_service import get_public_ip
from app.routes.monitoring_ws_routes import send_update_to_clients

# Charger les variables d'environnement
load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
MONGO_URI = os.getenv("MONGO_URI")

# Connexion à MongoDB
client = AsyncIOMotorClient(MONGO_URI)
db = client.monitoring_db
visits_collection = db.visits
ip_collection = db.ip_logs

app = FastAPI()
router = APIRouter()

# Modèles Pydantic
class TokenRequest(BaseModel):
    domain: str
    user_id: str

class UserVisit(BaseModel):
    ip: str
    user_agent: str
    date_entree: datetime.datetime
    date_sortie: Optional[datetime.datetime] = None
    domain: str
    tracking_user_analytics: str

class VisitUpdateData(BaseModel):
    date_sortie: datetime.datetime
    domain: str

# Fonction fictive pour incrémenter les tentatives
async def increment_attempts(ip: str):
    attempts_collection = db.attempts
    attempts = await attempts_collection.find_one({"ip": ip})
    
    if attempts:
        new_count = attempts['attempts'] + 1
        await attempts_collection.update_one({"ip": ip}, {"$set": {"attempts": new_count}})
    else:
        await attempts_collection.insert_one({"ip": ip, "attempts": 1})
    
    if attempts and attempts['attempts'] >= 5:
        raise HTTPException(status_code=403, detail="Trop de tentatives. Accès bloqué.")

# Route pour obtenir l'IP publique
@router.get("/agents/ip")
async def public_ip(request: Request):
    ip = get_public_ip(request)
    if ip:
        return {"ip": ip["ip"]}
    return {"error": "Unable to fetch public IP"}

# Route pour générer un token
@router.post("/agents/generate-token/")
async def generate_token(request: TokenRequest, req: Request):
    ip_info = get_public_ip(req)
    ip = ip_info["ip"]

    try:
        full_user_id = f"{request.domain}_user_{request.user_id}"
        payload = {
            "user_id": full_user_id,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        if isinstance(token, bytes):
            token = token.decode('utf-8')
        return {"token": token}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur de génération du token: {str(e)}")

# Vérification du token JWT
def verify_token(authorization: str = Header(...)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token manquant ou mal formaté")
    
    try:
        token = authorization.split("Bearer ")[1]
        decoded_token = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return decoded_token
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expiré")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invalide")

# Enregistrement d'une nouvelle visite
@router.post("/agents/visit/")
async def track_visit(visit: UserVisit, token: dict = Depends(verify_token)):
    try:
        visit_data = {
            "ip": visit.ip,
            "user_agent": visit.user_agent,
            "date_entree": visit.date_entree,
            "date_sortie": visit.date_sortie,
            "domain": visit.domain,
            "tracking_user_analytics": visit.tracking_user_analytics
        }
        result = await visits_collection.insert_one(visit_data)

        message = {"status": "new_visit", "visit": visit.dict()}
        await send_update_to_clients(message)

        return {
            "status": "success",
            "visit_id": str(result.inserted_id),
            "tracking_user_analytics": visit.tracking_user_analytics
        }
    except Exception as e:
        error_details = traceback.format_exc()
        print("❌ Erreur lors de l'enregistrement de la visite:", error_details)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'insertion: {str(e)}")

# Mise à jour de la sortie de visite
@router.put("/agents/visit/update/")
async def update_visit_exit(
    visit_id: str,
    visit_update: VisitUpdateData = Body(...),
    token: dict = Depends(verify_token)
):
    try:
        try:
            object_id = ObjectId(visit_id)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"visit_id invalide: {str(e)}")

        existing_visit = await visits_collection.find_one({"_id": object_id})
        if not existing_visit:
            raise HTTPException(status_code=404, detail="Visite non trouvée")

        update_result = await visits_collection.update_one(
            {"_id": object_id, "domain": visit_update.domain},
            {"$set": {"date_sortie": visit_update.date_sortie.isoformat() if visit_update.date_sortie else None}}
        )

        if update_result.modified_count == 0:
            raise HTTPException(status_code=400, detail="Sortie déjà mise à jour ou domaine incorrect")

        return {"status": "success", "message": "Sortie mise à jour"}
    except Exception as e:
        error_details = traceback.format_exc()
        print("❌ Erreur lors de la mise à jour:", error_details)
        raise HTTPException(status_code=500, detail=f"Erreur MongoDB: {str(e)}")

# Récupérer les visites par domaine
@router.get("/agents/visits/{domain}")
async def get_visits_by_domain(domain: str):
    try:
        visits = await visits_collection.find({"domain": domain}).to_list(100)

        if not visits:
            return {"status": "success", "visits": []}

        for visit in visits:
            visit["_id"] = str(visit["_id"])

        return {"status": "success", "visits": visits}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération des visites: {str(e)}")
