"""Explicit operator provisioning; secret values never enter arguments or output."""
import argparse
import json
import sqlite3
from pathlib import Path

from .models import ModelProfile, Settings, SipProfile
from .store import Store


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--password-file',type=Path,required=True)
    parser.add_argument('--state',type=Path,required=True)
    parser.add_argument('--credentials',type=Path,required=True)
    parser.add_argument('--backup',type=Path,required=True)
    args=parser.parse_args()
    password=args.password_file.read_text().rstrip('\r\n')
    if not password or len(password)>500:raise ValueError('Invalid operator password')
    sip_source=json.loads((args.credentials/'fonial-sip.json').read_text())
    openai=json.loads((args.credentials/'openai.json').read_text())
    sip=SipProfile(name='Fonial – Claudia',username=sip_source['username'],
        domain=sip_source['server_url'],registrar=sip_source['server_url'],
        proxy=sip_source['proxy_url'],caller_id=sip_source['username'],phone_number=sip_source.get('phone_number',''),
        phone_eur_per_minute=0.119,tariff_scope='de_standard',pricing_confirmed=True)
    model=ModelProfile(name='OpenAI Realtime – Deutsch',provider='openai',
        model='gpt-realtime-2.1',prep_model='gpt-6-luna',voice='marin',language='de',
        eagerness='high',maximum_token_eur_per_million=100,pricing_confirmed=True)
    store=Store(args.state/'work',args.credentials)
    args.backup.parent.mkdir(parents=True,exist_ok=True)
    if args.backup.exists():raise FileExistsError('Preserve previous backup; choose a fresh path')
    with sqlite3.connect(store.root/'app.sqlite3') as source,sqlite3.connect(args.backup) as target:
        source.backup(target)
    args.backup.chmod(0o600)
    for id,kind,value,secret in [('operator-sip-fonial','sip',sip,sip_source['password']),
                               ('operator-model-openai','model',model,openai['api_key'])]:
        old=store.get(id)
        ref=old.get('credential_ref') if old else None
        if not ref or store.secret(ref=ref)!=secret:ref=store.secret(secret)
        store.put(id,kind,value.model_dump(exclude={'password','api_key'})|{
            'id':id,'profile_kind':kind,'credential_ref':ref})
    settings=Settings.model_validate(store.get('settings') or {})
    settings.person.name='Christian Bayerlein'
    settings.person.callback=sip_source.get('phone_number','')
    settings.person.notes='Die Assistenz heißt Claudia und ruft im Auftrag von Christian Bayerlein an. Unbekannte Angaben nicht erfinden; Entscheidungen bei Chris rückfragen.'
    settings.default_sip='operator-sip-fonial';settings.default_model='operator-model-openai'
    settings.language='de';settings.model_selection='manual'
    store.put('settings','system',settings.model_dump())
    store.set_password(password)
    print(json.dumps({'configured':True,'sip_credentials':True,'openai_credentials':True,
                      'sip_tariff_confirmed':True,'tariff_scope':'de_standard','live_call_qualified':False}))


if __name__=='__main__':main()
