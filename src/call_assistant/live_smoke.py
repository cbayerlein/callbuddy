"""Bounded model-only readiness check. No SIP, no dial, no automatic retries."""
import argparse,asyncio,json,time,wave
from pathlib import Path
from .store import Store
from .live import LiveSession

async def check(state,credentials,output,fixture=None,exercise_delegation=False):
    pcm=None
    if fixture:
        with wave.open(str(fixture),'rb') as f:
            if (f.getnchannels(),f.getsampwidth(),f.getframerate())!=(1,2,24000) or f.getnframes()>12*24000:raise ValueError('Fixture must be mono PCM16 24 kHz, at most 12 seconds')
            pcm=f.readframes(f.getnframes())
    # Exclusive intent file prevents accidentally replaying an interrupted check.
    with output.open('x') as f:json.dump({'state':'started','time':time.time(),'maximum_seconds':40,'sip':False},f)
    store=Store(state/'work',credentials);profile=store.get('operator-model-openai')
    profile={**profile,'model':'gpt-live-1','backend_model':'gpt-6-luna'}
    observations=[]
    async def event(kind,**data):
        observations.append({'kind':kind,**data})
        if kind=='tool':
            if exercise_delegation and data['name']=='ask_user':
                await session.answer(data['id'],'This is a synthetic test reply from the private operator: permission is declined. Do not confirm anything to the callee. Say that you cannot confirm, then say goodbye.')
                observations.append({'kind':'synthetic_private_reply_delivered','approved':False})
            elif data['name']=='finish_call':
                await session.answer(data['id'],'No telephone call exists; this is only a model check. No external action performed.',name='finish_call')
    samples=0
    async def audio(pcm,rate):
        nonlocal samples
        if pcm.strip(b'\x00'):samples+=len(pcm)//2
    prompt='No telephone call is in progress. Listen silently. Do not delegate tasks.' if pcm is None else 'BESTÄTIGTER STECKBRIEF: Technischer Hörtest auf Deutsch. Höre die Äußerung der Gegenstelle und wiederhole den von ihr genannten Prüfcode einmal hörbar als vollständiges Wort. Antworte kurz, keine sonstigen Aktionen.'
    if exercise_delegation:prompt='BESTÄTIGTER STECKBRIEF: Kontrollierter Modelltest. Bevor du auf den gehörten Prüfcode antwortest, ist eine ausdrückliche private Nutzerentscheidung nötig. Delegiere diese Entscheidung an das Backend; es muss ask_user aufrufen und die Werkzeugantwort abwarten. Nie den Code bestätigen oder eine Freigabe erfinden. Nach einer Ablehnung sage kurz, dass keine Bestätigung möglich ist, und verabschiede dich.'
    session=LiveSession(profile,store.secret(ref=profile['credential_ref']),prompt,event,audio,lambda:True)
    receiver=None;result={'state':'failed','sip':False}
    try:
        await session.connect();receiver=asyncio.create_task(session.receive());ready=asyncio.create_task(session.ready.wait())
        try:
            done,_=await asyncio.wait({receiver,ready},timeout=10,return_when=asyncio.FIRST_COMPLETED)
            if receiver in done:await receiver;raise RuntimeError('Live closed before readiness')
            if ready not in done:raise TimeoutError('Live startup acknowledgement missing')
        finally:
            ready.cancel();await asyncio.gather(ready,return_exceptions=True)
        for _ in range(60):
            await session.input(bytes(960));await asyncio.sleep(.02)
            if receiver.done():await receiver;raise RuntimeError('Live ended during readiness check')
        if pcm is not None:
            for i in range(0,len(pcm),960):
                await session.input(pcm[i:i+960].ljust(960,b'\x00'));await asyncio.sleep(.02)
                if receiver.done():await receiver;raise RuntimeError('Live ended during audio check')
            for _ in range(350):
                await session.input(bytes(960));await asyncio.sleep(.02)
                if receiver.done():await receiver;raise RuntimeError('Live ended before speech completed')
                if samples>12000 and time.monotonic()-session.last_audio>1:break
            if samples<12000:raise RuntimeError('No substantive voice output received')
        result['state']='ready'
        if exercise_delegation and not any(e['kind']=='synthetic_private_reply_delivered' for e in observations):raise RuntimeError('Delegated private decision was not exercised')
    except Exception as exc:result.update(state='failed',error_type=type(exc).__name__,error=str(exc)[:1200])
    finally:
        await session.close()
        if receiver:receiver.cancel();await asyncio.gather(receiver,return_exceptions=True)
        result.update(finalized=session.finalized,output_samples=samples,observations=observations)
        output.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False))
    return 0 if result['state']=='ready' and session.finalized else 1

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--state',type=Path,required=True);p.add_argument('--credentials',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--fixture',type=Path);p.add_argument('--exercise-delegation',action='store_true')
    a=p.parse_args();raise SystemExit(asyncio.run(asyncio.wait_for(check(a.state,a.credentials,a.output,a.fixture,a.exercise_delegation),timeout=45)))
if __name__=='__main__':main()
