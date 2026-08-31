import os
import httpx
from base64 import b64encode


class ConfluenceClient:
    def __init__(self):
        base = os.getenv("CONFLUENCE_URL", "").rstrip("/")
        self.base_url = f"{base}/wiki/rest/api"

        email = os.getenv("CONFLUENCE_EMAIL", "")
        token = os.getenv("CONFLUENCE_API_TOKEN", "")
        credentials = b64encode(f"{email}:{token}".encode()).decode()

        self.headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def search_pages(self, query: str, limit: int = 10) -> dict:
        with httpx.Client() as c:
            r = c.get(
                f"{self.base_url}/content/search",
                headers=self.headers,
                params={"cql": f'text ~ "{query}"', "limit": limit, "expand": "space,title"},
            )
            r.raise_for_status()
            return r.json()

    def get_page(self, page_id: str) -> dict:
        with httpx.Client() as c:
            r = c.get(
                f"{self.base_url}/content/{page_id}",
                headers=self.headers,
                params={"expand": "body.storage,space,title,version"},
            )
            r.raise_for_status()
            return r.json()

    def list_spaces(self, limit: int = 25) -> dict:
        with httpx.Client() as c:
            r = c.get(
                f"{self.base_url}/space",
                headers=self.headers,
                params={"limit": limit},
            )
            r.raise_for_status()
            return r.json()

    def list_pages(self, space_key: str, limit: int = 25) -> dict:
        with httpx.Client() as c:
            r = c.get(
                f"{self.base_url}/content",
                headers=self.headers,
                params={
                    "spaceKey": space_key,
                    "type": "page",
                    "status": "current",
                    "limit": limit,
                    "expand": "space,version",
                },
            )
            r.raise_for_status()
            return r.json()

    def create_page(self, space_key: str, title: str, content: str, parent_id: str = None) -> dict:
        body = {
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "body": {"storage": {"value": content, "representation": "storage"}},
        }
        if parent_id:
            body["ancestors"] = [{"id": parent_id}]

        with httpx.Client() as c:
            r = c.post(f"{self.base_url}/content", headers=self.headers, json=body)
            r.raise_for_status()
            return r.json()

    def update_page(self, page_id: str, title: str, content: str, version: int) -> dict:
        body = {
            "version": {"number": version + 1},
            "title": title,
            "type": "page",
            "body": {"storage": {"value": content, "representation": "storage"}},
        }
        with httpx.Client() as c:
            r = c.put(f"{self.base_url}/content/{page_id}", headers=self.headers, json=body)
            r.raise_for_status()
            return r.json()