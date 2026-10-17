"""One real API-started model/SIP test against an allowlisted automatic peer."""
import argparse,base64,hashlib,json,time,wave
from pathlib import Path
import httpx,numpy as np
from fastapi.testclient import TestClient
from .api import create_app
from .store import Store
from .audio_acceptance import Pair

TERMINAL={'completed','cancelled','failed','inconclusive'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run-root',type=Path,required=True);p.add_argument('--provider',choices=['google','openai'],required=True);p.add_argument('--fixture',type=Path,required=True);p.add_argument('--code',type=int,required=True)
    p.add_argument('--expected-word')
    a=p.parse_args();a.run_root.mkdir(parents=True,exist_ok=False)
    (a.run_root/'retention.json').write_text(json.dumps({'owner':'gateway-owner','purpose':'Product API SIP/model hearing acceptance','createdAt':time.time(),'expiresAt':time.time()+30*86400,'preserveWhileReferenced':True,'deletionDisposition':'Delete after expiry only when unreferenced'}))
    credentials=Path('/var/lib/openclaw/state/credentials');main_store=Store(Path('/var/lib/openclaw/state/projects/call-assistant/work'),credentials)
    if any(c.get('status') not in TERMINAL for c in main_store.list('call')):raise RuntimeError('User call is active')
    original=json.loads((credentials/'archive/fonial-sip-before-claudia-20260703T132649Z.json').read_text())
    peer={'username':original['username'],'caller_id':original['username'],'domain':original['server_url'],'registrar':original['server_url'],'port':5060,'proxy':original['proxy_url'],'transport':'udp','credential_ref':'sipacceptancezoiper20261015'}
    runhash=hashlib.sha256(str(a.run_root).encode()).hexdigest()[:6];work=a.run_root.parent.parent
    # All three product socket names must fit Linux's 107-byte pathname limit.
    caller_root=work/('a'+runhash[:3]);peer_root=work/('cp-'+runhash)
    caller_root.mkdir(exist_ok=False);peer_root.mkdir(exist_ok=False)
    app=create_app(caller_root,credentials,live_enabled=True,test_endpoint={'dial_target':'1','expected_destination':'+492612039340'})
    store=app.state.store
    for id in ['operator-sip-fonial','operator-model-'+a.provider]:
        row=main_store.get(id);store.put(id,'sip' if row['profile_kind']=='sip' else 'model',row)
    store.put('settings','system',{'person':{'name':'Technischer Test','notes':'Keine echten Buchungen oder Zusagen.'},'recording':True})
    with wave.open(str(a.fixture),'rb') as f:
        assert f.getframerate()==16000 and f.getnchannels()==1 and f.getsampwidth()==2
        question=f.readframes(f.getnframes())
    pair=None;call=None;client=None;captured=bytearray();result={'passed':False,'provider':a.provider,'route':'fonial_internal_target_1','caller_root':str(caller_root),'peer_root':str(peer_root),'dial_attempts':0}
    try:
        pair=Pair(peer_root,[peer],[{'expected_caller':'+4926113493287','expected_user':'2','expires':time.time()+90}],credentials)
        pair.wait(lambda:(pair.peers[0][0]/'sip.sock').exists(),10)
        pair.wait(lambda:pair.rpc(0,command='inspect')['registered'],15)
        with TestClient(app) as client:
            assert client.post('/api/auth',json={'password':'synthetic-test-only-password'}).status_code==200
            b=client.post('/api/briefs',json={'number':'+492612039340','objective':'Technischer Hörtest. Begrüße die Gegenstelle kurz, höre ihren Prüfcode und wiederhole ihn einmal laut. Der Code wird ausschließlich im Gespräch mitgeteilt. Danach verabschiede dich kurz und beende mit finish_call. Keine sonstigen Aktionen.','answers':{'permissions':'Nur technischer Verbindungstest, keine Zusagen'},'model_profile':'operator-model-'+a.provider,'sip_profile':'operator-sip-fonial'}).json()
            r=client.post('/api/briefs/'+b['id']+'/accept');assert r.status_code==200,r.text
            r=client.post('/api/briefs/'+b['id']+'/calls',json={'request_id':'sip-audio-'+runhash,'accepted_revision':b['revision']});assert r.status_code==200,r.text
            call=r.json();result['call_id']=call['id'];result['dial_attempts']=1;cursor=0;connected_at=None;hangup=False;last_voice=time.monotonic()
            end=time.monotonic()+65
            while time.monotonic()<end:
                native=pair.rpc(0,command='read');captured.extend(base64.b64decode(native['rx']))
                pcm=np.frombuffer(base64.b64decode(native['rx']),dtype='<i2').astype(np.int32)
                if np.max(np.abs(pcm))>300:last_voice=time.monotonic()
                call=store.get(call['id'])
                if native['connected']:
                    connected_at=connected_at or time.monotonic()
                    if time.monotonic()-connected_at>1 and cursor<len(question) and native['buffer_frames']<50:
                        part=question[cursor:cursor+640*20];part=part.ljust((len(part)+639)//640*640,b'\x00')
                        if pair.rpc(0,command='write',pcm=base64.b64encode(part).decode())['accepted']:cursor+=len(part)
                if call.get('finished_at'):break
                if not hangup and cursor>=len(question) and native.get('received_voice_frames',0)>20 and time.monotonic()-last_voice>1.2:
                    events=store.events(call['id'])
                    complete=max((e['time'] for e in events if e['kind']=='turn_complete'),default=0)
                    spoken=max((e['time'] for e in events if e['kind']=='transcript' and e.get('speaker')=='assistant'),default=float('inf'))
                    if complete>=spoken:
                        pair.rpc(0,command='hangup');hangup=True
                time.sleep(0 if native.get('rx_queued',0)>1 else .01)
            if not call.get('finished_at'):
                client.post('/api/calls/'+call['id']+'/commands',json={'command_id':'stop-'+runhash,'kind':'hangup'})
                end=time.monotonic()+12
                while time.monotonic()<end:
                    pair.rpc(0,command='read');call=store.get(call['id'])
                    if call.get('finished_at'):break
                    time.sleep(.05)
            result['call']=call;result['events']=store.events(call['id']);result['peer']=pair.rpc(0,command='inspect')
    except Exception as exc:result['error']=type(exc).__name__+': '+str(exc)[:1000]
    finally:
        if pair:result['cleanup']=pair.close()
        path=a.run_root/'independent-peer-rx.wav'
        with wave.open(str(path),'wb') as w:w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(captured)
        result['independent_rx_samples']=len(captured)//2
        try:
            profile=main_store.get('operator-model-openai')
            with httpx.Client(timeout=40) as c, path.open('rb') as audio:
                r=c.post('https://api.openai.com/v1/audio/transcriptions',headers={'Authorization':'Bearer '+main_store.secret(ref=profile['credential_ref'])},data={'model':'gpt-4o-mini-transcribe','language':'de'},files={'file':('peer.wav',audio,'audio/wav')});r.raise_for_status();text=r.json()['text']
            result['blind_peer_transcript']=text
            words={47:'siebenundvierzig',63:'dreiundsechzig',82:'zweiundachtzig',59:'neunundfünfzig'}
            result['code_heard']=(a.expected_word.lower() in text.lower()) if a.expected_word else (str(a.code) in text or words[a.code] in text.lower().replace(' ',''))
            events=result.get('events',[])
            result['passed']=bool(result['code_heard'] and all(any(e.get('kind')=='transcript' and e.get('speaker')==side for e in events) for side in ['assistant','callee']) and result.get('call',{}).get('audio_state')=='ready' and result.get('call',{}).get('cleanup')=='registrar_ack_and_local_closure' and all(c.get('process_closed') and c.get('registration_removed') for c in result.get('cleanup',[])))
        except Exception as exc:result['evaluation_error']=type(exc).__name__
        (a.run_root/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        print(json.dumps({k:v for k,v in result.items() if k not in {'call','events','cleanup'}},ensure_ascii=False))
    if not result['passed']:raise SystemExit(2)

if __name__=='__main__':main()
