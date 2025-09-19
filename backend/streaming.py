"""
API de streaming pour les audits longs
Permet de suivre le progrès en temps réel
"""
from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict, Any
import asyncio
import json
import time


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                # Connection fermée, on la supprime
                self.active_connections.remove(connection)


manager = ConnectionManager()


async def stream_audit_progress(websocket: WebSocket, audit_id: str, total_prompts: int, provider: str):
    """Stream le progrès d'un audit en temps réel"""
    try:
        await manager.connect(websocket)

        # Message de début
        await manager.send_personal_message(json.dumps({
            "type": "audit_started",
            "audit_id": audit_id,
            "total_prompts": total_prompts,
            "provider": provider,
            "timestamp": time.time()
        }), websocket)

        # Simulation du progrès (dans la vraie implémentation, ce serait connecté aux appels LLM)
        for i in range(total_prompts):
            await asyncio.sleep(1)  # Simule le temps de traitement

            progress = {
                "type": "progress_update",
                "audit_id": audit_id,
                "completed_prompts": i + 1,
                "total_prompts": total_prompts,
                "progress_percent": round((i + 1) / total_prompts * 100, 1),
                "current_prompt": f"Prompt {i + 1}/{total_prompts}",
                "timestamp": time.time()
            }

            await manager.send_personal_message(json.dumps(progress), websocket)

        # Message de fin
        await manager.send_personal_message(json.dumps({
            "type": "audit_completed",
            "audit_id": audit_id,
            "timestamp": time.time()
        }), websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)


def create_progress_update(audit_id: str, completed: int, total: int, current_task: str) -> Dict[str, Any]:
    """Crée un message de mise à jour du progrès"""
    return {
        "type": "progress_update",
        "audit_id": audit_id,
        "completed": completed,
        "total": total,
        "progress_percent": round(completed / total * 100, 1) if total > 0 else 0,
        "current_task": current_task,
        "timestamp": time.time()
    }


def create_error_message(audit_id: str, error: str, provider: str = None) -> Dict[str, Any]:
    """Crée un message d'erreur"""
    return {
        "type": "error",
        "audit_id": audit_id,
        "error": error,
        "provider": provider,
        "timestamp": time.time()
    }


def create_completion_message(audit_id: str, results: Dict[str, Any]) -> Dict[str, Any]:
    """Crée un message de completion"""
    return {
        "type": "audit_completed",
        "audit_id": audit_id,
        "results": results,
        "timestamp": time.time()
    }