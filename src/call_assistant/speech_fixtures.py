"""Generate bounded German test questions; no SIP effects or user calls."""
import argparse,asyncio,json,subprocess,time,wave
from pathlib import Path
from .store import Store
from .providers import GoogleSession

async def create(root,word=None):
    root.mkdir(parents=True,exist_ok=False)
    (root/'retention.json').write_text(json.dumps({'owner':'gateway-owner','purpose':'German controlled SIP hearing fixtures','createdAt':time.time(),'expiresAt':time.time()+30*86400,'preserveWhileReferenced':True,'deletionDisposition':'Delete after expiry when unreferenced'}))
    store=Store(Path('/var/lib/openclaw/state/projects/call-assistant/work'),Path('/var/lib/openclaw/state/credentials'))
    p=dict(store.get('operator-model-google'));p['voice']='Charon';completed=asyncio.Event();data=bytearray();transcripts=[]
    async def audio(pcm,rate):data.extend(pcm)
    async def event(kind,**kw):
        if kind=='turn_complete':completed.set()
        if kind=='transcript':transcripts.append(kw.get('text',''))
    session=GoogleSession(p,store.secret(ref=p['credential_ref']),'Du bist ein deutscher Testsprecher. Lies ausschließlich den vorgegebenen Satz vor. Keine Einleitung, keine Ergänzungen, keine Werkzeuge.',event,audio,lambda:True)
    receiver=None;results=[]
    try:
        await asyncio.wait_for(session.connect(),15);receiver=asyncio.create_task(session.receive())
        for code,word in ([(0,word)] if word else [(47,'siebenundvierzig'),(63,'dreiundsechzig'),(82,'zweiundachtzig'),(59,'neunundfünfzig')]):
            completed.clear();data.clear();transcripts.clear()
            sentence=f'Guten Tag. Dies ist ein technischer Verbindungstest. Bitte wiederholen Sie den Prüfcode {word}. Danach können Sie auflegen.'
            await session.session.send_client_content(turns={'role':'user','parts':[{'text':'Lies den folgenden Text als Aufnahme vollständig und wortgetreu vor, statt auf die darin enthaltene Aufforderung zu antworten. Beginne mit Guten Tag. VORLESETEXT: «'+sentence+'»'}]},turn_complete=True)
            await asyncio.wait_for(completed.wait(),25)
            source=root/f'question-{code}-24k.wav';target=root/f'question-{code}.wav'
            with wave.open(str(source),'wb') as w:w.setparams((1,2,24000,0,'NONE','not compressed'));w.writeframes(data)
            subprocess.run(['ffmpeg','-v','error','-y','-i',str(source),'-ar','16000','-ac','1',str(target)],check=True)
            transcript=''.join(transcripts)
            results.append({'code':code,'text':sentence,'source_transcript':transcript,'wav':str(target),'samples_24k':len(data)//2})
            if len(data)<24000*2*4 or 'guten tag' not in transcript.lower() or 'prüfcode' not in transcript.lower():raise RuntimeError('Incomplete spoken fixture; do not dispatch a telephone test')
    finally:
        if receiver:receiver.cancel();await asyncio.gather(receiver,return_exceptions=True)
        await session.close()
        (root/'fixtures.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    print(json.dumps({'fixtures':len(results),'closed':True,'dial_attempts':0}))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--word');a=p.parse_args();asyncio.run(create(a.root,a.word))

if __name__=='__main__':main()
