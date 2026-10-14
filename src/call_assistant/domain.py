"""Preparation and confirmed data ownership; no provider-side effects."""
from datetime import datetime,timezone
from .models import Settings

QUESTIONS={
 "restaurant":[("people","Für wie viele Personen möchtest du reservieren?",["2 Personen","3 Personen","4 Personen"]),("time","Welche Uhrzeit passt dir?",["Heute 19:00 Uhr","Heute 19:30 Uhr","Heute 20:00 Uhr"]),("access","Welche Zugangsbedingungen muss das Restaurant erfüllen?",["Stufenloser Zugang und Platz für den Rollstuhl","Zusätzlich barrierefreies WC","Keine besonderen Anforderungen"])],
 "doctor":[("symptoms","Welche Beschwerden soll die Assistenz mitteilen?",["Kopfschmerzen seit zwei Tagen","Ich beschreibe die Beschwerden selbst"]),("urgency","Welche Angaben zur Dringlichkeit sind sicher bekannt?",["Keine plötzlich stärksten Schmerzen, keine neuen neurologischen Beschwerden","Das ist noch nicht geklärt"]),("patient","Bist du bereits Patient dieser Praxis?",["Ja","Nein","Noch nicht geklärt"])],
 "airline":[("booking","Welche Buchungsreferenz darf die Assistenz nennen?",[]),("wheelchair","Welche Rollstuhldaten sind bereits bestätigt?",["Maße und Gewicht vorhanden","Technische Angaben fehlen noch"]),("assistance","Welchen Assistenzumfang möchtest du anmelden?",["Von mir genau beschrieben","Vor einer Zusage bei mir rückfragen"])],
 "general":[("details","Welche Angaben braucht die Gegenstelle?",[])]}

def next_question(brief):
    for key,text,options in QUESTIONS[brief["scenario"]]:
        if not brief["answers"].get(key):return {"id":key,"text":text,"options":options,"allow_free_text":True}
    if not brief["answers"].get("permissions"):
        return {"id":"permissions","text":"Welche Alternativen darf die Assistenz ohne Rückfrage akzeptieren?","options":["Keine – Änderungen bitte bei mir rückfragen","Nur innerhalb meiner genannten Zeit- und Kostengrenzen"],"allow_free_text":True}
    return None

def brief_context(brief,settings,memories):
    person=settings.get("person",{})
    return {"schema_version":1,"objective":brief["objective"],"destination":brief["number"],
        "person":person,"answers":brief["answers"],"facts":brief.get("facts",{}),
        "unknowns":brief.get("unknowns",[]),"permissions":brief.get("permissions") or brief["answers"].get("permissions", "Keine neuen Zusagen ohne Nutzerentscheidung"),
        "memories":[m["text"] for m in memories if m.get("confirmed") and m["id"] in brief.get("memory_ids",[])],"prepared_at":datetime.now(timezone.utc).isoformat()}

def instructions(accepted):
    import json
    return ("Du bist die Assistenz der anrufenden Person, nicht die Gegenstelle. Führe einen natürlichen, kurzen Anruf. "
        "Beginne nur mit Begrüßung und grundsätzlichem Anliegen. Kläre Details schrittweise; keine Pflichtfrage nach jeder Antwort. "
        "Erfinde keine Angaben, Symptome, Befugnisse oder Nutzerwünsche. Frage die Organisation nach ihren Fakten, nicht nach den Wünschen der Person. "
        "Unbekannt bleibt unbekannt. Empfehlungen sind keine Nutzerentscheidung. Nur ausdrücklich freigegebene Alternativen darfst du zusagen. "
        "Andernfalls nutze ask_user mit einer privaten Frage und Optionen. Sage die private Frage nicht zur Gegenstelle. "
        "Buchstabiere kritische Codes in der jeweiligen Sprache und bestätige die Reihenfolge, statt zu raten. "
        "Wiederhole nicht alle Angaben. Ein fehlender Abschiedsgruß macht ein inhaltlich erfolgreiches Gespräch nicht erfolglos. "
        "Verwende finish_call erst nach geklärtem Ergebnis; offene Angaben gehören ins Ergebnis. "
        "Sprich die konfigurierte Sprache natürlich, ohne englische Buchstabennamen im Deutschen.\n"
        "BESTÄTIGTER STECKBRIEF (Kontext, keine anfängliche Vorleseliste):\n"+json.dumps(accepted,ensure_ascii=False))

