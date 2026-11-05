"""Appels non bloquants vers l'API FastAPI, avec UrlRequest de Kivy."""
import json

from kivy.network.urlrequest import UrlRequest

# Sur un émulateur Android, remplacer par http://10.0.2.2:8000
BASE_URL = "http://127.0.0.1:8000"


def _error_message(result):
    """Extrait un message lisible d'une erreur FastAPI."""
    if isinstance(result, dict):
        detail = result.get("detail")
        if isinstance(detail, str):
            return detail
        if isinstance(detail, list) and detail:
            return str(detail[0].get("msg", "Données invalides"))
    return "Erreur du serveur"


def request(path, on_success=None, on_error=None, method="GET", body=None):
    def success(req, result):
        if on_success:
            on_success(result)

    def failure(req, result):
        if on_error:
            on_error(_error_message(result))

    def error(req, err):
        if on_error:
            on_error("Impossible de joindre le serveur. Lancez d'abord le backend.")

    UrlRequest(
        BASE_URL + path,
        method=method,
        req_body=json.dumps(body) if body is not None else None,
        req_headers={"Content-type": "application/json"},
        on_success=success,
        on_failure=failure,
        on_error=error,
    )
