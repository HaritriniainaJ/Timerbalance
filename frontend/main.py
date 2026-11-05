import re
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.properties import BooleanProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.uix.screenmanager import Screen
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

import api

TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def fmt_minutes(minutes):
    h, m = divmod(int(minutes), 60)
    return f"{h} h {m:02d} min" if h else f"{m} min"


def make_row(height=40):
    return BoxLayout(size_hint_y=None, height=height, spacing=6)


def wrapped_label(text, **kwargs):
    """Label dont le texte passe à la ligne selon la largeur."""
    lbl = Label(text=text, halign="center", valign="middle", **kwargs)
    lbl.bind(width=lambda inst, w: setattr(inst, "text_size", (w, None)))
    return lbl


def small_label(text):
    return Label(text=text, size_hint_y=None, height=24)


def form_popup(title, widgets, on_save):
    """Fenêtre de saisie avec boutons Annuler / Enregistrer."""
    content = BoxLayout(orientation="vertical", padding=12, spacing=8)
    for w in widgets:
        content.add_widget(w)
    content.add_widget(Widget())  # espace libre
    buttons = BoxLayout(size_hint_y=None, height=44, spacing=8)
    cancel = Button(text="Annuler")
    save = Button(text="Enregistrer")
    buttons.add_widget(cancel)
    buttons.add_widget(save)
    content.add_widget(buttons)
    popup = Popup(title=title, content=content, size_hint=(0.9, 0.7))
    cancel.bind(on_release=popup.dismiss)
    save.bind(on_release=lambda _b: on_save(popup))
    popup.open()


class DashboardScreen(Screen):
    timer_text = StringProperty("00:00:00")
    button_text = StringProperty("Démarrer")
    alert_text = StringProperty("")
    running = BooleanProperty(False)

    activities = []
    start_at = None
    _tick_event = None

    def on_enter(self):
        self.refresh()
        if self._tick_event is None:
            self._tick_event = Clock.schedule_interval(self.tick, 1)

    def on_leave(self):
        if self._tick_event is not None:
            self._tick_event.cancel()
            self._tick_event = None

    # --- données ---
    def refresh(self):
        api.request("/activities", self._set_activities, self._error)

    def _set_activities(self, activities):
        self.activities = activities
        self.ids.activity_spinner.values = [a["name"] for a in activities]
        api.request("/timer/current", self._set_timer, self._error)
        api.request("/stats/today", self._set_stats, self._error)

    def _set_timer(self, status):
        self.running = status["running"]
        if status["running"]:
            self.start_at = datetime.fromisoformat(status["start_at"])
            self.ids.activity_spinner.text = status["activity_name"]
            self.button_text = "Arrêter"
        else:
            self.start_at = None
            self.timer_text = "00:00:00"
            self.button_text = "Démarrer"
        self.ids.activity_spinner.disabled = status["running"]

    def _set_stats(self, stats):
        self.alert_text = "\n".join(stats["alerts"])
        box = self.ids.stats_box
        box.clear_widgets()
        box.add_widget(
            Label(
                text=f"Total aujourd'hui : {fmt_minutes(stats['total_minutes'])}",
                size_hint_y=None,
                height=36,
            )
        )
        for s in stats["activities"]:
            limit = s["daily_limit_minutes"]
            text = f"{s['name']} : {fmt_minutes(s['minutes'])}"
            if limit:
                text += f" / {fmt_minutes(limit)}"
            row = BoxLayout(orientation="vertical", size_hint_y=None, height=56)
            lbl = Label(text=text, color=(1, 0.45, 0.35, 1) if s["exceeded"] else (1, 1, 1, 1))
            row.add_widget(lbl)
            row.add_widget(ProgressBar(max=limit or max(s["minutes"], 1), value=s["minutes"]))
            box.add_widget(row)

    # --- actions ---
    def toggle_timer(self):
        if self.running:
            api.request("/timer/stop", lambda r: self.refresh(), self._error, method="POST")
            return
        name = self.ids.activity_spinner.text
        activity = next((a for a in self.activities if a["name"] == name), None)
        if activity is None:
            App.get_running_app().notify("Choisissez d'abord une activité.")
            return
        api.request(
            "/timer/start",
            lambda r: self.refresh(),
            self._error,
            method="POST",
            body={"activity_id": activity["id"]},
        )

    def tick(self, dt):
        if self.running and self.start_at:
            elapsed = int((datetime.now() - self.start_at).total_seconds())
            h, rest = divmod(max(elapsed, 0), 3600)
            m, s = divmod(rest, 60)
            self.timer_text = f"{h:02d}:{m:02d}:{s:02d}"
            if elapsed % 60 == 0:  # rafraîchit les stats chaque minute
                api.request("/stats/today", self._set_stats, self._error)

    def _error(self, message):
        App.get_running_app().notify(message)


class PlanningScreen(Screen):
    activities = []

    def on_enter(self):
        api.request("/activities", self._set_activities, self._error)
        self.load_schedules()

    def _set_activities(self, activities):
        self.activities = activities
        self.ids.activity_spinner.values = [a["name"] for a in activities]

    def load_schedules(self):
        api.request("/schedules", self._show_schedules, self._error)

    def _show_schedules(self, schedules):
        box = self.ids.schedule_box
        box.clear_widgets()
        if not schedules:
            box.add_widget(Label(text="Aucun planning pour aujourd'hui", size_hint_y=None, height=40))
        for s in schedules:
            row = make_row()
            row.add_widget(Label(text=f"{s['start_time']} – {s['end_time']}   {s['activity_name']}"))
            edit = Button(text="Modifier", size_hint_x=None, width=90)
            edit.bind(on_release=lambda _b, sched=s: self.edit_dialog(sched))
            remove = Button(text="Suppr.", size_hint_x=None, width=80)
            remove.bind(on_release=lambda _b, sid=s["id"]: self.ask_delete(sid))
            row.add_widget(edit)
            row.add_widget(remove)
            box.add_widget(row)

    def _check(self, activity, start, end):
        """Retourne un message d'erreur, ou None si tout est valide."""
        if activity is None:
            return "Choisissez une activité."
        if not (TIME_RE.match(start) and TIME_RE.match(end)):
            return "Format d'heure invalide (HH:MM, ex. 07:30)."
        if end <= start:
            return "L'heure de fin doit être après l'heure de début."
        return None

    def add(self):
        name = self.ids.activity_spinner.text
        start = self.ids.start_input.text.strip()
        end = self.ids.end_input.text.strip()
        activity = next((a for a in self.activities if a["name"] == name), None)
        message = self._check(activity, start, end)
        if message:
            return self._error(message)
        api.request(
            "/schedules",
            lambda r: self.load_schedules(),
            self._error,
            method="POST",
            body={"activity_id": activity["id"], "start_time": start, "end_time": end},
        )

    def edit_dialog(self, sched):
        spinner = Spinner(
            text=sched["activity_name"],
            values=[a["name"] for a in self.activities],
            size_hint_y=None,
            height=44,
        )
        start_in = TextInput(text=sched["start_time"], multiline=False, size_hint_y=None, height=44)
        end_in = TextInput(text=sched["end_time"], multiline=False, size_hint_y=None, height=44)

        def save(popup):
            activity = next((a for a in self.activities if a["name"] == spinner.text), None)
            start, end = start_in.text.strip(), end_in.text.strip()
            message = self._check(activity, start, end)
            if message:
                return self._error(message)

            def done(_result):
                popup.dismiss()
                self.load_schedules()

            api.request(
                f"/schedules/{sched['id']}",
                done,
                self._error,
                method="PUT",
                body={"activity_id": activity["id"], "start_time": start, "end_time": end},
            )

        form_popup(
            "Modifier le créneau",
            [small_label("Activité"), spinner, small_label("Début (HH:MM)"), start_in,
             small_label("Fin (HH:MM)"), end_in],
            save,
        )

    def ask_delete(self, schedule_id):
        App.get_running_app().confirm("Supprimer ce créneau ?", lambda: self.delete(schedule_id))

    def delete(self, schedule_id):
        api.request(
            f"/schedules/{schedule_id}",
            lambda r: self.load_schedules(),
            self._error,
            method="DELETE",
        )

    def _error(self, message):
        App.get_running_app().notify(message)


class ActivitiesScreen(Screen):
    def on_enter(self):
        self.load()

    def load(self):
        api.request("/activities", self._show, self._error)

    def _show(self, activities):
        box = self.ids.activity_box
        box.clear_widgets()
        for a in activities:
            limit = a["daily_limit_minutes"]
            suffix = f"   (limite : {fmt_minutes(limit)}/jour)" if limit else ""
            row = make_row()
            row.add_widget(Label(text=a["name"] + suffix))
            edit = Button(text="Modifier", size_hint_x=None, width=90)
            edit.bind(on_release=lambda _b, act=a: self.edit_dialog(act))
            remove = Button(text="Suppr.", size_hint_x=None, width=80)
            remove.bind(on_release=lambda _b, act=a: self.ask_delete(act))
            row.add_widget(edit)
            row.add_widget(remove)
            box.add_widget(row)

    @staticmethod
    def _limit_error(limit_text):
        if limit_text and (not limit_text.isdigit() or int(limit_text) == 0):
            return "La limite doit être un nombre de minutes supérieur à 0."
        return None

    def add(self):
        name = self.ids.name_input.text.strip()
        limit_text = self.ids.limit_input.text.strip()
        if not name:
            return self._error("Donnez un nom à l'activité.")
        message = self._limit_error(limit_text)
        if message:
            return self._error(message)
        body = {"name": name, "daily_limit_minutes": int(limit_text) if limit_text else None}
        api.request("/activities", self._added, self._error, method="POST", body=body)

    def _added(self, _result):
        self.ids.name_input.text = ""
        self.ids.limit_input.text = ""
        self.load()

    def edit_dialog(self, act):
        name_in = TextInput(text=act["name"], multiline=False, size_hint_y=None, height=44)
        limit_in = TextInput(
            text=str(act["daily_limit_minutes"] or ""),
            hint_text="vide = pas de limite",
            input_filter="int",
            multiline=False,
            size_hint_y=None,
            height=44,
        )

        def save(popup):
            name = name_in.text.strip()
            limit_text = limit_in.text.strip()
            if not name:
                return self._error("Donnez un nom à l'activité.")
            message = self._limit_error(limit_text)
            if message:
                return self._error(message)

            def done(_result):
                popup.dismiss()
                self.load()

            api.request(
                f"/activities/{act['id']}",
                done,
                self._error,
                method="PUT",
                body={"name": name, "daily_limit_minutes": int(limit_text) if limit_text else None},
            )

        form_popup(
            "Modifier l'activité",
            [small_label("Nom"), name_in, small_label("Limite par jour (minutes)"), limit_in],
            save,
        )

    def ask_delete(self, act):
        App.get_running_app().confirm(
            f"Supprimer « {act['name']} » ?\nSes créneaux et son historique seront aussi supprimés.",
            lambda: self.delete(act["id"]),
        )

    def delete(self, activity_id):
        api.request(
            f"/activities/{activity_id}",
            lambda r: self.load(),
            self._error,
            method="DELETE",
        )

    def _error(self, message):
        App.get_running_app().notify(message)


class TimeBalanceApp(App):
    title = "TimeBalance"

    def notify(self, message):
        content = BoxLayout(orientation="vertical", padding=12, spacing=12)
        content.add_widget(wrapped_label(message))
        close = Button(text="OK", size_hint_y=None, height=44)
        content.add_widget(close)
        popup = Popup(title="TimeBalance", content=content, size_hint=(0.85, 0.4))
        close.bind(on_release=popup.dismiss)
        popup.open()

    def confirm(self, message, on_yes):
        content = BoxLayout(orientation="vertical", padding=12, spacing=12)
        content.add_widget(wrapped_label(message))
        buttons = BoxLayout(size_hint_y=None, height=44, spacing=8)
        no = Button(text="Annuler")
        yes = Button(text="Supprimer")
        buttons.add_widget(no)
        buttons.add_widget(yes)
        content.add_widget(buttons)
        popup = Popup(title="Confirmation", content=content, size_hint=(0.85, 0.4))
        no.bind(on_release=popup.dismiss)

        def confirmed(_b):
            popup.dismiss()
            on_yes()

        yes.bind(on_release=confirmed)
        popup.open()


if __name__ == "__main__":
    TimeBalanceApp().run()
