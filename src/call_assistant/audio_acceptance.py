"""Bounded two-process audio acceptance using the product's native endpoint."""
import argparse,base64,hashlib,json,math,os,signal,socket,subprocess,sys,time,wave
from pathlib import Path
import numpy as np
from .sip import rpc

def port():
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]

def tone(hz):return (np.sin(2*np.pi*hz*np.arange(16000)/16000)*7000).astype('<i2').tobytes()

def score(data,hz):
    x=np.frombuffer(data,dtype='<i2').astype(float)
    if len(x)<1600:return {'passed':False,'samples':len(x)}
    # Search 100-ms windows so codec startup/jitter does not dilute the signal.
    best=0.;peak=0.
    for i in range(0,len(x)-1600+1,800):
        part=x[i:i+1600];power=float(np.mean(part*part))
        if power<10000:continue
        phase=np.arange(1600)*2*np.pi*hz/16000
        ratio=2*abs(np.sum(part*np.exp(-1j*phase)))**2/(1600**2*power)
        if ratio>best:best=float(ratio);peak=math.sqrt(power)
    return {'passed':best>.55,'frequency_hz':hz,'matched_power_ratio':round(best,4),'rms':round(peak,2),'samples':len(x)}

class Pair:
    def __init__(self,root,profiles,tests,credentials):
        self.root=root;self.peers=[]
        if not all(t.get('local') for t in tests):
            from .store import Store
            Store(root/'work',credentials)
        for i in range(len(profiles)):
            d=root/'work/calls'/str(i);d.mkdir(parents=True,exist_ok=True)
            config={'root':str(root),'credential_root':str(credentials),'call_id':str(i),'sip':profiles[i],'test_endpoint':tests[i]}
            path=d/'config.json';path.write_text(json.dumps(config));path.chmod(0o600)
            self.lease(d)
            log=(d/'native.log').open('wb')
            proc=subprocess.Popen([sys.executable,'-m','call_assistant.sip',str(path)],stdout=log,stderr=log);log.close()
            self.peers.append((d,proc))
        self.deadline=time.monotonic()+85
    def lease(self,d):
        p=d/'lease.tmp';p.write_text(json.dumps({'expires':time.monotonic()+5}));p.replace(d/'lease.json')
    def tick(self):
        if time.monotonic()>self.deadline:raise TimeoutError('Acceptance deadline')
        for d,p in self.peers:
            self.lease(d)
            if p.poll() is not None:raise RuntimeError('Native endpoint exited: '+str(d))
    def rpc(self,i,**r):self.tick();return rpc(self.peers[i][0]/'sip.sock',r)
    def wait(self,predicate,seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            self.tick()
            if predicate():return
            for d,process in self.peers:
                if (d/'sip.sock').exists():rpc(d/'sip.sock',{'command':'read'})
            time.sleep(.02)
        raise TimeoutError('Acceptance condition not reached')
    def close(self):
        receipts=[]
        for d,p in self.peers:
            result={'process_closed':False}
            try:
                self.lease(d);rpc(d/'sip.sock',{'command':'hangup'});rpc(d/'sip.sock',{'command':'unregister'})
                end=time.monotonic()+8
                while time.monotonic()<end:
                    for living,process in self.peers:
                        if process.poll() is None:self.lease(living)
                    result.update(rpc(d/'sip.sock',{'command':'inspect'}))
                    if result['registration_removed'] and not result['connected']:break
                    time.sleep(.05)
            except Exception as e:result['error']=type(e).__name__
            if p.poll() is None:
                p.terminate()
                try:p.wait(timeout=4)
                except subprocess.TimeoutExpired:p.kill();p.wait(timeout=3)
            result['process_closed']=p.poll() is not None;receipts.append(result)
        return receipts

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run-root',type=Path,required=True)
    p.add_argument('--fonial',action='store_true');p.add_argument('--reverse',action='store_true')
    a=p.parse_args();a.run_root.mkdir(parents=True,exist_ok=False)
    (a.run_root/'retention.json').write_text(json.dumps({'owner':'gateway-owner','purpose':'SIP audio acceptance','createdAt':time.time(),'expiresAt':time.time()+30*86400,'preserveWhileReferenced':True,'deletionDisposition':'Delete after expiry only when unreferenced'}))
    ports=[port(),port()];profiles=[{'username':str(i),'domain':'127.0.0.1:'+str(ports[1-i]),'registrar':'127.0.0.1','port':5060,'transport':'udp'} for i in range(2)]
    tests=[{'local':True,'port':ports[i],'expected_caller':str(1-i),'expires':time.time()+90} for i in range(2)]
    numbers=['+4926113493287','+492612039340']
    if a.fonial:
        from .store import Store
        store=Store(Path('/var/lib/openclaw/state/projects/call-assistant/work'),Path('/var/lib/openclaw/state/credentials'))
        if any(c.get('status') not in {'completed','cancelled','failed','inconclusive'} for c in store.list('call')):raise RuntimeError('An app call is active')
        original=json.loads(Path('/var/lib/openclaw/state/credentials/archive/fonial-sip-before-claudia-20260703T132649Z.json').read_text())
        ref='sipacceptancezoiper20261015'
        try:
            if store.secret(ref=ref)!=original['password']:raise RuntimeError('Test credential reference changed')
        except FileNotFoundError:store.secret(original['password'],ref=ref)
        profiles=[store.get('operator-sip-fonial'),{'username':original['username'],'caller_id':original['username'],'domain':original['server_url'],'registrar':original['server_url'],'port':5060,'proxy':original['proxy_url'],'transport':'udp','credential_ref':ref}]
        targets=['2','1']
        tests=[{'expected_caller':numbers[1-i],'expected_user':targets[1-i],'expires':time.time()+90,'dial_target':targets[1-i],'expected_destination':numbers[1-i]} for i in range(2)]
    result={'mode':'fonial' if a.fonial else 'local','reverse':a.reverse,'passed':False};pair=None
    try:
        runtime=a.run_root.parent.parent/('at-'+hashlib.sha256(str(a.run_root).encode()).hexdigest()[:8])
        runtime.mkdir(exist_ok=False);result['runtime_root']=str(runtime)
        pair=Pair(runtime,profiles,tests,Path('/var/lib/openclaw/state/credentials'))
        pair.wait(lambda:all((d/'sip.sock').exists() for d,_ in pair.peers),10)
        pair.wait(lambda:all(pair.rpc(i,command='inspect')['registered'] for i in range(2)),15)
        caller=1 if a.reverse else 0
        pair.rpc(caller,command='dial',number=numbers[1-caller] if a.fonial else '+123456789')
        pair.wait(lambda:all(pair.rpc(i,command='inspect')['connected'] for i in range(2)),30 if a.fonial else 8)
        pair.wait(lambda:all(pair.rpc(i,command='inspect')['media_ready'] for i in range(2)),5)
        result['directions']=[]
        for sender,hz in [(0,440),(1,660)]:
            # Remove pre-signal silence before taking the independent capture.
            for i in range(2):pair.rpc(i,command='read')
            pcm=tone(hz);pair.rpc(sender,command='write',pcm=base64.b64encode(pcm).decode())
            captures=[bytearray(),bytearray()];end=time.monotonic()+2.5
            while time.monotonic()<end:
                for i in range(2):captures[i].extend(base64.b64decode(pair.rpc(i,command='read')['rx']))
                time.sleep(.015)
            data=bytes(captures[1-sender]);report=score(data,hz);result['directions'].append(report)
            with wave.open(str(a.run_root/f'received-{1-sender}.wav'),'wb') as w:w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(data)
        result['passed']=all(r['passed'] for r in result['directions'])
    except Exception as exc:result['error']=type(exc).__name__+': '+str(exc)
    finally:
        if pair:result['cleanup']=pair.close()
        (a.run_root/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
    if not result['passed']:raise SystemExit(2)

if __name__=='__main__':main()
