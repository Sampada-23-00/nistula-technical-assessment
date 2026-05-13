# Classification is handled inside claude_service.classify_and_reply.
# This module is retained as a thin re-export for import compatibility.

from app.services.claude_service import classify_and_reply  # noqa: F401
