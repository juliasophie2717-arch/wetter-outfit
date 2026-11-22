"""Wetter-Outfit: schlägt anhand des aktuellen Wetters vor, was man anziehen soll."""

from __future__ import annotations

import logging

from flask import Flask, jsonify, render_template, request

from recommender import DEFAULT_PREFERENCE, PREFERENCES, recommend
from weather import WeatherError, get_day_weather, search_city

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def _error(message: str, status: int):
    return jsonify({"error": message}), status


def _coordinate(name: str, low: float, high: float) -> float | None:
    raw = request.args.get(name, type=float)
    if raw is None or not (low <= raw <= high):
        return None
    return raw


@app.get("/")
def index():
    return render_template("index.html", preferences=PREFERENCES)


@app.get("/api/recommendation")
def api_recommendation():
    lat = _coordinate("lat", -90, 90)
    lon = _coordinate("lon", -180, 180)
    if lat is None or lon is None:
        return _error("Bitte gültige Koordinaten (lat, lon) angeben.", 400)

    preference = request.args.get("pref", DEFAULT_PREFERENCE)
    if preference not in PREFERENCES:
        preference = DEFAULT_PREFERENCE

    try:
        weather = get_day_weather(lat, lon)
    except WeatherError as exc:
        log.warning("Wetterabruf fehlgeschlagen: %s", exc)
        return _error(str(exc), 502)

    return jsonify(recommend(weather, preference))


@app.get("/api/geocode")
def api_geocode():
    name = (request.args.get("q") or "").strip()
    if len(name) < 2:
        return _error("Bitte mindestens zwei Buchstaben eingeben.", 400)
    try:
        return jsonify({"results": search_city(name[:100])})
    except WeatherError as exc:
        log.warning("Ortssuche fehlgeschlagen: %s", exc)
        return _error(str(exc), 502)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(debug=True, port=5000)
