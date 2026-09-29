import io
import unittest
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from probe import check, run
class Response(io.BytesIO):
    def __init__(self,code,body=b'ready'):
        super().__init__(body);self.code=code
class Fake:
    def __init__(self,items): self.items=iter(items);self.calls=0
    def open(self,*args,**kwargs):
        self.calls+=1
        value=next(self.items)
        if isinstance(value,Exception): raise value
        return value
class ProbeTests(unittest.TestCase):
    def test_healthy(self):
        f=Fake([Response(200)])
        self.assertTrue(check('http://localhost/ready',marker='ready',opener=f)['healthy'])
        self.assertEqual(f.calls,1)
    def test_transient_recovery(self):
        f=Fake([Response(503),Response(200)])
        waits=[]
        r=check('http://localhost',opener=f,sleep=waits.append)
        self.assertTrue(r['healthy']);self.assertEqual(len(r['observations']),2);self.assertEqual(waits,[0.1])
    def test_permanent_not_retried(self):
        f=Fake([Response(404)])
        self.assertFalse(check('http://localhost',opener=f)['healthy']);self.assertEqual(f.calls,1)
    def test_content_mismatch(self):
        r=check('http://localhost',marker='ready',opener=Fake([Response(200,b'login')]))
        self.assertEqual(r['observations'][0]['category'],'content_mismatch')
    def test_transport_failure_bounded(self):
        f=Fake([URLError('private detail'),URLError('private detail')])
        r=check('http://localhost',opener=f,sleep=lambda _:None)
        self.assertEqual(f.calls,2);self.assertFalse(r['healthy']);self.assertNotIn('private detail',str(r))
    def test_http_error_closed(self):
        body=io.BytesIO(b'not found')
        error=HTTPError('http://localhost',404,'missing',{},body)
        self.assertFalse(check('http://localhost',opener=Fake([error]))['healthy'])
        self.assertTrue(body.closed)
    def test_response_cap(self):
        r=check('http://localhost',opener=Fake([Response(200,b'x'*65537)]))
        self.assertEqual(r['observations'][0]['category'],'body_too_large')
    def test_sensitive_or_invalid_url(self):
        for url in ['file:///etc/passwd','http://user:pass@localhost','http://localhost/?token=abc','http://localhost/#secret']:
            with self.assertRaises(ValueError): check(url)
    def test_config_boundaries(self):
        for config in [[],[{'url':'http://localhost'}]*21,[{'url':'http://localhost','unknown':1}]]:
            with self.assertRaises(ValueError): run(config)
    def test_invalid_retry_limits(self):
        for kwargs in [{'attempts':0},{'attempts':6},{'timeout':0},{'timeout':31}]:
            with self.assertRaises(ValueError): check('http://localhost',**kwargs)

class HTTPIntegrationTests(unittest.TestCase):
    def test_redirect_not_followed_and_real_503_bounded(self):
        hits=[]
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                hits.append(self.path)
                if self.path=='/redirect':
                    self.send_response(302)
                    self.send_header('Location','/destination')
                else:
                    self.send_response(503)
                self.end_headers()
            def log_message(self,*args): pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            origin=f'http://127.0.0.1:{server.server_port}'
            redirected=check(origin+'/redirect')
            self.assertFalse(redirected['healthy'])
            self.assertEqual(redirected['observations'][0]['status'],302)
            self.assertEqual(hits,['/redirect'])
            failed=check(origin+'/broken',sleep=lambda _:None)
            self.assertEqual(len(failed['observations']),2)
            self.assertEqual(hits,['/redirect','/broken','/broken'])
        finally:
            server.shutdown();server.server_close();thread.join()
