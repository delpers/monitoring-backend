from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

# Connexion à MongoDB
client = AsyncIOMotorClient(MONGO_URI)
db = client.monitoring_db
ip_collection = db.ip_logs  # Collection pour les logs d'IP

router = APIRouter()

# Liste pour suivre les connexions WebSocket
clients: List[WebSocket] = []

# WebSocket pour les mises à jour en temps réel des visites
@router.websocket("/ws/ips")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Nouvelle connexion WebSocket établie!")
    clients.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            print(f"Message reçu du client: {data}")
            await websocket.send_text(f"Message reçu: {data}")
    except WebSocketDisconnect:
        clients.remove(websocket)
        print("Client déconnecté")

# Méthode pour envoyer des mises à jour en temps réel à tous les clients connectés
async def send_update_to_clients(message: dict):
    # Envoi d'un message à tous les clients connectés
    for client in clients:
        try:
            await client.send_json(message)
        except WebSocketDisconnect:
            clients.remove(client)  # Retirer le client déconnecté

# Fonction pour écouter les nouvelles entrées dans la collection MongoDB
async def watch_ip_logs():
    async with ip_collection.watch() as stream:
        async for change in stream:
            # Envoyer les nouvelles IP en temps réel aux clients connectés
            if change["operationType"] == "insert":
                new_ip = change["fullDocument"]
                await send_update_to_clients(new_ip)
