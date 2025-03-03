from fastapi import FastAPI, APIRouter, HTTPException, Depends, Query, Header, Body
from fastapi.middleware.cors import CORSMiddleware
from app.services.ip_public_service import get_public_ip
import jwt
import datetime
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional
from bson import ObjectId
from app.routes.monitoring_routes import router as monitoring_router  # Import du routeur de monitoring

# Charger les variables d'environnement
load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
MONGO_URI = os.getenv("MONGO_URI")

# Connexion à MongoDB
client = AsyncIOMotorClient(MONGO_URI)
db = client.monitoring_db
visits_collection = db.visits

app = FastAPI()

# Ajouter la configuration CORS
origins = [
    "http://localhost",  # Ajoutez ici l'URL de votre frontend en développement
    "http://localhost:3000",  # Exemple de port frontend React
    "*",  # Autorise toutes les origines (prenez garde en production, il est préférable de restreindre les origines)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Autoriser les origines spécifiées
    allow_credentials=True,
    allow_methods=["*"],  # Autoriser toutes les méthodes HTTP
    allow_headers=["*"],  # Autoriser tous les en-têtes
)

# Créer un routeur pour les services
router = APIRouter()

app.include_router(monitoring_router)

# Route pour obtenir l'IP publique
@router.get("/services/ip")
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

# Modèles
class TokenRequest(BaseModel):
    domain: str
    user_id: str  

class UserVisit(BaseModel):
    ip: str
    user_agent: str
    date_entree: datetime.datetime
    date_sortie: Optional[datetime.datetime] = None
    domain: str

class UpdateVisit(BaseModel):
    ip: Optional[str]
    user_agent: Optional[str]
    date_entree: Optional[datetime.datetime]
    date_sortie: Optional[datetime.datetime]
    domain: Optional[str]
class VisitUpdateData(BaseModel):
    date_sortie: datetime.datetime
    domain: str
# Route pour générer un token
@router.post("/mgt/generate-token/")
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

# Route pour enregistrer une visite
@router.post("/monitoring/visit/")
async def track_visit(visit: UserVisit, token: dict = Depends(verify_token)):
    try:
        visit_data = {
            "ip": visit.ip,
            "user_agent": visit.user_agent,
            "date_entree": visit.date_entree,
            "date_sortie": visit.date_sortie,
            "domain": visit.domain
        }
        result = await visits_collection.insert_one(visit_data)
        print(f"✅ Visite enregistrée: {result.inserted_id}")
        return {"status": "success", "visit_id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'insertion: {str(e)}")

# 🔄 Mise à jour de la sortie de visite
@router.put("/monitoring/visit/update/")
async def update_visit_exit(
    visit_id: str,
    visit_update: VisitUpdateData = Body(...),
    token: dict = Depends(verify_token)
):
    try:
        print("📡 Mise à jour d'une visite avec visit_id:", visit_id)
        print("📡 Données reçues:", visit_update.dict())

        # ✅ Vérification de la validité de l'ObjectId AVANT conversion
        if not ObjectId.is_valid(visit_id):
            print(f"❌ visit_id invalide: {visit_id}")
            raise HTTPException(status_code=400, detail="visit_id invalide")

        object_id = ObjectId(visit_id)

        # Vérifier si la visite existe
        existing_visit = await visits_collection.find_one({"_id": object_id})
        if not existing_visit:
            raise HTTPException(status_code=404, detail="Visite non trouvée")

        # Mise à jour de la date de sortie
        update_result = await visits_collection.update_one(
            {"_id": object_id, "domain": visit_update.domain},
            {"$set": {"date_sortie": visit_update.date_sortie.isoformat() if visit_update.date_sortie else None}}
        )

        print("📊 Résultat de la mise à jour:", update_result.modified_count)

        if update_result.modified_count == 0:
            print("⚠️ Aucune modification effectuée pour:", visit_id)
            if existing_visit.get("domain") != visit_update.domain:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Domaine incorrect. Attendu: {existing_visit.get('domain')}, Reçu: {visit_update.domain}"
                )
            raise HTTPException(status_code=400, detail="Sortie déjà mise à jour ou données inchangées")

        print("✅ Sortie mise à jour avec succès pour:", visit_id)
        return {"status": "success", "message": "Sortie mise à jour"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("❌ Erreur complète lors de la mise à jour:")
        print(error_details)
        raise HTTPException(status_code=500, detail=f"Erreur MongoDB: {str(e)}")

@router.get("/monitoring/visits/{domain}")
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


# Ajouter le routeur à l'application
app.include_router(router)
