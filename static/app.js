(function () {
  "use strict";

  var PREF_KEY = "wetterOutfit.pref";
  var PLACE_KEY = "wetterOutfit.place";

  var views = ["preference", "loading", "location", "error", "result"];
  var lastCoords = null; // { lat, lon, name|null }
  var retryAction = null;

  function $(id) { return document.getElementById(id); }

  // --- Speicher (localStorage kann in manchen Browsern fehlen oder blockiert sein) ---
  function load(key) {
    try { return JSON.parse(localStorage.getItem(key)); } catch (e) { return null; }
  }
  function save(key, value) {
    try {
      if (value === null) localStorage.removeItem(key);
      else localStorage.setItem(key, JSON.stringify(value));
    } catch (e) { /* ignorieren */ }
  }

  var memoryPref = null;
  function getPref() { return load(PREF_KEY) || memoryPref; }
  function setPref(p) { memoryPref = p; save(PREF_KEY, p); }

  // --- Ansichten ---
  function show(name) {
    views.forEach(function (v) { $("view-" + v).hidden = v !== name; });
  }

  function loading(text) {
    $("loading-text").textContent = text;
    show("loading");
  }

  function showError(message, retry) {
    $("error-text").textContent = message;
    retryAction = retry;
    show("error");
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  // --- Datum / Begrüßung ---
  function renderDateLine() {
    var now = new Date();
    var h = now.getHours();
    var greeting = h < 11 ? "Guten Morgen" : h < 18 ? "Hallo" : "Guten Abend";
    var date = now.toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long" });
    $("date-line").textContent = greeting + " · " + date;
  }

  // --- Kälteempfinden ---
  function showPreference() {
    var current = getPref();
    document.querySelectorAll(".pref-option").forEach(function (btn) {
      btn.classList.toggle("is-active", btn.dataset.pref === current);
    });
    show("preference");
  }

  document.querySelectorAll(".pref-option").forEach(function (btn) {
    btn.addEventListener("click", function () {
      setPref(btn.dataset.pref);
      if (lastCoords) fetchRecommendation(lastCoords);
      else locate();
    });
  });

  // --- Standort ---
  function locate() {
    var manual = load(PLACE_KEY);
    if (manual && typeof manual.lat === "number") {
      fetchRecommendation(manual);
      return;
    }
    if (!("geolocation" in navigator)) {
      showLocationForm("Dein Browser unterstützt keine Standortabfrage. Gib stattdessen einen Ort ein.");
      return;
    }
    loading("Standort wird ermittelt …");
    navigator.geolocation.getCurrentPosition(
      function (pos) {
        fetchRecommendation({ lat: pos.coords.latitude, lon: pos.coords.longitude, name: null });
      },
      function (err) {
        var reason = err && err.code === 1
          ? "Du hast den Standortzugriff nicht erlaubt. Gib stattdessen einen Ort ein – oder erlaube den Zugriff in den Browser-Einstellungen."
          : "Dein Standort konnte nicht ermittelt werden. Gib stattdessen einen Ort ein.";
        showLocationForm(reason);
      },
      { enableHighAccuracy: false, timeout: 12000, maximumAge: 30 * 60 * 1000 }
    );
  }

  function showLocationForm(reason) {
    $("location-reason").textContent = reason || "Gib einen Ort ein, für den du die Empfehlung möchtest.";
    $("city-results").innerHTML = "";
    show("location");
    setTimeout(function () { $("city-input").focus(); }, 50);
  }

  $("city-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var q = $("city-input").value.trim();
    if (q.length < 2) return;
    var list = $("city-results");
    list.innerHTML = "";
    list.appendChild(el("li", "muted", "Suche …"));

    fetch("/api/geocode?q=" + encodeURIComponent(q))
      .then(function (r) { return r.json().then(function (body) { return { ok: r.ok, body: body }; }); })
      .then(function (res) {
        list.innerHTML = "";
        if (!res.ok) throw new Error(res.body.error || "Fehler bei der Suche");
        if (!res.body.results.length) {
          list.appendChild(el("li", "muted", "Kein Ort gefunden."));
          return;
        }
        res.body.results.forEach(function (place) {
          var li = el("li");
          var btn = el("button");
          btn.type = "button";
          btn.appendChild(document.createTextNode(place.name + " "));
          btn.appendChild(el("small", null, [place.region, place.country].filter(Boolean).join(", ")));
          btn.addEventListener("click", function () {
            var chosen = { lat: place.lat, lon: place.lon, name: place.name };
            save(PLACE_KEY, chosen);
            fetchRecommendation(chosen);
          });
          li.appendChild(btn);
          list.appendChild(li);
        });
      })
      .catch(function (err) {
        list.innerHTML = "";
        list.appendChild(el("li", "muted", err.message || "Die Suche ist fehlgeschlagen."));
      });
  });

  // --- Empfehlung laden ---
  function fetchRecommendation(coords) {
    lastCoords = coords;
    loading("Wetter wird abgerufen …");
    var url = "/api/recommendation?lat=" + encodeURIComponent(coords.lat.toFixed(4)) +
      "&lon=" + encodeURIComponent(coords.lon.toFixed(4)) +
      "&pref=" + encodeURIComponent(getPref() || "normal");

    fetch(url)
      .then(function (r) { return r.json().then(function (body) { return { ok: r.ok, body: body }; }); })
      .then(function (res) {
        if (!res.ok) throw new Error(res.body.error || "Unbekannter Fehler");
        renderResult(res.body, coords);
      })
      .catch(function (err) {
        showError(
          (err && err.message && err.message !== "Failed to fetch")
            ? err.message
            : "Keine Verbindung zum Server. Bitte prüfe deine Internetverbindung.",
          function () { fetchRecommendation(coords); }
        );
      });
  }

  function fmtTemp(v) { return (v === null || v === undefined) ? "–" : Math.round(v) + "°"; }

  function renderResult(data, coords) {
    var w = data.weather;
    var place = coords.name || "Dein Standort";
    $("r-place").textContent = data.day === "morgen" ? place + " · Vorschlag für morgen" : place;
    $("r-headline").textContent = data.headline;
    $("r-summary").textContent = data.summary;

    var now = $("r-now");
    now.innerHTML = "";
    if (w.current_temperature !== null && w.current_temperature !== undefined) {
      now.appendChild(el("div", "now-icon", w.current_icon || w.icon));
      now.appendChild(el("div", "now-temp", fmtTemp(w.current_temperature)));
      now.appendChild(el("div", "now-feels", "gefühlt " + fmtTemp(w.current_apparent)));
    }

    var items = $("r-items");
    items.innerHTML = "";
    data.items.forEach(function (item) {
      var li = el("li");
      li.appendChild(el("span", "icon", item.icon));
      li.appendChild(el("span", "slot", item.slot));
      li.appendChild(el("span", "text", item.text));
      items.appendChild(li);
    });

    var extras = $("r-extras");
    extras.innerHTML = "";
    data.accessories.forEach(function (a) { extras.appendChild(el("li", null, a)); });
    $("r-extras-wrap").hidden = data.accessories.length === 0;

    var hints = $("r-hints");
    hints.innerHTML = "";
    data.hints.forEach(function (h) { hints.appendChild(el("li", null, h)); });

    var first = data.hourly.length ? data.hourly[0].time.slice(0, 2) : "7";
    $("r-hourly-title").textContent =
      (data.day === "morgen" ? "Morgen" : "Heute") + " ab " + parseInt(first, 10) + " Uhr · " + w.description;

    var stats = $("r-stats");
    stats.innerHTML = "";
    [
      [w.temp_min + "° / " + w.temp_max + "°", "min / max"],
      [w.precip_probability_max + " %", "Regenrisiko"],
      [w.wind_max + " km/h", "Wind"],
      [String(w.uv_max).replace(".", ","), "UV-Index"]
    ].forEach(function (s) {
      var d = el("div", "stat");
      d.appendChild(el("b", null, s[0]));
      d.appendChild(el("span", null, s[1]));
      stats.appendChild(d);
    });

    var hourly = $("r-hourly");
    hourly.innerHTML = "";
    data.hourly.forEach(function (h) {
      var li = el("li");
      li.appendChild(el("div", "h-time", h.time));
      li.appendChild(el("div", "h-icon", h.icon));
      li.appendChild(el("div", "h-temp", h.temperature + "°"));
      li.appendChild(el("div", "h-rain", h.precip_probability >= 20 ? h.precip_probability + " %" : ""));
      hourly.appendChild(li);
    });

    $("r-pref").textContent = data.preference_label;
    show("result");
  }

  // --- Buttons ---
  $("change-pref").addEventListener("click", showPreference);
  $("refresh").addEventListener("click", function () {
    save(PLACE_KEY, null);
    lastCoords = null;
    locate();
  });
  $("change-place").addEventListener("click", function () {
    showLocationForm("Für welchen Ort möchtest du die Empfehlung?");
  });
  $("retry-geo").addEventListener("click", function () {
    save(PLACE_KEY, null);
    locate();
  });
  $("error-retry").addEventListener("click", function () {
    if (retryAction) retryAction(); else locate();
  });

  // --- Start ---
  renderDateLine();
  if (getPref()) locate();
  else showPreference();
})();
