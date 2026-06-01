from __future__ import annotations

import os
import re
import requests
from dataclasses import dataclass, field


@dataclass
class WebResearchResult:
    url: str
    status_code: int
    title: str
    excerpt: str
    source: str = "fetch"   # "fetch" | "perplexity"
    citations: list = field(default_factory=list)


class WebResearcher:
    """Web research with Perplexity API (if configured) falling back to direct HTTP fetch."""

    PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"
    DEFAULT_MODEL = "sonar"

    def __init__(self):
        self._api_key: str = os.getenv("PERPLEXITY_API_KEY", "")

    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def search(self, query: str, timeout_s: float = 20.0) -> WebResearchResult:
        """Use Perplexity to answer a research query, or fall back to direct fetch if not configured."""
        if self.is_configured():
            return await self._perplexity_search(query, timeout_s)
        return self.fetch(query, timeout_s)

    async def _perplexity_search(self, query: str, timeout_s: float) -> WebResearchResult:
        import httpx
        payload = {
            "model": self.DEFAULT_MODEL,
            "messages": [{"role": "user", "content": query}],
            "max_tokens": 1024,
            "temperature": 0.2,
            "return_related_questions": False,
            "return_images": False,
        }
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                r = await client.post(
                    self.PERPLEXITY_URL,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
            if r.status_code == 200:
                data = r.json()
                content = data["choices"][0]["message"]["content"]
                citations = data.get("citations", [])
                return WebResearchResult(
                    url=self.PERPLEXITY_URL,
                    status_code=200,
                    title=query[:100],
                    excerpt=content[:2000],
                    source="perplexity",
                    citations=citations[:5],
                )
            return WebResearchResult(
                url=self.PERPLEXITY_URL,
                status_code=r.status_code,
                title="Perplexity error",
                excerpt=r.text[:300],
                source="perplexity",
            )
        except Exception as e:
            return WebResearchResult(
                url=self.PERPLEXITY_URL,
                status_code=0,
                title="Request failed",
                excerpt=str(e)[:200],
                source="perplexity",
            )

    def fetch(self, url: str, timeout_s: float = 8.0) -> WebResearchResult:
        """Direct HTTP fetch for a URL (sync, for non-async contexts)."""
        try:
            response = requests.get(
                url, timeout=timeout_s, headers={"User-Agent": "SODA-Researcher/1.0"}
            )
            text = response.text or ""
            title_match = re.search(r"<title>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
            title = (title_match.group(1).strip() if title_match else "")[:160]
            cleaned = re.sub(r"<[^>]+>", " ", text)
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            excerpt = cleaned[:1000]
            return WebResearchResult(
                url=url,
                status_code=response.status_code,
                title=title,
                excerpt=excerpt,
                source="fetch",
            )
        except Exception as e:
            return WebResearchResult(url=url, status_code=0, title="", excerpt=str(e)[:200], source="fetch")
