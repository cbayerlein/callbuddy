"""Independent native safety owner; never redials or replays model work."""
import json,subprocess,sys,time,os,signal
from pathlib import Path
from .store import Store
from .sip import rpc

def lease(root):
    temp=root/"lease.tmp";temp.write_text(json.dumps({"expires":time.monotonic()+5}));temp.replace(root/"lease.json")

def main():
    path=Path(sys.argv[1]);config=json.loads(path.read_text());id=config["call_id"]
    store=Store(Path(config["root"])/"work",Path(config["credential_root"]));root=path.parent
    lease(root);native=None;model=None;receipt=None;failure=None
    def update(**values):
        c=store.get(id);c.update(values);store.put(id,"call",c);store.event(id,"state",**values)
    try:
        native=subprocess.Popen([sys.executable,"-m","call_assistant.sip",str(path)])
        deadline=time.monotonic()+15
        while not (root/"sip.sock").exists():
            lease(root)
            if native.poll() is not None or time.monotonic()>deadline:raise RuntimeError("SIP initialization failed")
            time.sleep(.1)
        model=subprocess.Popen([sys.executable,"-m","call_assistant.worker",str(path)])
        model_started=time.time()
        while native.poll() is None and model.poll() is None:
            lease(root)
            for c in store.list("command"):
                if c["call_id"]!=id or c["status"]!="accepted" or c["kind"]=="instruction":continue
                request={"command":c["kind"]}
                if c["kind"]=="dtmf":request["digits"]=c["text"]
                try:
                    effect=rpc(root/"sip.sock",request);c.update(status="applied",native_receipt=effect)
                    store.put("cmd:"+c["command_id"],"command",c)
                    changes={"pause":{"paused":True},"resume":{"paused":False,"takeover":False},"takeover":{"paused":True,"takeover":True},"release":{"paused":True,"takeover":False}}
                    if c["kind"] in changes:update(**changes[c["kind"]])
                    store.event(id,"command",command_id=c["command_id"],kind_name=c["kind"],status="applied")
                    if c["kind"]=="hangup":update(status="cancelled",result="Durch Nutzer beendet");model.terminate()
                except Exception:
                    c["status"]="unknown";store.put("cmd:"+c["command_id"],"command",c);raise
            marker=root/"model-progress.json"
            progress=json.loads(marker.read_text())["time"] if marker.exists() else model_started
            if time.time()-progress>30:raise RuntimeError("Model worker stalled")
            time.sleep(.05)
        if native.poll() is not None:raise RuntimeError("Native endpoint stopped unexpectedly")
    except Exception as exc:
        failure=type(exc).__name__;update(status="inconclusive",result="Technischer Fehler oder unklarer Effekt; keine Wiederholung.")
    finally:
        if model and model.poll() is None:
            model.terminate()
            try:model.wait(timeout=5)
            except subprocess.TimeoutExpired:model.kill();model.wait(timeout=3)
        if native and native.poll() is None:
            try:
                rpc(root/"sip.sock",{"command":"hangup"});rpc(root/"sip.sock",{"command":"unregister"})
                deadline=time.monotonic()+8
                while time.monotonic()<deadline:
                    lease(root);receipt=rpc(root/"sip.sock",{"command":"inspect"})
                    if receipt["registration_removed"] and (receipt["disconnected"] or not receipt["connected"]):break
                    time.sleep(.1)
            except Exception:failure=failure or "cleanup_unknown"
            native.terminate()
            try:native.wait(timeout=3)
            except subprocess.TimeoutExpired:native.kill();native.wait(timeout=3)
        cleanup="registrar_ack_and_local_closure" if receipt and receipt.get("registration_removed") and not receipt.get("connected") else "unverified"
        c=store.get(id)
        if c["status"] not in {"completed","cancelled","failed","inconclusive"}:update(status="inconclusive",result="Modellprozess beendet; Ergebnis nicht bestätigt.")
        model_closed=(root/"model-closed.json").exists()
        if not model_closed:cleanup="unverified"
        update(cleanup=cleanup,model_closed=model_closed,finished_at=time.time())
        (root/"closure.json").write_text(json.dumps({"call_id":id,"cleanup":cleanup,"native_receipt":receipt,"model_closed":model_closed,"error":failure,"independent_audio_qualified":False}))
if __name__=="__main__":main()

