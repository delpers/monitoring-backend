from fastapi import FastAPI, APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
import jwt
import datetime
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional
from bson import ObjectId  # ✅ Fix pour MongoDB

# Charger les variables d'environnement
load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
MONGO_URI = os.getenv("MONGO_URI")

# Connexion à MongoDB
client = AsyncIOMotorClient(MONGO_URI)
db = client.monitoring_db
visits_collection = db.visits

app = FastAPI()
router = APIRouter()

### 📌 Modèles
class TokenRequest(BaseModel):
    domain: str
    user_id: str  

class UserVisit(BaseModel):
    ip: str
    user_agent: str
    date_entree: datetime.datetime
    date_sortie: Optional[datetime.datetime] = None
    domain: str

class VisitUpdate(BaseModel):
    visit_id: str
    date_sortie: datetime.datetime
    domain: str

### 🔐 Vérification du token
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

### 🔑 Génération de token /mgt/generate-token/
@router.post("/mgt/generate-token/")
async def generate_token(request: TokenRequest):
    try:
        full_user_id = f"{request.domain}_user_{request.user_id}"
        payload = {
            "user_id": full_user_id,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        return {"token": token}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur de génération du token: {str(e)}")

### 🚀 Suivi des visites /monitoring/visit/
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

### 🔄 Mise à jour de la sortie /monitoring/visit/update
@router.put("/monitoring/visit/update")
async def update_visit_exit(visit_update: VisitUpdate, token: dict = Depends(verify_token)):
    try:
        object_id = ObjectId(visit_update.visit_id)  # ✅ Fix conversion ObjectId
        result = await visits_collection.update_one(
            {"_id": object_id},
            {"$set": {"date_sortie": visit_update.date_sortie}}
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Visite non trouvée")

        print(f"✅ Sortie mise à jour pour {visit_update.visit_id}")
        return {"status": "success", "message": "Sortie mise à jour"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la mise à jour: {str(e)}")

### 🏠 Route principale
@app.get("/")
def read_root():
    return {"message": "API de monitoring prête!"}

app.include_router(router)
