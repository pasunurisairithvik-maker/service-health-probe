"""Bounded, read-only HTTP health probing; no automatic repair or alert sending."""
import argparse
import json
from http.client import HTTPException
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def check(url, timeout=2, attempts=2, expected_status=200, marker=None, opener=None, sleep=time.sleep):
    parsed=urlparse(url)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Use an HTTP(S) URL without credentials, query parameters, or fragments')
    if (type(timeout) not in (int,float) or not 0<timeout<=30
        or type(attempts) is not int or not 1<=attempts<=5
        or type(expected_status) is not int or not 100<=expected_status<=599
        or (marker is not None and not isinstance(marker,str))):
        raise ValueError('Invalid timeout, attempt count, or expected status')
    client=opener or build_opener(NoRedirect())
    observations=[]
    for i in range(attempts):
        started=time.monotonic()
        status=None
        category='network_error'
        try:
            try:
                response=client.open(Request(url,headers={'User-Agent':'student-health-probe/1.0'}),timeout=timeout)
            except HTTPError as exc:
                response=exc
            with response:
                status=response.code
                body=response.read(65537)
            if status!=expected_status:
                category='unexpected_status'
            elif len(body)>65536:
                category='body_too_large'
            elif marker is not None and marker not in body.decode('utf-8',errors='replace'):
                category='content_mismatch'
            else:
                category='healthy'
        except (URLError,TimeoutError,OSError,HTTPException):
            category='network_error'
        observations.append({'attempt':i+1,'status':status,'category':category,'elapsed_ms':round((time.monotonic()-started)*1000,3)})
        if category=='healthy': break
        # Retry transport errors and transient HTTP 5xx only; avoid repeatedly probing permanent errors.
        if i+1==attempts or not (category=='network_error' or (status is not None and 500<=status<=599)):
            break
        sleep(min(0.1*2**i,1))
    return {'url':url,'healthy':observations[-1]['category']=='healthy','observations':observations}

def run(config):
    if not isinstance(config,list) or not 1<=len(config)<=20:
        raise ValueError('Configure 1 to 20 targets')
    allowed={'url','timeout','attempts','expected_status','marker'}
    for target in config:
        if not isinstance(target,dict) or 'url' not in target or set(target)-allowed:
            raise ValueError('Invalid target fields')
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda target:check(**target),config))
    return {'checked_at':datetime.now(timezone.utc).isoformat(),'all_healthy':all(r['healthy'] for r in results),'results':results}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config')
    parser.add_argument('--output',default='health-report.json')
    args=parser.parse_args()
    try:
        with open(args.config) as handle: report=run(json.load(handle))
        with open(args.output,'w') as handle: json.dump(report,handle,indent=2)
        print('HEALTHY' if report['all_healthy'] else 'UNHEALTHY')
        raise SystemExit(0 if report['all_healthy'] else 1)
    except (ValueError,TypeError,OSError) as exc:
        parser.error(str(exc))
