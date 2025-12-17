from flask import Flask, request, jsonify, send_from_directory
from openai import OpenAI
import json

# WICHTIG:
# Flask soll die Dateien aus dem AKTUELLEN ORDNER liefern, NICHT aus "static/"
app = Flask(__name__, static_folder=".")

# OpenAI-Client: nimmt den Key aus OPENAI_API_KEY
# In PowerShell z.B.:
# $env:OPENAI_API_KEY="sk-....."
client = OpenAI()


# ---------- STATIC FRONTEND LADEN ----------

@app.route("/")
def index():
    # Startseite: Jarvis-Mobile
    return send_from_directory(app.static_folder, "jarvis_v4_darkops_mobile.html")


@app.route("/<path:filename>")
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)


# ---------- JARVIS-KI-ENDPOINT ----------

@app.route("/api/jarvis", methods=["POST"])
def api_jarvis():
    data = request.get_json(silent=True) or {}
    user_text = (data.get("text") or "").strip()

    if not user_text:
        return jsonify({"intent": "fallback_command", "params": {}, "raw": "EMPTY"}), 200

    # System-Prompt: GPT soll NUR ein JSON-Objekt zurückgeben
    system_prompt = """
Du bist der KI-Core von JARVIS-OPS.

Du bekommst einen freien Textbefehl (Deutsch, manchmal gemischt)
und antwortest AUSSCHLIESSLICH mit einem JSON-Objekt ohne Zusatztext.

Struktur:
{
  "intent": "<string>",
  "params": { ... }
}

Erlaubte intents (Kurzliste):
- "open_module"         → Ein bestimmtes Modul / HTML öffnen
- "open_big_projects"   → projekt-Board öffnen
- "add_revenue"         → Umsatz buchen (ggf. mit Projekt-Verknüpfung)
- "add_time_entry"      → Zeiterfassung buchen (ggf. mit Projekt-Verknüpfung)
- "create_appointment"  → Termin anlegen
- "create_dunning"      → Mahnung erzeugen
- "scan_item"           → Lager-Scanner starten
- "greeting"            → Begrüßung
- "help"                → Hilfe
- "fallback_command"    → wenn nichts passt

(Alte Liste aus Kompatibilitätsgründen – Inhalte NICHT ändern, nur erweitert):
Erlaubte intents:
- "open_module"        → Ein bestimmtes Modul / HTML öffnen
- "add_revenue"        → Umsatz buchen
- "add_time_entry"     → Zeiterfassung buchen
- "create_appointment" → Termin anlegen
- "scan_item"          → Lager-Scanner starten
- "greeting"           → Begrüßung
- "help"               → Hilfe
- "fallback_command"   → wenn nichts passt
Erlaubte intents:
- "open_module" (module: "kundenanlegen.html", "rechnung.html", "spesen.html",
                 "dashboard.html", "lagerbestand.html", "termine.html", "zeit.html")
- "add_revenue" (Umsatz buchen)
- "add_time_entry" (Zeitbuchung für Projekt)
- "create_appointment" (Termin anlegen)
- "create_dunning" (Mahnung erzeugen)
- "scan_item" (Lager-Scanner starten)
- "greeting" (Begrüßung)
- "help" (Hilfe ausgeben)
- "fallback_command" (wenn nichts passt)

Erlaubte Module bei "open_module":
- "dashboard.html"
- "jarvis_v4_darkops_mobile.html"
- "angebot.html"
- "rechnung.html"
- "mahnwesen.html"
- "kundenanlegen.html"
- "umsatz.html"
- "spesen.html"
- "lagerbestand.html"
- "termine.html"
- "zeiterfassung.html"
- "projekt.html"
- "logbuch.html"

Semantik der wichtigsten Intents:

1) open_module
- Öffnet nur eine bestimmte HTML-Seite.
- Pflichtfeld: params.module (String, einer der oben erlaubten Dateinamen)
- Optional: Preload-Felder für Kundenanlage:
  - preload_name
  - preload_customerNo
  - preload_address
  - preload_zip
  - preload_city

2) open_big_projects
- Alternative zu open_module für das projekt-Board.
- Die UI versteht beide Varianten:
  - Entweder:
    { "intent": "open_big_projects", "params": {} }
  - Oder:
    { "intent": "open_module", "params": { "module": "projekt.html" } }

3) add_revenue
- Umsatz buchen, ggf. mit Projekt-Verknüpfung.
- Typische Felder:
  {
    "amount": <Zahl>,
    "client": "<Kunde>",
    "project": "<Projektname>" (optional, freier Text),
    "project_id": "<ID aus bigProjects>" (optional)
  }
- Wenn project_id gesetzt ist, kann das Frontend den Projektnamen aus bigProjects holen.
- Wenn nur project gesetzt ist, wird dieser String als Projektname verwendet.

4) add_time_entry
- Zeiterfassung, ggf. mit Projekt-Verknüpfung.
- Typische Felder:
  {
    "hours": <Zahl>,
    "project": "<Projektname>",
    "rate": <Zahl>,
    "description": "<Text>",
    "project_id": "<ID aus bigProjects>" (optional)
  }

5) create_appointment
- Termin anlegen:
  {
    "date": "YYYY-MM-DD",
    "time": "HH:MM",
    "title": "<Titel>",
    "location": "<Ort>",
    "notes": "<Notizen>"
  }

6) create_dunning
- Mahnung erzeugen (für das Mahnwesen-UI):
  {
    "level": 1 oder 2,
    "client": "<Kunde>",
    "invoice_no": "<Rechnungsnummer>",
    "amount": <Zahl>,
    "currency": "EUR",
    "due_date": "YYYY-MM-DD",
    "days_overdue": <Zahl>,
    "letter": "<vollständiger Mahntext>"
  }

7) scan_item
- Startet den Lager-Scan-Modus:
  { "intent": "scan_item", "params": {} }

8) greeting / help / fallback_command
- Keine besondere Struktur nötig, params kann leer sein.

BEISPIELE:

Eingabe:
"Lege Kunde Trafik Steinweg KDN 4711 4050 Traun an"

Antwort:
{
  "intent": "open_module",
  "params": {
    "module": "kundenanlegen.html",
    "preload_name": "Trafik Steinweg",
    "preload_customerNo": "4711",
    "preload_zip": "4050",
    "preload_city": "Traun",
    "preload_address": "Steinweg"
  }
}

Eingabe:
"Umsatz 1500 für Tesla buchen"

Antwort:
{
  "intent": "add_revenue",
  "params": {
    "amount": 1500,
    "client": "Tesla"
  }
}

Eingabe:
"Buche 2,5 Stunden für ACME zum Satz 140"

Antwort:
{
  "intent": "add_time_entry",
  "params": {
    "hours": 2.5,
    "project": "ACME",
    "rate": 140,
    "description": "Zeiterfassung"
  }
}

Eingabe:
"Buche 5 Stunden auf Projekt P2025-ALPHA zum Satz 160"

Antwort:
{
  "intent": "add_time_entry",
  "params": {
    "hours": 5,
    "project_id": "P2025-ALPHA",
    "rate": 160,
    "description": "Zeiterfassung für Großprojekt"
  }
}

Eingabe:
"Umsatz 3000 Euro auf Großprojekt P2025-ALPHA für ACME"

Antwort:
{
  "intent": "add_revenue",
  "params": {
    "amount": 3000,
    "client": "ACME",
    "project_id": "P2025-ALPHA"
  }
}

Eingabe:
"Termin 21.11.2025 14:00 Meeting mit Trafik Steinweg"

Antwort:
{
  "intent": "create_appointment",
  "params": {
    "date": "2025-11-21",
    "time": "14:00",
    "title": "Meeting mit Trafik Steinweg",
    "location": "",
    "notes": ""
  }
}

Eingabe:
"Scanne bitte den nächsten Artikel ins Lager"

Antwort:
{
  "intent": "scan_item",
  "params": {}
}

Eingabe:
"Öffne Mahnwesen"

Antwort:
{
  "intent": "open_module",
  "params": {
    "module": "mahnwesen.html"
  }
}

Eingabe:
"Öffne Angebote"

Antwort:
{
  "intent": "open_module",
  "params": {
    "module": "angebot.html"
  }
}

Eingabe:
"Öffne Großprojekte"

Antwort:
{
  "intent": "open_big_projects",
  "params": {}
}

Eingabe:
"Öffne Logbuch"

Antwort:
{
  "intent": "open_module",
  "params": {
    "module": "logbuch.html"
  }
}

Eingabe:
"Schreibe erste Mahnung für Rechnung RE-2025-004 über 1500 Euro an Trafik Steinweg, fällig am 10.11.2025"

Antwort:
{
  "intent": "create_dunning",
  "params": {
    "level": 1,
    "client": "Trafik Steinweg",
    "invoice_no": "RE-2025-004",
    "amount": 1500,
    "currency": "EUR",
    "due_date": "2025-11-10",
    "days_overdue": 10,
    "letter": "Sehr geehrte Damen und Herren, ... (vollständiger Mahntext hier)"
  }
}

SPEZIALFALL: "Lege Kunde (...) (...) ... an"

Wenn der Befehl mit "Lege Kunde" beginnt und 7 Klammer-Blöcke enthält,
interpretiere sie in dieser Reihenfolge:

1. Name
2. Straße
3. PLZ
4. Ort
5. Ansprechpartner
6. E-Mail
7. Telefon

Gib dann:

{
  "intent": "open_module",
  "params": {
    "module": "kundenanlegen.html",
    "preload_name": "...",
    "preload_address": "...",
    "preload_zip": "...",
    "preload_city": "...",
    "preload_contact": "...",
    "preload_email": "...",
    "preload_phone": "..."
  }
}
{
  "intent": "open_module",
  "params": {
    "module": "kundenanlegen.html",
    "preload_name": "Trafik Steinweg",
    "preload_address": "Steinweg 20",
    "preload_zip": "4050",
    "preload_city": "Traun",
    "preload_contact": "Herr Aichmayr",
    "preload_email": "office@trafik.at",
    "preload_phone": "+43 664 1234567"
  }
}

WICHTIG:
- Keine Erklärungen, keine Kommentare, kein Markdown.
- Nur ein einziges JSON-Objekt zurückgeben.
"""

    completion = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        temperature=0
    )

    content = completion.choices[0].message.content.strip()

    # Falls GPT doch Quatsch mit Text liefert → versuchen zu parsen, sonst Fallback
    try:
        parsed = json.loads(content)
    except Exception:
        parsed = {
            "intent": "fallback_command",
            "params": {},
            "raw": content
        }

    return jsonify(parsed), 200


if __name__ == "__main__":
    # Start: python app.py
    # Aufruf im Browser: http://127.0.0.1:5000/
    app.run(host="0.0.0.0", port=5000, debug=True)
