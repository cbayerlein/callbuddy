"""Switch the operator's OpenAI live profile without rewriting call evidence."""
import argparse,json
from pathlib import Path
from .store import Store

def upgrade(store):
    if any(c.get('status') not in {'completed','cancelled','failed','inconclusive'} for c in store.list('call')):
        raise RuntimeError('An app call is active; postpone migration')
    current=store.get('operator-model-openai')
    if not current or not current.get('credential_ref'):raise RuntimeError('Existing OpenAI credential missing')
    if current.get('model')!='gpt-live-1' and not store.get('operator-model-openai-realtime'):
        previous={**current,'id':'operator-model-openai-realtime','name':'OpenAI Realtime – previous comparison baseline'}
        store.put(previous['id'],'model',previous)
    profile={**current,'model':'gpt-live-1','backend_model':'gpt-6-luna','name':'OpenAI GPT-Live 1 – Deutsch','purpose':'live'}
    store.put(profile['id'],'model',profile)
    settings=store.get('settings') or {};settings.update(default_model=profile['id'],model_selection='manual')
    store.put('settings','system',settings)
    changed=[]
    for b in store.list('brief'):
        if b.get('model_profile')==profile['id'] and b.get('accepted'):
            b.update(accepted=False,revision=b.get('revision',0)+1);store.put(b['id'],'brief',b);changed.append(b['id'])
    return {'model':profile['model'],'backend_model':profile['backend_model'],'reconfirm_briefs':changed,'secrets_rotated':False,'historical_calls_unchanged':True}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--state',type=Path,required=True);p.add_argument('--credentials',type=Path,required=True)
    a=p.parse_args();print(json.dumps(upgrade(Store(a.state/'work',a.credentials))))
if __name__=='__main__':main()
