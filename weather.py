"""Abruf und Aufbereitung von Wetterdaten über die Open-Meteo API.

Open-Meteo ist kostenlos und benötigt keinen API-Key:
https://open-meteo.com/en/docs
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime

import requests

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"

HOURLY_VARS = [
    "temperature_2m",
    "apparent_temperature",
    "precipitation_probability",
    "precipitation",
    "weather_code",
    "wind_speed_10m",
    "uv_index",
]
CURRENT_VARS = ["temperature_2m", "apparent_temperature", "weather_code", "wind_speed_10m"]

# Tageszeitfenster, für das die Empfehlung gilt (lokale Stunden)
DAY_START_HOUR = 7
DAY_END_HOUR = 21  # exklusiv: letzte berücksichtigte Stunde ist 20 Uhr
MIN_HOURS_LEFT = 3  # sind heute weniger Stunden übrig, wird der nächste Tag genommen

CACHE_SECONDS = 15 * 60
REQUEST_TIMEOUT = 10

# WMO-Wettercodes -> deutsche Beschreibung und Symbol
WEATHER_CODES: dict[int, tuple[str, str]] = {
    0: ("Klar", "☀️"),
    1: ("Überwiegend klar", "🌤️"),
    2: ("Teilweise bewölkt", "⛅"),
    3: ("Bedeckt", "☁️"),
    45: ("Nebel", "🌫️"),
    48: ("Nebel mit Reif", "🌫️"),
    51: ("Leichter Nieselregen", "🌦️"),
    53: ("Nieselregen", "🌦️"),
    55: ("Starker Nieselregen", "🌧️"),
    56: ("Gefrierender Nieselregen", "🌧️"),
    57: ("Starker gefrierender Nieselregen", "🌧️"),
    61: ("Leichter Regen", "🌦️"),
    63: ("Regen", "🌧️"),
    65: ("Starker Regen", "🌧️"),
    66: ("Gefrierender Regen", "🌧️"),
    67: ("Starker gefrierender Regen", "🌧️"),
    71: ("Leichter Schneefall", "🌨️"),
    73: ("Schneefall", "🌨️"),
    75: ("Starker Schneefall", "❄️"),
    77: ("Schneegriesel", "🌨️"),
    80: ("Leichte Regenschauer", "🌦️"),
    81: ("Regenschauer", "🌧️"),
    82: ("Heftige Regenschauer", "⛈️"),
    85: ("Leichte Schneeschauer", "🌨️"),
    86: ("Starke Schneeschauer", "❄️"),
    95: ("Gewitter", "⛈️"),
    96: ("Gewitter mit Hagel", "⛈️"),
    99: ("Starkes Gewitter mit Hagel", "⛈️"),
}

SNOW_CODES = {71, 73, 75, 77, 85, 86}
FREEZING_CODES = {56, 57, 66, 67}
THUNDER_CODES = {95, 96, 99}


class WeatherError(Exception):
    """Wetterdaten konnten nicht abgerufen oder gelesen werden."""


def describe_code(code: int | None) -> tuple[str, str]:
    if code is None:
        return ("Unbekannt", "🌡️")
    return WEATHER_CODES.get(int(code), ("Unbekannt", "🌡️"))


@dataclass
class HourlyPoint:
    time: datetime
    temperature: float
    apparent: float
    precip_probability: float
    precipitation: float
    weather_code: int
    wind_speed: float
    uv_index: float


@dataclass
class DayWeather:
    """Wetter für das relevante Tageszeitfenster."""

    label: str  # "heute" oder "morgen"
    hours: list[HourlyPoint]
    current_temperature: float | None = None
    current_apparent: float | None = None
    current_code: int | None = None
    timezone: str = ""
    codes: set[int] = field(default_factory=set)

    @property
    def apparent_min(self) -> float:
        return min(h.apparent for h in self.hours)

    @property
    def apparent_max(self) -> float:
        return max(h.apparent for h in self.hours)

    @property
    def apparent_mean(self) -> float:
        return sum(h.apparent for h in self.hours) / len(self.hours)

    @property
    def temp_min(self) -> float:
        return min(h.temperature for h in self.hours)

    @property
    def temp_max(self) -> float:
        return max(h.temperature for h in self.hours)

    @property
    def precip_probability_max(self) -> float:
        return max(h.precip_probability for h in self.hours)

    @property
    def precipitation_sum(self) -> float:
        return sum(h.precipitation for h in self.hours)

    @property
    def wind_max(self) -> float:
        return max(h.wind_speed for h in self.hours)

    @property
    def uv_max(self) -> float:
        return max(h.uv_index for h in self.hours)

    @property
    def dominant_code(self) -> int:
        """Der 'schlimmste' Wettercode im Fenster (höherer WMO-Code = stärkeres Wetter)."""
        return max(h.weather_code for h in self.hours)


def _num(value, default: float = 0.0) -> float:
    return default if value is None else float(value)


def parse_forecast(data: dict, now: datetime | None = None) -> DayWeather:
    """Wandelt die Open-Meteo-Antwort in ein DayWeather-Objekt für das Tagesfenster um.

    `now` ist die lokale Uhrzeit am Standort (ohne Zeitzone). Ohne Angabe wird
    die Zeit aus dem `current`-Block der Antwort verwendet.
    """
    try:
        hourly = data["hourly"]
        times = [datetime.fromisoformat(t) for t in hourly["time"]]
    except (KeyError, TypeError, ValueError) as exc:
        raise WeatherError("Unerwartetes Format der Wetterdaten") from exc

    current = data.get("current") or {}
    if now is None:
        if current.get("time"):
            now = datetime.fromisoformat(current["time"])
        else:
            now = times[0]

    points: list[HourlyPoint] = []
    for i, t in enumerate(times):
        temp = hourly["temperature_2m"][i]
        if temp is None:
            continue
        points.append(
            HourlyPoint(
                time=t,
                temperature=float(temp),
                apparent=_num(hourly["apparent_temperature"][i], float(temp)),
                precip_probability=_num(hourly["precipitation_probability"][i]),
                precipitation=_num(hourly["precipitation"][i]),
                weather_code=int(_num(hourly["weather_code"][i])),
                wind_speed=_num(hourly["wind_speed_10m"][i]),
                uv_index=_num(hourly["uv_index"][i]),
            )
        )

    today = now.date()
    start_hour = max(DAY_START_HOUR, now.hour)
    window = [
        p for p in points if p.time.date() == today and start_hour <= p.time.hour < DAY_END_HOUR
    ]
    label = "heute"

    if len(window) < MIN_HOURS_LEFT:
        future_days = sorted({p.time.date() for p in points if p.time.date() > today})
        if future_days:
            tomorrow = future_days[0]
            window = [
                p
                for p in points
                if p.time.date() == tomorrow and DAY_START_HOUR <= p.time.hour < DAY_END_HOUR
            ]
            label = "morgen"

    if not window:
        raise WeatherError("Keine Wetterdaten für den Tag verfügbar")

    return DayWeather(
        label=label,
        hours=window,
        current_temperature=current.get("temperature_2m"),
        current_apparent=current.get("apparent_temperature"),
        current_code=current.get("weather_code"),
        timezone=data.get("timezone", ""),
        codes={p.weather_code for p in window},
    )


_cache: dict[tuple[float, float], tuple[float, dict]] = {}


def fetch_forecast(lat: float, lon: float) -> dict:
    """Holt die Rohdaten von Open-Meteo (mit kurzem In-Memory-Cache)."""
    key = (round(lat, 2), round(lon, 2))
    cached = _cache.get(key)
    if cached and time.time() - cached[0] < CACHE_SECONDS:
        return cached[1]

    params = {
        "latitude": key[0],
        "longitude": key[1],
        "hourly": ",".join(HOURLY_VARS),
        "current": ",".join(CURRENT_VARS),
        "timezone": "auto",
        "forecast_days": 2,
        "wind_speed_unit": "kmh",
    }
    try:
        resp = requests.get(FORECAST_URL, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise WeatherError("Der Wetterdienst ist gerade nicht erreichbar") from exc

    _cache[key] = (time.time(), data)
    if len(_cache) > 500:  # Cache klein halten
        oldest = min(_cache, key=lambda k: _cache[k][0])
        _cache.pop(oldest, None)
    return data


def get_day_weather(lat: float, lon: float) -> DayWeather:
    return parse_forecast(fetch_forecast(lat, lon))


def search_city(name: str) -> list[dict]:
    """Sucht Orte per Name (Fallback, falls der Browser-Standort nicht freigegeben wird)."""
    params = {"name": name, "count": 5, "language": "de", "format": "json"}
    try:
        resp = requests.get(GEOCODING_URL, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        results = resp.json().get("results") or []
    except (requests.RequestException, ValueError) as exc:
        raise WeatherError("Die Ortssuche ist gerade nicht erreichbar") from exc

    return [
        {
            "name": r.get("name"),
            "region": r.get("admin1") or "",
            "country": r.get("country") or "",
            "lat": r.get("latitude"),
            "lon": r.get("longitude"),
        }
        for r in results
        if r.get("latitude") is not None and r.get("longitude") is not None
    ]
