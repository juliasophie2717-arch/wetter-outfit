from datetime import datetime

import pytest

from weather import WeatherError, describe_code, parse_forecast


def test_window_morning_uses_7_to_20(forecast_factory):
    data = forecast_factory(temps=list(range(48)))  # 2 Tage, Temperatur = Stundenindex
    day = parse_forecast(data, now=datetime(2026, 11, 23, 6, 30))
    assert day.label == "heute"
    assert [h.time.hour for h in day.hours] == list(range(7, 21))
    assert day.temp_min == 7
    assert day.temp_max == 20


def test_window_starts_at_current_hour(forecast_factory):
    data = forecast_factory(temps=list(range(48)))
    day = parse_forecast(data, now=datetime(2026, 11, 23, 15, 10))
    assert day.hours[0].time.hour == 15
    assert day.label == "heute"


def test_evening_switches_to_tomorrow(forecast_factory):
    data = forecast_factory(temps=list(range(48)))
    day = parse_forecast(data, now=datetime(2026, 11, 23, 19, 0))
    assert day.label == "morgen"
    assert day.hours[0].time == datetime(2026, 11, 24, 7, 0)


def test_uses_current_time_from_response(forecast_factory):
    data = forecast_factory(temps=list(range(48)), current_time="2026-11-23T10:00")
    day = parse_forecast(data)
    assert day.hours[0].time.hour == 10


def test_missing_values_are_tolerated(forecast_factory):
    data = forecast_factory(temps=[5.0] * 48)
    data["hourly"]["uv_index"][8] = None
    data["hourly"]["precipitation_probability"][9] = None
    data["hourly"]["temperature_2m"][10] = None  # Stunde wird übersprungen
    day = parse_forecast(data, now=datetime(2026, 11, 23, 7, 0))
    assert 10 not in [h.time.hour for h in day.hours]
    assert day.uv_max == 0


def test_invalid_data_raises():
    with pytest.raises(WeatherError):
        parse_forecast({"foo": "bar"})


def test_describe_code():
    assert describe_code(0)[0] == "Klar"
    assert describe_code(999)[0] == "Unbekannt"
    assert describe_code(None)[0] == "Unbekannt"
