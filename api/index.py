import os
import sys
import urllib.parse

# Ensure repository root is on sys.path for backend imports
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from backend.main import app as fastapi_app

async def app(scope, receive, send):
    if scope["type"] == "http":
        raw_query = scope.get("query_string", b"").decode("latin1")
        query_params = urllib.parse.parse_qs(raw_query)

        # Extract path forwarded by vercel.json rewrite rule
        if "__path__" in query_params:
            forwarded_path = query_params["__path__"][0]
            # Normalize path (ensure leading slash, strip redundant index.py)
            if not forwarded_path.startswith("/"):
                forwarded_path = "/" + forwarded_path
            scope["path"] = forwarded_path

            # Clean __path__ out of query string so route handlers receive pristine query params
            del query_params["__path__"]
            scope["query_string"] = urllib.parse.urlencode(query_params, doseq=True).encode("latin1")

    await fastapi_app(scope, receive, send)
