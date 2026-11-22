"""Leitet aus den Wetterdaten eine Kleidungsempfehlung ab."""

from __future__ import annotations

from dataclasses import dataclass, field

from weather import FREEZING_CODES, SNOW_CODES, THUNDER_CODES, DayWeather, describe_code

# Kälteempfinden: Verschiebung der gefühlten Temperatur in °C.
# Wer sich eher wärmer anzieht, "erlebt" das Wetter kälter und bekommt mehr Schichten.
PREFERENCES = {
    "waermer": {"offset": -3.0, "label": "Ich ziehe mich eher wärmer an"},
    "normal": {"offset": 0.0, "label": "Ganz normal"},
    "kuehler": {"offset": 3.0, "label": "Ich ziehe mich eher kühler an"},
}
DEFAULT_PREFERENCE = "normal"

# Schwellen für Zusatzhinweise
RAIN_LIKELY = 50  # % Regenwahrscheinlichkeit
RAIN_POSSIBLE = 30
RAIN_SUM_MM = 1.0
WINDY_KMH = 30
STORMY_KMH = 45
UV_SUNGLASSES = 3
UV_HAT = 6
LAYER_SPREAD = 7  # °C Unterschied zwischen kühlster und wärmster Stunde


@dataclass
class Tier:
    max_temp: float  # gilt für angepasste Temperatur < max_temp
    name: str
    headline: str
    top: str
    jacket: str | None
    bottom: str
    shoes: str
    accessories: list[str] = field(default_factory=list)


TIERS: list[Tier] = [
    Tier(-5, "eisig", "Eisig – richtig warm einpacken",
         "Thermo-Unterhemd und dicker Wollpullover",
         "Dicke Winter- oder Daunenjacke",
         "Gefütterte Hose oder Thermo-Leggings unter der Hose",
         "Gefütterte Winterstiefel",
         ["Mütze", "Schal", "Handschuhe"]),
    Tier(3, "frostig", "Kalt – Wintersachen anziehen",
         "Langarmshirt und warmer Pullover",
         "Winterjacke oder Wintermantel",
         "Lange, warme Hose",
         "Warme, geschlossene Stiefel",
         ["Mütze", "Schal", "Handschuhe"]),
    Tier(9, "kalt", "Kühl – Pullover und warme Jacke",
         "Langarmshirt und Pullover",
         "Warme Übergangsjacke oder leichter Wintermantel",
         "Lange Hose",
         "Geschlossene Schuhe",
         ["Schal"]),
    Tier(14, "frisch", "Frisch – Jacke nicht vergessen",
         "Langarmshirt oder leichter Pullover",
         "Übergangsjacke",
         "Lange Hose oder Jeans",
         "Sneaker oder Halbschuhe"),
    Tier(19, "mild", "Mild – leichte Schicht reicht",
         "T-Shirt oder Langarmshirt",
         "Dünne Jacke, Strickjacke oder Hoodie zum Überziehen",
         "Lange Hose oder Jeans",
         "Sneaker"),
    Tier(24, "warm", "Angenehm warm – T-Shirt-Wetter",
         "T-Shirt oder Bluse",
         None,
         "Leichte Hose, Rock oder Chino",
         "Sneaker oder leichte Schuhe"),
    Tier(float("inf"), "heiss", "Heiß – so luftig wie möglich",
         "Luftiges T-Shirt, Top oder Leinenhemd",
         None,
         "Shorts, Rock oder leichtes Kleid",
         "Sandalen oder luftige Sneaker",
         ["Wasserflasche"]),
]


def outfit_temperature(weather: DayWeather, preference: str) -> float:
    """Temperatur, nach der sich das Outfit richtet.

    Mischung aus Tagesdurchschnitt und kühlster Stunde (man ist morgens schon
    unterwegs), plus Verschiebung durch das persönliche Kälteempfinden.
    """
    offset = PREFERENCES.get(preference, PREFERENCES[DEFAULT_PREFERENCE])["offset"]
    base = 0.6 * weather.apparent_mean + 0.4 * weather.apparent_min
    return base + offset


def pick_tier(temp: float) -> Tier:
    for tier in TIERS:
        if temp < tier.max_temp:
            return tier
    return TIERS[-1]


def _round(value: float) -> int:
    return int(round(value))


def recommend(weather: DayWeather, preference: str = DEFAULT_PREFERENCE) -> dict:
    if preference not in PREFERENCES:
        preference = DEFAULT_PREFERENCE

    temp = outfit_temperature(weather, preference)
    tier = pick_tier(temp)
    offset = PREFERENCES[preference]["offset"]

    top = tier.top
    jacket = tier.jacket
    bottom = tier.bottom
    shoes = tier.shoes
    accessories = list(tier.accessories)
    hints: list[str] = []

    codes = weather.codes
    rain_prob = weather.precip_probability_max
    rain_sum = weather.precipitation_sum
    wind = weather.wind_max
    uv = weather.uv_max
    has_snow = bool(codes & SNOW_CODES)
    rainy = (rain_prob >= RAIN_LIKELY or rain_sum >= RAIN_SUM_MM) and not has_snow
    maybe_rain = not rainy and not has_snow and rain_prob >= RAIN_POSSIBLE

    # Regen
    if rainy:
        if jacket is None:
            jacket = "Leichte Regenjacke"
        elif tier.name in ("frisch", "mild"):
            jacket = "Regenjacke (bei Bedarf mit Pullover darunter)"
        else:
            jacket = f"{jacket} – möglichst wasserdicht und mit Kapuze"
        if tier.name != "heiss":
            shoes = "Wasserdichte Schuhe oder Stiefel"
        if wind >= WINDY_KMH:
            hints.append("Zu windig für einen Schirm – lieber eine Kapuze.")
        else:
            accessories.append("Regenschirm")
    elif maybe_rain:
        accessories.append("Kleiner Knirps für alle Fälle")

    # Schnee und Glätte
    if has_snow:
        shoes = "Wasserdichte Winterstiefel mit gutem Profil"
        hints.append("Es soll schneien – rutschfeste Schuhe einplanen.")
    if codes & FREEZING_CODES:
        hints.append("Achtung, gefrierender Regen: Es kann glatt werden.")
    if codes & THUNDER_CODES:
        hints.append("Gewitter möglich – Aufenthalt im Freien gut planen.")

    # Wind
    if wind >= STORMY_KMH:
        hints.append(f"Stürmisch (bis {_round(wind)} km/h) – winddichte Jacke anziehen.")
    elif wind >= WINDY_KMH:
        hints.append(f"Windig (bis {_round(wind)} km/h) – es fühlt sich kälter an.")
        if jacket is None and temp < 22:
            jacket = "Leichte, winddichte Jacke"

    # Sonne
    if uv >= UV_SUNGLASSES:
        accessories.append("Sonnenbrille")
        accessories.append("Sonnencreme")
    if uv >= UV_HAT:
        accessories.append("Cap oder Sonnenhut")

    # Zwiebellook bei großen Temperaturschwankungen
    spread = weather.apparent_max - weather.apparent_min
    if spread >= LAYER_SPREAD:
        hints.append(
            f"Zwiebellook: Gefühlt {_round(weather.apparent_min)} °C am kühlsten und "
            f"{_round(weather.apparent_max)} °C am wärmsten – Schichten zum Ausziehen wählen."
        )

    items = [
        {"slot": "Oberteil", "icon": "👕", "text": top},
    ]
    if jacket:
        items.append({"slot": "Jacke", "icon": "🧥", "text": jacket})
    items.append({"slot": "Unten", "icon": "👖", "text": bottom})
    items.append({"slot": "Schuhe", "icon": "👟", "text": shoes})

    # Doppelte Accessoires entfernen, Reihenfolge erhalten
    accessories = list(dict.fromkeys(accessories))

    description, icon = describe_code(weather.dominant_code)
    summary_parts = [
        f"Gefühlt {_round(weather.apparent_min)} bis {_round(weather.apparent_max)} °C"
    ]
    if has_snow:
        summary_parts.append("Schnee erwartet")
    elif rainy:
        summary_parts.append(f"Regen wahrscheinlich ({_round(rain_prob)} %)")
    elif maybe_rain:
        summary_parts.append(f"vereinzelt Regen möglich ({_round(rain_prob)} %)")
    else:
        summary_parts.append("trocken")

    return {
        "day": weather.label,
        "tier": tier.name,
        "headline": tier.headline,
        "summary": ", ".join(summary_parts) + ".",
        "items": items,
        "accessories": accessories,
        "hints": hints,
        "preference": preference,
        "preference_label": PREFERENCES[preference]["label"],
        "preference_offset": offset,
        "outfit_temperature": round(temp, 1),
        "weather": {
            "description": description,
            "icon": icon,
            "current_temperature": weather.current_temperature,
            "current_apparent": weather.current_apparent,
            "current_description": describe_code(weather.current_code)[0]
            if weather.current_code is not None
            else None,
            "current_icon": describe_code(weather.current_code)[1]
            if weather.current_code is not None
            else None,
            "temp_min": _round(weather.temp_min),
            "temp_max": _round(weather.temp_max),
            "apparent_min": _round(weather.apparent_min),
            "apparent_max": _round(weather.apparent_max),
            "precip_probability_max": _round(rain_prob),
            "precipitation_sum": round(rain_sum, 1),
            "wind_max": _round(wind),
            "uv_max": round(uv, 1),
            "timezone": weather.timezone,
        },
        "hourly": [
            {
                "time": h.time.strftime("%H:%M"),
                "temperature": _round(h.temperature),
                "apparent": _round(h.apparent),
                "precip_probability": _round(h.precip_probability),
                "icon": describe_code(h.weather_code)[1],
            }
            for h in weather.hours
        ],
    }
