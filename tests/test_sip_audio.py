import ast,asyncio,json,secrets,subprocess,sys,time
from pathlib import Path
from call_assistant.audio_acceptance import score,tone
from call_assistant.telemetry import record_failure
from call_assistant.store import Store

def test_frequency_check_rejects_silence_and_wrong_direction():
    assert score(tone(440),440)['passed']
    assert not score(tone(660),440)['passed']
    assert not score(bytes(32000),440)['passed']

def test_swig_media_callback_keeps_parent_alive():
    import call_assistant.sip as sip
    tree=ast.parse(Path(sip.__file__).read_text())
    callback=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='onCallMediaState')
    assert any(isinstance(n,ast.Assign) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute) and n.value.func.attr=='getInfo' for n in ast.walk(callback))
    assert not any(isinstance(n,ast.Attribute) and n.attr=='media' and isinstance(n.value,ast.Call) for n in ast.walk(callback))

def test_audio_failure_is_distinct_from_provider_failure(tmp_path):
    store=Store(tmp_path/'work',tmp_path/'credentials')
    d=record_failure(store,'call',RuntimeError('no media'),'media_connect')
    assert 'Audiokanal' in d['message'] and d['phase']=='media_connect'

def test_real_local_product_audio_in_both_directions():
    root=Path('/var/lib/openclaw/state/projects/call-assistant/work/media-runs')/('pytest-sip-'+secrets.token_hex(4))
    r=subprocess.run([sys.executable,'-m','call_assistant.audio_acceptance','--run-root',str(root)],capture_output=True,text=True,timeout=40)
    assert r.returncode==0,r.stdout[-3000:]+r.stderr[-1000:]
    result=json.loads((root/'result.json').read_text())
    assert all(d['passed'] for d in result['directions'])
    assert all(c['process_closed'] and c['audio_dropped']==0 for c in result['cleanup'])

def test_worker_missing_audio_fails_instead_of_claiming_success(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from call_assistant import worker
    store=Store(tmp_path/'work',tmp_path/'creds')
    profile={'provider':'google','credential_ref':store.secret('fake')}
    store.put('x','call',{'id':'x','status':'preparing','destination':'+492611234567'})
    root=store.root/'calls/x';root.mkdir(parents=True)
    class Clock:
        n=0
        def monotonic(self):self.n+=10;return self.n
        def time(self):return time.time()
    class Session:
        rate=16000
        def __init__(self,*a):self.ready=asyncio.Event()
        async def connect(self):self.ready.set()
        async def receive(self):await asyncio.Future()
        async def close(self):pass
    def native(*a):return {'registered':True,'connected':True,'disconnected':False,'media_ready':False,'received_frames':0,'sent_frames':0,'audio_dropped':0}
    monkeypatch.setitem(worker.ADAPTERS,'google',Session)
    monkeypatch.setattr(worker,'rpc',native);monkeypatch.setattr(worker,'time',Clock())
    asyncio.run(worker.run({'root':str(tmp_path),'credential_root':str(tmp_path/'creds'),'call_id':'x','model':profile,'sip':{'phone_eur_per_minute':0},'instructions':'test'}))
    call=store.get('x')
    assert call['status']=='inconclusive' and call['audio_state']=='failed'
    assert call['diagnostic']['phase']=='media_connect' and 'Audiokanal' in call['result']
    assert (root/'model-closed.json').exists()

def test_ringing_drains_early_media_and_retains_first_connected_frame():
    from call_assistant.worker import wait_connected
    async def check():
        requests=[];states=[{'connected':False,'disconnected':False,'rx_queued':20},{'connected':True,'disconnected':False,'rx':'first-voice-frame'}]
        async def native(request):requests.append(request['command']);return states.pop(0)
        receiver=asyncio.create_task(asyncio.sleep(10))
        try:
            result=await wait_connected(native,asyncio.Event(),receiver)
            assert result['rx']=='first-voice-frame' and requests==['read','read']
        finally:receiver.cancel();await asyncio.gather(receiver,return_exceptions=True)
    asyncio.run(check())

def test_unspoken_finish_is_removed_before_audio_only_correction():
    from call_assistant.providers import OpenAISession
    async def check():
        sent=[]
        session=OpenAISession({},'fake','',None,None,lambda:True)
        async def send(event):sent.append(event)
        session.send=send
        await session.reject_unspoken_finish('item-unconfirmed','call-test','The result is not confirmed. Speak the original answer.')
        assert sent[0]=={'type':'conversation.item.delete','item_id':'item-unconfirmed'}
        assert sent[1]['item']['role']=='system'
        assert sent[2]=={'type':'response.create','response':{'tool_choice':'none'}}
    asyncio.run(check())

def test_first_openai_turn_can_ask_user_but_cannot_finish_silently():
    from call_assistant.providers import OpenAISession
    async def check():
        sent=[];session=OpenAISession({},'fake','',None,None,lambda:True)
        async def send(event):sent.append(event)
        session.send=send
        await session.reply()
        assert [t['name'] for t in sent[0]['response']['tools']]==['ask_user']
        session.has_audio_output=True;await session.reply()
        assert sent[1]=={'type':'response.create'}
    asyncio.run(check())

def test_pending_decision_blocks_audio_and_finish_until_timeout(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from call_assistant import worker
    import base64
    store=Store(tmp_path/'work',tmp_path/'creds')
    profile={'provider':'google','credential_ref':store.secret('fake')}
    store.put('x','call',{'id':'x','status':'preparing','destination':'+492611234567'})
    (store.root/'calls/x').mkdir(parents=True)
    sent=[];tick=[0]
    def clock():tick[0]+=1;return tick[0]
    class Session:
        rate=16000
        def __init__(self,profile,key,prompt,event,audio,admit):self.ready=asyncio.Event();self.event=event;self.audio=audio
        async def connect(self):self.ready.set()
        async def receive(self):
            await asyncio.sleep(.05)
            await self.event('tool',name='ask_user',id='choice',args={'question':'Mittwoch statt Freitag?','options':['Ja','Nein']})
            await self.audio(bytes(1280),24000)
            await self.event('transcript',speaker='assistant',text='Mittwoch passt',source='model_output')
            await self.event('tool',name='finish_call',id='finish',args={'result':'Mittwoch bestätigt'})
            await self.event('turn_complete')
            await asyncio.Future()
        async def steer(self,text):pass
        async def close(self):pass
    def native(path,request):
        sent.append(request['command'])
        return {'registered':True,'connected':True,'disconnected':False,'media_ready':True,'received_frames':1,'sent_frames':1,'audio_dropped':0,'buffer_frames':0,'rx':base64.b64encode(bytes(640)).decode(),'tx':base64.b64encode(bytes(640)).decode()}
    async def input(self,pcm):pass
    Session.input=input
    monkeypatch.setitem(worker.ADAPTERS,'google',Session)
    monkeypatch.setattr(worker,'rpc',native)
    monkeypatch.setattr(worker,'time',SimpleNamespace(time=clock,monotonic=time.monotonic))
    asyncio.run(worker.run({'root':str(tmp_path),'credential_root':str(tmp_path/'creds'),'call_id':'x','model':profile,'sip':{'phone_eur_per_minute':0},'instructions':'test'}))
    call=store.get('x')
    assert call['status']=='inconclusive' and 'Keine Zusage' in call['result']
    assert 'write' not in sent and 'interrupt' in sent
    assert any(e['kind']=='withheld_transcript' for e in store.events('x'))
    assert not any(e['kind']=='transcript' for e in store.events('x'))

def test_worker_repairs_missing_farewell_before_finishing(tmp_path,monkeypatch):
    from call_assistant import worker
    import base64
    store=Store(tmp_path/'work',tmp_path/'creds')
    profile={'provider':'google','credential_ref':store.secret('fake')}
    store.put('x','call',{'id':'x','status':'preparing','destination':'+492611234567'})
    (store.root/'calls/x').mkdir(parents=True)
    corrections=[]
    class Session:
        rate=16000
        def __init__(self,profile,key,prompt,event,audio,admit):self.ready=asyncio.Event();self.event=event;self.audio=audio
        async def connect(self):self.ready.set()
        async def receive(self):
            await asyncio.sleep(.05)
            await self.audio(bytes(1280),24000)
            await self.event('transcript',speaker='assistant',text='Das Essen ist fertig.',source='model_output')
            await self.event('tool',name='finish_call',id='finish',args={'result':'Botschaft übermittelt'})
            await self.event('turn_complete')
            await asyncio.Future()
        async def answer(self,id,value,**kwargs):
            corrections.append(value)
            await self.audio(bytes(1280),24000)
            await self.event('transcript',speaker='assistant',text=' Danke, auf Wiederhören.',source='model_output')
            await self.event('turn_complete')
        async def input(self,pcm):pass
        async def close(self):pass
    def native(path,request):
        return {'accepted':True,'registered':True,'connected':True,'disconnected':False,'media_ready':True,'received_frames':1,'sent_frames':1,'audio_dropped':0,'buffer_frames':0,'rx':base64.b64encode(bytes(640)).decode(),'tx':base64.b64encode(bytes(640)).decode()}
    monkeypatch.setitem(worker.ADAPTERS,'google',Session);monkeypatch.setattr(worker,'rpc',native)
    asyncio.run(worker.run({'root':str(tmp_path),'credential_root':str(tmp_path/'creds'),'call_id':'x','model':profile,'sip':{'phone_eur_per_minute':0},'instructions':'test'}))
    assert len(corrections)==1 and 'Verabschiedung fehlt' in corrections[0]
    assert store.get('x')['status']=='completed'
    assert store.get('x')['result']=='Botschaft übermittelt'
