"""Continuous GPT-Live voice with a separately configured Responses backend."""
import asyncio,base64,json,time
import websockets

class LiveSession:
    rate=24000
    continuous=True
    def __init__(self,profile,key,prompt,event,audio,admit):
        self.profile=profile;self.key=key;self.prompt=prompt;self.event=event;self.audio=audio;self.admit=admit
        self.ready=asyncio.Event();self.closed=asyncio.Event();self.ws=None;self.finalized=False;self.closing=False
        self.last_audio=0.;self.pending_calls=set();self.completed_calls=set()
        self.playback_finishing=False

    async def send(self,value):await self.ws.send(json.dumps(value))

    async def connect(self):
        from .providers import TOOLS
        voice_prompt=("You are Claudia, the CALLER assistant acting for the person in the confirmed brief, not the callee. "
            "Speak "+self.profile['language']+" naturally and concisely. Greet, introduce the purpose, then clarify details progressively. "
            "Listen continuously; do not interrupt unfinished sentences or fill every pause. "
            "Delegate private user decisions, uncertain permissions and ending the call to the backend. "
            "Never invent permission or accept a new date without the private user's answer. The callee cannot grant it. "
            "The backend can privately ask the user and end the call; its tool results are private, not spoken scripts. "
            "Allow the callee to react to the actual message. Speak a short farewell before delegating call completion. "
            "Do not greet or speak before the telephone counterpart speaks. Confirmed task context follows:\n"+self.prompt.split('BESTÄTIGTER STECKBRIEF')[-1])
        self.ws=await websockets.connect('wss://api.openai.com/v1/live/sessions',additional_headers={'Authorization':'Bearer '+self.key},max_size=4*1024*1024,open_timeout=10)
        await self.send({'type':'session.start','session':{
            'model':self.profile['model'],'instructions':voice_prompt,'store':False,
            'audio':{'format':{'type':'audio/pcm','rate':24000},'output':{'voice':self.profile['voice']}},
            'delegation':{'type':'responses','responses':{
                'model':self.profile.get('backend_model','gpt-6-luna'),
                'instructions':self.prompt+'\nYou are the reasoning backend, not the speaking model. Return verified task facts for the voice frontend. Never claim a private user answer that has not been delivered. finish_call requires an actually spoken farewell. Do not treat a completed backend response as completed speech.',
                'tools':TOOLS,'parallel_tool_calls':False,'max_output_tokens':1024,
                'reasoning':{'effort':'low'},'tool_choice':'auto'}}}})

    async def input(self,pcm):
        if not self.closing:await self.send({'type':'session.input_audio.append','audio':base64.b64encode(pcm).decode()})

    async def steer(self,text):
        # The protocol limits appended context to 500 tokens. Bound each chunk
        # conservatively without silently discarding the operator's instruction.
        for start in range(0,len(text),400):
            await self.send({'type':'session.instructions.append','delegation_id':None,'content':text[start:start+400]})

    async def answer(self,id,value,name='ask_user',audio_only=False):
        if id not in self.pending_calls:raise RuntimeError('Unknown or already answered Live tool call')
        self.pending_calls.remove(id);self.completed_calls.add(id)
        await self.send({'type':'response.item.create','item':{'type':'function_call_output','call_id':id,'output':json.dumps({'answer':value,'source':'private application/user, not callee'})}})
        if not self.pending_calls:await self.send({'type':'response.create'})
        if audio_only:await self.steer(value)

    async def interrupt(self):
        # Local playback is controlled by the native endpoint. GPT-Live has no
        # Realtime response.cancel / input-commit turn protocol.
        await self.event('native_output_cut')

    async def receive(self):
        from .providers import ProviderFailure
        async for raw in self.ws:
            e=json.loads(raw);kind=e.get('type','')
            if kind=='session.started':
                self.ready.set();await self.event('live_started',session_id=e.get('session',{}).get('id'),backend_model=self.profile.get('backend_model','gpt-6-luna'))
            elif kind=='session.output_audio.delta':
                pcm=base64.b64decode(e['delta'])
                # Preserve pauses inside normal speech. Only after the app has
                # accepted a finish request may continuous digital silence be
                # left to the native endpoint instead of keeping its queue full.
                audible=bool(pcm.strip(b'\x00'))
                if audible:self.last_audio=time.monotonic()
                if audible or not self.playback_finishing:await self.audio(pcm,self.rate)
            elif kind in ('session.input_transcript.delta','session.output_transcript.delta'):
                assistant=kind=='session.output_transcript.delta'
                await self.event('transcript',speaker='assistant' if assistant else 'callee',text=e.get('delta',''),source='model_output' if assistant else 'recognition',start_ms=e.get('start_ms'),end_ms=e.get('end_ms'))
            elif kind in ('session.usage.updated','session.closed'):
                await self.event('voice_usage',seconds=e.get('usage',{}).get('seconds'),final=kind=='session.closed')
                if kind=='session.closed':
                    self.finalized=True;self.closed.set();return
            elif kind=='response.event':
                nested=e.get('event',{});t=nested.get('type')
                if t=='response.output_item.done':
                    item=nested.get('item',{});id=item.get('call_id')
                    if item.get('type')=='function_call' and id not in self.pending_calls|self.completed_calls:
                        self.pending_calls.add(id)
                        await self.event('tool',name=item['name'],id=id,item_id=item.get('id'),args=json.loads(item.get('arguments','{}')))
                elif t=='response.completed':
                    r=nested.get('response',{});await self.event('usage',usage=r.get('usage'),usage_id=r.get('id'),cumulative=False)
                elif t in ('response.failed','response.incomplete'):
                    raise ProviderFailure(nested.get('response',{}).get('error') or {'message':'Live reasoning backend failed','code':t})
            elif kind=='error':raise ProviderFailure(e.get('error',{}))

    async def close(self):
        if not self.ws:return
        try:
            if self.ready.is_set() and not self.closed.is_set():
                self.closing=True;await self.send({'type':'session.close'})
                try:await asyncio.wait_for(self.closed.wait(),3)
                except TimeoutError:await self.event('live_finalization',confirmed=False)
        finally:await self.ws.close()
