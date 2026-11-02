"""Read-only connectors. Extracted page text is data, never executable instructions."""

import http.client
import ipaddress
import json
import socket
import ssl
import time
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from merchmind.models import Evidence, SupplierQuote
from merchmind.storage import evidence_record, load, load_csv, redact

USER_AGENT = "MerchMind/0.1 (+read-only product research)"


def validate_url(url: str, allowed_hosts: list[str]) -> tuple[str, str]:
    if any(ord(c) < 33 or ord(c) == 127 for c in url) or "\\" in url:
        raise ValueError("URL contains unsafe characters")
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Only HTTPS source URLs are supported")
    host = parsed.hostname.lower()
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("Credentials and custom ports are forbidden")
    if parsed.query or parsed.fragment:
        raise ValueError("Remove URL queries and fragments before research")
    if host not in allowed_hosts:
        raise ValueError("Source host is not on the merchant allowlist (exact host matching)")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("IP-literal source URLs are forbidden")
    return host, parsed.path or "/"


def public_addresses(host: str) -> list[str]:
    addresses = sorted(
        {record[4][0] for record in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    )
    if not addresses or any(
        not ipaddress.ip_address(a).is_global
        or ipaddress.ip_address(a).is_multicast
        or ipaddress.ip_address(a).is_reserved
        for a in addresses
    ):
        raise ValueError("DNS resolves to a non-public address")
    return addresses


class PinnedHTTPS(http.client.HTTPSConnection):
    """Connect to an already-validated address while verifying TLS for the hostname."""

    def __init__(self, host: str, address: str, timeout: float):
        super().__init__(host, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self) -> None:
        sock = socket.create_connection((self.address, 443), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hidden = 0
        self.in_title = False
        self.title: list[str] = []
        self.visible: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            self.hidden = max(0, self.hidden - 1)
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.visible.append(data.strip())
            if self.in_title:
                self.title.append(data.strip())


@dataclass
class FetchSession:
    allowed_hosts: list[str]
    max_requests_per_host: int = 3
    max_bytes: int = 1_000_000
    deadline: float = field(default_factory=lambda: time.monotonic() + 60)
    counts: dict[str, int] = field(default_factory=dict)

    def request(self, host: str, path: str) -> tuple[int, str, bytes]:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0 or self.counts.get(host, 0) >= self.max_requests_per_host:
            raise ValueError("Source request or duration budget exhausted")
        self.counts[host] = self.counts.get(host, 0) + 1
        addresses = public_addresses(host)
        conn = PinnedHTTPS(host, addresses[0], min(remaining, 10))
        try:
            conn.request(
                "GET",
                path,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,text/plain",
                    "Accept-Encoding": "identity",
                },
            )
            response = conn.getresponse()
            # Never follow redirects, even to another public host.
            if 300 <= response.status < 400:
                raise ValueError("Redirect requires manual review")
            content_length = response.getheader("Content-Length")
            if content_length and int(content_length) > self.max_bytes:
                raise ValueError("Source exceeds response size budget")
            chunks, size = [], 0
            while True:
                if time.monotonic() >= self.deadline:
                    raise ValueError("Source duration budget exhausted")
                if conn.sock is not None:
                    conn.sock.settimeout(max(0.1, min(10, self.deadline - time.monotonic())))
                chunk = response.read1(min(65536, self.max_bytes + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > self.max_bytes:
                    raise ValueError("Source exceeds response size budget")
            return response.status, response.getheader("Content-Type", ""), b"".join(chunks)
        finally:
            conn.close()

    def fetch(self, url: str) -> tuple[dict, Evidence | None]:
        host, path = validate_url(url, self.allowed_hosts)
        try:
            status, _, body = self.request(host, "/robots.txt")
            if status == 404:
                rules = []
            elif status == 200:
                rules = body.decode("utf-8", errors="replace").splitlines()
            else:
                return {
                    "source": url,
                    "status": "unavailable",
                    "reason": "Robots policy unavailable",
                }, None
            robots = RobotFileParser()
            robots.parse(rules)
            if not robots.can_fetch(USER_AGENT, url):
                return {
                    "source": url,
                    "status": "blocked",
                    "reason": "Robots policy disallows access",
                }, None
            if robots.crawl_delay(USER_AGENT) or robots.request_rate(USER_AGENT):
                return {
                    "source": url,
                    "status": "needs_review",
                    "reason": "Manual review required for source-specific crawl scheduling",
                }, None
            status, content_type, body = self.request(host, path)
            if status in {429, 503} and self.counts.get(host, 0) < self.max_requests_per_host:
                if self.deadline - time.monotonic() > 2:
                    time.sleep(1)
                    status, content_type, body = self.request(host, path)
            if status != 200:
                return {
                    "source": url,
                    "status": "unavailable",
                    "reason": f"HTTP {status}; no access bypass attempted",
                }, None
            if not any(kind in content_type for kind in ("text/html", "text/plain")):
                return {
                    "source": url,
                    "status": "unsupported",
                    "reason": "Only text or HTML supported",
                }, None
            parser = PageParser()
            parser.feed(body.decode("utf-8", errors="replace"))
            title = redact(" ".join(parser.title))[:300]
            evidence = evidence_record(
                {"body_sha256": __import__("hashlib").sha256(body).hexdigest()},
                kind="marketplace_listing",
                reference=url,
                uri=url,
                verified="unverified",
                assertion=f"Page retrieved with title: {title}. Listing facts and variant require review.",
            )
            return {
                "source": url,
                "status": "retrieved_unverified",
                "title": title,
                "evidence_id": evidence.evidence_id,
            }, evidence
        except (OSError, ValueError, http.client.HTTPException):
            return {
                "source": url,
                "status": "unavailable",
                "reason": "Access failed, unsafe address, timeout, redirect or budget limit; use a manual export",
            }, None


def import_quotes(path: Path) -> tuple[list[SupplierQuote], list[Evidence]]:
    if path.suffix.lower() == ".csv":
        _, raw = load_csv(path)
        for row in raw:
            for field_name in (
                "price_tiers",
                "evidence_ids",
                "verification_flags",
                "verification_checks",
            ):
                if field_name in row:
                    row[field_name] = json.loads(row[field_name])
            for field_name in ("moq", "lead_time_days"):
                if field_name in row and row[field_name]:
                    row[field_name] = int(row[field_name])
            for key, value in list(row.items()):
                if value == "":
                    row[key] = None
    else:
        raw = load(path)
    if not isinstance(raw, list):
        raise ValueError("Supplier import requires an array")
    quotes, sources = [], []
    for i, row in enumerate(raw, start=1):
        # A manually imported quotation is merchant-provided, not independently verified.
        clean = dict(row)
        clean.pop("evidence_ids", None)
        evidence = evidence_record(
            clean,
            kind="supplier_quote",
            reference=f"supplier-import:{i}",
            uri=clean.get("listing_url"),
            assertion="Merchant imported supplier terms; confirmation status is merchant-declared.",
        )
        clean["listing_url"] = evidence.source_uri
        quote = SupplierQuote.model_validate({**clean, "evidence_ids": [evidence.evidence_id]})
        quotes.append(quote)
        sources.append(evidence)
    keys = [(q.supplier_id, q.product_variant_key) for q in quotes]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate supplier and variant; merge quote tiers before import")
    return quotes, sources
