from starlette.responses import JSONResponse


class RequestBodyLimit:
    """Bound streamed and multipart requests before the framework parses them."""

    def __init__(self, app, maximum=6 * 1024 * 1024):
        self.app, self.maximum = app, maximum

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}:
            return await self.app(scope, receive, send)
        chunks = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.maximum:
                response = JSONResponse(
                    {
                        "error": {
                            "code": "REQUEST_SIZE",
                            "message": "Request exceeds 6 MB",
                            "details": [],
                            "correlation_id": scope.get("state", {}).get("correlation_id", "unavailable"),
                        }
                    },
                    status_code=413,
                )
                return await response(scope, receive, send)
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        consumed = False

        async def bounded_receive():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)
