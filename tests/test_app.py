import asyncio,json,time
from pathlib import Path
from fastapi.testclient import TestClient
import pytest
from call_assistant.api import create_app
from call_assistant.store import Store
from call_assistant.models import SipProfile,ModelProfile
from call_assistant.domain import brief_context,instructions
from call_assistant.providers import OpenAISession,GoogleSession,ADAPTERS
from call_assistant.worker import Budget

@pytest.fixture
def client(tmp_path):
    app=create_app(tmp_path,tmp_path/"credentials",live_enabled=False)
    with TestClient(app) as c:
        assert c.post('/api/auth',json={'password':'test-only-password-long'}).status_code==200
        yield c

def prepare(c,scenario='restaurant'):
    b=c.post('/api/briefs',json={'number':'+492611234567','objective':'Tisch für zwei reservieren','scenario':scenario}).json()
    for _ in range(10):
        b=c.get('/api/briefs/'+b['id']).json()
        if not b['question']:break
        q=b['question'];assert c.post(f"/api/briefs/{b['id']}/answers",json={'question_id':q['id'],'answer':'Noch unbekannt'}).status_code==200
    return c.post(f"/api/briefs/{b['id']}/accept").json()

def test_auth_origin_and_restart_persistence(client):
    assert client.get('/api/settings').status_code==200
    assert client.put('/api/settings',headers={'Origin':'https://evil.example'},json={}).status_code==403
    client.put('/api/settings',json={'person':{'name':'Testperson'}})
    s=client.app.state.store
    again=Store(s.root,s.credentials)
    assert again.get('settings')['person']['name']=='Testperson'
    client.delete('/api/auth');assert client.get('/api/settings').status_code==401

def test_exports_are_authenticated_and_audio_requires_real_file(client):
    b=prepare(client)
    c=client.post('/api/briefs/'+b['id']+'/calls',json={'request_id':'export-test-123','accepted_revision':b['revision'],'mode':'demo','budget_eur':2}).json()
    path='/api/calls/'+c['id']
    export=client.get(path+'/transcript')
    assert export.status_code==200 and 'attachment' in export.headers['content-disposition']
    assert export.json()['call']['mode']=='demo'
    assert client.get(path+'/audio').status_code==409
    client.post(path+'/commands',json={'command_id':'export-hangup-123','kind':'hangup'})
    assert client.get(path+'/audio').status_code==404
    client.delete('/api/auth')
    assert client.get(path+'/transcript').status_code==401

def test_early_demo_hangup_cannot_be_resurrected(client):
    b=prepare(client)
    c=client.post('/api/briefs/'+b['id']+'/calls',json={'request_id':'early-hangup-123','accepted_revision':b['revision'],'mode':'demo','budget_eur':2}).json()
    path='/api/calls/'+c['id']
    client.post(path+'/commands',json={'command_id':'early-stop-123','kind':'hangup'})
    time.sleep(.7)
    assert client.get(path).json()['status']=='cancelled'

def test_secrets_are_private_and_rotation_immutable(client):
    body={'name':'Test','provider':'openai','model':'gpt-realtime-2.1','voice':'marin','api_key':'synthetic-test-key'}
    p=client.post('/api/profiles/model',json=body).json();assert 'api_key' not in p and 'credential_ref' not in p
    store=client.app.state.store;ref=store.get(p['id'])['credential_ref']
    assert 'synthetic-test-key' not in json.dumps(client.get('/api/profiles').json())
    assert not (store.credentials/f'call-assistant-{ref}.json').stat().st_mode&0o077
    client.put('/api/profiles/model/'+p['id'],json={**body,'api_key':'replacement-test-key'})
    assert store.get(p['id'])['credential_ref']!=ref
    assert store.secret(ref=ref)=='synthetic-test-key'

@pytest.mark.parametrize('transport',['udp','tcp','tls'])
def test_sip_profiles_not_fonial_hardcoded(client,transport):
    p=client.post('/api/profiles/sip',json={'name':'Other provider','username':'u','domain':'sip.example.org','registrar':'registrar.example.org','transport':transport,'password':'synthetic-password'}).json()
    assert p['transport']==transport and p['registrar']=='registrar.example.org'
    r=client.post('/api/profiles/'+p['id']+'/check').json();assert not r['ready'] and 'Live' in r['detail']

def test_memory_requires_confirmation_and_selection(client):
    a=client.post('/api/memory',json={'text':'Dauerhafte Vorliebe','confirmed':True}).json()
    b=client.post('/api/memory',json={'text':'Unbestätigte Vermutung'}).json()
    draft={'objective':'Test','number':'+492611234567','answers':{},'memory_ids':[a['id'],b['id']]}
    ctx=brief_context(draft,{},client.get('/api/memory').json());assert ctx['memories']==['Dauerhafte Vorliebe']
    assert not brief_context({**draft,'memory_ids':[]},{},client.get('/api/memory').json())['memories']

def test_preparation_unknowns_revision_and_stale_answer(client):
    b=prepare(client);assert b['accepted']
    assert all(v=='Noch unbekannt' for v in b['accepted_context']['answers'].values())
    assert client.post(f"/api/briefs/{b['id']}/answers",json={'question_id':'people','answer':'2'}).status_code==409
    data={k:v for k,v in b.items() if k not in {'id','revision','accepted','accepted_context'}}
    new=client.put('/api/briefs/'+b['id'],json=data).json();assert not new['accepted'] and new['revision']==b['revision']+1

def test_demo_idempotency_no_live_effects_and_private_decision(client):
    b=prepare(client);body={'request_id':'test-start-123456','accepted_revision':b['revision'],'mode':'demo','budget_eur':2}
    call=client.post('/api/briefs/'+b['id']+'/calls',json=body).json()
    duplicate=client.post('/api/briefs/'+b['id']+'/calls',json=body).json();assert duplicate['id']==call['id']
    assert call['mode']=='demo' and call['estimated_eur']==0
    for _ in range(50):
        time.sleep(.05);call=client.get('/api/calls/'+call['id']).json()
        if call.get('decision'):break
    d=call['decision'];assert d
    r=client.post(f"/api/calls/{call['id']}/decisions/{d['id']}/answer",json={'answer':'Nein'});assert r.status_code==200
    assert client.post(f"/api/calls/{call['id']}/decisions/{d['id']}/answer",json={'answer':'Ja'}).status_code==409
    assert client.get('/api/calls/'+call['id']).json()['status']=='completed'
    assert not client.get('/api/memory').json()

def test_live_cannot_dispatch_without_explicit_activation(client):
    b=prepare(client)
    r=client.post('/api/briefs/'+b['id']+'/calls',json={'request_id':'blocked-live-request','accepted_revision':b['revision'],'mode':'live','budget_eur':2})
    assert r.status_code==409 and 'gesperrt' in r.json()['detail']
    assert not client.get('/api/calls').json()

def test_demo_controls_and_duplicate_command(client):
    b=prepare(client);c=client.post('/api/briefs/'+b['id']+'/calls',json={'request_id':'controls-test-123','accepted_revision':b['revision'],'mode':'demo','budget_eur':2}).json()
    body={'command_id':'pause-test-123','kind':'pause'}
    a=client.post('/api/calls/'+c['id']+'/commands',json=body).json()
    assert client.post('/api/calls/'+c['id']+'/commands',json=body).json()==a
    assert client.get('/api/calls/'+c['id']).json()['paused']
    assert client.post('/api/calls/'+c['id']+'/commands',json={'command_id':'bad-dtmf-command','kind':'dtmf','text':'x'}).status_code==409
    client.post('/api/calls/'+c['id']+'/commands',json={'command_id':'hangup-test-command','kind':'hangup'})
    assert client.get('/api/calls/'+c['id']).json()['status']=='cancelled'

def test_research_is_candidate_only_and_requires_evidence(client):
    assert client.post('/api/research',json={'name':'bad'}).status_code==422
    r=client.post('/api/research',json={'name':'candidate','source_hash':'a'*64,'evidence':['offline.xml']}).json()
    assert r['status']=='candidate'
    r=client.post('/api/research/'+r['id']+'/approve').json();assert r['status']=='approved'
    assert not r['human_listening_approved']

def test_actual_runtime_reference_role_instructions():
    text=instructions({'unknowns':['patient status']})
    assert 'Unbekannt bleibt unbekannt' in text and 'nicht die Gegenstelle' in text
    assert 'ask_user' in text

def test_native_cancellation_prevents_later_dial_without_network():
    from call_assistant.sip import Endpoint
    endpoint=Endpoint.__new__(Endpoint)
    endpoint.pj=object();endpoint.registered=True;endpoint.calls=0;endpoint.dial_blocked=True
    with pytest.raises(RuntimeError,match='cancellation'):
        endpoint.command({'command':'dial','number':'+492611234567'})

@pytest.mark.parametrize('scenario',['restaurant','doctor','airline','general'])
def test_all_preparations_require_explicit_acceptance(client,scenario):
    b=prepare(client,scenario)
    assert b['accepted'] and b['accepted_context']['permissions']
    assert b['scenario']==scenario

def test_two_adapter_contracts_no_network_on_construction():
    for cls in ADAPTERS.values():
        s=cls({'language':'de'},'fake','prompt',None,None,None)
        assert s.rate in (16000,24000)
        assert all(hasattr(s,x) for x in ('connect','input','answer','steer','interrupt','receive','close'))

def test_openai_native_pause_prevents_response_dispatch():
    async def check():
        sent=[];s=OpenAISession({},'fake','prompt',None,None,lambda:False)
        async def send(value):sent.append(value)
        s.send=send;await s.reply();assert not sent
    asyncio.run(check())

def test_budget_rejects_missing_usage_and_duplicate_billing():
    b=Budget({'budget_eur':1,'model':{'maximum_token_eur_per_million':100},'sip':{'phone_eur_per_minute':0},'instructions':'x'})
    b.admit();b.usage({'total_tokens':100},'r',False);b.usage({'total_tokens':100},'r',False);assert b.used==pytest.approx(.01)
    with pytest.raises(ValueError):b.usage(None,'bad',False)
    b.instruction_bytes=100000
    with pytest.raises(PermissionError):b.admit()

def test_google_schema_and_function_response_contract():
    from google.genai import types
    config=types.LiveConnectConfig(response_modalities=['AUDIO'],max_output_tokens=512,input_audio_transcription={},output_audio_transcription={},tools=[{'function_declarations':[{'name':'ask_user','parameters':{'type':'object','properties':{'question':{'type':'string'}}}}]}])
    assert config.max_output_tokens==512
    assert types.FunctionResponse(id='q',name='ask_user',response={'answer':'Nein'}).id=='q'

def test_real_local_webrtc_demo_audio_and_close(tmp_path):
    from aiortc import RTCPeerConnection,RTCSessionDescription,RTCConfiguration
    from call_assistant.runtime import Runtime
    async def check():
        store=Store(tmp_path.parent/'rtc'/'work',tmp_path.parent/'rtc'/'credentials')
        call=store.add('call',{'status':'connected','mode':'demo','takeover':False})
        runtime=Runtime(store)
        browser=RTCPeerConnection(RTCConfiguration(iceServers=[]))
        received=asyncio.Future()
        @browser.on('track')
        def track(audio):
            if not received.done():received.set_result(audio)
        try:
            browser.addTransceiver('audio',direction='recvonly')
            await browser.setLocalDescription(await browser.createOffer())
            answer=await runtime.rtc(call['id'],{'sdp':browser.localDescription.sdp,'type':'offer'})
            assert answer['audio_source']=='demo_silence'
            await browser.setRemoteDescription(RTCSessionDescription(sdp=answer['sdp'],type=answer['type']))
            track=await asyncio.wait_for(received,5)
            frame=await asyncio.wait_for(track.recv(),5)
            assert frame.sample_rate==48000 and frame.samples>0
        finally:
            await browser.close();await runtime.close_browser_peers()
        assert all(p.connectionState=='closed' for p in runtime.peers.values())
    asyncio.run(check())
