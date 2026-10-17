"""Configure the authorized Google account without resetting existing settings."""
import argparse
import asyncio
import json
from pathlib import Path

from .models import ModelProfile
from .providers import check_account
from .store import Store


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',type=Path,required=True)
    parser.add_argument('--credentials',type=Path,required=True)
    args=parser.parse_args()
    source=json.loads((args.credentials/'google-gemini.json').read_text())
    profile=ModelProfile(name='Google Gemini Live – Deutsch',provider='google',
        model='gemini-3.8-live',prep_model='gemini-3.8-flash',voice='Kore',language='de',
        maximum_token_eur_per_million=100,pricing_confirmed=True)
    checks={}
    for field in ('model','prep_model'):
        checks[field]=asyncio.run(check_account(profile.model_dump()|{'model':getattr(profile,field)},source['api_key']))
    if not all(r['ready'] for r in checks.values()):
        print(json.dumps({'configured':False,'checks':checks}));raise SystemExit(2)
    store=Store(args.state/'work',args.credentials)
    id='operator-model-google';old=store.get(id)
    ref=old.get('credential_ref') if old else None
    if not ref or store.secret(ref=ref)!=source['api_key']:ref=store.secret(source['api_key'])
    store.put(id,'model',profile.model_dump(exclude={'api_key'})|{'id':id,'profile_kind':'model','credential_ref':ref})
    sip=store.get('operator-sip-fonial')
    if sip:
        account=json.loads((args.credentials/'fonial-sip.json').read_text())
        sip['phone_number']=account['phone_number'];store.put(sip['id'],'sip',sip)
    print(json.dumps({'configured':True,'checks':checks,'default_changed':False,
                      'credentials_exposed':False,'audio_sessions':0,'pricing_confirmed':True}))


if __name__=='__main__':main()
