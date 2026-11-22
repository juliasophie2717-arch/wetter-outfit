from datetime import datetime

import pytest

from recommender import pick_tier, recommend
from weather import parse_forecast

MORNING = datetime(2026, 11, 23, 7, 0)


def day(factory, temp, **kwargs):
    data = factory(temps=[temp] * 48, **kwargs)
    return parse_forecast(data, now=MORNING)


def slots(result):
    return {item["slot"]: item["text"] for item in result["items"]}


@pytest.mark.parametrize(
    "temp,tier",
    [(-10, "eisig"), (0, "frostig"), (5, "kalt"), (12, "frisch"), (17, "mild"),
     (22, "warm"), (30, "heiss")],
)
def test_tiers(temp, tier):
    assert pick_tier(temp).name == tier


def test_cold_day_has_winter_gear(forecast_factory):
    result = recommend(day(forecast_factory, -2))
    assert result["tier"] == "frostig"
    assert "Winterjacke" in slots(result)["Jacke"]
    assert "Handschuhe" in result["accessories"]


def test_hot_day_has_no_jacket(forecast_factory):
    result = recommend(day(forecast_factory, 28))
    assert result["tier"] == "heiss"
    assert "Jacke" not in slots(result)


def test_preference_shifts_outfit(forecast_factory):
    weather = day(forecast_factory, 16)
    normal = recommend(weather, "normal")
    warmer = recommend(weather, "waermer")
    cooler = recommend(weather, "kuehler")
    assert normal["tier"] == "mild"
    assert warmer["tier"] == "frisch"  # mehr Schichten
    assert cooler["tier"] == "warm"  # weniger Schichten
    assert warmer["outfit_temperature"] < normal["outfit_temperature"] < cooler["outfit_temperature"]


def test_unknown_preference_falls_back_to_normal(forecast_factory):
    result = recommend(day(forecast_factory, 15), "quatsch")
    assert result["preference"] == "normal"


def test_rain_adds_umbrella_and_rain_jacket(forecast_factory):
    result = recommend(day(forecast_factory, 12, precip_prob=80, precip=0.5, codes=63))
    assert "Regenjacke" in slots(result)["Jacke"]
    assert "Wasserdicht" in slots(result)["Schuhe"]
    assert "Regenschirm" in result["accessories"]
    assert "Regen wahrscheinlich" in result["summary"]


def test_rain_with_wind_suggests_hood_instead_of_umbrella(forecast_factory):
    result = recommend(day(forecast_factory, 12, precip_prob=80, wind=40))
    assert "Regenschirm" not in result["accessories"]
    assert any("Kapuze" in h for h in result["hints"])


def test_possible_rain_suggests_small_umbrella(forecast_factory):
    result = recommend(day(forecast_factory, 12, precip_prob=35))
    assert any("Knirps" in a for a in result["accessories"])


def test_snow_needs_boots(forecast_factory):
    result = recommend(day(forecast_factory, -1, precip_prob=90, precip=3, codes=73))
    assert "Profil" in slots(result)["Schuhe"]
    assert "Schnee" in result["summary"]
    assert "Regenschirm" not in result["accessories"]


def test_high_uv_adds_sun_protection(forecast_factory):
    result = recommend(day(forecast_factory, 26, uv=7))
    assert "Sonnenbrille" in result["accessories"]
    assert "Sonnencreme" in result["accessories"]
    assert "Cap oder Sonnenhut" in result["accessories"]


def test_big_temperature_spread_suggests_layers(forecast_factory):
    temps = [5] * 7 + [5, 6, 8, 10, 13, 16, 18, 19, 18, 16, 13, 10, 8, 6] + [5] * 27
    weather = parse_forecast(forecast_factory(temps=temps), now=MORNING)
    result = recommend(weather)
    assert any("Zwiebellook" in h for h in result["hints"])


def test_result_contains_hourly_overview(forecast_factory):
    result = recommend(day(forecast_factory, 10))
    assert len(result["hourly"]) == 14
    assert result["hourly"][0]["time"] == "07:00"
