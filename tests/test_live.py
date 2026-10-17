import asyncio,base64,json
from unittest.mock import AsyncMock
from call_assistant.live import LiveSession
from call_assistant.providers import adapter_class,OpenAISession

PROFILE={'provider':'openai','model':'gpt-live-1','voice':'marin','language':'de','backend_model':'gpt-6-luna'}

class Socket:
    def __init__(self,events=()):self.events=list(events);self.sent=[];self.closed=False
    async def send(self,value):self.sent.append(json.loads(value))
    def __aiter__(self):return self
    async def __anext__(self):
        if not self.events:raise StopAsyncIteration
        return json.dumps(self.events.pop(0))
    async def close(self):self.closed=True

def test_live_routes_separately_and_never_commits_audio(monkeypatch):
    async def check():
        socket=Socket();connection={}
        async def connect(url,**kw):connection['url']=url;return socket
        monkeypatch.setattr('call_assistant.live.websockets.connect',connect)
        s=LiveSession(PROFILE,'fake','BESTÄTIGTER STECKBRIEF: test',AsyncMock(),AsyncMock(),lambda:True)
        assert adapter_class(PROFILE) is LiveSession
        assert adapter_class({**PROFILE,'model':'gpt-realtime-2.1'}) is OpenAISession
        await s.connect();await s.input(bytes(960));await s.steer('Private instruction')
        assert connection['url']=='wss://api.openai.com/v1/live/sessions'
        config=socket.sent[0]['session']
        assert socket.sent[0]['type']=='session.start'
        assert config['model']=='gpt-live-1' and config['delegation']['responses']['model']=='gpt-6-luna'
        assert config['delegation']['responses']['parallel_tool_calls'] is False
        assert 'turn_detection' not in json.dumps(config)
        assert socket.sent[1]['type']=='session.input_audio.append'
        assert socket.sent[2]['delegation_id'] is None
    asyncio.run(check())

def test_live_nested_tools_transcripts_usage_and_finalization():
    async def check():
        events=AsyncMock();audio=AsyncMock()
        s=LiveSession(PROFILE,'fake','',events,audio,lambda:True)
        s.ws=Socket([
            {'type':'session.started','session':{'id':'test'}},
            {'type':'session.output_audio.delta','delta':base64.b64encode(b'\x01\x02'*480).decode()},
            {'type':'session.output_audio.delta','delta':base64.b64encode(bytes(960)).decode()},
            {'type':'session.output_transcript.delta','delta':'Hallo','start_ms':1,'end_ms':2},
            {'type':'response.event','event':{'type':'response.output_item.done','item':{'type':'function_call','call_id':'tool','name':'ask_user','arguments':'{"question":"Mittwoch?","options":[]}'}}},
            {'type':'response.event','event':{'type':'response.completed','response':{'id':'r','usage':{'total_tokens':20}}}},
            {'type':'session.usage.updated','usage':{'seconds':12}},
            {'type':'session.closed','usage':{'seconds':15}},
        ])
        await s.receive()
        assert s.ready.is_set() and s.finalized
        assert audio.await_count==2  # Preserve normal zero-only pauses too.
        kinds=[c.args[0] for c in events.await_args_list]
        assert 'tool' in kinds and 'usage' in kinds and 'turn_complete' not in kinds
        await s.answer('tool','No, only Friday')
        assert [e['type'] for e in s.ws.sent]==['response.item.create','response.create']
        try:await s.answer('tool','duplicate')
        except RuntimeError:pass
        else:assert False,'Duplicate private answer must not replay'
        await s.close();assert s.ws.closed
    asyncio.run(check())

def test_live_close_keeps_receiver_until_terminal_ack():
    async def check():
        s=LiveSession(PROFILE,'fake','',AsyncMock(),AsyncMock(),lambda:True);s.ws=Socket();s.ready.set()
        async def send(value):
            s.ws.sent.append(json.loads(value))
            if json.loads(value)['type']=='session.close':s.closed.set();s.finalized=True
        s.ws.send=send
        await s.close()
        assert s.finalized and s.ws.closed and s.ws.sent==[{'type':'session.close'}]
    asyncio.run(check())

def test_live_profile_upgrade_preserves_history_and_credentials(tmp_path):
    from call_assistant.store import Store
    from call_assistant.upgrade_live import upgrade
    store=Store(tmp_path/'work',tmp_path/'creds')
    store.put('operator-model-openai','model',{'id':'operator-model-openai','model':'gpt-realtime-2.1','credential_ref':'unchanged'})
    store.put('settings','system',{'default_text_model':'text-original'})
    store.put('past','call',{'id':'past','status':'completed','model_snapshot':{'model':'gpt-realtime-2.1'}})
    result=upgrade(store)
    assert result['model']=='gpt-live-1'
    assert store.get('operator-model-openai')['credential_ref']=='unchanged'
    assert store.get('operator-model-openai-realtime')['model']=='gpt-realtime-2.1'
    assert store.get('settings')['default_text_model']=='text-original'
    assert store.get('past')['model_snapshot']['model']=='gpt-realtime-2.1'
    upgrade(store)  # Does not overwrite the retained original baseline.
    assert store.get('operator-model-openai-realtime')['model']=='gpt-realtime-2.1'

def test_smoke_failure_after_readiness_cannot_report_success(tmp_path,monkeypatch):
    from call_assistant import live_smoke
    class Store:
        def __init__(self,*args):pass
        def get(self,id):return {**PROFILE,'credential_ref':'fake'}
        def secret(self,**kwargs):return 'fake'
    class Session:
        def __init__(self,*args):self.ready=asyncio.Event();self.finalized=False
        async def connect(self):self.ready.set()
        async def receive(self):await asyncio.Future()
        async def input(self,pcm):pass
        async def close(self):self.finalized=True
    async def immediate(*args):pass
    monkeypatch.setattr(live_smoke,'Store',Store);monkeypatch.setattr(live_smoke,'LiveSession',Session)
    monkeypatch.setattr(live_smoke.asyncio,'sleep',immediate)
    path=tmp_path/'result.json'
    code=asyncio.run(live_smoke.check(tmp_path,tmp_path,path,exercise_delegation=True))
    result=json.loads(path.read_text())
    assert code==1 and result['state']=='failed'
    assert result['finalized'] and result['error_type']=='RuntimeError'
