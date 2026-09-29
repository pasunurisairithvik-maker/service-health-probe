"""A healthy endpoint and a failing endpoint on localhost; no external requests."""
import json
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from probe import run
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200 if self.path=='/ready' else 503)
        self.end_headers()
        self.wfile.write(b'ready' if self.path=='/ready' else b'unavailable')
    def log_message(self,*args): pass
if __name__=='__main__':
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        origin=f'http://127.0.0.1:{server.server_port}'
        report=run([{'url':origin+'/ready','marker':'ready'}, {'url':origin+'/broken'}])
        Path('results').mkdir(exist_ok=True)
        Path('results/demo.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        server.shutdown();server.server_close();thread.join()
