#!/usr/bin/env python3
"""Validate Hermes web backend env vars — catch misconfiguration before it breaks."""
import os, sys, re, urllib.request, urllib.error, json, ssl

def fail(msg):
    print(f"  FAIL: {msg}")
    return 1

def ok(msg):
    print(f"  OK: {msg}")
    return 0

def check_url(url, desc):
    """Check a URL is a valid base (no path beyond /)."""
    parsed = urllib.parse.urlparse(url)
    if parsed.path and parsed.path != "/":
        return fail(f"{desc} contains path '{parsed.path}' — should be base URL only (no /v1, /v2, /scrape)")
    return ok(f"{desc} = {url}")

def check_search(url):
    """Verify SearXNG responds to search queries."""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(f"{url}/search?q=healthcheck&format=json")
        resp = urllib.request.urlopen(req, timeout=10, context=ctx)
        data = json.loads(resp.read())
        if "results" in data:
            return ok(f"SearXNG search works ({len(data['results'])} results)")
        return fail(f"SearXNG returned unexpected response")
    except Exception as e:
        return fail(f"SearXNG unreachable: {e}")

def check_extract(url):
    """Verify Firecrawl/fastcrw responds to scrape requests."""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        data = json.dumps({"url": "https://example.com", "formats": ["markdown"]}).encode()
        req = urllib.request.Request(f"{url}/v2/scrape", data=data,
                                     headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=15, context=ctx)
        result = json.loads(resp.read())
        if "data" in result and not result.get("error"):
            return ok(f"Firecrawl extraction works")
        return fail(f"Firecrawl returned error: {result.get('error', 'unknown')}")
    except Exception as e:
        return fail(f"Firecrawl unreachable: {e}")

def main():
    errors = 0
    print("=== Hermes Web Backend Validation ===\n")

    # 1. FIRECRAWL_API_URL: must be base URL only
    firecrawl_url = os.environ.get("FIRECRAWL_API_URL", "")
    if not firecrawl_url:
        errors += fail("FIRECRAWL_API_URL not set")
    else:
        errors += check_url(firecrawl_url, "FIRECRAWL_API_URL")
        errors += check_extract(firecrawl_url)

    # 2. SEARXNG_URL: must be base URL only
    searxng_url = os.environ.get("SEARXNG_URL", "")
    if not searxng_url:
        errors += fail("SEARXNG_URL not set")
    else:
        errors += check_url(searxng_url, "SEARXNG_URL")
        errors += check_search(searxng_url)

    # 3. FIRECRAWL_API_KEY conflict: self-hosted should NOT have this set
    if os.environ.get("FIRECRAWL_API_KEY"):
        errors += fail("FIRECRAWL_API_KEY is set — will conflict with self-hosted FIRECRAWL_API_URL")

    print(f"\n{'ALL CHECKS PASSED' if errors == 0 else f'{errors} CHECK(S) FAILED'}")
    return 0 if errors == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
