#!/usr/bin/env python3
import os
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
log = logging.getLogger('subserver')

# Файл, в который бот записывает ссылки
CONFIG_FILE = 'alive_configs.txt'
PORT = int(os.environ.get('PORT', 8080))

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Любой из этих путей отдаёт список конфигов в чистом виде
        if self.path in ('/', '/sub', '/subscription', '/plain'):
            self.serve_plain()
        elif self.path == '/status':
            self.serve_status()
        else:
            self.send_error(404)

    def _read_configs(self):
        if not os.path.exists(CONFIG_FILE):
            return None
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]

    def serve_plain(self):
        configs = self._read_configs()
        if configs is None:
            self.send_error(503, 'No configs yet')
            return
        
        text = '\n'.join(configs)
        
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.end_headers()
        self.wfile.write(text.encode())
        log.info(f'GET {self.path} -> {len(configs)} configs')

    def serve_status(self):
        configs = self._read_configs()
        count = len(configs) if configs else 0
        body = f'OK\nconfigs: {count}\nfile_exists: {configs is not None}\n'.encode()
        
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        log.info(f'GET /status -> {count} configs')

    def log_message(self, fmt, *args):
        log.info(f'{self.address_string()} - {fmt % args}')

if __name__ == '__main__':
    log.info(f'Starting server on port {PORT}')
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    log.info('Server ready')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info('Shutdown')
