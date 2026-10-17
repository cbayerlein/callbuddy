"""Durable, credential-redacted provider diagnostics, available without exports."""
import re,time,secrets

def record_failure(store,call_id,exc,phase,profile=None):
    profile=profile or {}
    detail=str(exc)
    response=getattr(exc,"response",None)
    if response is not None:
        try:
            error=response.json().get("error",{})
            if isinstance(error,dict):detail+=" "+str({k:error.get(k) for k in ("type","code","message","status")})
        except (ValueError,AttributeError):pass
    ref=profile.get("credential_ref")
    if ref:
        try:detail=detail.replace(store.secret(ref=ref),"[REDACTED]")
        except (OSError,ValueError,KeyError):pass
    detail=re.sub(r"(?i)(?:Bearer\s+|key=|api_key[\s:=]+)[^\s\"'&,}]+","[REDACTED]",detail)
    detail=re.sub(r"(?:AIza|sk-)[A-Za-z0-9_-]+","[REDACTED]",detail)[:2500]
    status=getattr(exc,"status_code",None) or getattr(exc,"code",None)
    if response is not None:status=getattr(response,"status_code",status)
    if any(term in detail.lower() for term in ("credits are depleted","insufficient_quota","billing")):
        message="Beim Modellanbieter ist das Guthaben aufgebraucht oder die Abrechnung nicht freigeschaltet. Bitte Anbieter-Guthaben prüfen oder ein anderes Modell wählen."
    elif status in (401,403):message="Der Modellanbieter hat den Zugang abgelehnt. Bitte Schlüssel und Projektberechtigung prüfen."
    elif status==404:message="Das ausgewählte Modell ist unter diesem API-Zugang nicht verfügbar. Bitte Modell-ID und API prüfen."
    elif status==429:message="Der Modellanbieter meldet ein Kontingent- oder Ratenlimit. Bitte Anbieter-Konto prüfen."
    elif status in (400,1007,1008):message="Der Modellanbieter hat die Sitzungskonfiguration abgelehnt. Die technische Diagnose ist gespeichert."
    elif phase=="media_connect":message="Die Telefonverbindung stand, aber der Audiokanal konnte nicht aktiviert werden. Das Gespräch wurde beendet; die Medien-Diagnose ist gespeichert."
    elif phase=="model_connect":message="Die Sprachmodell-Verbindung konnte nicht aufgebaut werden. Es wurde noch keine Telefonnummer gewählt."
    else:message="Das Gespräch wurde wegen eines technischen Fehlers beendet. Die Diagnose ist gespeichert; es wird nicht automatisch erneut angerufen."
    result={"id":secrets.token_hex(8),"time":time.time(),"phase":phase,"provider":profile.get("provider"),"model":profile.get("model"),"error_type":type(exc).__name__,"status_code":status if isinstance(status,(str,int)) else None,"detail":detail,"message":message}
    store.event(call_id,"diagnostic",diagnostic=result)
    return result
