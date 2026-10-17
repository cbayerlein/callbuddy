"""Generic PJSUA2 endpoint in a separate process, owned by the guardian."""
import base64,gc,hashlib,ipaddress,json,os,re,socket,sys,time
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
        self.media_error=None;self.media_observations=[];self.media_callbacks=0;self.last_call_code=None;self.last_call_reason=None
        self.rtp={};self.last_rtp=0.;self.sent_voice_frames=0;self.received_voice_frames=0
        self.test=config.get("test_endpoint",{})
        owner=self
        class Source(pj.AudioMediaPort):
            def onFrameRequested(self,frame):
                payload=owner.tx.popleft() if owner.tx and (not owner.paused or owner.takeover) else bytes(640)
                frame.type=pj.PJMEDIA_TYPE_AUDIO;frame.buf.assign_from_bytes(payload);owner.last_tx=payload;owner.sent_frames+=1
                if any(payload):owner.sent_voice_frames+=1
        class Sink(pj.AudioMediaPort):
            def onFrameReceived(self,frame):
                data=bytearray(frame.buf.size());frame.buf.copy_to_bytearray(data)
                if len(data)!=640:return
                if len(owner.rx)>=250:owner.audio_dropped+=1;return
                owner.rx.append(bytes(data));owner.last_rx=bytes(data);owner.received_frames+=1
                if any(data):owner.received_voice_frames+=1
        class Account(pj.Account):
            def onRegState(self,param):
                owner.registration_code=int(param.code)
                if int(param.code)==200:
                    owner.reg_active=bool(param.expiration)
                    if param.expiration:owner.registered=True
                    else:owner.removed=True
            def onIncomingCall(self,param):
                expected=owner.test.get("expected_caller")
                candidate=owner.Call(self,param.callId)
                remote=candidate.getInfo().remoteUri
                match=re.search(r"sips?:([^@;>]+)@",remote)
                caller=match.group(1) if match else ""
                if caller.startswith("00"):caller="+"+caller[2:]
                elif caller.startswith("0") and expected and expected.startswith("+49"):caller="+49"+caller[1:]
                owner.event("incoming_observed",caller_sha256=hashlib.sha256(caller.encode()).hexdigest(),expected_match=caller in [expected,owner.test.get("expected_user")])
                if expected and caller in [expected,owner.test.get("expected_user")] and time.time()<owner.test.get("expires",0) and not owner.call:
                    owner.call=candidate;op=pj.CallOpParam();op.statusCode=200;candidate.answer(op);owner.event("incoming_accepted")
                    return
                c=pj.Call(self,param.callId);op=pj.CallOpParam();op.statusCode=486;c.answer(op)
        class Call(pj.Call):
            def onCallState(self,param):
                state=self.getInfo().state
                info=self.getInfo();owner.last_call_code=int(info.lastStatusCode);owner.last_call_reason=str(info.lastReason)
                owner.event("call_state",state=int(state),code=owner.last_call_code,reason=owner.last_call_reason)
                owner.connected=state==pj.PJSIP_INV_STATE_CONFIRMED
                if state==pj.PJSIP_INV_STATE_DISCONNECTED:owner.disconnected=True
            def onCallMediaState(self,param):
                owner.media_callbacks+=1
                try:
                    # SWIG vector entries borrow CallInfo storage. Keep the
                    # owner alive throughout both iteration and port attachment.
                    info=self.getInfo()
                    owner.media_observations=[{"type":int(m.type),"status":int(m.status),"index":int(m.index),"direction":int(m.dir)} for m in info.media]
                    owner.event("media_state",media=owner.media_observations)
                    for m in info.media:
                        if m.type==pj.PJMEDIA_TYPE_AUDIO and m.status==pj.PJSUA_CALL_MEDIA_ACTIVE:
                            audio=self.getAudioMedia(m.index);audio.startTransmit(owner.sink);owner.source.startTransmit(audio);owner.media_ready=True
                            stream=self.getStreamInfo(m.index)
                            owner.event("media_attached",codec=str(stream.codecName),clock_rate=int(stream.codecClockRate))
                except Exception as exc:
                    owner.media_error=type(exc).__name__+": "+str(exc)[:500];owner.event("media_error",error=owner.media_error)
        self.Call=Call
        profile=config["sip"]
        password="" if self.test.get("local") else Store(Path(config["root"])/"work",Path(config["credential_root"])).secret(ref=profile["credential_ref"])
        self.ep=pj.Endpoint();self.ep.libCreate();ec=pj.EpConfig();ec.uaConfig.threadCnt=0;ec.uaConfig.mainThreadOnly=True
        ec.logConfig.level=0;ec.logConfig.consoleLevel=0;ec.medConfig.clockRate=16000;ec.medConfig.sndClockRate=16000;ec.medConfig.audioFramePtime=20
        for line in Path('/etc/resolv.conf').read_text().splitlines():
            fields=line.split()
            if len(fields)>=2 and fields[0]=='nameserver':
                try:ec.uaConfig.nameserver.append(str(ipaddress.ip_address(fields[1])))
                except ValueError:pass
        if profile.get("stun"):ec.uaConfig.stunServer.append(profile["stun"])
        self.ep.libInit(ec)
        tc=pj.TransportConfig();tc.port=int(self.test.get("port",0))
        if profile["transport"]=="tls":tc.tlsConfig.verifyServer=True
        transport=self.ep.transportCreate({"udp":pj.PJSIP_TRANSPORT_UDP,"tcp":pj.PJSIP_TRANSPORT_TCP,"tls":pj.PJSIP_TRANSPORT_TLS}[profile["transport"]],tc)
        self.ep.libStart();self.ep.audDevManager().setNullDev()
        fmt=pj.MediaFormatAudio();fmt.type=pj.PJMEDIA_TYPE_AUDIO;fmt.clockRate=16000;fmt.channelCount=1;fmt.bitsPerSample=16;fmt.frameTimeUsec=20000
        self.source=Source();self.source.createPort("call-assistant-tx",fmt);self.sink=Sink();self.sink.createPort("call-assistant-rx",fmt)
        ac=pj.AccountConfig();ac.idUri=f"sip:{profile.get('caller_id') or profile['username']}@{profile['domain']}"
        scheme="sips" if profile["transport"]=="tls" else "sip"
        ac.regConfig.registrarUri=f"{scheme}:{profile['registrar']}:{profile['port']};transport={profile['transport']}"
        if self.test.get("local"):
            ac.regConfig.registrarUri="";ac.regConfig.registerOnAdd=False;self.registered=True;self.removed=True
        ac.regConfig.timeoutSec=120;ac.sipConfig.transportId=transport
        ac.regConfig.retryIntervalSec=0;ac.regConfig.firstRetryIntervalSec=0
        ac.natConfig.sdpNatRewriteUse=1
        ac.sipConfig.authCreds.append(pj.AuthCredInfo("digest","*",profile.get("auth_id") or profile["username"],0,password))
        if profile.get("proxy"):ac.sipConfig.proxies.append(f"{scheme}:{profile['proxy']};transport={profile['transport']};lr")
        self.account=Account();self.account.create(ac);self.call=None
        self.transport_address=str(self.ep.transportGetInfo(transport).localAddress)
    def event(self,kind,**data):
        with (self.root/"native-events.jsonl").open("a") as f:f.write(json.dumps({"time":time.time(),"kind":kind,**data})+"\n")
    def inspect(self):
        if self.call and self.media_ready and time.monotonic()-self.last_rtp>1:
            try:
                stats=self.call.getStreamStat(0)
                self.rtp={"rx_packets":int(stats.rtcp.rxStat.pkt),"tx_packets":int(stats.rtcp.txStat.pkt),"rx_loss":int(stats.rtcp.rxStat.loss)}
            except Exception:pass
            self.last_rtp=time.monotonic()
        return {"registered":self.registered,"registration_active":self.reg_active,"registration_removed":self.removed,"registration_code":self.registration_code,"connected":self.connected,"disconnected":self.disconnected,"media_ready":self.media_ready,"audio_dropped":self.audio_dropped,"received_frames":self.received_frames,"sent_frames":self.sent_frames,"buffer_frames":len(self.tx),"paused":self.paused,"takeover":self.takeover,"media_callbacks":self.media_callbacks,"media_error":self.media_error,"media":self.media_observations,"call_code":self.last_call_code,"transport_address":self.transport_address,"rtp":self.rtp,"sent_voice_frames":self.sent_voice_frames,"received_voice_frames":self.received_voice_frames}
    def command(self,r):
        pj=self.pj;kind=r["command"]
        if kind=="dial":
            if not self.registered or self.calls or self.dial_blocked:raise RuntimeError("One admitted outbound dial only after registration and before cancellation")
            number=r["number"]
            if not number.startswith("+") or not number[1:].isdigit():raise ValueError("E164 destination required")
            target=number
            if self.test.get("dial_target"):
                if number!=self.test.get("expected_destination") or self.test["dial_target"] not in {"1","2"}:raise ValueError("Unapproved internal test target")
                target=self.test["dial_target"]
            self.calls+=1;self.call=self.Call(self.account);op=pj.CallOpParam(True);self.call.makeCall(f"sip:{target}@{self.config['sip']['domain']}",op)
        elif kind=="read":
            rx=self.rx.popleft() if self.rx else bytes(640)
            return {**self.inspect(),"rx_queued":len(self.rx),"rx":base64.b64encode(rx).decode(),"tx":base64.b64encode(self.last_tx).decode()}
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
        elif kind=="unregister":
            if not self.test.get("local"):self.account.setRegistration(False)
        elif kind!="inspect":raise ValueError("Unknown endpoint command")
        return self.inspect()
    def close(self):
        self.call=None
        if self.account:
            self.account.shutdown()
            self.account=None
        self.source=None;self.sink=None
        gc.collect()
        self.ep.libDestroy()

def main():
    config=json.loads(Path(sys.argv[1]).read_text());root=Path(config["root"])/"work/calls"/config["call_id"]
    endpoint=Endpoint(config);path=root/"sip.sock"
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as server:
        server.bind(str(path));path.chmod(0o600);server.listen(8);server.settimeout(.005)
        try:
            while True:
                lease=json.loads((root/"lease.json").read_text())
                if time.monotonic()>lease["expires"]:break
                endpoint.ep.libHandleEvents(1)
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
