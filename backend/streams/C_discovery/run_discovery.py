"""CLI client of the same authenticated Ask/Discover search. No separate provider."""
import argparse,json,os
from urllib.request import Request,urlopen

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--query',required=True)
    parser.add_argument('--url',default='http://127.0.0.1:8000')
    args=parser.parse_args(argv)
    from urllib.parse import urlsplit
    endpoint=urlsplit(args.url)
    if endpoint.scheme!='https' and not (endpoint.scheme=='http' and endpoint.hostname in ('127.0.0.1','localhost')):raise SystemExit('Use HTTPS or a localhost server.')
    token=os.getenv('CHANDELLE_MEMBER_TOKEN','')
    if not token:raise SystemExit('Set CHANDELLE_MEMBER_TOKEN locally. Do not paste it into chat.')
    request=Request(args.url.rstrip('/')+'/api/v2/dates/search',data=json.dumps({'constraints':{'text':args.query,'mode':'auto'}}).encode(),headers={'Content-Type':'application/json','X-Member-Token':token},method='POST')
    with urlopen(request,timeout=60) as response:result=json.loads(response.read())
    print(json.dumps({'status':result['status'],'count':len(result['activities']),'message':result['message'],'trace':result['trace']},ensure_ascii=False))
    return 0

if __name__=='__main__':raise SystemExit(main())
