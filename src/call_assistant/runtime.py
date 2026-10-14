"""Durable call commands; demo is explicit and never touches a provider."""
import asyncio,hashlib,json,os,signal,subprocess,sys,time
from pathlib import Path
from .domain import instructions

class Runtime:
    terminal={"completed","cancelled","failed","inconclusive"}
    def __init__(self,store,live_enabled=False):self.store=store;self.live_enabled=live_enabled;self.peers={};self.demo_tasks={}
    def reconcile(self):
        for c in self.store.list("call"):
            if c["status"] not in self.terminal:
                if c["mode"]=="demo":self.update(c["id"],status="inconclusive",result="Demo wurde durch Neustart beendet; nicht wiederholt.")
                elif not self.owner_alive(c):self.update(c["id"],status="inconclusive",result="Worker-Eigentum unklar. Keine automatische Wiederholung.",cleanup="unverified")
    def owner_alive(self,c):
        pid=c.get("guardian_pid")
        return bool(pid and Path(f"/proc/{pid}/cmdline").exists() and c["id"].encode() in Path(f"/proc/{pid}/cmdline").read_bytes())
    def update(self,id,**values):
        c=self.store.get(id);c.update(values);self.store.put(id,"call",c);self.store.event(id,"state",**{k:v for k,v in values.items() if k!="guardian_pid"});return c
    async def start(self,brief,request):
        settings=self.store.get("settings") or {}
        existing=self.store.get("start:"+request.request_id)
        if existing:
            if existing.get("brief_id")!=brief["id"] or existing.get("revision")!=request.accepted_revision or existing.get("mode")!=request.mode:raise ValueError("Anfrage-ID gehört zu einer anderen Freigabe")
            return self.store.get(existing["call_id"])
        if any(c["status"] not in self.terminal for c in self.store.list("call")):raise ValueError("Ein Gespräch läuft bereits")
        model=self.store.get(brief.get("model_profile")) if brief.get("model_profile") else None
        sip=self.store.get(brief.get("sip_profile")) if brief.get("sip_profile") else None
        recommendation=None
        if not model and settings.get("model_selection")=="recommended" and request.mode=="live":
            candidates=sorted(self.store.list("research"),key=lambda r:r.get("approved_at",0),reverse=True)
            for r in candidates:
                p=self.store.get(r.get("model_profile")) if r.get("model_profile") else None
                if p and r.get("status")=="approved" and r.get("measured_audio") and r.get("human_listening_approved") and r.get("role_and_reference_passed") and r.get("approved_model")==self.store.public(p):model=p;recommendation=r;break
            if not model:raise ValueError("Keine qualifizierte Empfehlung. Modell ausdrücklich auswählen.")
        if request.mode=="live":
            if not self.live_enabled:raise PermissionError("Live-Telefonie ist bis zur gesonderten Abnahme gesperrt. Demo ist verfügbar.")
            if not model or model.get("profile_kind")!="model" or not sip or sip.get("profile_kind")!="sip":raise ValueError("SIP- und Modellprofil auswählen")
            if not model.get("credential_ref") or not sip.get("credential_ref"):raise ValueError("Zugangsdaten fehlen")
            if not model.get("pricing_confirmed") or not sip.get("pricing_confirmed"):raise ValueError("Konservative Modellpreise und Telefontarif zuerst bestätigen")
        research=[r for r in self.store.list("research") if r.get("status")=="approved"]
        call=self.store.add("call",{"mode":request.mode,"status":"preparing","scenario":brief["scenario"],"objective":brief["objective"],"destination":brief["number"],"accepted_context":brief["accepted_context"],"brief_revision":brief["revision"],"model_profile":brief.get("model_profile"),"sip_profile":brief.get("sip_profile"),"model_snapshot":self.store.public(model) if model else None,"sip_snapshot":self.store.public(sip) if sip else None,"research_snapshot":[{"id":r["id"],"source_hash":r["source_hash"]} for r in research],"budget_eur":request.budget_eur,"estimated_eur":0,"cleanup":"pending","created_at":time.time(),"paused":False,"takeover":False,"decision":None,"result":None})
        if model:
            call["model_profile"]=model["id"];self.store.put(call["id"],"call",call)
        self.store.put("start:"+request.request_id,"start",{"call_id":call["id"],"brief_id":brief["id"],"revision":request.accepted_revision,"mode":request.mode})
        self.store.event(call["id"],"state",status="preparing",mode=request.mode)
        if request.mode=="demo":self.demo_tasks[call["id"]]=asyncio.create_task(self.demo(call["id"]))
        else:
            root=self.store.root/"calls"/call["id"];root.mkdir(parents=True)
            frozen_model=dict(model)
            if recommendation:frozen_model["eagerness"]=recommendation["eagerness"]
            config={"call_id":call["id"],"root":str(self.store.root.parent),"credential_root":str(self.store.credentials),"sip":sip,"model":frozen_model,"instructions":instructions(brief["accepted_context"]),"recording":settings.get("recording",False),"budget_eur":request.budget_eur}
            config_path=root/"config.json";config_path.write_text(json.dumps(config));config_path.chmod(0o600)
            with (root/"guardian.log").open("wb") as log:
                proc=subprocess.Popen([sys.executable,"-m","call_assistant.guardian",str(config_path),call["id"]],stdout=log,stderr=log,start_new_session=True)
            self.update(call["id"],guardian_pid=proc.pid)
        return self.store.get(call["id"])
    async def demo(self,id):
        await asyncio.sleep(.5)
        if self.store.get(id)["status"] in self.terminal:return
        self.update(id,status="connected",cleanup="not_applicable_demo")
        self.store.event(id,"transcript",speaker="callee",text="Guten Tag, wie kann ich Ihnen helfen?",source="demo_script")
        await asyncio.sleep(.8)
        c=self.store.get(id)
        if c["status"] in self.terminal:return
        self.store.event(id,"transcript",speaker="assistant",text=c["objective"],source="demo_script")
        await asyncio.sleep(.8)
        if self.store.get(id)["status"] in self.terminal:return
        decision=self.store.add("decision",{"call_id":id,"status":"pending","question":"Die gewünschte Zeit ist nicht frei. Darf ich die angebotene Alternative akzeptieren?","options":["Ja, diese Alternative passt","Nein, bitte andere Möglichkeiten erfragen","Ohne Zusage beenden"],"tool_id":"demo"})
        self.update(id,status="awaiting_user",decision=decision)
        self.store.event(id,"decision",decision=decision)
    async def command(self,id,command):
        key="cmd:"+command.command_id;prior=self.store.get(key)
        if prior:
            if prior["call_id"]!=id:raise ValueError("Befehl gehört zu einem anderen Gespräch")
            return prior
        c=self.store.get(id)
        if c["status"] in self.terminal:raise ValueError("Gespräch bereits beendet")
        if command.kind=="dtmf" and (not command.text or any(x not in "0123456789ABCD*#" for x in command.text)):raise ValueError("Ungültige DTMF-Zeichen")
        if command.kind=="instruction" and not command.text.strip():raise ValueError("Anweisung fehlt")
        receipt={"call_id":id,"command_id":command.command_id,"kind":command.kind,"text":command.text,"status":"accepted","created_at":time.time()}
        self.store.put(key,"command",receipt)
        if c["mode"]=="demo":
            updates={"pause":{"paused":True},"resume":{"paused":False},"takeover":{"takeover":True,"paused":True},"release":{"takeover":False,"paused":True},"hangup":{"status":"cancelled","result":"Demo ausdrücklich beendet","cleanup":"not_applicable_demo"}}
            self.update(id,**updates.get(command.kind,{}));receipt["status"]="applied_demo";self.store.put(key,"command",receipt)
            self.store.event(id,"command",command_id=command.command_id,kind_name=command.kind,status="applied_demo")
            if command.kind=="instruction":self.store.event(id,"private_instruction",speaker="user",text=command.text,source="private_user")
        return receipt
    async def answer(self,id,decision_id,answer):
        d=self.store.get(decision_id)
        if not d or d.get("call_id")!=id:raise ValueError("Rückfrage fehlt")
        if d["status"]!="pending":
            if d.get("answer")==answer:return d
            raise ValueError("Rückfrage bereits beantwortet")
        if self.store.get(id)["status"] in self.terminal:raise ValueError("Gespräch bereits beendet")
        d.update(status="answered",answer=answer,answered_at=time.time());self.store.put(decision_id,"decision",d)
        self.store.event(id,"decision_answer",speaker="user",text=answer,decision_id=decision_id,source="private_user")
        c=self.store.get(id);self.update(id,status="connected",decision=None)
        if c["mode"]=="demo":
            self.store.event(id,"transcript",speaker="assistant",text="Danke. Ich gebe Ihre Entscheidung weiter.",source="demo_script")
            self.update(id,status="completed",result="Demo-Ablauf beendet – keine Reservierung, kein echter Anruf und keine Audioqualifikation.",cleanup="not_applicable_demo")
        return d
    async def rtc(self,id,data):
        from .media import browser_peer
        if self.store.get(id)["status"] in self.terminal:raise ValueError("Gespräch beendet")
        return await browser_peer(self,id,data)
    async def close_browser_peers(self):
        await asyncio.gather(*(p.close() for p in self.peers.values()),return_exceptions=True)
