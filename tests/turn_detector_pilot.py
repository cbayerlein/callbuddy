"""Bounded offline shadow comparison; no provider credentials or live effects.

This is a development screening on model-generated speech, not human-language
qualification. Internal playback pauses are operational hold labels, not an
independent semantic gold standard. Neither detector receives future PCM.
"""
import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import time
import urllib.request
import wave
from pathlib import Path

import numpy as np
import onnxruntime as ort
from scipy.signal import resample_poly
from transformers import WhisperFeatureExtractor
from livekit import rtc
from livekit.agents.inference import TurnDetector
from livekit.agents.language import LanguageCode

REVISION='f766f81d3cfdf7737ac64aad813d91bbfd56bf93'
MODEL_URL=f'https://huggingface.co/pipecat-ai/smart-turn-v3/resolve/{REVISION}/smart-turn-v3.2-cpu.onnx'


def spans(report):
    result=[]
    for role,state in report['roles'].items():
        for first in state['events']:
            if first['kind']!='direct_audio.first_delivered_pcm':continue
            last=next((r for r in state['events'] if r['kind']=='direct_audio.playback_finished'
                and r.get('response_id')==first['response_id'] and r.get('recording_end_sample_24k') is not None),None)
            if last:result.append({'role':role,'channel':0 if role=='caller' else 1,
                'start':first['recording_sample_24k'],'end':last['recording_end_sample_24k']})
    return sorted(result,key=lambda r:r['start'])


def cases(pcm,segments):
    result=[]
    for index,segment in enumerate(segments[:4]):
        data=resample_poly(pcm[segment['start']:segment['end'],segment['channel']].astype(np.float32),2,3)
        frames=len(data)//320
        if frames<40:continue
        voiced=np.sqrt(np.mean(data[:frames*320].reshape(-1,320)**2,axis=1))>=150
        active=np.flatnonzero(voiced)
        if not active.size:continue
        # Entire delivered turn is preserved; silence is added, never removed.
        final=np.concatenate((data,np.zeros(4000,dtype=np.float32)))
        result.append({'id':f'{index}-end','label':'end','role':segment['role'],
            'pcm':final,'detector_action_delay_ms':round(1000*(len(final)/16000-(active[-1]+1)*.02),2)})
        holds=[];start=None
        for f in range(int(active[0])+1,int(active[-1])):
            if not voiced[f] and start is None:start=f
            if voiced[f] and start is not None:
                if f-start>=15 and start>=25 and active[-1]-f>=20:holds.append((start,f))
                start=None
        if holds:
            begin,end=max(holds,key=lambda p:p[1]-p[0])
            cut=begin*320+4000
            assert cut<=end*320
            result.append({'id':f'{index}-hold','label':'hold','role':segment['role'],
                'pcm':data[:cut],'detector_action_delay_ms':250,'internal_pause_ms':(end-begin)*20})
    return result


async def livekit_predict(detector,pcm):
    stream=detector.stream()
    try:
        samples=np.clip(pcm,-32768,32767).astype(np.int16)
        for offset in range(0,len(samples),320):
            frame=samples[offset:offset+320]
            stream.push_audio(rtc.AudioFrame(data=frame.tobytes(),sample_rate=16000,num_channels=1,samples_per_channel=len(frame)))
        # Verify ingress at the pinned SDK transport before requesting prediction.
        deadline=time.monotonic()+1
        expected=min(len(samples),19200)
        while len(stream._transport._buf.read())!=expected:
            if time.monotonic()>deadline:raise TimeoutError('Framework audio ingress incomplete')
            await asyncio.sleep(.001)
        started=time.perf_counter()
        event=await asyncio.wait_for(stream.predict(),timeout=5)
        elapsed=(time.perf_counter()-started)*1000
        threshold=await stream.unlikely_threshold(LanguageCode('de'))
        return {'probability':float(event.end_of_turn_probability),'threshold':threshold,
                'prediction_ms':elapsed,'complete':event.end_of_turn_probability>=threshold}
    finally:await stream.aclose()


async def run(args):
    model=args.work/'smart-turn-v3.2-cpu.onnx';args.work.mkdir(parents=True,exist_ok=True)
    if not model.exists():
        with urllib.request.urlopen(MODEL_URL,timeout=30) as response:model.write_bytes(response.read(16*1024*1024))
    options=ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1
    options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
    session=ort.InferenceSession(str(model),sess_options=options,providers=['CPUExecutionProvider'])
    extractor=WhisperFeatureExtractor(chunk_length=8)
    detector=TurnDetector(version='v1-mini')
    if not await detector.supports_language(LanguageCode('de')):raise RuntimeError('German unavailable')
    with wave.open(str(args.audio),'rb') as wav:
        assert wav.getframerate()==24000 and wav.getnchannels()==2 and wav.getsampwidth()==2
        pcm=np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2').reshape(-1,2)
    selected=cases(pcm,spans(json.loads(args.source_report.read_text())))
    if args.human_corpus:
        selected=[]
        for row in json.loads(args.human_corpus.read_text())['rows']:
            with wave.open(row['audio'],'rb') as wav:
                assert wav.getframerate()==16000 and wav.getnchannels()==1 and wav.getsampwidth()==2
                data=np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2').astype(np.float32)
            pauses=row['silence_spans'];hold=next(p for p in pauses[:-1] if p['end']-p['start']>=.3)
            for label,pause in [('hold',hold),('end',pauses[-1])]:
                cut=round((pause['start']+.25)*16000)
                if cut>len(data):raise ValueError('Annotated silence too short for fixed action delay')
                selected.append({'id':f'{row["row_idx"]}-{label}','label':label,'role':'human',
                    'pcm':data[:cut],'detector_action_delay_ms':250,'public_row':row['row_idx']})
    results=[]
    for case in selected:
        data=case.pop('pcm');started=time.perf_counter()
        array=data[-128000:]/32768.;array=np.pad(array,(128000-len(array),0))
        features=extractor(array,sampling_rate=16000,return_tensors='np',padding='max_length',max_length=128000,truncation=True,do_normalize=True)
        probability=float(session.run(None,{'input_features':features.input_features.astype(np.float32)})[0].reshape(-1)[0])
        smart={'probability':probability,'threshold':.5,'prediction_ms':(time.perf_counter()-started)*1000,'complete':probability>.5}
        livekit=await livekit_predict(detector,data)
        results.append({**case,'causal_input_samples':len(data),'smart_turn':smart,'livekit_agents_mini':livekit})
    summary={}
    for name in ('smart_turn','livekit_agents_mini'):
        rows=[r for r in results if r['label']=='hold'];ends=[r for r in results if r['label']=='end']
        summary[name]={'hold_cases':len(rows),'false_cutoffs':sum(r[name]['complete'] for r in rows),
            'end_cases':len(ends),'recognized_ends':sum(r[name]['complete'] for r in ends),
            'median_prediction_ms':float(np.median([r[name]['prediction_ms'] for r in results]))}
    report={'development_only':True,'production_promoted':False,'human_gold_labels':bool(args.human_corpus),
        'livekit_used_through_agents_framework':True,'source_audio_sha256':hashlib.sha256(args.audio.read_bytes()).hexdigest(),
        'model_sha256':hashlib.sha256(model.read_bytes()).hexdigest(),'model_revision':REVISION,
        'versions':{n:importlib.metadata.version(n) for n in ('livekit-agents','livekit-local-inference','onnxruntime','transformers')},
        'new_paid_model_sessions':0,'dials':0,'summary':summary,'cases':results}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2))
    print(json.dumps({'summary':summary,'case_count':len(results),'production_promoted':False}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio',type=Path,required=True);parser.add_argument('--source-report',type=Path,required=True)
    parser.add_argument('--work',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--human-corpus',type=Path)
    asyncio.run(run(parser.parse_args()))
