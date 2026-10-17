"""Retrieve four public German human turns with annotated internal pauses."""
import argparse
import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args();args.root.mkdir(parents=True,exist_ok=True)
    # Read-only row inventory confirmed row 500 is German. Avoid the slow
    # remote SQL filter; preserve this fixed window before model scoring.
    selected=[]
    for index in range(500,530):
        query=urllib.parse.urlencode({'dataset':'livekit/eot-bench-data','config':'all','split':'validation',
            'offset':index,'length':1})
        with urllib.request.urlopen('https://datasets-server.huggingface.co/rows?'+query,timeout=10) as response:
            data=json.load(response)
        if not data.get('rows'):break
        row=data['rows'][0]
        value=row['row'];spans=value['silence_spans']
        if value['language']!='de' or not any(p['end']-p['start']>=.3 for p in spans[:-1]):continue
        path=args.root/f'german-row-{row["row_idx"]}.wav'
        if not path.exists():
            with urllib.request.urlopen(value['audio'][0]['src'],timeout=20) as response:
                content=response.read(2*1024*1024)
            path.write_bytes(content)
        selected.append({'row_idx':row['row_idx'],'id':value['id'],'language':'de',
            'audio':str(path),'audio_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'silence_spans':spans})
        if len(selected)==4:break
    if len(selected)!=4:raise RuntimeError('Insufficient matching public turns; do not substitute labels')
    manifest={'dataset':'livekit/eot-bench-data','split':'validation','license':'Apache-2.0',
        'selection':'First four matching German rows in fixed window 500:530 with an internal annotated pause >=300ms; no detector scores used',
        'rows':selected}
    (args.root/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps({'human_turns':len(selected),'row_indices':[r['row_idx'] for r in selected]}))


if __name__=='__main__':main()
