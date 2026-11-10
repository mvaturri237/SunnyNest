"""Unit tests for the multi-city scrape feature (plans/multi-city-scrape.md).

Covers ADR-002 Option A: a backward-compatible ``search.cities`` list that all
three scrapers loop over, plus the admin System Health display.

Three groups of tests (per the spec's Testing Strategy):

  (a) ``resolve_cities()`` accepts the legacy ``search.city`` scalar AND the new
      ``search.cities`` list — and never silently targets zero territory.
  (b) Each scraper constructs the correct per-city query params for a 2-city
      config.  **All network / browser calls are mocked — no live API calls**
      (preserves the Zillow/Realtor monthly budget; runs offline).
  (c) The Zillow/Realtor budget guard still short-circuits *mid-city-loop* the
      moment the monthly threshold is reached.

Runs two ways:

    .venv/bin/python -m pytest scripts/test_multi_city_scrape.py -v   # pytest
    .venv/bin/python scripts/test_multi_city_scrape.py                # plain script

The plain-script mode matches the existing ``scripts/test_*.py`` convention and
does not require pytest to be installed.  Exit code 0 = pass, 1 = fail.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

# Ensure project root is importable when run as a plain script.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.utils import resolve_cities  # noqa: E402


# ---------------------------------------------------------------------------
# Shared fixtures / fakes
# ---------------------------------------------------------------------------

# A representative 2-city config used to construct scrapers under test.
_TWO_CITY_CONFIG: dict[str, Any] = {
    "search": {
        "cities": ["Sunnyvale", "Los Altos"],
        "state": "CA",
        "zip_codes": ["94087", "94024"],
    },
    "filters": {
        "min_price": 5000,
        "max_price": 7500,
        "min_bedrooms": 3,
        "max_bedrooms": 4,
    },
    "scraper": {"max_pages": 2, "request_delay_min": 0, "request_delay_max": 0},
    "zillow_api": {"rapidapi_key": "test-key", "rapidapi_host": "zllw.test"},
    "realtor_api": {
        "rapidapi_key": "test-key",
        "rapidapi_host": "realtor.test",
        "enabled": True,
        "monthly_budget": 100,
        "budget_threshold": 90,
    },
}


class _FakeResponse:
    """Minimal stand-in for an ``httpx.Response`` returning one empty page."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.status_code = 200
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:  # pragma: no cover - trivial
        return None


class _RecordingClient:
    """Async context-manager fake that records every request's params.

    Substitutes for ``httpx.AsyncClient`` so scraper ``scrape()`` runs without
    touching the network.  Each ``get()`` returns an *empty* results page so the
    per-city loop advances to the next city after exactly one call per city.
    """

    def __init__(self, *_args: Any, empty_payload: dict[str, Any], **_kwargs: Any) -> None:
        self.calls: list[dict[str, Any]] = []
        self._empty_payload = empty_payload

    async def __aenter__(self) -> "_RecordingClient":
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        return None

    async def get(self, url: str, *, headers: Any = None, params: Any = None) -> _FakeResponse:
        self.calls.append({"url": url, "params": params})
        return _FakeResponse(self._empty_payload)


# ---------------------------------------------------------------------------
# (a) resolve_cities() — legacy scalar AND new list  (backward compatibility)
# ---------------------------------------------------------------------------


def test_resolver_accepts_new_cities_list() -> None:
    """New-style ``cities`` list is returned verbatim, order-preserving."""
    result = resolve_cities({"cities": ["Sunnyvale", "Los Altos"], "state": "CA"})
    assert result == ["Sunnyvale", "Los Altos"]


def test_resolver_accepts_legacy_city_scalar() -> None:
    """Legacy ``city`` scalar still works → wrapped into a one-element list."""
    result = resolve_cities({"city": "Sunnyvale", "state": "CA"})
    assert result == ["Sunnyvale"]


def test_resolver_legacy_scalar_regression_returns_sunnyvale_only() -> None:
    """Explicit backward-compat regression guard (spec 'Verify before completing')."""
    assert resolve_cities({"city": "Sunnyvale"}) == ["Sunnyvale"]


def test_resolver_cities_list_takes_precedence_over_scalar() -> None:
    """When both keys exist, the new ``cities`` list wins."""
    result = resolve_cities({"cities": ["Los Altos"], "city": "Sunnyvale"})
    assert result == ["Los Altos"]


def test_resolver_empty_list_falls_back_to_legacy_then_default() -> None:
    """An empty ``cities`` list falls through to the scalar, then the default."""
    assert resolve_cities({"cities": [], "city": "Mountain View"}) == ["Mountain View"]
    assert resolve_cities({"cities": []}) == ["Sunnyvale"]


def test_resolver_none_and_missing_return_default() -> None:
    """``None`` or an absent search block never yields an empty territory."""
    assert resolve_cities(None) == ["Sunnyvale"]
    assert resolve_cities({}) == ["Sunnyvale"]


def test_resolver_strips_and_drops_blank_entries() -> None:
    """Whitespace is stripped and blank entries dropped."""
    result = resolve_cities({"cities": ["  Sunnyvale  ", "", "   ", "Los Altos"]})
    assert result == ["Sunnyvale", "Los Altos"]


def test_resolver_tolerates_scalar_under_cities_key() -> None:
    """A scalar mistakenly placed under ``cities`` is wrapped, not crashed on."""
    assert resolve_cities({"cities": "Sunnyvale"}) == ["Sunnyvale"]


# ---------------------------------------------------------------------------
# (b) Per-city query-param construction — all 3 scrapers, network mocked
# ---------------------------------------------------------------------------


def test_zillow_builds_one_location_per_city() -> None:
    """Zillow issues a request for EACH configured city, with 'City, State'."""
    from src.scrapers import zillow_scraper as zmod

    empty = {"message": "200", "searchResults": [], "pagesInfo": {"totalPages": 1}}
    recording = _RecordingClient(empty_payload=empty)

    with patch.object(zmod, "load_config", return_value=_TWO_CITY_CONFIG), patch.object(
        zmod, "get_api_call_count", return_value=0
    ), patch.object(zmod, "log_api_call"), patch.object(
        zmod.httpx, "AsyncClient", return_value=recording
    ), patch.object(
        zmod.ZillowScraper, "_build_ssl_context", return_value=False, create=True
    ):
        scraper = zmod.ZillowScraper()
        # Confirm territory resolved from config, not hardcoded.
        assert scraper.cities == ["Sunnyvale", "Los Altos"]
        asyncio.run(scraper.scrape())

    locations = [c["params"]["location"] for c in recording.calls]
    assert locations == ["Sunnyvale, CA", "Los Altos, CA"]


def test_realtor_builds_one_city_param_per_city() -> None:
    """Realtor issues 'city:<City>, <State>' for EACH configured city."""
    from src.scrapers import realtor_scraper as rmod

    empty = {
        "status": True,
        "data": {"results": [], "total": 0},
        "meta": {"totalPage": 1},
    }
    recording = _RecordingClient(empty_payload=empty)

    with patch.object(rmod, "load_config", return_value=_TWO_CITY_CONFIG), patch.object(
        rmod, "get_api_call_count", return_value=0
    ), patch.object(rmod, "log_api_call"), patch.object(
        rmod.httpx, "AsyncClient", return_value=recording
    ), patch.object(
        rmod.RealtorScraper, "_build_ssl_context", return_value=False, create=True
    ):
        scraper = rmod.RealtorScraper()
        assert scraper.cities == ["Sunnyvale", "Los Altos"]
        asyncio.run(scraper.scrape())

    locations = [c["params"]["location"] for c in recording.calls]
    assert locations == ["city:Sunnyvale, CA", "city:Los Altos, CA"]


def test_craigslist_derives_query_term_per_city_lowercased() -> None:
    """Craigslist derives the query term per city (lowercased) from config.

    Verified via ``_build_url`` (pure, no browser) — the exact function the
    per-city loop calls.  No hardcoded 'sunnyvale' anywhere.
    """
    from src.scrapers import craigslist_scraper as cmod

    with patch.object(cmod, "load_config", return_value=_TWO_CITY_CONFIG):
        scraper = cmod.CraigslistScraper()

    assert scraper.cities == ["Sunnyvale", "Los Altos"]

    def _query_of(city: str) -> str:
        url = scraper._build_url(city.lower())
        qs = parse_qs(urlparse(url).query)
        return qs["query"][0]

    assert _query_of("Sunnyvale") == "sunnyvale"
    assert _query_of("Los Altos") == "los altos"
    # min_bedrooms filter from config is preserved on the query.
    qs = parse_qs(urlparse(scraper._build_url("sunnyvale")).query)
    assert qs.get("min_bedrooms") == ["3"]


def test_craigslist_query_is_config_driven_not_hardcoded() -> None:
    """Behavioural guard: the query term follows config, not a hardcoded string.

    The former implementation hardcoded ``self.query_params = {"query":
    "sunnyvale"}`` and ignored config entirely.  We prove the new behaviour is
    config-driven by feeding a config whose cities are NOT Sunnyvale and
    asserting the derived query follows it — a hardcoded "sunnyvale" would fail.
    """
    from src.scrapers import craigslist_scraper as cmod

    alt_config = {
        "search": {"cities": ["Mountain View", "Palo Alto"], "state": "CA"},
        "filters": {"min_bedrooms": 2},
        "scraper": {},
    }
    with patch.object(cmod, "load_config", return_value=alt_config):
        scraper = cmod.CraigslistScraper()

    assert scraper.cities == ["Mountain View", "Palo Alto"]
    query_terms = [
        parse_qs(urlparse(scraper._build_url(c.lower())).query)["query"][0]
        for c in scraper.cities
    ]
    assert query_terms == ["mountain view", "palo alto"]
    # A leftover hardcoded default would surface here as an unexpected term.
    assert "sunnyvale" not in query_terms


def test_craigslist_city_is_config_driven_not_hardcoded() -> None:
    """Behavioural guard: normalize() stores the per-listing source city.

    The former implementation hardcoded ``"city": "Sunnyvale"`` in the
    normalized dict.  For a multi-city config, every Craigslist listing was
    therefore stamped "Sunnyvale" regardless of its actual source city — which
    the orchestrator then fed to ``geocode_address(city=...)``, producing a
    Sunnyvale centroid pin for e.g. Los Altos listings (P2 CRAIG-MULTI-P2).

    The fix threads the per-city loop context onto each raw listing dict via
    ``_source_city`` so ``normalize()`` uses it.  Here we assert that a raw
    listing tagged with a non-Sunnyvale source city normalizes to that city — a
    hardcoded "Sunnyvale" would fail the ``Los Altos`` assertion.  No browser /
    network is touched: ``normalize()`` is a pure raw-dict → column-dict map.
    """
    from src.scrapers import craigslist_scraper as cmod

    with patch.object(cmod, "load_config", return_value=_TWO_CITY_CONFIG):
        scraper = cmod.CraigslistScraper()

    # Two raw listings as produced by the per-city loop for a 2-city config:
    # each carries the config city that drove its search pass.
    sunnyvale_raw = {
        "external_id": "111",
        "url": "https://sfbay.craigslist.org/apa/111.html",
        "title": "3BR house in Sunnyvale",
        "street_address": "123 Main St",
        "_source_city": "Sunnyvale",
    }
    los_altos_raw = {
        "external_id": "222",
        "url": "https://sfbay.craigslist.org/apa/222.html",
        "title": "3BR house in Los Altos",
        "street_address": "456 Oak Ave",
        "_source_city": "Los Altos",
    }

    assert scraper.normalize(sunnyvale_raw)["city"] == "Sunnyvale"
    # A leftover hardcoded "Sunnyvale" would fail this assertion.
    assert scraper.normalize(los_altos_raw)["city"] == "Los Altos"


def test_craigslist_normalize_falls_back_to_sunnyvale_when_no_source_city() -> None:
    """Backward-compat guard: a raw dict lacking ``_source_city`` → "Sunnyvale".

    Preserves the legacy single-city behaviour for any raw listing that was not
    tagged with a source city (e.g. produced by older code paths).
    """
    from src.scrapers import craigslist_scraper as cmod

    with patch.object(cmod, "load_config", return_value=_TWO_CITY_CONFIG):
        scraper = cmod.CraigslistScraper()

    untagged_raw = {
        "external_id": "333",
        "url": "https://sfbay.craigslist.org/apa/333.html",
        "title": "2BR near downtown",
        "street_address": "789 Elm St",
    }
    assert scraper.normalize(untagged_raw)["city"] == "Sunnyvale"


# ---------------------------------------------------------------------------
# (c) Budget guard short-circuits mid-city-loop
# ---------------------------------------------------------------------------


def test_zillow_budget_guard_short_circuits_mid_city_loop() -> None:
    """Once the monthly threshold is hit, no further city is queried.

    First call is under budget; the guard re-check then reports the threshold
    reached, so the loop must stop before issuing a request for the 2nd city.
    """
    from src.scrapers import zillow_scraper as zmod

    empty = {
        "message": "200",
        "searchResults": [{"x": 1}],  # non-empty so loop would continue but for guard
        "pagesInfo": {"totalPages": 5},
    }
    recording = _RecordingClient(empty_payload=empty)

    # get_api_call_count: initial guard sees 0; every re-check sees 450 (>=450),
    # so the very first per-call re-check inside the loop trips and returns.
    counts = iter([0])  # initial pre-loop guard

    def _count(_source: str) -> int:
        try:
            return next(counts)
        except StopIteration:
            return 450  # threshold reached on the first in-loop re-check

    with patch.object(zmod, "load_config", return_value=_TWO_CITY_CONFIG), patch.object(
        zmod, "get_api_call_count", side_effect=_count
    ), patch.object(zmod, "log_api_call"), patch.object(
        zmod.httpx, "AsyncClient", return_value=recording
    ), patch.object(
        zmod.ZillowScraper, "_build_ssl_context", return_value=False, create=True
    ):
        scraper = zmod.ZillowScraper()
        asyncio.run(scraper.scrape())

    # Guard tripped on the first in-loop re-check → zero HTTP requests issued,
    # and crucially the 2nd city ("Los Altos, CA") was never reached.
    assert recording.calls == []


def test_realtor_budget_guard_short_circuits_mid_city_loop() -> None:
    """Realtor equivalent: threshold mid-loop stops remaining cities."""
    from src.scrapers import realtor_scraper as rmod

    empty = {
        "status": True,
        "data": {"results": [{"x": 1}], "total": 1},
        "meta": {"totalPage": 5},
    }
    recording = _RecordingClient(empty_payload=empty)

    counts = iter([0])  # initial pre-loop guard

    def _count(_source: str) -> int:
        try:
            return next(counts)
        except StopIteration:
            return 90  # realtor threshold reached on first in-loop re-check

    with patch.object(rmod, "load_config", return_value=_TWO_CITY_CONFIG), patch.object(
        rmod, "get_api_call_count", side_effect=_count
    ), patch.object(rmod, "log_api_call"), patch.object(
        rmod.httpx, "AsyncClient", return_value=recording
    ), patch.object(
        rmod.RealtorScraper, "_build_ssl_context", return_value=False, create=True
    ):
        scraper = rmod.RealtorScraper()
        asyncio.run(scraper.scrape())

    assert recording.calls == []


# ---------------------------------------------------------------------------
# Plain-script runner (matches existing scripts/test_*.py convention)
# ---------------------------------------------------------------------------


def _run_all() -> int:
    """Discover and run every ``test_*`` function in this module as a script."""
    tests = [
        (name, obj)
        for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    failures: list[str] = []
    for name, fn in tests:
        try:
            fn()
            print(f"  ✓ {name}")
        except Exception as exc:  # noqa: BLE001 - report all, don't stop
            failures.append(name)
            print(f"  ✗ {name}: {type(exc).__name__}: {exc}")

    print()
    if failures:
        print(f"FAILED: {len(failures)}/{len(tests)} — {', '.join(failures)}")
        return 1
    print(f"PASSED: {len(tests)}/{len(tests)}")
    return 0


if __name__ == "__main__":
    sys.exit(_run_all())
