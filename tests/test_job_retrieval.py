"""Synthetic websites and fake DNS, including requests through the real safety transport."""

import json
import socket
from datetime import UTC, datetime

import httpx
import pytest

from aura.services import job_retrieval as retrieval
from aura.services.job_retrieval import (
    JobRetrievalError,
    PublicHTTPTransport,
    extract_job_html,
    retrieve_job,
    validate_public_url,
)

DESCRIPTION = (
    "<h2>Responsibilities</h2><p>Build and maintain Python data pipelines "
    "for synthetic datasets.</p>"
    "<h2>Requirements</h2><ul><li>Python and SQL required.</li><li>Git preferred.</li></ul>"
)


def job_html(**overrides):
    posting = {
        "@type": "JobPosting",
        "title": "Synthetic Python Developer",
        "hiringOrganization": {"name": "Example Analytics"},
        "description": DESCRIPTION,
        **overrides,
    }
    return '<script type="application/ld+json">' + json.dumps(posting) + "</script>"


def html_response(html=None, *, status=200, headers=None):
    return httpx.Response(
        status,
        headers={"content-type": "text/html; charset=utf-8", **(headers or {})},
        stream=httpx.ByteStream((html if html is not None else job_html()).encode("utf-8")),
    )


@pytest.fixture
def website(monkeypatch):
    """Retain URL/DNS checks and IP pinning; replace only the outgoing socket transport."""

    def setup(handler=None, addresses=None):
        requests, resolutions, responses = [], [], []

        def dns(host, port, **kwargs):
            resolutions.append(host)
            ips = addresses(host) if addresses else ["93.184.216.34"]
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in ips]

        def respond(request):
            requests.append(request)
            response = handler(request) if handler else html_response()
            responses.append(response)
            return response

        transport = PublicHTTPTransport()
        transport._transport.close()
        transport._transport = httpx.MockTransport(respond)
        monkeypatch.setattr(retrieval, "PublicHTTPTransport", lambda: transport)
        monkeypatch.setattr(socket, "getaddrinfo", dns)
        return requests, resolutions, responses

    return setup


def test_public_fetch_pins_ip_and_preserves_host_sni_and_source(website):
    requests, resolutions, responses = website()
    result = retrieve_job("https://jobs.example.test/posting?id=7#details")
    assert "Python and SQL required" in result.text
    assert "Example Analytics" in result.text
    assert result.final_url == "https://jobs.example.test/posting?id=7"
    assert result.extraction_method == "json_ld_job_posting"
    assert resolutions == ["jobs.example.test"]
    assert requests[0].url.host == "93.184.216.34"
    assert requests[0].headers["host"] == "jobs.example.test"
    assert requests[0].extensions["sni_hostname"] == "jobs.example.test"
    assert requests[0].headers["accept-encoding"] == "identity"
    assert "authorization" not in requests[0].headers
    assert all(response.is_closed for response in responses)


@pytest.mark.parametrize(
    "url",
    [
        "file:///private.txt",
        "ftp://example.test/a",
        "https://user:pass@example.test/",
        "http://example.test:9000/",
        "https://example.test:80/",
        "",
        "not a URL",
        "https://example.test/\nsecret",
        "http://[fe80::1%25eth0]/",
    ],
)
def test_unsupported_urls_rejected_without_dns_or_http(url):
    with pytest.raises(JobRetrievalError, match="public HTTP"):
        validate_public_url(url)


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "10.0.0.1",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.169.254",
        "0.0.0.0",
        "100.64.0.1",
        "224.0.0.1",
        "::1",
        "fe80::1",
        "fc00::1",
        "fec0::1",
        "::ffff:127.0.0.1",
        "64:ff9b::7f00:1",
        "2002:7f00:1::",
    ],
)
def test_nonpublic_and_transition_destinations_never_reach_transport(website, ip):
    requests, _, _ = website(addresses=lambda _: [ip])
    with pytest.raises(JobRetrievalError):
        retrieve_job("https://jobs.example.test/posting")
    assert requests == []


def test_mixed_public_private_dns_answers_fail_closed(website):
    requests, _, _ = website(addresses=lambda _: ["93.184.216.34", "127.0.0.1"])
    with pytest.raises(JobRetrievalError, match="blocked"):
        retrieve_job("https://jobs.example.test/posting")
    assert requests == []


def test_each_redirect_is_checked_before_connecting(website):
    requests, resolutions, responses = website(
        lambda _: html_response(status=302, headers={"location": "https://internal.example.test/"}),
        addresses=lambda host: ["127.0.0.1" if host.startswith("internal") else "93.184.216.34"],
    )
    with pytest.raises(JobRetrievalError, match="blocked"):
        retrieve_job("https://jobs.example.test/posting")
    assert len(requests) == 1
    assert resolutions == ["jobs.example.test", "internal.example.test"]
    assert responses[0].is_closed


def test_relative_redirect_retains_final_url(website):
    def handler(request):
        if request.url.path == "/old":
            return html_response(status=302, headers={"location": "/new"})
        return html_response()

    requests, _, _ = website(handler)
    result = retrieve_job("https://jobs.example.test/old")
    assert result.final_url == "https://jobs.example.test/new"
    assert len(requests) == 2


@pytest.mark.parametrize("location", ["http://jobs.example.test/plain", "file:///secret"])
def test_insecure_or_unsupported_redirects_blocked(website, location):
    requests, _, _ = website(lambda _: html_response(status=302, headers={"location": location}))
    with pytest.raises(JobRetrievalError):
        retrieve_job("https://jobs.example.test/old")
    assert len(requests) == 1


def test_redirect_hops_bounded(website):
    counter = 0

    def handler(_):
        nonlocal counter
        counter += 1
        return html_response(status=302, headers={"location": f"/hop-{counter}"})

    requests, _, _ = website(handler)
    with pytest.raises(JobRetrievalError, match="redirect limit"):
        retrieve_job("https://jobs.example.test/start")
    assert len(requests) == 4


@pytest.mark.parametrize("status", [401, 403, 404, 410, 429, 500, 503])
def test_http_failures_offer_pasted_fallback_without_retry(website, status):
    requests, _, responses = website(
        lambda _: html_response("SYNTHETIC_PRIVATE_ERROR", status=status)
    )
    with pytest.raises(JobRetrievalError, match="Paste") as failure:
        retrieve_job("https://jobs.example.test/posting")
    assert "PRIVATE_ERROR" not in str(failure.value)
    assert len(requests) == 1
    assert responses[0].is_closed


def test_timeout_hides_raw_details_and_makes_one_request(website):
    def handler(request):
        raise httpx.ReadTimeout("SYNTHETIC_PRIVATE_DATA", request=request)

    requests, _, _ = website(handler)
    with pytest.raises(JobRetrievalError, match="Paste") as failure:
        retrieve_job("https://jobs.example.test/posting")
    assert "PRIVATE_DATA" not in str(failure.value)
    assert len(requests) == 1


@pytest.mark.parametrize(
    "headers",
    [{"content-type": "application/pdf"}, {"content-encoding": "gzip"}],
)
def test_unsupported_content_rejected(website, headers):
    _, _, responses = website(lambda _: html_response(headers=headers))
    with pytest.raises(JobRetrievalError, match="Paste"):
        retrieve_job("https://jobs.example.test/posting")
    assert responses[0].is_closed


def test_oversized_response_rejected_without_truncation(website, monkeypatch):
    monkeypatch.setattr(retrieval, "MAX_RESPONSE_BYTES", 40)
    _, _, responses = website()
    with pytest.raises(JobRetrievalError, match="size/time limit"):
        retrieve_job("https://jobs.example.test/posting")
    assert responses[0].is_closed


def test_jsonld_graph_preserves_original_requirements():
    data = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "Organization", "name": "Unrelated"},
            {"@type": ["Thing", "JobPosting"], "title": "SQL Analyst", "description": DESCRIPTION},
        ],
    }
    html = (
        '<nav>Secret menu</nav><script type="application/ld+json">' + json.dumps(data) + "</script>"
    )
    result = extract_job_html(html, final_url="https://jobs.example.test/sql")
    assert "SQL Analyst" in result.text and "Python and SQL required" in result.text
    assert "Secret menu" not in result.text and "<li>" not in result.text


def test_clear_main_job_region_without_jsonld():
    html = "<nav>Unrelated menu</nav><main><h1>Python Developer</h1>" + DESCRIPTION * 2 + "</main>"
    result = extract_job_html(html, final_url="https://jobs.example.test/python")
    assert result.extraction_method == "visible_job_region"
    assert "Unrelated menu" not in result.text


def test_article_with_job_description_and_requirements_headings():
    html = (
        "<nav>Other jobs</nav><article><h1>Python Developer</h1>"
        + (DESCRIPTION.replace("Responsibilities", "Job Description") * 2)
        + "</article><footer>Unrelated opportunities</footer>"
    )
    result = extract_job_html(html, final_url="https://jobs.example.test/a")
    assert "Python and SQL required" in result.text
    assert "Unrelated opportunities" not in result.text


@pytest.mark.parametrize(
    "html",
    [
        "",
        "<main>Please sign in to continue.</main>",
        "<script>loadJobs()</script>",
        job_html(description="Short"),
        job_html() + job_html(title="Second job"),
        job_html(validThrough="2000-01-01"),
    ],
)
def test_ambiguous_empty_expired_and_listing_pages_offer_fallback(html):
    with pytest.raises(JobRetrievalError, match="Paste"):
        extract_job_html(html, final_url="https://jobs.example.test/posting")


def test_date_only_expiry_does_not_invent_a_midnight_cutoff():
    today = datetime.now(UTC).date().isoformat()
    assert extract_job_html(job_html(validThrough=today), final_url="https://jobs.example.test/a")


def test_long_posting_is_rejected_not_silently_cut():
    with pytest.raises(JobRetrievalError, match="not silently truncated"):
        extract_job_html(
            job_html(description="word " * 5000), final_url="https://jobs.example.test/a"
        )
