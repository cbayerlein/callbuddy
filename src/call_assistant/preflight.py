"""Bounded account checks. Explicit --register never dials or starts model audio."""
import argparse
import asyncio
import json
import time
from pathlib import Path

from .providers import check_account
from .store import Store


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',type=Path,required=True)
    parser.add_argument('--credentials',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--register',action='store_true')
    args=parser.parse_args()
    store=Store(args.state/'work',args.credentials)
    model=store.get('operator-model-openai')
    result={'model':asyncio.run(check_account(model,store.secret(ref=model['credential_ref']))),
            'dial_attempts':0,'model_audio_sessions':0,'sip_registration_tested':False}
    if args.register:
        if any(c['status'] not in {'completed','cancelled','failed','inconclusive'} for c in store.list('call')):
            raise RuntimeError('An application call is active; do not interfere')
        from .sip import Endpoint
        endpoint=None
        try:
            endpoint=Endpoint({'root':str(args.state),'credential_root':str(args.credentials),
                'call_id':'account-preflight','sip':store.get('operator-sip-fonial')})
            deadline=time.monotonic()+12
            while time.monotonic()<deadline and not endpoint.registered:
                endpoint.ep.libHandleEvents(20)
            result['sip_registration_tested']=True
            result['registration']=endpoint.inspect()
        finally:
            if endpoint:
                try:
                    endpoint.command({'command':'hangup'})
                    if endpoint.reg_active:
                        endpoint.command({'command':'unregister'})
                        deadline=time.monotonic()+8
                        while time.monotonic()<deadline and not endpoint.removed:
                            endpoint.ep.libHandleEvents(20)
                    result['removal']=endpoint.inspect()
                finally:
                    endpoint.close()
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(result,indent=2))
    print(json.dumps(result))
    if not result['model']['ready']:raise SystemExit(2)
    if args.register and not (result['registration']['registered'] and result['removal']['registration_removed']):raise SystemExit(2)


if __name__=='__main__':main()
