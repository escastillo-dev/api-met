"""Validación HTTP de lecturas autenticadas. No evita la autorización ni la consulta SQL."""
import hashlib
import json


class ConditionalReadMiddleware:
    def __init__(self, app, max_body_bytes=2 * 1024 * 1024):
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope, receive, send):
        paths = ("/mermas/", "/caducidad/", "/recuperaciones", "/dashboard/",
                 "/productos-consumidos", "/apci/", "/mmv/")
        if scope["type"] != "http" or scope["method"] != "GET" or not scope["path"].startswith(paths):
            return await self.app(scope, receive, send)
        start = None
        chunks = []
        size = 0
        passthrough = False
        request_headers = dict(scope.get("headers", []))

        async def capture(message):
            nonlocal start, size, passthrough
            if message["type"] == "http.response.start":
                if message["status"] != 200:
                    passthrough = True
                    await send(message)
                else:
                    start = message
                return
            if passthrough or message["type"] != "http.response.body":
                await send(message)
                return
            chunk = message.get("body", b"")
            chunks.append(chunk)
            size += len(chunk)
            if size > self.max_body_bytes:
                passthrough = True
                await send(start)
                await send({**message, "body": b"".join(chunks)})
                chunks.clear()
                return
            if message.get("more_body", False):
                return
            body = b"".join(chunks)
            try:
                payload = json.loads(body)
            except (ValueError, UnicodeDecodeError):
                payload = None
            if not isinstance(payload, dict) or payload.get("estatus") != 1:
                await send(start)
                await send({"type": "http.response.body", "body": body})
                return
            etag = f'W/"{hashlib.sha256(body).hexdigest()}"'.encode("ascii")
            headers = [(k, v) for k, v in start.get("headers", [])
                       if k.lower() not in (b"etag", b"cache-control", b"vary")]
            vary = b", ".join(v for k, v in start.get("headers", []) if k.lower() == b"vary")
            headers.extend([(b"etag", etag), (b"cache-control", b"private, max-age=0, must-revalidate"),
                            (b"vary", vary + b", Authorization" if vary else b"Authorization")])
            supplied = request_headers.get(b"if-none-match", b"")
            # GET usa comparación débil: W/"abc" y "abc" representan el mismo contenido.
            def weak_value(tag):
                tag = tag.strip()
                return tag[2:] if tag.startswith(b"W/") else tag
            matches = any(weak_value(tag) in (b"*", weak_value(etag))
                          for tag in supplied.split(b","))
            if matches:
                headers = [(k, v) for k, v in headers if k.lower() not in (b"content-length", b"content-type")]
                await send({"type": "http.response.start", "status": 304, "headers": headers})
                await send({"type": "http.response.body", "body": b""})
            else:
                await send({**start, "headers": headers})
                await send({"type": "http.response.body", "body": body})

        await self.app(scope, receive, capture)
