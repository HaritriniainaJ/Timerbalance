import sqlite3
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Response, status

from database import get_db, init_db
from schemas import (
    Activity,
    ActivityCreate,
    ActivityStat,
    Schedule,
    ScheduleCreate,
    TimerStart,
    TimerStatus,
    TodayStats,
)

DB = Annotated[sqlite3.Connection, Depends(get_db)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="TimeBalance API", lifespan=lifespan)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@app.get("/")
def root():
    return {"message": "TimeBalance fonctionne"}


# ---------- Activités ----------
@app.get("/activities", response_model=list[Activity])
def list_activities(db: DB):
    rows = db.execute("SELECT * FROM activities ORDER BY id").fetchall()
    return [dict(r) for r in rows]


@app.post("/activities", response_model=Activity, status_code=status.HTTP_201_CREATED)
def create_activity(activity: ActivityCreate, db: DB):
    try:
        cur = db.execute(
            "INSERT INTO activities (name, daily_limit_minutes) VALUES (?, ?)",
            (activity.name.strip(), activity.daily_limit_minutes),
        )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Cette activité existe déjà")
    db.commit()
    return {"id": cur.lastrowid, **activity.model_dump()}


# ---------- Planning ----------
@app.get("/schedules", response_model=list[Schedule])
def list_schedules(db: DB, day: str | None = None):
    day = day or date.today().isoformat()
    rows = db.execute(
        """SELECT s.id, s.activity_id, a.name AS activity_name,
                  s.day, s.start_time, s.end_time
           FROM schedules s JOIN activities a ON a.id = s.activity_id
           WHERE s.day = ? ORDER BY s.start_time""",
        (day,),
    ).fetchall()
    return [dict(r) for r in rows]


@app.post("/schedules", response_model=Schedule, status_code=status.HTTP_201_CREATED)
def create_schedule(schedule: ScheduleCreate, db: DB):
    activity = db.execute(
        "SELECT name FROM activities WHERE id = ?", (schedule.activity_id,)
    ).fetchone()
    if activity is None:
        raise HTTPException(status_code=404, detail="Activité introuvable")
    day = schedule.day or date.today().isoformat()
    cur = db.execute(
        "INSERT INTO schedules (activity_id, day, start_time, end_time) VALUES (?, ?, ?, ?)",
        (schedule.activity_id, day, schedule.start_time, schedule.end_time),
    )
    db.commit()
    return {
        "id": cur.lastrowid,
        "activity_id": schedule.activity_id,
        "activity_name": activity["name"],
        "day": day,
        "start_time": schedule.start_time,
        "end_time": schedule.end_time,
    }


@app.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(schedule_id: int, db: DB):
    cur = db.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
    db.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Planning introuvable")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Chronomètre (time tracker) ----------
def _running_log(db: sqlite3.Connection):
    return db.execute(
        """SELECT l.id, l.activity_id, l.start_at, a.name
           FROM time_logs l JOIN activities a ON a.id = l.activity_id
           WHERE l.end_at IS NULL ORDER BY l.id DESC LIMIT 1"""
    ).fetchone()


@app.get("/timer/current", response_model=TimerStatus)
def timer_current(db: DB):
    log = _running_log(db)
    if log is None:
        return TimerStatus(running=False)
    return TimerStatus(
        running=True,
        activity_id=log["activity_id"],
        activity_name=log["name"],
        start_at=log["start_at"],
    )


@app.post("/timer/start", response_model=TimerStatus)
def timer_start(body: TimerStart, db: DB):
    activity = db.execute(
        "SELECT name FROM activities WHERE id = ?", (body.activity_id,)
    ).fetchone()
    if activity is None:
        raise HTTPException(status_code=404, detail="Activité introuvable")
    # Un seul chronomètre à la fois : on arrête celui en cours.
    db.execute("UPDATE time_logs SET end_at = ? WHERE end_at IS NULL", (now_iso(),))
    start = now_iso()
    db.execute(
        "INSERT INTO time_logs (activity_id, start_at) VALUES (?, ?)",
        (body.activity_id, start),
    )
    db.commit()
    return TimerStatus(
        running=True,
        activity_id=body.activity_id,
        activity_name=activity["name"],
        start_at=start,
    )


@app.post("/timer/stop", response_model=TimerStatus)
def timer_stop(db: DB):
    db.execute("UPDATE time_logs SET end_at = ? WHERE end_at IS NULL", (now_iso(),))
    db.commit()
    return TimerStatus(running=False)


# ---------- Statistiques du jour + alertes ----------
@app.get("/stats/today", response_model=TodayStats)
def stats_today(db: DB):
    today = date.today().isoformat()
    now = datetime.now()
    activities = db.execute("SELECT * FROM activities ORDER BY id").fetchall()
    logs = db.execute(
        "SELECT activity_id, start_at, end_at FROM time_logs WHERE start_at LIKE ?",
        (today + "%",),
    ).fetchall()

    seconds: dict[int, float] = {}
    for log in logs:
        start = datetime.fromisoformat(log["start_at"])
        end = datetime.fromisoformat(log["end_at"]) if log["end_at"] else now
        seconds[log["activity_id"]] = seconds.get(log["activity_id"], 0) + max(
            0.0, (end - start).total_seconds()
        )

    stats, alerts = [], []
    for a in activities:
        minutes = int(seconds.get(a["id"], 0) // 60)
        limit = a["daily_limit_minutes"]
        exceeded = limit is not None and minutes >= limit
        if exceeded:
            alerts.append(
                f"Votre temps de {a['name']} prévu est terminé. "
                "Pensez à vos autres objectifs de la journée."
            )
        stats.append(
            ActivityStat(
                activity_id=a["id"],
                name=a["name"],
                minutes=minutes,
                daily_limit_minutes=limit,
                exceeded=exceeded,
            )
        )
    return TodayStats(
        day=today,
        total_minutes=sum(s.minutes for s in stats),
        activities=stats,
        alerts=alerts,
    )