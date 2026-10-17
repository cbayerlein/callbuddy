import asyncio,json
from unittest.mock import AsyncMock
from call_assistant.domain import enrich_brief,next_question
from call_assistant.telemetry import record_failure
from call_assistant.providers import GoogleSession
from call_assistant.store import Store
from call_assistant.upgrade_dialogue import upgrade

def test_preparation_channel_and_simple_message_contract():
    from call_assistant.domain import preparation_prompt
    prompt=preparation_prompt({'objective':'Bitte sag meiner Freundin, dass das Essen fertig ist.','answers':{}})
    assert 'channel is already decided: phone' in prompt
    assert 'Never ask whether to call' in prompt
    assert 'simple message with complete wording, done=true' in prompt
    assert 'Essen fertig' in prompt

def test_closure_requires_farewell_not_just_a_result():
    from call_assistant.domain import has_farewell,instructions
    assert not has_farewell('Das Essen ist fertig.')
    assert has_farewell('Danke, auf Wiederhören!')
    assert has_farewell('Thank you, goodbye.')
    assert 'kurze Reaktion' in instructions({})

def test_free_text_people_are_not_asked_twice():
    b=enrich_brief({'objective':'Ich möchte heute Abend einen Tisch für 2 Personen reservieren.','answers':{}})
    assert b['answers']['people']=='2 Personen'
    assert next_question(b)['id']=='time'
    b['answers']['time']='19 Uhr'
    assert next_question(b)['id']=='access'

def test_ai_done_and_unknown_general_task():
    assert next_question({'objective':'Paket suchen','answers':{},'ai_done':True}) is None
    assert next_question({'objective':'Paket suchen','answers':{}})['id']=='permissions'

def test_diagnostics_redact_and_survive_restart(tmp_path):
    store=Store(tmp_path/'work',tmp_path/'creds');ref=store.secret('synthetic-private-key')
    class Failure(Exception):code=1011
    d=record_failure(store,'call',Failure('credits are depleted key=synthetic-private-key'),'model_connect',{'credential_ref':ref,'provider':'google'})
    assert 'Guthaben' in d['message'] and 'synthetic-private-key' not in json.dumps(d)
    assert Store(store.root,store.credentials).events('call')[0]['diagnostic']['id']==d['id']

def test_google_connect_does_not_send_openai_schema(monkeypatch):
    from google import genai
    captured={}
    class Context:
        async def __aenter__(self):return object()
    class Live:
        def connect(self,**kw):captured.update(kw);return Context()
    class Client:
        def __init__(self,**kw):self.aio=type('Aio',(),{'live':Live()})()
    monkeypatch.setattr(genai,'Client',Client)
    s=GoogleSession({'model':'test','voice':'Kore','language':'de'},'fake','prompt',AsyncMock(),AsyncMock(),lambda:True)
    asyncio.run(s.connect())
    assert 'additionalProperties' not in json.dumps(captured)
    assert captured['config']['tools'][0]['function_declarations'][0]['parameters']['required']==['question','options']

def test_text_default_separate_and_preserves_live(tmp_path):
    store=Store(tmp_path/'work',tmp_path/'creds');ref=store.secret('fake')
    store.put('operator-model-openai','model',{'model':'gpt-realtime-2.1','credential_ref':ref})
    store.put('settings','system',{'default_model':'google-live','call_budget_eur':2})
    upgrade(store)
    assert store.get('settings')['default_model']=='google-live'
    assert store.get('settings')['default_text_model']=='operator-text-openai'
    assert 'call_budget_eur' not in store.get('settings')
