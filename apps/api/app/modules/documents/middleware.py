from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.modules.documents.extraction import MAX_UPLOAD_BYTES

# Multipart framing adds a little over the file itself; allow that overhead so
# a file of exactly MAX_UPLOAD_BYTES is not rejected before extraction sees it.
MAX_MULTIPART_OVERHEAD_BYTES = 64 * 1024
MAX_REQUEST_BYTES = MAX_UPLOAD_BYTES + MAX_MULTIPART_OVERHEAD_BYTES


class UploadSizeLimitMiddleware:
    """Reject declared oversize uploads before Starlette parses the body.

    FastAPI resolves ``UploadFile`` (and therefore spools the multipart body)
    before the route handler runs, so a handler-level check cannot stop the
    common oversize case from being written to disk. This wraps the app and
    answers 413 from the ``Content-Length`` header alone.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self._is_document_upload(scope):
            headers = dict(scope["headers"])
            declared = headers.get(b"content-length")
            if declared is not None and declared.isdigit() and int(declared) > MAX_REQUEST_BYTES:
                response = JSONResponse({"detail": "File is larger than 5 MB"}, status_code=413)
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)

    @staticmethod
    def _is_document_upload(scope: Scope) -> bool:
        return (
            scope["type"] == "http"
            and scope["method"] == "POST"
            and scope["path"].rstrip("/").endswith("/documents")
        )
