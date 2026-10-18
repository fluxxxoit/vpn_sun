#!/usr/bin/env python3

import os
import base64
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
log = logging.getLogger('subserver')

CONFIG_FILE = 'alive_configs.txt'
PORT = int(os.environ.get('PORT', 8080))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ('/', '/sub', '/subscription'):
            self.serve_subscription()
        elif self.path == '/plain':
            self.serve_plain()
        elif self.path == '/status':
            self.serve_status()
        else:
            self.send_error(404)

    def serve_subscription(self):
        try:
            if not os.path.exists(CONFIG_FILE):
                self.send_error(503, 'No configs yet')
                return
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                configs = [l.strip() for l in f if l.strip()]
            raw = '\n'.join(configs).encode()
            b64 = base64.b64encode(raw).decode()

            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(b64)))
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.end_headers()
            self.wfile.write(b64.encode())
            log.info('GET /sub -> %d configs', len(configs))
        except Exception as e:
            log.error('/sub error: %s', e)
            self.send_error(500)

    def serve_plain(self):
        try:
            if not os.path.exists(CONFIG_FILE):
                self.send_error(503, 'No configs yet')
                return
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                text = f.read().strip()

            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.end_headers()
            self.wfile.write(text.encode())
            count = len([l for l in text.split('\n') if l.strip()])
            log.info('GET /plain -> %d configs', count)
        except Exception as e:
            log.error('/plain error: %s', e)
            self.send_error(500)

    def serve_status(self):
        try:
            exists = os.path.exists(CONFIG_FILE)
            count = 0
            if exists:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    count = len([l for l in f if l.strip()])
            body = ('OK\nconfigs: %d\nfile_exists: %s\n' % (count, exists)).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            log.info('GET /status -> %d configs', count)
        except Exception:
            self.send_error(500)

    def log_message(self, fmt, *args):
        log.info('%s - %s', self.address_string(), fmt % args)


if __name__ == '__main__':
    log.info('Starting server on port %d', PORT)
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    log.info('Server ready')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info('Shutdown')
