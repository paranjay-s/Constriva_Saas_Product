"""Unexpected errors still reach the browser as errors, not as "CORS errors".

Starlette answers an unhandled exception from its outermost layer, outside the CORS
middleware, so that 500 response has no Access-Control-Allow-Origin header. A frontend on
another origin (the deployed site calling this API) then sees only a CORS failure and never
the status. This middleware sits inside the CORS middleware: it sends the 500 itself, so CORS
adds its headers, and then re-raises, so the server still logs the traceback exactly as before.
"""

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

BODY = json.dumps({"detail": "Internal server error"}).encode()


class ServerErrorWithCors:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def tracked(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, tracked)
        except Exception:
            if not started:
                await send({
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [(b"content-type", b"application/json"),
                                (b"content-length", str(len(BODY)).encode())],
                })
                await send({"type": "http.response.body", "body": BODY})
            raise
