"""Persistent provider adapters. No network effects until explicitly connected."""
import asyncio,base64,json
from urllib.parse import quote
import httpx
import websockets

TOOLS=[{"type":"function","name":"ask_user","description":"Privately ask the person for a decision; do not speak the private question to the callee.","parameters":{"type":"object","properties":{"question":{"type":"string"},"options":{"type":"array","items":{"type":"string"}}},"required":["question","options"],"additionalProperties":False}},
 {"type":"function","name":"finish_call","description":"Finish the call after stating the result and unresolved facts.","parameters":{"type":"object","properties":{"result":{"type":"string"}},"required":["result"],"additionalProperties":False}}]

async def check_account(profile,key):
    async with httpx.AsyncClient(timeout=8) as c:
        if profile["provider"]=="openai":
            r=await c.get("https://api.openai.com/v1/models/"+quote(profile["model"],safe=""),headers={"Authorization":"Bearer "+key})
        else:
            r=await c.get("https://generativelanguage.googleapis.com/v1beta/models/"+quote(profile["model"],safe=""),headers={"x-goog-api-key":key})
    return {"ready":r.status_code==200,"detail":"Modellzugang bestätigt; Audio und Aussprache noch nicht live abgenommen." if r.status_code==200 else "Modell oder Zugang nicht verfügbar"}

class OpenAISession:
    rate=24000
    def __init__(self,profile,key,prompt,event,audio,admit):
        self.profile=profile;self.key=key;self.prompt=prompt;self.event=event;self.audio=audio;self.admit=admit;self.ws=None;self.ready=asyncio.Event()
    async def connect(self):
        self.ws=await websockets.connect("wss://api.openai.com/v1/realtime?model="+quote(self.profile["model"],safe=""),additional_headers={"Authorization":"Bearer "+self.key},max_size=4*1024*1024,open_timeout=10)
        await self.send({"type":"session.update","session":{"type":"realtime","model":self.profile["model"],"output_modalities":["audio"],"instructions":self.prompt+"\nSpeaking language: "+self.profile["language"],"max_output_tokens":512,"tools":TOOLS,
          "audio":{"input":{"format":{"type":"audio/pcm","rate":24000},"transcription":{"model":"gpt-4o-mini-transcribe","language":self.profile["language"]},"turn_detection":{"type":"semantic_vad","eagerness":self.profile["eagerness"],"create_response":False,"interrupt_response":True}},"output":{"format":{"type":"audio/pcm","rate":24000},"voice":self.profile["voice"]}}}})
    async def send(self,value):await self.ws.send(json.dumps(value))
    async def input(self,pcm):await self.send({"type":"input_audio_buffer.append","audio":base64.b64encode(pcm).decode()})
    async def reply(self):
        if self.admit():await self.send({"type":"response.create"})
    async def steer(self,text):
        await self.send({"type":"conversation.item.create","item":{"type":"message","role":"system","content":[{"type":"input_text","text":"Private user guidance, not the callee: "+text}]}})
    async def answer(self,id,value):
        await self.send({"type":"conversation.item.create","item":{"type":"function_call_output","call_id":id,"output":json.dumps({"answer":value,"role":"The caller assistant, not the callee"})}});await self.reply()
    async def interrupt(self):await self.send({"type":"response.cancel"})
    async def receive(self):
        async for raw in self.ws:
            e=json.loads(raw);kind=e.get("type","")
            if kind=="session.updated":self.ready.set()
            elif kind=="input_audio_buffer.committed":await self.reply()
            elif kind=="response.output_audio.delta":await self.audio(base64.b64decode(e["delta"]),24000)
            elif kind=="input_audio_buffer.speech_started":await self.event("interrupted")
            elif kind=="response.output_audio_transcript.done":await self.event("transcript",speaker="assistant",text=e.get("transcript",""),source="model_output")
            elif kind=="conversation.item.input_audio_transcription.completed":await self.event("transcript",speaker="callee",text=e.get("transcript",""),source="recognition")
            elif kind=="response.function_call_arguments.done":await self.event("tool",name=e.get("name"),id=e.get("call_id"),args=json.loads(e.get("arguments","{}")))
            elif kind=="response.done":
                await self.event("usage",usage=e.get("response",{}).get("usage"),usage_id=e.get("response",{}).get("id"),cumulative=False)
                await self.event("turn_complete")
            elif kind=="error" and e.get("error",{}).get("code")!="response_cancel_not_active":raise RuntimeError("OpenAI session error")
    async def close(self):
        if self.ws:await self.ws.close()

class GoogleSession:
    rate=16000
    def __init__(self,profile,key,prompt,event,audio,admit):
        self.profile=profile;self.key=key;self.prompt=prompt;self.event=event;self.audio=audio;self.admit=admit;self.ready=asyncio.Event()
    async def connect(self):
        from google import genai
        self.client=genai.Client(api_key=self.key)
        declarations=[{k:v for k,v in t.items() if k!="type"} for t in TOOLS]
        self.context=self.client.aio.live.connect(model=self.profile["model"],config={"response_modalities":["AUDIO"],"max_output_tokens":512,"system_instruction":self.prompt+"\nSpeak "+self.profile["language"],"speech_config":{"voice_config":{"prebuilt_voice_config":{"voice_name":self.profile["voice"]}}},"input_audio_transcription":{},"output_audio_transcription":{},"tools":[{"function_declarations":declarations}]})
        self.admit();self.session=await self.context.__aenter__();self.ready.set()
    async def input(self,pcm):
        from google.genai import types
        await self.session.send_realtime_input(audio=types.Blob(data=pcm,mime_type="audio/pcm;rate=16000"))
    async def steer(self,text):await self.session.send_realtime_input(text="Private user guidance, not the callee: "+text)
    async def answer(self,id,value):
        from google.genai import types
        self.admit();await self.session.send_tool_response(function_responses=types.FunctionResponse(id=id,name="ask_user",response={"answer":value,"role":"Caller assistant, not callee"}))
    async def interrupt(self):
        # Native output is cut immediately by the audio owner; Google's server
        # uses incoming audio interruption, not an invented response.cancel API.
        await self.event("native_output_cut")
    async def receive(self):
        while True:
            async for e in self.session.receive():
                sc=e.server_content
                if sc:
                    if sc.interrupted:await self.event("interrupted")
                    if sc.model_turn:
                        for p in sc.model_turn.parts or []:
                            if p.inline_data:await self.audio(p.inline_data.data,24000)
                    if sc.input_transcription and sc.input_transcription.text:await self.event("transcript",speaker="callee",text=sc.input_transcription.text,source="recognition")
                    if sc.output_transcription and sc.output_transcription.text:await self.event("transcript",speaker="assistant",text=sc.output_transcription.text,source="model_output")
                    if sc.turn_complete:
                        await self.event("turn_complete")
                        self.admit()
                if e.tool_call:
                    for t in e.tool_call.function_calls or []:await self.event("tool",name=t.name,id=t.id,args=t.args or {})
                if e.usage_metadata:await self.event("usage",usage=e.usage_metadata.model_dump(),usage_id=None,cumulative=True)
    async def close(self):
        if hasattr(self,"context"):await self.context.__aexit__(None,None,None)
        if hasattr(self,"client"):await self.client.aio.aclose()

ADAPTERS={"openai":OpenAISession,"google":GoogleSession}

async def text_json(profile,key,prompt):
    """One explicit paid text request, no retries or expected-answer ASR use."""
    if not profile.get("prep_model"):raise ValueError("Vorbereitungsmodell zuerst konfigurieren")
    if profile["provider"]=="openai":
        async with httpx.AsyncClient(timeout=25) as c:
            r=await c.post("https://api.openai.com/v1/responses",headers={"Authorization":"Bearer "+key},json={"model":profile["prep_model"],"input":prompt,"max_output_tokens":512,"text":{"format":{"type":"json_object"}}})
            r.raise_for_status();body=r.json()
        text="".join(p.get("text","") for item in body.get("output",[]) for p in item.get("content",[]) if p.get("type")=="output_text")
        usage=body.get("usage",{}).get("total_tokens")
    else:
        from google import genai
        client=genai.Client(api_key=key,http_options={"retry_options":{"attempts":1}})
        try:
            r=await client.aio.models.generate_content(model=profile["prep_model"],contents=prompt,config={"response_mime_type":"application/json","max_output_tokens":512})
            text=r.text;usage=r.usage_metadata.total_token_count if r.usage_metadata else None
        finally:await client.aio.aclose()
    result=json.loads(text)
    if not isinstance(result,dict):raise ValueError("Structured JSON object required")
    return result,usage

