"""Bounded public-page retrieval with conservative job extraction and no model calls."""

import ipaddress
import json
import re
import socket
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from aura.schemas.job import MAX_JOB_CHARACTERS

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 3
_FALLBACK = " Paste the job description instead."


class JobRetrievalError(ValueError):
    """A safe, predefined failure; no raw website or transport error is exposed."""


@dataclass(frozen=True)
class RetrievedJob:
    text: str
    final_url: str
    extraction_method: str


def validate_public_url(value: str) -> httpx.URL:
    """Validate URL syntax without making a network request. DNS is checked at connection."""
    try:
        if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 32 for c in value):
            raise ValueError
        url = httpx.URL(value)
        if (
            url.scheme not in {"http", "https"}
            or not url.host
            or url.username
            or url.password
            or url.port not in {None, 80 if url.scheme == "http" else 443}
            or "%" in url.host
        ):
            raise ValueError
    except (ValueError, httpx.InvalidURL):
        raise JobRetrievalError("Supply a public HTTP(S) job URL without credentials.") from None
    return url.copy_with(fragment=None)


def _public_address(host: str, port: int) -> str:
    """Reject mixed DNS answers too, then pin the connection to one validated address."""
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        ips = [ipaddress.ip_address(result[4][0]) for result in addresses]
    except (OSError, ValueError):
        raise JobRetrievalError("The job host could not be resolved." + _FALLBACK) from None
    if not ips or any(
        not ip.is_global
        or ip.is_multicast
        or ip.is_reserved
        or isinstance(ip, ipaddress.IPv6Address)
        and ip.is_site_local
        for ip in ips
    ):
        raise JobRetrievalError("Local, private, or reserved network destinations are blocked.")
    # Block IPv6 transition mechanisms rather than allowing embedded IPv4 destinations.
    for ip in ips:
        if isinstance(ip, ipaddress.IPv6Address) and (
            ip.ipv4_mapped
            or ip.sixtofour
            or ip.teredo
            or ip in ipaddress.ip_network("64:ff9b::/96")
        ):
            raise JobRetrievalError("IPv6 transition destinations are not supported." + _FALLBACK)
    return str(ips[0])


class PublicHTTPTransport(httpx.BaseTransport):
    """Connect to the validated IP, retaining the original HTTP Host and TLS hostname.

    Rewriting the connection target prevents a second DNS lookup from bypassing the
    private-address check. HTTPX's documented SNI extension retains TLS verification.
    """

    def __init__(self) -> None:
        self._transport = httpx.HTTPTransport(
            retries=0,
            trust_env=False,
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=0),
        )

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        url = validate_public_url(str(request.url))
        ip = _public_address(url.host, url.port or (443 if url.scheme == "https" else 80))
        pinned = httpx.Request(
            method=request.method,
            url=url.copy_with(host=ip),
            headers=request.headers,
            stream=request.stream,
            extensions={**request.extensions, "sni_hostname": url.host},
        )
        return self._transport.handle_request(pinned)

    def close(self) -> None:
        self._transport.close()


def _plain_html(value: str) -> str:
    soup = BeautifulSoup(value, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "form", "svg"]):
        tag.decompose()
    return "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())


def _reported_expired(value: str) -> bool:
    """Interpret date-only expiry at day precision, not an invented midnight cutoff."""
    now = datetime.now(UTC)
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return date.fromisoformat(value) < now.date()
        reported = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if reported.tzinfo is None:
            return reported.date() < now.date()  # No timezone was supplied; use day precision.
        return reported < now
    except ValueError:
        return False


def _job_postings(data: object, depth: int = 0) -> list[dict]:
    if depth > 20:
        return []
    if isinstance(data, list):
        return [job for item in data for job in _job_postings(item, depth + 1)]
    if isinstance(data, dict):
        kind = data.get("@type", [])
        if kind == "JobPosting" or isinstance(kind, list) and "JobPosting" in kind:
            return [data]
        return [job for item in data.values() for job in _job_postings(item, depth + 1)]
    return []


def extract_job_html(html: str, *, final_url: str) -> RetrievedJob:
    """Prefer one schema.org posting; otherwise require recognizable job sections.

    No JavaScript, linked resource, JSON-LD context, or embedded instruction is executed.
    Text is document evidence, not a verified job record or guaranteed complete posting.
    """
    soup = BeautifulSoup(html, "html.parser")
    postings = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            postings.extend(_job_postings(json.loads(script.string or script.get_text())))
        except (ValueError, RecursionError):
            continue
    if len(postings) > 1:
        raise JobRetrievalError(
            "The URL contains multiple postings; supply one posting." + _FALLBACK
        )
    if postings:
        job = postings[0]
        if not isinstance(job.get("title"), str) or not isinstance(job.get("description"), str):
            raise JobRetrievalError("The page has incomplete job information." + _FALLBACK)
        expiry = job.get("validThrough")
        if isinstance(expiry, str) and _reported_expired(expiry):
            raise JobRetrievalError("The posting reports an expired date." + _FALLBACK)
        description = _plain_html(job["description"])
        if len(description) < 80:
            raise JobRetrievalError("The page has too little job information." + _FALLBACK)
        lines = ["Title: " + _plain_html(job["title"])]
        for key in (
            "hiringOrganization",
            "jobLocation",
            "jobLocationType",
            "employmentType",
            "datePosted",
            "validThrough",
            "baseSalary",
            "qualifications",
            "responsibilities",
        ):
            if key in job:
                lines.append(f"{key}: {json.dumps(job[key], ensure_ascii=False)}")
        text = "\n".join([*lines, "Description:", description])
        method = "json_ld_job_posting"
    else:
        region = soup.find("main") or soup.find("article")
        if region is None:
            raise JobRetrievalError("No clear job-content region was found." + _FALLBACK)
        text = _plain_html(str(region))
        # Conservative English-language fallback: prefer rejection to a menu/login summary.
        groups = (
            r"\b(responsibilities|duties|what you.ll do|job description|about the role)\b",
            r"\b(requirements|qualifications|what you.ll bring)\b",
        )
        if len(text) < 200 or not all(re.search(pattern, text, re.I) for pattern in groups):
            raise JobRetrievalError(
                "The page does not clearly contain a job description." + _FALLBACK
            )
        if re.search(
            r"\b(no longer accepting|position (?:is )?filled|job (?:has )?expired)\b", text, re.I
        ):
            raise JobRetrievalError("The page reports that the job is unavailable." + _FALLBACK)
        method = "visible_job_region"
    if len(text) > MAX_JOB_CHARACTERS:
        raise JobRetrievalError(
            "The posting is too long; it was not silently truncated." + _FALLBACK
        )
    return RetrievedJob(text=text, final_url=final_url, extraction_method=method)


def retrieve_job(url: str) -> RetrievedJob:
    """Fetch only the supplied public posting, checking every redirect and response limit."""
    current = validate_public_url(url)
    visited = set()
    deadline = time.monotonic() + 30
    try:
        with httpx.Client(
            transport=PublicHTTPTransport(),
            trust_env=False,
            follow_redirects=False,
            timeout=10,
            headers={"User-Agent": "AuraCareerAssistant/0.1", "Accept-Encoding": "identity"},
        ) as client:
            for hop in range(MAX_REDIRECTS + 1):
                if str(current) in visited or time.monotonic() > deadline:
                    raise JobRetrievalError(
                        "The job request exceeded its redirect/time limit." + _FALLBACK
                    )
                visited.add(str(current))
                with client.stream("GET", current) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location or hop == MAX_REDIRECTS:
                            raise JobRetrievalError(
                                "The job request exceeded its redirect limit." + _FALLBACK
                            )
                        target = validate_public_url(urljoin(str(current), location))
                        if current.scheme == "https" and target.scheme != "https":
                            raise JobRetrievalError("An insecure redirect was blocked." + _FALLBACK)
                        current = target
                        continue
                    if response.status_code in {404, 410}:
                        raise JobRetrievalError(
                            "The job posting is missing or expired." + _FALLBACK
                        )
                    if response.status_code != 200:
                        raise JobRetrievalError(
                            "The website denied or could not serve the posting." + _FALLBACK
                        )
                    kind = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    if kind not in {"text/html", "application/xhtml+xml"}:
                        raise JobRetrievalError(
                            "The URL did not return an HTML job page." + _FALLBACK
                        )
                    if response.headers.get("content-encoding", "identity").lower() != "identity":
                        raise JobRetrievalError(
                            "Compressed job responses are not supported." + _FALLBACK
                        )
                    body = bytearray()
                    for chunk in response.iter_raw():
                        if (
                            len(body) + len(chunk) > MAX_RESPONSE_BYTES
                            or time.monotonic() > deadline
                        ):
                            raise JobRetrievalError(
                                "The job response exceeded its size/time limit." + _FALLBACK
                            )
                        body.extend(chunk)
                    html = body.decode(response.encoding or "utf-8", errors="replace")
                return extract_job_html(html, final_url=str(current))
    except JobRetrievalError:
        raise
    except Exception:
        raise JobRetrievalError("The job page could not be read." + _FALLBACK) from None
    raise JobRetrievalError("The job page could not be read." + _FALLBACK)
