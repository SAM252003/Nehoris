"""
Routes WebSocket pour le streaming en temps réel des audits
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import List
import asyncio
import json
import time

from backend.streaming import manager, stream_audit_progress, create_progress_update, create_error_message, create_completion_message
from backend.async_llm import process_llm_batch, optimize_request_batching
from src.geo_agent.brand.detector import detect
from backend.routes.geo import _apply_match_mode, _summarize_matches, _aggregate_batch

router = APIRouter()

@router.websocket("/ws/audit/{audit_id}")
async def websocket_audit_endpoint(
    websocket: WebSocket,
    audit_id: str,
    provider: str = Query("openai"),
    model: str = Query(None),
    prompts: List[str] = Query([]),
    brands: List[str] = Query([]),
    temperature: float = Query(0.2)
):
    """
    WebSocket endpoint pour streaming d'audit en temps réel
    """
    await manager.connect(websocket)

    try:
        # Valider les paramètres
        if not prompts or not brands:
            await manager.send_personal_message(
                json.dumps(create_error_message(audit_id, "Prompts et brands requis")),
                websocket
            )
            return

        total_prompts = len(prompts)

        # Message de début
        await manager.send_personal_message(json.dumps({
            "type": "audit_started",
            "audit_id": audit_id,
            "total_prompts": total_prompts,
            "provider": provider,
            "timestamp": time.time()
        }), websocket)

        # Préparer les requêtes pour traitement parallèle
        requests = optimize_request_batching(prompts, provider, model, temperature)

        # Variables pour tracking du progrès
        completed_prompts = 0
        per_prompt_results = []

        # Traitement par chunks pour donner un feedback plus granulaire
        chunk_size = max(1, total_prompts // 10)  # 10% à la fois minimum

        for i in range(0, len(requests), chunk_size):
            chunk_requests = requests[i:i + chunk_size]

            # Envoyer mise à jour du progrès
            await manager.send_personal_message(
                json.dumps(create_progress_update(
                    audit_id,
                    completed_prompts,
                    total_prompts,
                    f"Traitement des prompts {completed_prompts + 1}-{min(completed_prompts + len(chunk_requests), total_prompts)}"
                )),
                websocket
            )

            try:
                # Traiter le chunk
                chunk_result = await process_llm_batch(chunk_requests)

                # Traiter les résultats du chunk
                for result in chunk_result["results"]:
                    original_index = result["index"]
                    if original_index < len(prompts):
                        prompt_text = prompts[original_index]

                        if not result["error"]:
                            answer_text = result["response"]

                            # Détection de marques
                            matches = detect(answer_text, brands=brands)
                            matches = _apply_match_mode(matches, "exact_only")
                            summary = _summarize_matches(matches)

                            per_prompt_results.append({
                                "prompt": prompt_text,
                                "answer_text": answer_text,
                                "summary": summary,
                                "matches": [m.model_dump() for m in matches],
                                "execution_time": result["execution_time"]
                            })
                        else:
                            # Gérer l'erreur
                            per_prompt_results.append({
                                "prompt": prompt_text,
                                "answer_text": f"Erreur: {result['response']}",
                                "summary": {},
                                "matches": [],
                                "execution_time": result["execution_time"],
                                "error": True
                            })

                    completed_prompts += 1

                    # Envoyer mise à jour du progrès après chaque prompt
                    await manager.send_personal_message(
                        json.dumps(create_progress_update(
                            audit_id,
                            completed_prompts,
                            total_prompts,
                            f"Prompt {completed_prompts}/{total_prompts} terminé"
                        )),
                        websocket
                    )

                    # Pause courte pour éviter de surcharger le WebSocket
                    await asyncio.sleep(0.1)

            except Exception as chunk_error:
                # Erreur sur un chunk entier
                await manager.send_personal_message(
                    json.dumps(create_error_message(
                        audit_id,
                        f"Erreur lors du traitement: {str(chunk_error)}",
                        provider
                    )),
                    websocket
                )

                # Marquer les prompts du chunk comme échoués
                for req in chunk_requests:
                    if req["index"] < len(prompts):
                        per_prompt_results.append({
                            "prompt": prompts[req["index"]],
                            "answer_text": f"Erreur: {str(chunk_error)}",
                            "summary": {},
                            "matches": [],
                            "execution_time": 0,
                            "error": True
                        })
                        completed_prompts += 1

        # Calculer les métriques finales
        final_metrics = _aggregate_batch([item["summary"] for item in per_prompt_results])

        # Ajouter les statistiques de performance
        successful_prompts = sum(1 for item in per_prompt_results if not item.get("error", False))
        total_execution_time = sum(item["execution_time"] for item in per_prompt_results)

        final_metrics["performance"] = {
            "total_prompts": total_prompts,
            "successful_prompts": successful_prompts,
            "failed_prompts": total_prompts - successful_prompts,
            "total_execution_time": total_execution_time,
            "average_time_per_prompt": total_execution_time / total_prompts if total_prompts > 0 else 0,
            "provider": provider
        }

        # Message de completion
        completion_data = {
            "per_prompt": per_prompt_results,
            "metrics": final_metrics
        }

        await manager.send_personal_message(
            json.dumps(create_completion_message(audit_id, completion_data)),
            websocket
        )

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print(f"Client disconnecté de l'audit {audit_id}")

    except Exception as e:
        # Erreur générale
        await manager.send_personal_message(
            json.dumps(create_error_message(audit_id, f"Erreur générale: {str(e)}", provider)),
            websocket
        )
        manager.disconnect(websocket)

@router.websocket("/ws/test")
async def websocket_test_endpoint(websocket: WebSocket):
    """Endpoint de test pour WebSocket"""
    await manager.connect(websocket)

    try:
        while True:
            # Attendre un message du client
            data = await websocket.receive_text()
            message = json.loads(data)

            # Echo du message avec timestamp
            response = {
                "type": "echo",
                "original_message": message,
                "timestamp": time.time(),
                "server_status": "connected"
            }

            await manager.send_personal_message(json.dumps(response), websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("Client de test déconnecté")