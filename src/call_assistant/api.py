"""Persistent single-owner API. Native call effects belong to supervised workers."""
import asyncio, hashlib, json, os, time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI,Request,HTTPException
from fastapi.responses import JSONResponse,StreamingResponse,FileResponse
from fastapi.staticfiles import StaticFiles
from .store import Store
from .models import Settings,SipProfile,ModelProfile,Preparation,StartCall,Command,Answer,Memory,TextRequest,ResearchCandidate
from .domain import next_question,brief_context

STATE=Path(os.environ.get("CALL_ASSISTANT_STATE","/var/lib/openclaw/state/projects/call-assistant"))

def create_app(root=STATE,credential_root=None,*,live_enabled=None):
    root=Path(root);store=Store(root/"work",credential_root or Path(os.environ.get("CALL_ASSISTANT_CREDENTIALS","/var/lib/openclaw/state/credentials")))
    from .runtime import Runtime
    runtime=Runtime(store,live_enabled=os.environ.get("CALL_ASSISTANT_LIVE","0")=="1" if live_enabled is None else live_enabled)
    @asynccontextmanager
    async def lifespan(app):
        runtime.reconcile()
        yield
        await runtime.close_browser_peers()
    app=FastAPI(title="Telefonassistenz",lifespan=lifespan)
    app.state.store=store;app.state.runtime=runtime
    @app.middleware("http")
    async def guard(request,call_next):
        if request.url.path.startswith("/api/"):
            origin=request.headers.get("origin")
            configured=os.environ.get("PUBLIC_URL", "")
            expected=(urlsplit(configured).scheme+"://"+urlsplit(configured).netloc) if configured else str(request.base_url).rstrip("/")
            if origin and origin!=expected:return JSONResponse({"detail":"Origin not allowed"},403)
            if request.url.path not in {"/api/auth","/api/health"} and not store.authorized(request.cookies.get("call_assistant_session")):
                return JSONResponse({"detail":"Bitte anmelden"},401)
        response=await call_next(request)
        response.headers["X-Content-Type-Options"]="nosniff"
        response.headers["Cache-Control"]="no-store" if request.url.path.startswith("/api/") else "no-cache"
        return response
    @app.get("/api/health")
    def health():return {"setup_required":store.get("auth") is None,"live_enabled":runtime.live_enabled,"version":"0.1.0"}
    @app.post("/api/auth")
    async def auth(request:Request):
        body=await request.json();password=body.get("password","")
        if not isinstance(password,str) or len(password)<12 or len(password)>500:raise HTTPException(400,"Mindestens 12 Zeichen verwenden")
        if not store.get("auth"):store.set_password(password)
        token=store.login(password)
        if not token:raise HTTPException(401,"Anmeldung fehlgeschlagen")
        r=JSONResponse({"authenticated":True});r.set_cookie("call_assistant_session",token,httponly=True,samesite="strict",secure=request.url.scheme=="https",max_age=86400)
        return r
    @app.delete("/api/auth")
    def logout(request:Request):
        token=request.cookies.get("call_assistant_session")
        if token:store.delete("session:"+hashlib.sha256(token.encode()).hexdigest())
        r=JSONResponse({"authenticated":False});r.delete_cookie("call_assistant_session");return r
    @app.get("/api/settings")
    def settings():return store.get("settings") or Settings().model_dump()
    @app.put("/api/settings")
    def save_settings(value:Settings):return store.put("settings","system",value.model_dump())
    def profiles(kind):return [store.public(p)|{"has_credential":bool(p.get("credential_ref")),"qualification":"not_live_verified"} for p in store.list(kind)]
    @app.get("/api/profiles")
    def get_profiles():return {"sip":profiles("sip"),"models":profiles("model")}
    def save_profile(kind,value,id=None):
        data=value.model_dump();secret=data.pop("password" if kind=="sip" else "api_key",None)
        old=store.get(id) if id else None
        if id and (not old or old.get("profile_kind")!=kind):raise HTTPException(404,"Profil fehlt")
        ref=old.get("credential_ref") if old else None
        if secret:ref=store.secret(secret.get_secret_value())
        data.update(credential_ref=ref,profile_kind=kind)
        saved=store.put(id,kind,data|{"id":id}) if id else store.add(kind,data)
        return store.public(saved)|{"has_credential":bool(ref)}
    @app.post("/api/profiles/sip")
    def add_sip(value:SipProfile):return save_profile("sip",value)
    @app.put("/api/profiles/sip/{id}")
    def update_sip(id:str,value:SipProfile):return save_profile("sip",value,id)
    @app.post("/api/profiles/model")
    def add_model(value:ModelProfile):return save_profile("model",value)
    @app.put("/api/profiles/model/{id}")
    def update_model(id:str,value:ModelProfile):return save_profile("model",value,id)
    @app.delete("/api/profiles/{id}")
    def remove_profile(id:str):
        if any(c.get("status") not in runtime.terminal and id in (c.get("model_profile"),c.get("sip_profile")) for c in store.list("call")):raise HTTPException(409,"Profil wird noch verwendet")
        p=store.get(id)
        if not p or p.get("profile_kind") not in ("sip","model"):raise HTTPException(404,"Profil fehlt")
        store.delete(id);return {"deleted":True}
    @app.post("/api/profiles/{id}/check")
    async def check_profile(id:str):
        p=store.get(id)
        if not p:raise HTTPException(404,"Profil fehlt")
        if not p.get("credential_ref"):return {"ready":False,"detail":"Zugangsdaten fehlen"}
        if p.get("profile_kind")=="sip":return {"ready":False,"detail":"Konfiguration gespeichert. Registrierung und Audio benötigen eine ausdrücklich freigegebene Live-Probe."}
        from .providers import check_account
        try:return await check_account(p,store.secret(ref=p["credential_ref"]))
        except Exception:return {"ready":False,"detail":"Anbieterzugang nicht bestätigt; Schlüssel und Modell prüfen."}
    @app.get("/api/memory")
    def get_memory():return store.list("memory")
    @app.post("/api/memory")
    def add_memory(value:Memory):return store.add("memory",value.model_dump()|{"updated_at":time.time()})
    @app.put("/api/memory/{id}")
    def edit_memory(id:str,value:Memory):
        if not any(m["id"]==id for m in store.list("memory")):raise HTTPException(404,"Eintrag fehlt")
        return store.put(id,"memory",value.model_dump()|{"id":id,"updated_at":time.time()})
    @app.delete("/api/memory/{id}")
    def delete_memory(id:str):
        if not any(m["id"]==id for m in store.list("memory")):raise HTTPException(404,"Eintrag fehlt")
        store.delete(id);return {"deleted":True}
    @app.post("/api/briefs")
    def create_brief(value:Preparation):return store.add("brief",value.model_dump()|{"revision":1,"accepted":False})
    def brief(id):
        b=store.get(id)
        if not b or "revision" not in b:raise HTTPException(404,"Steckbrief fehlt")
        return b
    @app.get("/api/briefs/{id}")
    def get_brief(id:str):
        b=brief(id);return b|{"question":b.get("ai_question") or next_question(b),"context":brief_context(b,settings(),get_memory())}
    @app.put("/api/briefs/{id}")
    def edit_brief(id:str,value:Preparation):
        old=brief(id);return store.put(id,"brief",value.model_dump()|{"id":id,"revision":old["revision"]+1,"accepted":False})
    @app.post("/api/briefs/{id}/answers")
    async def prep_answer(id:str,request:Request):
        b=brief(id);data=await request.json();q=b.get("ai_question") or next_question(b)
        if not q or data.get("question_id")!=q["id"]:raise HTTPException(409,"Frage ist nicht mehr aktuell")
        answer=Answer(answer=data.get("answer","")).answer
        b["answers"]={**b["answers"],q["id"]:answer};b["revision"]+=1;b["accepted"]=False;b.pop("ai_question",None)
        store.put(id,"brief",b);return get_brief(id)
    @app.post("/api/briefs/{id}/accept")
    def accept(id:str):
        b=brief(id)
        if b.get("ai_question") or next_question(b):raise HTTPException(409,"Vorbereitung noch nicht vollständig")
        b.update(accepted=True,accepted_context=brief_context(b,settings(),get_memory()));store.put(id,"brief",b);return b
    async def paid_text(value,prompt):
        key="text:"+value.request_id
        old=store.get(key)
        if old:
            if old.get("status")!="completed":raise HTTPException(409,"Vorheriger Effekt unklar; nicht wiederholen")
            return old["result"]
        p=store.get(value.model_profile)
        if not p or not p.get("credential_ref") or not p.get("pricing_confirmed") or not p.get("prep_model"):raise HTTPException(409,"Modell, Zugang und bestätigte Preise erforderlich")
        ceiling=(len(prompt.encode())+2048)*p["maximum_token_eur_per_million"]/1e6
        if ceiling>value.budget_eur:raise HTTPException(409,"Konservative Reservierung übersteigt das freigegebene Textbudget")
        store.put(key,"text_request",{"status":"dispatching","reserved_eur":value.budget_eur,"model_profile":value.model_profile})
        from .providers import text_json
        try:
            result,tokens=await text_json(p,store.secret(ref=p["credential_ref"]),prompt)
            cost=tokens*p["maximum_token_eur_per_million"]/1e6 if type(tokens) is int and tokens>=0 else value.budget_eur
            store.put(key,"text_request",{"status":"completed","result":result,"estimated_eur":cost,"invoice_verified":False})
            return result
        except Exception:
            raise HTTPException(409,"Textanfrage nicht bestätigt; Reservierung bleibt erhalten. Keine automatische Wiederholung.")
    @app.post("/api/briefs/{id}/prepare-ai")
    async def prepare_ai(id:str,value:TextRequest):
        b=brief(id);context=brief_context(b,settings(),get_memory())
        prompt="Return JSON with question_id, question, options (array), done (boolean). Ask ONE missing task-specific question, do not invent facts or repeat answered questions. A complete user brief may be done=true. Do not create instructions or make decisions. Language: German. Known confirmed context: "+json.dumps(context,ensure_ascii=False)
        result=await paid_text(value,prompt)
        if result.get("done") is not True:
            qid=str(result.get("question_id",""))[:80];question=str(result.get("question",""))[:2000];options=result.get("options",[])
            if not qid or not question or qid in b["answers"] or not isinstance(options,list):raise HTTPException(409,"KI-Frage ungültig oder bereits beantwortet; regelbasierte Vorbereitung bleibt verfügbar")
            b["ai_question"]={"id":qid,"text":question,"options":[str(x)[:500] for x in options[:5]],"allow_free_text":True};b["accepted"]=False;b["revision"]+=1;store.put(id,"brief",b)
        return get_brief(id)
    @app.post("/api/calls/{id}/memory-proposals")
    async def propose_memory(id:str,value:TextRequest):
        c=call(id)
        if c["status"] not in runtime.terminal:raise HTTPException(409,"Gespräch läuft noch")
        rows=[e for e in store.events(id) if e["kind"] in {"transcript","decision_answer"}]
        prompt="Return JSON {proposals:[{text:string,category:fact|preference}]}. Suggest only durable USER facts/preferences, never callee offers or assistant inventions. A one-off choice is not a preference. Role provenance must remain distinct. Uncertainty means omit. No automatic memory write. German.\n"+json.dumps(rows,ensure_ascii=False)
        result=await paid_text(value,prompt)
        proposals=result.get("proposals",[])
        if not isinstance(proposals,list):raise HTTPException(409,"Vorschläge ungültig")
        created=[]
        for p in proposals[:10]:
            m=Memory(text=p["text"],category=p.get("category","preference"),source="call:"+id,confirmed=False)
            created.append(store.add("memory",m.model_dump()|{"updated_at":time.time()}))
        return created
    @app.post("/api/briefs/{id}/calls")
    async def start(id:str,value:StartCall):
        b=brief(id)
        if not b.get("accepted") or b["revision"]!=value.accepted_revision:raise HTTPException(409,"Aktuellen Steckbrief zuerst freigeben")
        try:return await runtime.start(b,value)
        except (ValueError,PermissionError) as e:raise HTTPException(409,str(e))
    @app.get("/api/calls")
    def calls():return store.list("call")
    @app.get("/api/calls/{id}")
    def call(id:str):
        c=store.get(id)
        if not c or "status" not in c:raise HTTPException(404,"Gespräch fehlt")
        return c
    @app.get("/api/calls/{id}/events")
    async def events(id:str,request:Request,after:int=0):
        call(id)
        try:after=max(after,int(request.headers.get("last-event-id","0")))
        except ValueError:raise HTTPException(400,"Ungültiger Cursor")
        if after<0:raise HTTPException(400,"Ungültiger Cursor")
        async def stream():
            cursor=after
            while not await request.is_disconnected():
                for e in store.events(id,cursor):
                    cursor=e["seq"];yield f"id: {cursor}\ndata: {json.dumps(e,ensure_ascii=False)}\n\n"
                yield ": heartbeat\n\n";await asyncio.sleep(.5)
        return StreamingResponse(stream(),media_type="text/event-stream")
    @app.get("/api/calls/{id}/transcript")
    def transcript_export(id:str):
        c=call(id)
        return JSONResponse({"call":c,"events":store.events(id)},headers={"Content-Disposition":f'attachment; filename="conversation-{id}.json"'})
    @app.get("/api/calls/{id}/audio")
    def audio_export(id:str):
        c=call(id)
        if c["status"] not in runtime.terminal:raise HTTPException(409,"Aufzeichnung noch nicht abgeschlossen")
        path=root/"results"/"audio"/(id+".wav")
        if not path.is_file():raise HTTPException(404,"Keine Aufzeichnung vorhanden")
        return FileResponse(path,media_type="audio/wav",filename="conversation-"+id+".wav")
    @app.post("/api/calls/{id}/commands")
    async def command(id:str,value:Command):
        call(id)
        try:return await runtime.command(id,value)
        except ValueError as e:raise HTTPException(409,str(e))
    @app.post("/api/calls/{id}/decisions/{decision}/answer")
    async def answer(id:str,decision:str,value:Answer):
        call(id)
        try:return await runtime.answer(id,decision,value.answer)
        except ValueError as e:raise HTTPException(409,str(e))
    @app.post("/api/calls/{id}/rtc")
    async def rtc(id:str,request:Request):
        call(id)
        try:return await runtime.rtc(id,await request.json())
        except ValueError as e:raise HTTPException(409,str(e))
    @app.get("/api/research")
    def research():return store.list("research")
    @app.post("/api/research")
    async def import_research(value:ResearchCandidate):
        return store.add("research",value.model_dump()|{"status":"candidate"})
    @app.post("/api/research/{id}/approve")
    def approve_research(id:str):
        r=store.get(id)
        if not r or r.get("status")!="candidate":raise HTTPException(409,"Kein offener Kandidat")
        p=store.get(r.get("model_profile")) if r.get("model_profile") else None
        r.update(status="approved",approved_at=time.time(),approved_model=store.public(p) if p else None);store.put(id,"research",r);return r
    dist=Path(os.environ.get("CALL_ASSISTANT_WEB",str(root/"packages/web")))
    if (dist/"assets").is_dir():app.mount("/assets",StaticFiles(directory=dist/"assets"),name="assets")
    @app.get("/{path:path}")
    def index(path:str):
        if path.startswith("api/"):raise HTTPException(404,"Route fehlt")
        if not (dist/"index.html").is_file():raise HTTPException(503,"Web-App noch nicht gebaut")
        return FileResponse(dist/"index.html")
    return app
