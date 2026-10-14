"""Generic PJSUA2 endpoint in a separate process, owned by the guardian."""
import base64,json,os,socket,sys,time
from collections import deque
from pathlib import Path

def rpc(path,request):
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
        s.settimeout(3);s.connect(str(path));s.sendall(json.dumps(request).encode()+b"\n")
        data=b""
        while b"\n" not in data:
            chunk=s.recv(65536)
            if not chunk:raise RuntimeError("Endpoint closed without receipt")
            data+=chunk
            if len(data)>2*1024*1024:raise RuntimeError("Oversized endpoint receipt")
    result=json.loads(data.split(b"\n",1)[0])
    if "error" in result:raise RuntimeError(result["error"])
    return result

class Endpoint:
    def __init__(self,config):
        import pjsua2 as pj
        from .store import Store
        self.pj=pj;self.config=config;self.root=Path(config["root"])/"work/calls"/config["call_id"]
        self.rx=deque();self.tx=deque();self.last_rx=bytes(640);self.last_tx=bytes(640)
        self.connected=False;self.disconnected=False;self.registered=False;self.removed=False;self.media_ready=False;self.paused=False;self.takeover=False;self.calls=0
        self.registration_code=None;self.received_frames=0;self.sent_frames=0;self.audio_dropped=0;self.reg_active=False
        self.dial_blocked=False
        owner=self
        class Source(pj.AudioMediaPort):
            def onFrameRequested(self,frame):
                payload=owner.tx.popleft() if owner.tx and (not owner.paused or owner.takeover) else bytes(640)
                frame.type=pj.PJMEDIA_TYPE_AUDIO;frame.buf.assign_from_bytes(payload);owner.last_tx=payload;owner.sent_frames+=1
        class Sink(pj.AudioMediaPort):
            def onFrameReceived(self,frame):
                data=bytearray(frame.buf.size());frame.buf.copy_to_bytearray(data)
                if len(data)!=640:return
                if len(owner.rx)>=250:owner.audio_dropped+=1;return
                owner.rx.append(bytes(data));owner.last_rx=bytes(data);owner.received_frames+=1
        class Account(pj.Account):
            def onRegState(self,param):
                owner.registration_code=int(param.code)
                if int(param.code)==200:
                    owner.reg_active=bool(param.expiration)
                    if param.expiration:owner.registered=True
                    else:owner.removed=True
            def onIncomingCall(self,param):
                c=pj.Call(self,param.callId);op=pj.CallOpParam();op.statusCode=486;c.answer(op)
        class Call(pj.Call):
            def onCallState(self,param):
                state=self.getInfo().state
                owner.connected=state==pj.PJSIP_INV_STATE_CONFIRMED
                if state==pj.PJSIP_INV_STATE_DISCONNECTED:owner.disconnected=True
            def onCallMediaState(self,param):
                for m in self.getInfo().media:
                    if m.type==pj.PJMEDIA_TYPE_AUDIO and m.status==pj.PJSUA_CALL_MEDIA_ACTIVE:
                        audio=self.getAudioMedia(m.index);audio.startTransmit(owner.sink);owner.source.startTransmit(audio);owner.media_ready=True
        self.Call=Call
        profile=config["sip"];store=Store(Path(config["root"])/"work",Path(config["credential_root"]))
        password=store.secret(ref=profile["credential_ref"])
        self.ep=pj.Endpoint();self.ep.libCreate();ec=pj.EpConfig();ec.uaConfig.threadCnt=0;ec.uaConfig.mainThreadOnly=True
        ec.logConfig.level=0;ec.logConfig.consoleLevel=0;ec.medConfig.clockRate=16000;ec.medConfig.sndClockRate=16000;ec.medConfig.audioFramePtime=20
        if profile.get("stun"):ec.uaConfig.stunServer.append(profile["stun"])
        self.ep.libInit(ec)
        tc=pj.TransportConfig();tc.port=0
        if profile["transport"]=="tls":tc.tlsConfig.verifyServer=True
        transport=self.ep.transportCreate({"udp":pj.PJSIP_TRANSPORT_UDP,"tcp":pj.PJSIP_TRANSPORT_TCP,"tls":pj.PJSIP_TRANSPORT_TLS}[profile["transport"]],tc)
        self.ep.libStart();self.ep.audDevManager().setNullDev()
        fmt=pj.MediaFormatAudio();fmt.type=pj.PJMEDIA_TYPE_AUDIO;fmt.clockRate=16000;fmt.channelCount=1;fmt.bitsPerSample=16;fmt.frameTimeUsec=20000
        self.source=Source();self.source.createPort("call-assistant-tx",fmt);self.sink=Sink();self.sink.createPort("call-assistant-rx",fmt)
        ac=pj.AccountConfig();ac.idUri=f"sip:{profile.get('caller_id') or profile['username']}@{profile['domain']}"
        scheme="sips" if profile["transport"]=="tls" else "sip"
        ac.regConfig.registrarUri=f"{scheme}:{profile['registrar']}:{profile['port']};transport={profile['transport']}"
        ac.regConfig.timeoutSec=120;ac.sipConfig.transportId=transport
        ac.sipConfig.authCreds.append(pj.AuthCredInfo("digest","*",profile.get("auth_id") or profile["username"],0,password))
        if profile.get("proxy"):ac.sipConfig.proxies.append(f"{scheme}:{profile['proxy']};transport={profile['transport']};lr")
        self.account=Account();self.account.create(ac);self.call=None
    def inspect(self):
        return {"registered":self.registered,"registration_active":self.reg_active,"registration_removed":self.removed,"registration_code":self.registration_code,"connected":self.connected,"disconnected":self.disconnected,"media_ready":self.media_ready,"audio_dropped":self.audio_dropped,"received_frames":self.received_frames,"sent_frames":self.sent_frames,"buffer_frames":len(self.tx),"paused":self.paused,"takeover":self.takeover}
    def command(self,r):
        pj=self.pj;kind=r["command"]
        if kind=="dial":
            if not self.registered or self.calls or self.dial_blocked:raise RuntimeError("One admitted outbound dial only after registration and before cancellation")
            number=r["number"]
            if not number.startswith("+") or not number[1:].isdigit():raise ValueError("E164 destination required")
            self.calls+=1;self.call=self.Call(self.account);op=pj.CallOpParam(True);self.call.makeCall(f"sip:{number}@{self.config['sip']['domain']}",op)
        elif kind=="read":
            rx=self.rx.popleft() if self.rx else bytes(640)
            return {**self.inspect(),"rx":base64.b64encode(rx).decode(),"tx":base64.b64encode(self.last_tx).decode()}
        elif kind=="write":
            data=base64.b64decode(r["pcm"])
            if len(data)%640 or len(data)>640*250:raise ValueError("Bounded 20ms mono PCM16 frames required")
            if len(self.tx)+len(data)//640>250:return {"accepted":False}
            self.tx.extend(data[i:i+640] for i in range(0,len(data),640));return {"accepted":True}
        elif kind in {"pause","resume","takeover","release","interrupt"}:
            self.tx.clear()
            if kind=="resume":self.paused=False;self.takeover=False
            elif kind=="takeover":self.paused=True;self.takeover=True
            elif kind=="release":self.paused=True;self.takeover=False
            elif kind=="pause":self.paused=True
        elif kind=="dtmf":
            digits=r["digits"]
            if not self.connected or not digits or any(c not in "0123456789ABCD*#" for c in digits):raise ValueError("Connected DTMF required")
            self.call.dialDtmf(digits)
        elif kind=="hangup":
            self.dial_blocked=True
            if self.call and not self.disconnected:op=pj.CallOpParam();op.statusCode=200;self.call.hangup(op)
        elif kind=="unregister":self.account.setRegistration(False)
        elif kind!="inspect":raise ValueError("Unknown endpoint command")
        return self.inspect()
    def close(self):
        self.ep.libDestroy()

def main():
    config=json.loads(Path(sys.argv[1]).read_text());root=Path(config["root"])/"work/calls"/config["call_id"]
    endpoint=Endpoint(config);path=root/"sip.sock"
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as server:
        server.bind(str(path));path.chmod(0o600);server.listen(8);server.settimeout(.01)
        try:
            while True:
                lease=json.loads((root/"lease.json").read_text())
                if time.monotonic()>lease["expires"]:break
                endpoint.ep.libHandleEvents(5)
                try:s,_=server.accept()
                except socket.timeout:continue
                with s:
                    s.settimeout(.3);data=b""
                    while b"\n" not in data:
                        part=s.recv(65536)
                        if not part or len(data)>1024*1024:break
                        data+=part
                    try:result=endpoint.command(json.loads(data.split(b"\n",1)[0]))
                    except Exception as e:result={"error":type(e).__name__}
                    s.sendall(json.dumps(result).encode()+b"\n")
        finally:
            try:endpoint.command({"command":"hangup"});endpoint.command({"command":"unregister"})
            except Exception:pass
            endpoint.close()
if __name__=="__main__":main()
