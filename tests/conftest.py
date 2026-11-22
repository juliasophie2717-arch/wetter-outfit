import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def make_forecast(
    temps,
    apparent=None,
    precip_prob=None,
    precip=None,
    codes=None,
    wind=None,
    uv=None,
    start="2026-11-23T00:00",
    current_time="2026-11-23T07:00",
):
    """Baut eine Antwort im Format der Open-Meteo-API nach.

    Die Listen beginnen bei `start` und enthalten einen Wert pro Stunde.
    Einzelwerte werden auf alle Stunden übertragen.
    """
    n = len(temps)

    def expand(value, default):
        if value is None:
            value = default
        if isinstance(value, (int, float)):
            return [value] * n
        return list(value)

    t0 = datetime.fromisoformat(start)
    return {
        "timezone": "Europe/Berlin",
        "current": {
            "time": current_time,
            "temperature_2m": temps[0],
            "apparent_temperature": (apparent or temps)[0],
            "weather_code": 0,
            "wind_speed_10m": 5,
        },
        "hourly": {
            "time": [(t0 + timedelta(hours=i)).isoformat(timespec="minutes") for i in range(n)],
            "temperature_2m": list(temps),
            "apparent_temperature": expand(apparent, None) if apparent is not None else list(temps),
            "precipitation_probability": expand(precip_prob, 0),
            "precipitation": expand(precip, 0.0),
            "weather_code": expand(codes, 0),
            "wind_speed_10m": expand(wind, 5),
            "uv_index": expand(uv, 0),
        },
    }


@pytest.fixture
def forecast_factory():
    return make_forecast
