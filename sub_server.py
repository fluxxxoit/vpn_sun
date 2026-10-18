#!/usr/bin/env python3
import os
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger('subserver')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SUBS_DIR = os.path.join(BASE_DIR, 'subscriptions')
PORT = int(os.environ.get('PORT', 8080))

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/status':
            self.serve_status()
            return
        
        name = None
        if self.path.startswith('/sub/'):
            name = self.path[5:].strip('/')
        elif self.path == '/sub':
            name = 'default'
        
        if name:
            self.serve_sub(name)
        else:
            self.send_error(404)

    def serve_sub(self, name):
        safe_name = os.path.basename(name)
        file_path = os.path.join(SUBS_DIR, f'{safe_name}.txt')
        
        if not os.path.exists(file_path):
            self.send_error(404, f'Subscription {safe_name} not found')
            return
        
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read().strip()
        
        if not text:
            self.send_error(503, 'Subscription is empty')
            return
        
        body = (text + '\n').encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.end_headers()
        self.wfile.write(body)
        log.info(f'GET /sub/{safe_name} -> served')

    def serve_status(self):
        subs = []
        if os.path.exists(SUBS_DIR):
            subs = [f for f in os.listdir(SUBS_DIR) if f.endswith('.txt')]
        body = f'OK\nTotal subscriptions: {len(subs)}\nNames: {", ".join(subs)}\n'.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        log.info(f'{self.address_string()} - {fmt % args}')

if __name__ == '__main__':
    os.makedirs(SUBS_DIR, exist_ok=True)
    log.info(f'Starting server on port {PORT}')
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    log.info(f'Server ready. Subs dir: {SUBS_DIR}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info('Shutdown')
