"""Durable live call commands; external effects require accepted user context."""
import asyncio,hashlib,json,os,re,signal,subprocess,sys,time
from pathlib import Path
from .domain import instructions

class Runtime:
    terminal={"completed","cancelled","failed","inconclusive"}
    def __init__(self,store,live_enabled=False,*,test_endpoint=None):self.store=store;self.live_enabled=live_enabled;self.peers={};self.test_endpoint=test_endpoint
    def reconcile(self):
        for c in self.store.list("call"):
            if c["status"] not in self.terminal:
                if not self.owner_alive(c):self.update(c["id"],status="inconclusive",result="Gesprächsprozess nicht mehr aktiv. Kein automatischer Wiederanruf.",cleanup="unverified")
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
            if not self.live_enabled:raise PermissionError("Telefonie ist noch gesperrt.")
            if not model or model.get("profile_kind")!="model" or not sip or sip.get("profile_kind")!="sip":raise ValueError("SIP- und Modellprofil auswählen")
            if not model.get("credential_ref") or not sip.get("credential_ref"):raise ValueError("Zugangsdaten fehlen")
            if model.get("purpose","live")!="live":raise ValueError("Ein Live-Audiomodell auswählen, kein Textmodell")
        research=[r for r in self.store.list("research") if r.get("status")=="approved"]
        call=self.store.add("call",{"mode":"live","status":"preparing","scenario":brief["scenario"],"objective":brief["objective"],"destination":brief["number"],"accepted_context":brief["accepted_context"],"brief_revision":brief["revision"],"model_profile":brief.get("model_profile"),"sip_profile":brief.get("sip_profile"),"model_snapshot":self.store.public(model),"sip_snapshot":self.store.public(sip),"research_snapshot":[{"id":r["id"],"source_hash":r["source_hash"]} for r in research],"cleanup":"pending","created_at":time.time(),"paused":False,"takeover":False,"decision":None,"result":None})
        if model:
            call["model_profile"]=model["id"];self.store.put(call["id"],"call",call)
        self.store.put("start:"+request.request_id,"start",{"call_id":call["id"],"brief_id":brief["id"],"revision":request.accepted_revision,"mode":request.mode})
        self.store.event(call["id"],"state",status="preparing",mode=request.mode)
        if request.mode=="live":
            root=self.store.root/"calls"/call["id"];root.mkdir(parents=True)
            frozen_model=dict(model)
            if recommendation:frozen_model["eagerness"]=recommendation["eagerness"]
            config={"call_id":call["id"],"root":str(self.store.root.parent),"credential_root":str(self.store.credentials),"sip":sip,"model":frozen_model,"instructions":instructions(brief["accepted_context"]),"recording":settings.get("recording",False)}
            if self.test_endpoint:config["test_endpoint"]=self.test_endpoint
            config_path=root/"config.json";config_path.write_text(json.dumps(config));config_path.chmod(0o600)
            with (root/"guardian.log").open("wb") as log:
                proc=subprocess.Popen([sys.executable,"-m","call_assistant.guardian",str(config_path),call["id"]],stdout=log,stderr=log,start_new_session=True)
            self.update(call["id"],guardian_pid=proc.pid)
        return self.store.get(call["id"])
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
        return d
    async def rtc(self,id,data):
        from .media import browser_peer
        if self.store.get(id)["status"] in self.terminal:raise ValueError("Gespräch beendet")
        return await browser_peer(self,id,data)
    async def close_browser_peers(self):
        await asyncio.gather(*(p.close() for p in self.peers.values()),return_exceptions=True)
