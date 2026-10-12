# src/shopify.py
import os, time
import httpx
from dotenv import load_dotenv

load_dotenv()
SHOP = os.environ["SHOPIFY_SHOP"]
API_VERSION = "2026-10"
_token: str | None = None
_expires_at = 0.0


def _get_token() -> str:
    """Exchange client ID + secret for a 24-hour access token, cached in memory."""
    global _token, _expires_at
    if _token and time.time() < _expires_at - 60:
        return _token
    r = httpx.post(
        f"https://{SHOP}.myshopify.com/admin/oauth/access_token",
        data={
            "grant_type": "client_credentials",
            "client_id": os.environ["SHOPIFY_CLIENT_ID"],
            "client_secret": os.environ["SHOPIFY_CLIENT_SECRET"],
        },
    )
    r.raise_for_status()
    body = r.json()
    _token = body["access_token"]
    _expires_at = time.time() + body["expires_in"]
    return _token


def graphql(query: str, variables: dict | None = None) -> dict:
    r = httpx.post(
        f"https://{SHOP}.myshopify.com/admin/api/{API_VERSION}/graphql.json",
        headers={"X-Shopify-Access-Token": _get_token()},
        json={"query": query, "variables": variables or {}},
        timeout=30,
    )
    r.raise_for_status()
    body = r.json()
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    return body["data"]


if __name__ == "__main__":
    print(graphql("{ products(first: 3) { nodes { id title } } }"))