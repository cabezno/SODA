from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ReferenceReport:
    total_urls: int
    unique_urls: int
    broken_candidates: int


class ReferenceAnalyzer:
    """Parses text and extracts URL reference quality signals."""

    URL_RE = re.compile(r"https?://[^\s\]\)\"']+")

    def analyze(self, text: str) -> ReferenceReport:
        urls = self.URL_RE.findall(text or "")
        unique = set(urls)
        broken = sum(1 for u in unique if any(x in u for x in ("localhost", "example.com")))
        return ReferenceReport(total_urls=len(urls), unique_urls=len(unique), broken_candidates=broken)
