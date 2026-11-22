import pytest

import app as app_module
from weather import WeatherError


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def test_index(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Was ziehe ich heute an" in resp.get_data(as_text=True)


def test_healthz(client):
    assert client.get("/healthz").get_json() == {"status": "ok"}


def test_recommendation_requires_coordinates(client):
    assert client.get("/api/recommendation").status_code == 400
    assert client.get("/api/recommendation?lat=100&lon=10").status_code == 400


def test_recommendation(client, monkeypatch, forecast_factory):
    data = forecast_factory(temps=[4] * 48)
    monkeypatch.setattr("weather.fetch_forecast", lambda lat, lon: data)
    resp = client.get("/api/recommendation?lat=52.5&lon=13.4&pref=waermer")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["preference"] == "waermer"
    assert body["items"]


def test_recommendation_weather_error(client, monkeypatch):
    def boom(lat, lon):
        raise WeatherError("Der Wetterdienst ist gerade nicht erreichbar")

    monkeypatch.setattr("weather.fetch_forecast", boom)
    resp = client.get("/api/recommendation?lat=52.5&lon=13.4")
    assert resp.status_code == 502
    assert "nicht erreichbar" in resp.get_json()["error"]


def test_geocode_validation(client):
    assert client.get("/api/geocode?q=a").status_code == 400
