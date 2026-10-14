"""One persistent model session connected to the guarded native endpoint."""
import asyncio,base64,json,math,signal,socket,sys,time,wave
from pathlib import Path
import av,numpy as np
from .store import Store
from .sip import rpc
from .providers import ADAPTERS

class Budget:
    def __init__(self,config):
        self.cap=config["budget_eur"];self.rate=config["model"]["maximum_token_eur_per_million"]/1e6
        self.phone=config["sip"]["phone_eur_per_minute"];self.connected=None;self.input_frames=0;self.responses=0;self.used=0.;self.seen=set();self.pending=False
        self.instruction_bytes=len(config["instructions"].encode())
    def phone_cost(self):return math.ceil((time.monotonic()-self.connected)/60)*self.phone if self.connected else 0
    def admit(self):
        if self.pending:return True
        reserve=(self.input_frames+1024*self.responses+self.instruction_bytes+1024)*self.rate
        if self.used+self.phone_cost()+reserve+self.phone>self.cap:raise PermissionError("Budget headroom exhausted")
        self.pending=True;self.responses+=1;return True
    def usage(self,usage,id,cumulative):
        if usage is None:raise ValueError("Provider usage missing; conservative reserve retained")
        tokens=usage.get("total_tokens") if not cumulative else usage.get("total_token_count")
        if type(tokens) is not int or tokens<0:raise ValueError("Invalid provider usage")
        if id and id in self.seen:return
        if id:self.seen.add(id)
        cost=tokens*self.rate
        self.used=max(self.used,cost) if cumulative else self.used+cost
        self.pending=False
        if self.used+self.phone_cost()>self.cap:raise PermissionError("Budget estimate exceeded")

async def run(config):
    store=Store(Path(config["root"])/"work",Path(config["credential_root"]));id=config["call_id"];root=store.root/"calls"/id
    budget=Budget(config);stop=asyncio.Event();loop=asyncio.get_running_loop()
    for sig in (signal.SIGINT,signal.SIGTERM):loop.add_signal_handler(sig,stop.set)
    session=None;recv=None;feed=None;mic_transport=None;audio_tail=bytearray();output_resampler=av.AudioResampler(format="s16",layout="mono",rate=16000)
    finish_requested=None;turn_finished=False
    monitor=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM);monitor.setblocking(False)
    recording=None
    if config.get("recording"):
        audio_root=Path(config["root"])/"results/audio";audio_root.mkdir(parents=True,exist_ok=True)
        recording=wave.open(str(audio_root/(id+".wav")),"wb");recording.setnchannels(2);recording.setsampwidth(2);recording.setframerate(16000)
    def update(**values):
        c=store.get(id);c.update(values);store.put(id,"call",c);store.event(id,"state",**values)
    async def native(request):return await asyncio.to_thread(rpc,root/"sip.sock",request)
    async def audio(pcm,rate):
        c=store.get(id)
        if c.get("paused") or c.get("takeover"):return
        f=av.AudioFrame.from_ndarray(np.frombuffer(pcm,dtype=np.int16).reshape(1,-1),format="s16",layout="mono");f.sample_rate=rate
        for out in output_resampler.resample(f):audio_tail.extend(out.to_ndarray().tobytes())
        while len(audio_tail)>=640:
            part=bytes(audio_tail[:640]);del audio_tail[:640]
            while not stop.is_set():
                r=await native({"command":"write","pcm":base64.b64encode(part).decode()})
                if r["accepted"]:break
                await asyncio.sleep(.02)
    async def event(kind,**data):
        nonlocal finish_requested,turn_finished
        if kind=="usage":budget.usage(data["usage"],data.get("usage_id"),data.get("cumulative",False));update(estimated_eur=round(budget.used+budget.phone_cost(),4))
        elif kind=="interrupted":audio_tail.clear();await native({"command":"interrupt"});store.event(id,"interruption",source="provider")
        elif kind=="tool":
            args=data["args"]
            if data["name"]=="finish_call":
                finish_requested=time.monotonic();turn_finished=False
                update(result=args.get("result", "Ergebnis fehlt"))
            elif data["name"]=="ask_user":
                d=store.add("decision",{"call_id":id,"status":"pending","tool_id":data["id"],"question":str(args.get("question",""))[:2000],"options":[str(x)[:500] for x in args.get("options",[])[:5]]})
                update(status="awaiting_user",decision=d);store.event(id,"decision",decision=d)
        elif kind=="turn_complete":
            if audio_tail:
                final=bytes(audio_tail).ljust(640,b"\x00");audio_tail.clear()
                while not (await native({"command":"write","pcm":base64.b64encode(final).decode()}))["accepted"]:
                    if stop.is_set():return
                    await asyncio.sleep(.02)
            turn_finished=True;store.event(id,kind)
        else:store.event(id,kind,**data)
    def admit():
        if store.get(id).get("paused") and config["model"]["provider"]=="openai":return False
        return budget.admit()
    try:
        # Prepare the persistent model before dialing, so model setup failure
        # cannot create a connected but silent telephone call.
        profile=config["model"];session=ADAPTERS[profile["provider"]](profile,store.secret(ref=profile["credential_ref"]),config["instructions"],event,audio,admit)
        budget.admit();await session.connect();recv=asyncio.create_task(session.receive());await asyncio.wait_for(session.ready.wait(),10)
        store.event(id,"model_prepared",provider=profile["provider"])
        deadline=time.monotonic()+15
        while not (await native({"command":"inspect"}))["registered"]:
            if stop.is_set():raise RuntimeError("Preparation cancelled")
            if time.monotonic()>deadline:raise RuntimeError("Registration unconfirmed")
            await asyncio.sleep(.1)
        if stop.is_set() or finish_requested is not None or recv.done():raise RuntimeError("Model preparation ended before dial")
        await native({"command":"dial","number":store.get(id)["destination"]});update(status="dialling")
        deadline=time.monotonic()+60
        while not (await native({"command":"inspect"}))["connected"]:
            if stop.is_set() or time.monotonic()>deadline:raise RuntimeError("Call not connected")
            await asyncio.sleep(.1)
        budget.connected=time.monotonic();update(status="connected")
        mic_tail=bytearray()
        class Mic(asyncio.DatagramProtocol):
            def datagram_received(self,data,addr):
                if store.get(id).get("takeover") and len(mic_tail)<16000*2:mic_tail.extend(data)
        path=root/"mic.sock";mic_transport,_=await loop.create_datagram_endpoint(Mic,local_addr=str(path),family=socket.AF_UNIX);path.chmod(0o600)
        input_resampler=av.AudioResampler(format="s16",layout="mono",rate=session.rate)
        answered=set()
        while not stop.is_set():
            start=time.monotonic();now=await native({"command":"read"})
            if now["disconnected"]:update(status="completed",result=store.get(id).get("result") or "Gegenstelle hat aufgelegt; fachliches Ergebnis offen.");break
            if now["audio_dropped"]:raise RuntimeError("Audio buffer overflow")
            rx=base64.b64decode(now["rx"]);tx=base64.b64decode(now["tx"]);budget.input_frames+=1
            if finish_requested is not None:
                if turn_finished and not now["buffer_frames"]:
                    update(status="completed");break
                if time.monotonic()-finish_requested>15:
                    raise RuntimeError("Final audio drain was not confirmed")
            if budget.used+budget.phone_cost()+budget.input_frames*budget.rate>budget.cap:raise PermissionError("Input/phone budget exhausted")
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
            if recv.done():await recv;raise RuntimeError("Model receive ended")
            temp=root/"progress.tmp";temp.write_text(json.dumps({"time":time.time()}));temp.replace(root/"model-progress.json")
            await asyncio.sleep(max(0,.02-(time.monotonic()-start)))
    except Exception as exc:
        if store.get(id)["status"]!="cancelled":update(status="inconclusive",result="Technik-/Budgetabbruch: "+type(exc).__name__+". Keine automatische Wiederholung.")
    finally:
        stop.set()
        if recv:recv.cancel();await asyncio.gather(recv,return_exceptions=True)
        if mic_transport:mic_transport.close()
        if recording:recording.close()
        monitor.close()
        if session:
            try:await session.close();(root/"model-closed.json").write_text(json.dumps({"closed":True,"invoice_verified":False}))
            except Exception:pass

if __name__=="__main__":asyncio.run(run(json.loads(Path(sys.argv[1]).read_text())))
