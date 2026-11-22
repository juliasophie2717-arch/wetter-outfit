"""Wetter-Outfit: schlägt anhand des aktuellen Wetters vor, was man anziehen soll.

Die Wetterdaten holt normalerweise der Browser direkt bei Open-Meteo (über die
IP-Adresse der Nutzerin) und schickt sie per POST an /api/recommendation.
Der Server ruft Open-Meteo nur als Fallback selbst ab, weil sich Hosting-
Anbieter wie Render ausgehende IP-Adressen teilen und Open-Meteo pro IP limitiert.
"""

from __future__ import annotations

import logging

from flask import Flask, jsonify, render_template, request

from recommender import DEFAULT_PREFERENCE, PREFERENCES, recommend
from weather import (
    FORECAST_URL,
    GEOCODING_URL,
    WeatherError,
    forecast_params,
    get_day_weather,
    parse_forecast,
    search_city,
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 256 * 1024  # Wetterdaten vom Browser sind ca. 10 KB

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def _error(message: str, status: int):
    return jsonify({"error": message}), status


def _preference(value) -> str:
    return value if value in PREFERENCES else DEFAULT_PREFERENCE


def _coordinate(name: str, low: float, high: float) -> float | None:
    raw = request.args.get(name, type=float)
    if raw is None or not (low <= raw <= high):
        return None
    return raw


@app.get("/")
def index():
    client_config = {
        "forecastUrl": FORECAST_URL,
        "forecastParams": forecast_params(),
        "geocodingUrl": GEOCODING_URL,
    }
    return render_template("index.html", preferences=PREFERENCES, client_config=client_config)


@app.post("/api/recommendation")
def api_recommendation_from_data():
    """Empfehlung aus Wetterdaten, die der Browser selbst bei Open-Meteo geholt hat."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not isinstance(body.get("forecast"), dict):
        return _error("Es wurden keine Wetterdaten mitgeschickt.", 400)

    try:
        weather = parse_forecast(body["forecast"])
    except WeatherError as exc:
        return _error(str(exc), 400)

    return jsonify(recommend(weather, _preference(body.get("pref"))))


@app.get("/api/recommendation")
def api_recommendation():
    """Fallback: Der Server holt die Wetterdaten selbst."""
    lat = _coordinate("lat", -90, 90)
    lon = _coordinate("lon", -180, 180)
    if lat is None or lon is None:
        return _error("Bitte gültige Koordinaten (lat, lon) angeben.", 400)

    try:
        weather = get_day_weather(lat, lon)
    except WeatherError as exc:
        return _error(str(exc), 502)

    return jsonify(recommend(weather, _preference(request.args.get("pref"))))


@app.get("/api/geocode")
def api_geocode():
    name = (request.args.get("q") or "").strip()
    if len(name) < 2:
        return _error("Bitte mindestens zwei Buchstaben eingeben.", 400)
    try:
        return jsonify({"results": search_city(name[:100])})
    except WeatherError as exc:
        return _error(str(exc), 502)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(debug=True, port=5000)
