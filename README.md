# TimeBalance

Application de gestion du temps et de l'équilibre de vie, réalisée avec **Kivy** (interface) et **FastAPI** (backend, base SQLite).

## Fonctionnalités

- **Activités** : Trading, Études, Sport, Personnel, Repos, avec une limite quotidienne optionnelle.
- **Planning quotidien** : ajouter et supprimer des créneaux (HH:MM).
- **Time Tracker** : chronomètre pour mesurer le temps réellement passé sur une activité.
- **Statistiques du jour** : temps par activité avec barre de progression.
- **Trading-Life Balance** : quand la limite quotidienne d'une activité est atteinte
  (180 min pour le Trading par défaut), une alerte s'affiche :
  « Votre temps de Trading prévu est terminé. Pensez à vos autres objectifs de la journée. »

## Structure

    backend/   FastAPI : main.py (routes), schemas.py (Pydantic), database.py (SQLite)
    frontend/  Kivy : main.py (écrans), timebalance.kv (interface), api.py (appels HTTP)

## Installation et lancement

Créer l'environnement virtuel : `python -m venv venv` puis `source venv/bin/activate`.

Backend (premier terminal) :

    cd backend
    pip install -r requirements.txt
    fastapi dev main.py

Documentation Swagger : http://127.0.0.1:8000/docs

Interface (deuxième terminal) :

    cd frontend
    pip install -r requirements.txt
    python main.py

## Routes de l'API

| Méthode | Route | Rôle |
|---|---|---|
| GET, POST | /activities | Lister, créer des activités |
| GET, POST | /schedules | Planning du jour, ajouter un créneau |
| DELETE | /schedules/{id} | Supprimer un créneau |
| GET | /timer/current | Chronomètre en cours |
| POST | /timer/start, /timer/stop | Démarrer, arrêter le chronomètre |
| GET | /stats/today | Temps par activité et alertes |
