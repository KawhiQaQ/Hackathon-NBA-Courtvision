"""AgentCore HTTP protocol probe: deliberately has no model dependencies."""

import json
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

INSTANCE_ID = str(uuid.uuid4())


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, body):
        data = json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == '/ping':
            self.reply(200, {'status': 'Healthy'})
        else:
            self.reply(404, {'error': 'Not found'})

    def do_POST(self):
        if self.path != '/invocations':
            return self.reply(404, {'error': 'Not found'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size < 1 or size > 1024:
                return self.reply(400, {'error': 'Invalid payload size'})
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict) or body.get('action') != 'ping':
                return self.reply(400, {'error': 'Only action=ping is supported'})
            nonce = body.get('nonce')
            if not isinstance(nonce, str) or not 1 <= len(nonce) <= 64:
                return self.reply(400, {'error': 'Invalid nonce'})
        except (ValueError, UnicodeDecodeError):
            return self.reply(400, {'error': 'Invalid JSON'})
        self.reply(200, {
            'ok': True,
            'service': 'Amazon Bedrock AgentCore Runtime',
            'mode': 'connectivity-probe',
            'modelInvoked': False,
            'nonce': nonce,
            'instanceId': INSTANCE_ID,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'message': 'AgentCore 已收到请求并完成处理。',
        })


if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
