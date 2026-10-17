"""Preparation and confirmed data ownership; no provider-side effects."""
from datetime import datetime,timezone
from .models import Settings
import re

def preparation_prompt(context):
    import json
    return ("Return JSON with question_id, question, options (array), done (boolean). "
        "This application makes a TELEPHONE CALL to the supplied destination. The channel is already decided: phone. "
        "Never ask whether to call, send a message, use SMS, email or another channel. "
        "Ask ONE missing question only if its answer materially changes what the caller must say or may agree to. "
        "Read the objective and all existing answers first; do not repeat facts, ask generic preference questions or invent decisions. "
        "For a simple message with complete wording, done=true; no extra questions are necessary. "
        "Do not create instructions or make decisions. Language: German. Known confirmed context: "+json.dumps(context,ensure_ascii=False))

def has_farewell(text):
    return bool(re.search(r"\b(auf wiederhören|auf wiedersehen|tschüss|tschüs|bis bald|schönen (?:tag|abend)|goodbye|bye|have a (?:good|nice) (?:day|evening))\b",text,re.I))

def enrich_brief(brief):
    """Extract only explicit facts; never ask again for facts already supplied."""
    text=brief["objective"]
    if brief.get("scenario","general")=="general":
        brief["scenario"] = "restaurant" if re.search(r"Tisch|Restaurant|Personen.{0,20}reserv",text,re.I) else "doctor" if re.search(r"Arzt|Praxis|Kopfschmerz",text,re.I) else "airline" if re.search(r"Flug|Airline",text,re.I) else "general"
    answers=dict(brief.get("answers",{}))
    people=re.search(r"\b(\d+|zwei|drei|vier|fünf|sechs|eine?)\s+Person(?:en)?\b",text,re.I)
    if people:answers.setdefault("people",people.group(0))
    clock=re.search(r"\b(?:[01]?\d|2[0-3])(?::[0-5]\d)?\s*Uhr\b",text,re.I)
    if clock:answers.setdefault("time",clock.group(0))
    brief["answers"]=answers
    return brief

QUESTIONS={
 "restaurant":[("people","Für wie viele Personen möchtest du reservieren?",["2 Personen","3 Personen","4 Personen"]),("time","Welche Uhrzeit passt dir?",["Heute 19:00 Uhr","Heute 19:30 Uhr","Heute 20:00 Uhr"]),("access","Welche Zugangsbedingungen muss das Restaurant erfüllen?",["Stufenloser Zugang und Platz für den Rollstuhl","Zusätzlich barrierefreies WC","Keine besonderen Anforderungen"])],
 "doctor":[("symptoms","Welche Beschwerden soll die Assistenz mitteilen?",["Kopfschmerzen seit zwei Tagen","Ich beschreibe die Beschwerden selbst"]),("urgency","Welche Angaben zur Dringlichkeit sind sicher bekannt?",["Keine plötzlich stärksten Schmerzen, keine neuen neurologischen Beschwerden","Das ist noch nicht geklärt"]),("patient","Bist du bereits Patient dieser Praxis?",["Ja","Nein","Noch nicht geklärt"])],
 "airline":[("booking","Welche Buchungsreferenz darf die Assistenz nennen?",[]),("wheelchair","Welche Rollstuhldaten sind bereits bestätigt?",["Maße und Gewicht vorhanden","Technische Angaben fehlen noch"]),("assistance","Welchen Assistenzumfang möchtest du anmelden?",["Von mir genau beschrieben","Vor einer Zusage bei mir rückfragen"])],
 "general":[("details","Welche Angaben braucht die Gegenstelle?",[])]}

def next_question(brief):
    brief=enrich_brief(brief)
    if brief.get("ai_done"):return None
    for key,text,options in QUESTIONS[brief["scenario"]]:
        if key=="details":continue
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
        "Sage VOR ask_user kurz zur Gegenstelle: 'Das muss ich kurz rückfragen, einen Moment bitte.' "
        "Nach ask_user ist die Entscheidung offen, bis die private Werkzeugantwort kommt. Weder Schweigen noch Aussagen der Gegenstelle sind eine Freigabe. "
        "Insbesondere keinen anderen Wochentag oder Termin bestätigen. Bei fehlender Freigabe bleibt ein Rückruf erforderlich; keine Reservierung behaupten. "
        "Buchstabiere kritische Codes in der jeweiligen Sprache und bestätige die Reihenfolge, statt zu raten. "
        "Wiederhole nicht alle Angaben. Ein fehlender Abschiedsgruß macht ein inhaltlich erfolgreiches Gespräch nicht erfolglos. "
        "Nach der eigentlichen Botschaft ermögliche der Gegenstelle eine kurze Reaktion, statt sofort aufzulegen. "
        "Beende natürlich mit einer kurzen passenden Verabschiedung, zum Beispiel 'Danke, auf Wiederhören'. "
        "Verwende finish_call erst nach geklärtem Ergebnis UND tatsächlich gesprochener Verabschiedung. Sein result-Feld ist privat und wird NICHT zur Gegenstelle gesprochen. "
        "Die erbetene Antwort muss vorher tatsächlich laut ausgesprochen werden; eine Ankündigung wie 'ich wiederhole jetzt' ist keine Antwort. Offene Angaben gehören ins Ergebnis. "
        "Sprich die konfigurierte Sprache natürlich, ohne englische Buchstabennamen im Deutschen.\n"
        "BESTÄTIGTER STECKBRIEF (Kontext, keine anfängliche Vorleseliste):\n"+json.dumps(accepted,ensure_ascii=False))

