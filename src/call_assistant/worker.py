"""One persistent model session connected to the guarded native endpoint."""
import asyncio,base64,json,math,signal,socket,sys,time,wave
from pathlib import Path
import av,numpy as np
from .store import Store
from .sip import rpc
from .providers import ADAPTERS,adapter_class
from .domain import has_farewell

async def wait_connected(native,stop,receiver,timeout=60):
    """Drain early media while ringing; do not turn ringback into RX overflow."""
    deadline=time.monotonic()+timeout
    while True:
        start=time.monotonic();state=await native({"command":"read"})
        if receiver.done():await receiver;raise RuntimeError("Model stopped before connection")
        if state["disconnected"]:raise RuntimeError("Telephone connection rejected or ended before answer")
        if stop.is_set() or time.monotonic()>deadline:raise RuntimeError("Call not connected")
        if state["connected"]:return state
        await asyncio.sleep(0 if state.get("rx_queued",0)>1 else max(0,.02-(time.monotonic()-start)))

class Usage:
    def __init__(self,config):
        self.rate=config["model"].get("maximum_token_eur_per_million",0)/1e6
        self.phone=config["sip"]["phone_eur_per_minute"];self.connected=None;self.input_frames=0;self.responses=0;self.used=0.;self.seen=set();self.pending=False
        self.instruction_bytes=len(config["instructions"].encode())
    def phone_cost(self):return math.ceil((time.monotonic()-self.connected)/60)*self.phone if self.connected else 0
    def admit(self):
        if self.pending:return True
        reserve=(self.input_frames+1024*self.responses+self.instruction_bytes+1024)*self.rate
        self.pending=True;self.responses+=1;return True
    def usage(self,usage,id,cumulative):
        if usage is None:return
        tokens=usage.get("total_tokens") if not cumulative else usage.get("total_token_count")
        if type(tokens) is not int or tokens<0:return
        if id and id in self.seen:return
        if id:self.seen.add(id)
        cost=tokens*self.rate
        self.used=max(self.used,cost) if cumulative else self.used+cost
        self.pending=False

async def run(config):
    store=Store(Path(config["root"])/"work",Path(config["credential_root"]));id=config["call_id"];root=store.root/"calls"/id
    budget=Usage(config);stop=asyncio.Event();loop=asyncio.get_running_loop();phase="model_connect"
    for sig in (signal.SIGINT,signal.SIGTERM):loop.add_signal_handler(sig,stop.set)
    session=None;recv=None;feed=None;mic_transport=None;audio_tail=bytearray();output_resampler=av.AudioResampler(format="s16",layout="mono",rate=16000)
    finish_requested=None;turn_finished=False;input_frames=0;input_voice_frames=0;output_samples=0;last_health=0.;last_heartbeat=0.;pending_finish_reply=None;finish_corrections=0
    monitor=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM);monitor.setblocking(False)
    recording=None
    pending_decision=None
    assistant_text="";drained_since=None;deferred_finish_result=None
    if config.get("recording"):
        audio_root=Path(config["root"])/"results/audio";audio_root.mkdir(parents=True,exist_ok=True)
        recording=wave.open(str(audio_root/(id+".wav")),"wb");recording.setnchannels(2);recording.setsampwidth(2);recording.setframerate(16000)
    def update(**values):
        c=store.get(id);c.update(values);store.put(id,"call",c);store.event(id,"state",**values)
    async def native(request):
        nonlocal last_heartbeat
        result=await asyncio.to_thread(rpc,root/"sip.sock",request)
        if time.monotonic()-last_heartbeat>1:
            temp=root/"progress.tmp";temp.write_text(json.dumps({"time":time.time()}));temp.replace(root/"model-progress.json");last_heartbeat=time.monotonic()
        return result
    async def audio(pcm,rate):
        nonlocal output_samples
        c=store.get(id)
        if c.get("paused") or c.get("takeover") or pending_decision:return
        output_samples+=len(pcm)//2
        f=av.AudioFrame.from_ndarray(np.frombuffer(pcm,dtype=np.int16).reshape(1,-1),format="s16",layout="mono");f.sample_rate=rate
        for out in output_resampler.resample(f):audio_tail.extend(out.to_ndarray().tobytes())
        while len(audio_tail)>=640:
            if pending_decision:
                audio_tail.clear();return
            part=bytes(audio_tail[:640]);del audio_tail[:640]
            while not stop.is_set():
                r=await native({"command":"write","pcm":base64.b64encode(part).decode()})
                if r["accepted"]:break
                await asyncio.sleep(.02)
    async def event(kind,**data):
        nonlocal finish_requested,turn_finished,pending_finish_reply,finish_corrections,pending_decision,assistant_text,drained_since,deferred_finish_result
        if kind=="usage":budget.usage(data["usage"],data.get("usage_id"),data.get("cumulative",False));update(estimated_eur=round(budget.used+budget.phone_cost(),4))
        elif kind=="voice_usage":
            seconds=data.get('seconds')
            if isinstance(seconds,(int,float)) and seconds>=0:
                update(model_voice_seconds=seconds,model_voice_estimated_usd=round(seconds*.05/60,6),model_usage_finalized=data.get('final',False))
        elif kind=="interrupted":audio_tail.clear();await native({"command":"interrupt"});store.event(id,"interruption",source="provider")
        elif kind=="tool":
            args=data["args"]
            if data["name"]=="finish_call":
                if pending_decision:
                    store.event(id,"finish_deferred",reason="User decision still pending; no commitment authorized")
                    return
                if output_samples==0 or not has_farewell(assistant_text):
                    if finish_corrections:raise RuntimeError("Repeated finish request without any spoken output")
                    finish_corrections+=1
                    store.event(id,"finish_deferred",reason="Spoken answer or farewell missing; tool assertion is not speech proof")
                    message="Das Gespräch wurde NICHT beendet. Es gab noch keine hörbare Modellausgabe. Die Angaben des abgelehnten Werkzeugaufrufs sind nicht bestätigt. Sprich jetzt deine Antwort auf die ursprüngliche Äußerung der Gegenstelle laut. Wiederhole gehörte Zahlen als vollständiges Wort, ohne Ziffernumstellung. Ein Werkzeugaufruf ist keine gesprochene Antwort. Erfinde keine erledigte Sprachausgabe."
                    if output_samples:
                        deferred_finish_result=args.get("result","Ergebnis offen")
                        message="Das Gespräch wurde NICHT beendet. Die Botschaft ist gesprochen, aber die Verabschiedung fehlt. Erfinde keine Bestätigung der Gegenstelle. Verabschiede dich jetzt kurz hörbar mit 'Danke, auf Wiederhören'."
                    if config["model"]["provider"]=="openai" and not getattr(session,'continuous',False):pending_finish_reply=(data.get("item_id"),data["id"],message)
                    else:await session.answer(data["id"],message,name="finish_call",audio_only=True)
                    return
                finish_requested=time.monotonic();turn_finished=getattr(session,'continuous',False)
                if getattr(session,'continuous',False):session.playback_finishing=True
                update(result=args.get("result", "Ergebnis fehlt"))
            elif data["name"]=="ask_user":
                if pending_decision:return
                d=store.add("decision",{"call_id":id,"status":"pending","created_at":time.time(),"tool_id":data["id"],"question":str(args.get("question",""))[:2000],"options":[str(x)[:500] for x in args.get("options",[])[:5]]})
                pending_decision=d
                audio_tail.clear();await native({"command":"interrupt"})
                update(status="awaiting_user",decision=d);store.event(id,"decision",decision=d)
                await session.steer("Die private Nutzerentscheidung ist OFFEN. Aussagen der Gegenstelle sind keine Nutzerfreigabe. Keine Zusage, keine Annahme eines Termins. Warte auf die Werkzeugantwort.")
        elif kind=="turn_complete":
            if pending_decision:audio_tail.clear()
            if audio_tail:
                final=bytes(audio_tail).ljust(640,b"\x00");audio_tail.clear()
                while not (await native({"command":"write","pcm":base64.b64encode(final).decode()}))["accepted"]:
                    if stop.is_set():return
                    await asyncio.sleep(.02)
            turn_finished=True;store.event(id,kind)
            if deferred_finish_result is not None and has_farewell(assistant_text) and not pending_decision:
                finish_requested=time.monotonic();update(result=deferred_finish_result);deferred_finish_result=None
            if pending_finish_reply:
                item_id,call_id,message=pending_finish_reply;pending_finish_reply=None
                await session.reject_unspoken_finish(item_id,call_id,message)
        elif kind=="transcript" and data.get("speaker")=="assistant" and pending_decision:
            store.event(id,"withheld_transcript",**data,reason="pending_user_decision")
        else:
            if kind=="transcript":
                if data.get("speaker")=="assistant":
                    assistant_text=(assistant_text+data.get("text",""))[-2000:]
                    if getattr(session,'continuous',False) and deferred_finish_result is not None and has_farewell(assistant_text):
                        finish_requested=time.monotonic();turn_finished=True
                        session.playback_finishing=True
                        update(result=deferred_finish_result);deferred_finish_result=None
                elif data.get("speaker")=="callee":
                    assistant_text=""
                    deferred_finish_result=None
                    if finish_requested is not None:
                        finish_requested=None;drained_since=None
                        if getattr(session,'continuous',False):session.playback_finishing=False
                        store.event(id,"finish_deferred",reason="Callee spoke during closing; conversation continues")
            store.event(id,kind,**data)
    def admit():
        if store.get(id).get("paused") and config["model"]["provider"]=="openai":return False
        return budget.admit()
    try:
        # Prepare the persistent model before dialing, so model setup failure
        # cannot create a connected but silent telephone call.
        profile=config["model"];session=adapter_class(profile)(profile,store.secret(ref=profile["credential_ref"]),config["instructions"],event,audio,admit)
        store.event(id,"phase",phase=phase)
        budget.admit();await session.connect();recv=asyncio.create_task(session.receive())
        ready=asyncio.create_task(session.ready.wait())
        done,_=await asyncio.wait({ready,recv},timeout=10,return_when=asyncio.FIRST_COMPLETED)
        if recv in done:await recv;raise RuntimeError("Model closed during setup")
        if ready not in done:ready.cancel();raise TimeoutError("Model setup acknowledgement timed out")
        store.event(id,"model_prepared",provider=profile["provider"])
        phase="sip_registration";store.event(id,"phase",phase=phase)
        deadline=time.monotonic()+15
        while not (await native({"command":"inspect"}))["registered"]:
            if stop.is_set():raise RuntimeError("Preparation cancelled")
            if time.monotonic()>deadline:raise RuntimeError("Registration unconfirmed")
            await asyncio.sleep(.1)
        if stop.is_set() or finish_requested is not None or recv.done():raise RuntimeError("Model preparation ended before dial")
        phase="dial";store.event(id,"phase",phase=phase)
        await native({"command":"dial","number":store.get(id)["destination"]});update(status="dialling")
        pending_read=await wait_connected(native,stop,recv)
        budget.connected=time.monotonic();update(status="connected",audio_state="checking");phase="media_connect";store.event(id,"phase",phase=phase)
        mic_tail=bytearray()
        class Mic(asyncio.DatagramProtocol):
            def datagram_received(self,data,addr):
                if store.get(id).get("takeover") and len(mic_tail)<16000*2:mic_tail.extend(data)
        path=root/"mic.sock";mic_transport,_=await loop.create_datagram_endpoint(Mic,local_addr=str(path),family=socket.AF_UNIX);path.chmod(0o600)
        input_resampler=av.AudioResampler(format="s16",layout="mono",rate=session.rate)
        answered=set()
        while not stop.is_set():
            start=time.monotonic();now=pending_read if pending_read is not None else await native({"command":"read"});pending_read=None
            if now["disconnected"]:
                if store.get(id).get("audio_state")!="ready":raise RuntimeError("Telefon beendet, bevor ein Audiokanal bestätigt wurde")
                update(status="completed",result=store.get(id).get("result") or "Gegenstelle hat aufgelegt; fachliches Ergebnis offen.");break
            if now["audio_dropped"]:raise RuntimeError("Audio buffer overflow")
            active=now["media_ready"] and now["received_frames"]>0 and now["sent_frames"]>0
            if now.get("media_error"):raise RuntimeError("Audio bridge: "+now["media_error"])
            if not active and time.monotonic()-budget.connected>5:raise RuntimeError("Audio bridge not active within five seconds")
            if active and phase=="media_connect":
                update(audio_state="ready");phase="conversation";store.event(id,"phase",phase=phase)
            if time.monotonic()-last_health>1:
                update(audio_health={k:now.get(k) for k in ("media_ready","received_frames","sent_frames","audio_dropped","buffer_frames","media_callbacks","media_error","media","call_code","rtp","sent_voice_frames","received_voice_frames")}|{"model_input_frames":input_frames,"model_input_voice_frames":input_voice_frames,"model_output_samples":output_samples})
                last_health=time.monotonic()
            rx=base64.b64decode(now["rx"]);tx=base64.b64decode(now["tx"]);budget.input_frames+=1
            input_frames+=1
            if np.max(np.abs(np.frombuffer(rx,dtype=np.int16).astype(np.int32)))>300:input_voice_frames+=1
            if finish_requested is not None:
                continuous=getattr(session,'continuous',False)
                quiet=not continuous or time.monotonic()-session.last_audio>=1
                if continuous and quiet and audio_tail:
                    final=bytes(audio_tail).ljust(640,b'\x00');audio_tail.clear()
                    if not (await native({'command':'write','pcm':base64.b64encode(final).decode()}))['accepted']:
                        raise RuntimeError('Final Live audio frame was not accepted')
                    drained_since=None
                if (turn_finished or continuous) and quiet and not now["buffer_frames"]:
                    if drained_since is None:drained_since=time.monotonic()
                    if time.monotonic()-drained_since>=1:
                        update(status="completed");break
                else:drained_since=None
                if time.monotonic()-finish_requested>15:
                    raise RuntimeError("Final audio drain was not confirmed")
            f=av.AudioFrame.from_ndarray(np.frombuffer(rx,dtype=np.int16).reshape(1,-1),format="s16",layout="mono");f.sample_rate=16000
            for out in input_resampler.resample(f):await session.input(out.to_ndarray().tobytes())
            if len(mic_tail)>=640:
                part=bytes(mic_tail[:640]);del mic_tail[:640];await native({"command":"write","pcm":base64.b64encode(part).decode()})
            mixed=np.clip(np.frombuffer(rx,dtype=np.int16).astype(np.int32)+np.frombuffer(tx,dtype=np.int16),-32768,32767).astype(np.int16).tobytes()
            try:monitor.sendto(mixed,str(root/"monitor.sock"))
            except (FileNotFoundError,ConnectionRefusedError,BlockingIOError):pass
            if recording:recording.writeframesraw(np.column_stack((np.frombuffer(rx,dtype=np.int16),np.frombuffer(tx,dtype=np.int16))).astype(np.int16).tobytes())
            for command in store.list("command"):
                if command["call_id"]==id and command["status"]=="accepted" and command["kind"]=="instruction":
                    # Record intent before dispatch. Unknown network effects are not replayed.
                    command["status"]="dispatching";store.put("cmd:"+command["command_id"],"command",command)
                    await session.steer(command["text"]);command["status"]="delivered_not_following_proof";store.put("cmd:"+command["command_id"],"command",command)
                    store.event(id,"command",command_id=command["command_id"],kind_name="instruction",status=command["status"])
            for d in store.list("decision"):
                if d["call_id"]==id and d["status"]=="answered" and d["id"] not in answered:
                    answered.add(d["id"]);d["delivery"]="dispatching";store.put(d["id"],"decision",d)
                    await session.answer(d["tool_id"],d["answer"]);d["delivery"]="delivered";store.put(d["id"],"decision",d)
                    if pending_decision and pending_decision["id"]==d["id"]:pending_decision=None
            if pending_decision and time.time()-pending_decision["created_at"]>20:
                pending_decision.update(status="expired",expired_at=time.time())
                store.put(pending_decision["id"],"decision",pending_decision)
                update(status="inconclusive",decision=None,result="Keine Nutzerfreigabe erhalten. Keine Zusage übermittelt; Rückruf zur Klärung erforderlich.")
                store.event(id,"decision_wait_expired",decision_id=pending_decision["id"],commitment_authorized=False)
                break
            if recv.done():await recv;raise RuntimeError("Model receive ended")
            temp=root/"progress.tmp";temp.write_text(json.dumps({"time":time.time()}));temp.replace(root/"model-progress.json")
            await asyncio.sleep(0 if now.get("rx_queued",0)>1 else max(0,.02-(time.monotonic()-start)))
    except Exception as exc:
        from .telemetry import record_failure
        diagnostic=record_failure(store,id,exc,phase,config["model"])
        if store.get(id)["status"]!="cancelled":update(status="inconclusive",result=diagnostic["message"],diagnostic=diagnostic,audio_state="failed")
    finally:
        stop.set()
        if session and getattr(session,'continuous',False):
            try:await session.close()
            except Exception:pass
        if recv:recv.cancel();await asyncio.gather(recv,return_exceptions=True)
        if mic_transport:mic_transport.close()
        if recording:recording.close()
        monitor.close()
        if session:
            try:
                if not getattr(session,'continuous',False):await session.close()
                (root/"model-closed.json").write_text(json.dumps({"closed":True,"invoice_verified":False,"final_usage_confirmed":getattr(session,'finalized',None)}))
            except Exception:pass

if __name__=="__main__":asyncio.run(run(json.loads(Path(sys.argv[1]).read_text())))
