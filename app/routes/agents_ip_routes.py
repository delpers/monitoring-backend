import logging
from fastapi import (
    FastAPI,
    APIRouter,
    HTTPException,
    Request,
    Depends,
    Header,
    Body,
    WebSocket,
    WebSocketDisconnect,
)
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel
import jwt
import datetime
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional, List
import traceback
from bson import ObjectId, json_util
import json
import asyncio

# ip_public_service
from app.services.ip_public_service import get_public_ip

# Initialisation du logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration de SlowAPI
limiter = Limiter(key_func=get_remote_address)

# Liste des connexions WebSocket actives
active_connections: List[WebSocket] = []

# Liste globale des clients connectés
clients: List[WebSocket] = []

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
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
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


# 📌 Fonction
# Fonction pour convertir automatiquement ObjectId en chaînes lors de la sérialisation
def custom_json_serializer(obj):
    if isinstance(obj, ObjectId):
        return str(obj)  # Convertir ObjectId en chaîne
    if hasattr(obj, "isoformat"):
        return obj.isoformat()  # Convertir les objets datetime en chaîne
    raise TypeError(f"Type {type(obj)} not serializable")


# 🔐 Vérification du token JWT
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


# Fonction pour envoyer une mise à jour en temps réel à toutes les connexions actives
async def notify_visits_change(visit_data: dict, event_type: str = "new_visit"):
    message = json.dumps(
        {"event": event_type, "data": visit_data}, default=custom_json_serializer
    )  # Utiliser la fonction de sérialisation personnalisée
    # Envoyer le message à toutes les connexions actives
    for connection in active_connections:
        try:
            await connection.send_text(message)
        except Exception as e:
            print(f"Erreur lors de l'envoi du message: {e}")


# Fonction pour vérifier les connexions WebSocket inactives
async def clean_inactive_connections():
    try:
        while True:
            active_connections[:] = [
                conn
                for conn in active_connections
                if conn.client_state == WebSocket.OPEN
            ]
            await asyncio.sleep(60)
    except asyncio.CancelledError:
        print("🛑 Cleaning task cancelled.")
        pass  # Ensure we handle task cancellation gracefully


# Fonction pour vérifier si une IP est suspecte
async def is_suspect_ip(ip: str, domain: str) -> bool:
    # Récupérer les visites récentes pour cette IP et domaine
    recent_visits = await visits_collection.find(
        {
            "ip": ip,
            "domain": domain,
            "date_entree": {
                "$gt": datetime.datetime.utcnow() - datetime.timedelta(hours=1)
            },
        }
    ).to_list(100)

    # Si l'IP a plus de 5 visites dans la dernière heure, elle est suspecte
    if len(recent_visits) > 5:
        return True
    return False


# Route WebSocket pour les connexions en temps réel
async def websocket_visits(websocket: WebSocket, token: str = Depends(verify_token)):
    try:
        await websocket.accept()
        active_connections.append(websocket)
        print(
            f"🔌 Connexion WebSocket acceptée. Nombre de clients connectés: {len(active_connections)}"
        )

        # Maintenant, vous pouvez gérer les messages comme vous le faisiez précédemment
        # Assurez-vous que le token est bien vérifié avant de continuer
    except Exception as e:
        print(f"Erreur de connexion WebSocket: {e}")
        await websocket.close()
        active_connections.remove(websocket)


# 📌 Routes
# Fonction pour générer un token JWT
@router.post("/agents/generate-token")
@limiter.limit("5/minute")
async def generate_token(request: Request, token_request: TokenRequest):
    try:
        # Extraire des données de la requête si nécessaire
        full_user_id = f"{token_request.domain}_user_{token_request.user_id}"

        # Payload JWT
        payload = {
            "user_id": full_user_id,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
        }

        # Générer le token
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")

        # Si le token est en bytes, on le décode
        if isinstance(token, bytes):
            token = token.decode("utf-8")

        return {"token": token}

    except RateLimitExceeded as e:
        # Si le taux de limitation est dépassé, affichage du message rouge dans la console
        logger.error("\033[91m[ALERT] L'utilisateur a généré trop de tokens !\033[0m")
        raise HTTPException(
            status_code=429,
            detail="Limite de génération de tokens dépassée. Veuillez réessayer plus tard.",
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erreur de génération du token: {str(e)}"
        )


# Route pour récupérer l'IP publique
@router.get("/agents/ip")
async def get_ip(request: Request):
    ip_data = get_public_ip(request)

    if "error" in ip_data:
        raise HTTPException(status_code=500, detail=ip_data["error"])

    return ip_data


# Route pour enregistrer une nouvelle visite ou mettre à jour une visite existante
@router.post("/agents/visit/")
@limiter.limit("10/minute")
async def track_visit(
    request: Request, visit: UserVisit, token: dict = Depends(verify_token)
):
    try:
        print("✅ Enregistrement d'une nouvelle visite:", visit.dict())

        # Vérifier si une visite existe déjà pour cet utilisateur, sans date de sortie
        existing_visit = await visits_collection.find_one(
            {
                "domain": visit.domain,
                "tracking_user_analytics": visit.tracking_user_analytics,
                "date_sortie": None,  # Si une visite est en cours
            }
        )

        if existing_visit:
            existing_visit_id = existing_visit["_id"]
            await visits_collection.update_one(
                {"_id": existing_visit_id},
                {
                    "$set": {"date_sortie": datetime.datetime.utcnow()}
                },  # Mettre à jour la date de sortie
            )
            print(
                f"🔄 La visite existante pour l'utilisateur {visit.tracking_user_analytics} a été mise à jour avec une date de sortie."
            )

        # Préparer les données de la nouvelle visite
        visit_data = {
            "ip": visit.ip,
            "user_agent": visit.user_agent,
            "date_entree": visit.date_entree.astimezone(
                datetime.timezone.utc
            ),  # Assurer que c'est en UTC
            "date_sortie": (
                visit.date_sortie.astimezone(datetime.timezone.utc)
                if visit.date_sortie
                else None
            ),
            "domain": visit.domain,
            "tracking_user_analytics": visit.tracking_user_analytics,
        }

        # Insérer la nouvelle visite dans la collection "visits"
        result = await visits_collection.insert_one(visit_data)

        # Ajouter ou mettre à jour l'IP dans la collection "ip_collection"
        ip_data = {
            "ip": visit.ip,
            "user_agent": visit.user_agent,
            "date_entree": visit.date_entree,
            "date_sortie": visit.date_sortie,
            "tracking_user_analytics": visit.tracking_user_analytics,
        }

        await ip_collection.update_one(
            {"domain": visit.domain},  # Recherche par domaine
            {"$push": {"ips": ip_data}},  # Ajouter la nouvelle IP sous le domaine
            upsert=True,  # Crée une entrée si le domaine n'existe pas
        )

        # Notifier du changement de visite (ex: via WebSocket ou autre mécanisme)
        await notify_visits_change(visit_data)

        return {
            "status": "success",
            "visit_id": str(result.inserted_id),
            "tracking_user_analytics": visit.tracking_user_analytics,
        }
    except Exception as e:
        error_details = traceback.format_exc()
        print("❌ Erreur lors de l'enregistrement de la visite:", error_details)
        raise HTTPException(
            status_code=500, detail=f"Erreur lors de l'insertion: {str(e)}"
        )


# Mise à jour de la sortie de la visite
@router.put("/agents/visit/update/")
async def update_visit_exit(
    visit_id: str,
    visit_update: VisitUpdateData = Body(...),
    token: dict = Depends(verify_token),
):
    try:
        print("📡 Mise à jour d'une visite avec visit_id:", visit_id)
        print("📡 Données reçues:", visit_update.dict())

        try:
            object_id = ObjectId(visit_id)  # Convertir l'ID de la visite en ObjectId
        except Exception as e:
            raise HTTPException(status_code=400, detail="ID de visite invalide")

        existing_visit = await visits_collection.find_one({"_id": object_id})
        if not existing_visit:
            raise HTTPException(status_code=404, detail="Visite introuvable")

        update_data = {}

        if (
            hasattr(visit_update, "date_sortie")
            and visit_update.date_sortie is not None
        ):
            if visit_update.date_sortie.tzinfo is None:
                visit_update.date_sortie = visit_update.date_sortie.replace(
                    tzinfo=datetime.timezone.utc
                )
            update_data["date_sortie"] = visit_update.date_sortie
        else:
            update_data["date_sortie"] = None
            update_data["date_entree"] = datetime.datetime.utcnow()

        update_result = await visits_collection.update_one(
            {"_id": object_id}, {"$set": update_data}
        )

        if update_result.modified_count == 0:
            raise HTTPException(status_code=400, detail="Mise à jour impossible")

        updated_visit = await visits_collection.find_one({"_id": object_id})
        if not updated_visit:
            raise HTTPException(
                status_code=404, detail="Visite introuvable après mise à jour"
            )

        event_type = (
            "update_exit"
            if "date_sortie" in update_data and update_data["date_sortie"] is not None
            else "update_session"
        )
        await notify_visits_change(updated_visit, event_type)

        # Retourner les résultats après conversion de l'ObjectId en chaîne
        return {
            "status": "success",
            "message": "Session mise à jour",
            "visit_id": str(object_id),
            "updated_visit": json.dumps(
                updated_visit, default=custom_json_serializer
            ),  # Sérialisation personnalisée
        }

    except Exception as e:
        error_details = traceback.format_exc()
        print(f"❌ Erreur lors de la mise à jour: {error_details}")
        raise HTTPException(
            status_code=500, detail=f"Erreur lors de la mise à jour: {str(e)}"
        )


@router.get("/agents/visits")
@limiter.limit("20/minute")
async def get_visits_and_ips(request: Request):
    try:
        print("📥 Tentative de récupération des visites...")
        visits = await visits_collection.find().to_list(100)
        print(f"🔍 Visites récupérées: {visits}")

        if not visits:
            print("📭 Aucune visite trouvée.")
            return {"status": "success", "visits": [], "ips": []}

        for visit in visits:
            visit["_id"] = str(visit["_id"])

        print("📥 Tentative de récupération des IPs...")
        ip_logs = await ip_collection.find().to_list(100)
        print(f"🔍 IPs récupérées: {ip_logs}")

        for ip_log in ip_logs:
            ip_log["_id"] = str(ip_log["_id"])

        return {"status": "success", "visits": visits, "ips": ip_logs}

    except Exception as e:
        error_details = traceback.format_exc()
        print(f"❌ Erreur lors de la récupération des visites et IPs: {error_details}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la récupération des visites et IPs: {str(e)}",
        )


# Route WebSocket pour les connexions en temps réel
@router.websocket("/ws/visits")
async def websocket_visits(websocket: WebSocket):
    try:
        await websocket.accept()
        active_connections.append(
            websocket
        )  # Ajouter le client à la liste des connexions actives
        print("🔌 Connexion WebSocket acceptée")
        print(f"🌐 Nombre de clients connectés : {len(active_connections)}")

        while True:
            # Recevoir les messages du client
            data = await websocket.receive_text()
            print(f"📨 Message brut reçu: {data}")

            try:
                # On suppose que les messages sont en JSON
                message = json.loads(data)

                if message.get("event") == "new_visit":
                    print("Nouvelle visite reçue", message)
                    # Diffuser la nouvelle visite à tous les clients
                    await notify_visits_change(message["data"], event_type="new_visit")

                elif message.get("event") == "update_exit":
                    print("Mise à jour de sortie reçue", message)
                    # Diffuser la mise à jour de sortie à tous les clients
                    await notify_visits_change(
                        message["data"], event_type="update_exit"
                    )

                else:
                    print("Événement inconnu")
            except json.JSONDecodeError:
                print("Erreur de décodage JSON reçu")
                await websocket.send_text("Erreur: message malformé")

    except WebSocketDisconnect:
        # Supprimer la connexion de la liste active lorsqu'un client se déconnecte
        active_connections.remove(websocket)
        print("❌ Un client s'est déconnecté.")
        print(f"🌐 Nombre de clients restants : {len(active_connections)}")

    except Exception as e:
        print(f"❗ Erreur WebSocket: {e}")
        await websocket.send_text(f"Erreur serveur: {str(e)}")


# Ajouter la tâche de nettoyage lors du démarrage du serveur
@app.on_event("shutdown")
async def shutdown_event():
    # Close all active WebSocket connections
    for connection in active_connections:
        await connection.close()
    active_connections.clear()
    print("🌐 All WebSocket connections closed.")
