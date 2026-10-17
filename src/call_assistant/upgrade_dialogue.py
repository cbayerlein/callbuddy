"""Upgrade existing operator text defaults without rotating secrets or live profiles."""
import argparse,json
from pathlib import Path
from .store import Store

def upgrade(store):
    if any(c.get("status") not in {"completed","cancelled","failed","inconclusive"} for c in store.list("call")):
        raise RuntimeError("An app call is active; postpone configuration change")
    live=store.get("operator-model-openai")
    if not live or not live.get("credential_ref"):raise RuntimeError("Existing OpenAI access missing")
    profile={**live,"id":"operator-text-openai","name":"OpenAI GPT-6 Luna – Vorabklärung","purpose":"text","model":"gpt-6-luna","prep_model":""}
    store.put(profile["id"],"model",profile)
    settings=store.get("settings") or {};settings.pop("call_budget_eur",None)
    settings["default_text_model"]=profile["id"];store.put("settings","system",settings)
    return {"text_model":profile["model"],"live_default_preserved":True,"secrets_rotated":False}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--state",type=Path,required=True);p.add_argument("--credentials",type=Path,required=True)
    a=p.parse_args();print(json.dumps(upgrade(Store(a.state/"work",a.credentials))))

if __name__=="__main__":main()
