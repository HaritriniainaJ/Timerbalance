from pydantic import BaseModel, Field, model_validator

TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"  # HH:MM


class ActivityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    daily_limit_minutes: int | None = Field(default=None, gt=0)


class Activity(ActivityCreate):
    id: int


class ScheduleCreate(BaseModel):
    activity_id: int
    start_time: str = Field(pattern=TIME_PATTERN)
    end_time: str = Field(pattern=TIME_PATTERN)
    day: str | None = None  # AAAA-MM-JJ, aujourd'hui par défaut

    @model_validator(mode="after")
    def check_order(self):
        if self.end_time <= self.start_time:
            raise ValueError("L'heure de fin doit être après l'heure de début")
        return self


class Schedule(BaseModel):
    id: int
    activity_id: int
    activity_name: str
    day: str
    start_time: str
    end_time: str


class TimerStart(BaseModel):
    activity_id: int


class TimerStatus(BaseModel):
    running: bool
    activity_id: int | None = None
    activity_name: str | None = None
    start_at: str | None = None


class ActivityStat(BaseModel):
    activity_id: int
    name: str
    minutes: int
    daily_limit_minutes: int | None
    exceeded: bool


class TodayStats(BaseModel):
    day: str
    total_minutes: int
    activities: list[ActivityStat]
    alerts: list[str]