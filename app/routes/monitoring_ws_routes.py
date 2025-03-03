# app/routes/monitoring_ws_routes.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List

router = APIRouter()

# Liste pour suivre les connexions WebSocket
clients: List[WebSocket] = []

# WebSocket pour les mises à jour en temps réel des visites
@router.websocket("/ws/visits")
async def websocket_endpoint(websocket: WebSocket):
    # Accepter la connexion WebSocket
    await websocket.accept()
    clients.append(websocket)
    try:
        while True:
            # Attendre un message du client (si nécessaire)
            data = await websocket.receive_text()
            print(f"Message reçu du client: {data}")
            # Optionnel: envoyer une réponse au client (exemple)
            await websocket.send_text(f"Message reçu: {data}")
    except WebSocketDisconnect:
        # Gérer la déconnexion
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
