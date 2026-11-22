# Wetter-Outfit 🧥

Eine kleine Python-Webanwendung, die dir jeden Morgen anhand des aktuellen Wetters an deinem Standort vorschlägt, was du anziehen solltest.

- **Standort** wird automatisch über den Browser ermittelt (Fallback: Ort per Suche eingeben).
- **Kälteempfinden** wird beim ersten Besuch abgefragt („eher wärmer“, „normal“, „eher kühler“) und im Browser gespeichert.
- **Wetterdaten** kommen von [Open-Meteo](https://open-meteo.com/), kostenlos und ohne API-Key.

## Woher kommen die Wetterdaten?

Der **Browser** ruft Open-Meteo direkt ab und schickt die Daten per `POST /api/recommendation` an den Server, der daraus die Empfehlung berechnet. Grund: Hosting-Anbieter wie Render teilen sich ausgehende IP-Adressen, und Open-Meteo begrenzt kostenlose Anfragen pro IP. Über den Browser zählt die IP der Nutzerin.

Klappt der Abruf im Browser nicht, holt der Server die Daten selbst (`GET /api/recommendation?lat=…&lon=…`). Fehler dabei, z. B. HTTP 429 „Limit erreicht“, stehen mit Details im Render-Log.

## So funktioniert die Empfehlung

1. Für das Tageszeitfenster 7–20 Uhr (bzw. ab der aktuellen Stunde) werden stündliche Werte geladen: Temperatur, gefühlte Temperatur, Regenwahrscheinlichkeit und -menge, Wind, UV-Index, Wettercode. Ab 19 Uhr gibt es die Empfehlung für den nächsten Tag.
2. Daraus wird eine **Outfit-Temperatur** berechnet: `0,6 × Durchschnitt + 0,4 × Minimum` der gefühlten Temperatur.
3. Das Kälteempfinden verschiebt diesen Wert: **−3 °C** für „eher wärmer“, **+3 °C** für „eher kühler“.
4. Die Outfit-Temperatur bestimmt die Stufe (eisig, frostig, kalt, frisch, mild, warm, heiß) mit Oberteil, Jacke, Hose und Schuhen.
5. Zusatzregeln: Regen (Regenjacke, Schirm bzw. Kapuze bei Wind), Schnee (Stiefel mit Profil), Wind, UV (Sonnenbrille, Sonnencreme, Hut) und Zwiebellook bei großen Temperaturschwankungen.

Die Schwellenwerte stehen oben in `recommender.py` und lassen sich leicht anpassen.

## Projektstruktur

```
app.py              Flask-App mit Routen (/, /api/recommendation, /api/geocode, /healthz)
weather.py          Abruf und Aufbereitung der Open-Meteo-Daten
recommender.py      Kleidungslogik
templates/          HTML
static/             CSS und JavaScript
tests/              pytest-Tests
render.yaml         Deploy-Konfiguration für Render.com
```

## Lokal starten

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python app.py                    # http://localhost:5000
pytest                           # Tests ausführen
```

Die Standortabfrage funktioniert im Browser nur über `https://` oder `localhost`.

## Deployment auf Render.com

1. Bei [render.com](https://render.com) mit GitHub anmelden.
2. **New → Blueprint** wählen und dieses Repository verbinden. Render liest `render.yaml` und legt den Web Service an.
   Alternativ: **New → Web Service** mit
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
3. Nach dem Build ist die App unter `https://<name>.onrender.com` erreichbar.
4. Jeder Push auf `main` löst automatisch ein neues Deployment aus.

Hinweis: Instanzen im kostenlosen Tarif schlafen nach einiger Zeit ohne Aufrufe ein. Der erste Aufruf am Morgen kann daher ein paar Sekunden dauern.
