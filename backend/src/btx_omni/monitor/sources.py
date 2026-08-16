"""Live source registry and adapter boundary. No source-shaped payload crosses this module."""
from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as element_tree
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from enum import StrEnum
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from btx_omni.monitor.contracts import (
    RawEvidenceReference,
    SourceIdentity,
    SourceObservation,
    SourceVersion,
)
from btx_omni.monitor.ontology import EventType


class SourceTier(StrEnum):
    TIER_1_AUTHORITATIVE_STRUCTURED = "TIER_1_AUTHORITATIVE_STRUCTURED"
    TIER_2_AUTHORITATIVE_PUBLISHER = "TIER_2_AUTHORITATIVE_PUBLISHER"
    TIER_3_REPUTABLE_SECONDARY = "TIER_3_REPUTABLE_SECONDARY"
    TIER_4_DISCOVERY = "TIER_4_DISCOVERY"


@dataclass(frozen=True)
class SourceDefinition:
    source_id: str
    source_name: str
    source_tier: SourceTier
    authority_type: str
    industries_supported: tuple[str, ...]
    event_types_supported: tuple[EventType, ...]
    cadence: str
    backfill_capability: str
    authentication_requirement: str
    rate_limit_notes: str
    api_base: str
    identifier_strategy: str


HttpGet = Callable[[str, dict[str, str]], tuple[int, bytes, dict[str, str]]]


def default_get(url: str, headers: dict[str, str]) -> tuple[int, bytes, dict[str, str]]:
    request = Request(url, headers=headers)
    with urlopen(request, timeout=20) as response:  # nosec B310: source bases are registry-owned
        return response.status, response.read(), dict(response.headers.items())


class LiveSourceAdapter:
    definition: SourceDefinition

    def __init__(self, get: HttpGet = default_get) -> None:
        self.get = get

    def available(self, settings: Any) -> tuple[bool, str | None]:
        return True, None

    def request_url(self, limit: int) -> str:
        return self.definition.api_base

    def collect(self, *, run_id: str, settings: Any, limit: int = 10) -> list[SourceObservation]:
        allowed, reason = self.available(settings)
        if not allowed:
            raise PermissionError(reason or "source credentials unavailable")
        status, payload, _headers = self.get(self.request_url(limit), self.headers(settings))
        if status == 429:
            raise RuntimeError("RATE_LIMITED")
        if status >= 400:
            raise RuntimeError(f"HTTP_{status}")
        return self.parse(payload, run_id=run_id)[:limit]

    def headers(self, settings: Any) -> dict[str, str]:
        return {"User-Agent": "OmniProspectMonitor/2.0 contact=monitor@localhost"}

    def parse(self, payload: bytes, *, run_id: str) -> list[SourceObservation]:
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("MALFORMED_SOURCE_RESPONSE") from exc
        return [self._observation(item, run_id) for item in self.items(decoded)]

    def items(self, decoded: Any) -> list[dict[str, Any]]:
        return decoded if isinstance(decoded, list) else []

    def record_id(self, item: dict[str, Any]) -> str:
        return str(item.get("id") or item.get("noticeId") or item.get("accessionNumber") or item.get("document_number") or item.get("Award ID") or item.get("k_number") or item.get("url") or hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest())

    def title(self, item: dict[str, Any]) -> str:
        return str(item.get("title") or item.get("description") or item.get("Description") or item.get("device_name") or item.get("name") or self.record_id(item))

    def url(self, item: dict[str, Any]) -> str:
        return str(item.get("url") or item.get("link") or item.get("uiLink") or item.get("html_url") or self.definition.api_base)

    def published(self, item: dict[str, Any]) -> datetime | None:
        for key in ("publication_date", "publish_date", "postedDate", "date", "filingDate", "Action Date"):
            value = item.get(key)
            if value:
                try:
                    return datetime.fromisoformat(str(value)).astimezone(UTC)
                except ValueError:
                    try:
                        return parsedate_to_datetime(str(value)).astimezone(UTC)
                    except (TypeError, ValueError):
                        return None
        return None

    def _observation(self, item: dict[str, Any], run_id: str) -> SourceObservation:
        now = datetime.now(UTC)
        record_id = self.record_id(item)
        content = json.dumps(item, sort_keys=True, separators=(",", ":"))
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        identity = SourceIdentity(self.definition.source_id, record_id)
        version = SourceVersion(record_id, str(item.get("version") or item.get("lastModifiedDate") or ""), content_hash, now, now)
        evidence_id = f"evidence-{self.definition.source_id}-{content_hash[:16]}"
        evidence = RawEvidenceReference(evidence_id, identity, version, self.url(item), now, self.title(item), "application/json")
        return SourceObservation(f"observation-{self.definition.source_id}-{content_hash[:16]}", identity, version, now, self.title(item), evidence, self.published(item), self.url(item), self.definition.source_tier.value, run_id, content)


class SamAdapter(LiveSourceAdapter):
    definition = SourceDefinition("sam_gov", "SAM.gov Contract Opportunities", SourceTier.TIER_1_AUTHORITATIVE_STRUCTURED, "federal procurement", ("defense", "space", "commercial_aerospace"), (EventType.SOLICITATION, EventType.CONTRACT_AWARD, EventType.CONTRACT_MODIFICATION), "hourly", "search date range", "SAM_API_KEY required", "API key; obey published rate limits", "https://api.sam.gov/prod/opportunities/v2/search", "noticeId; UEI/CAGE when published")
    def available(self, settings: Any) -> tuple[bool, str | None]: return bool(settings.sam_api_key), "SAM_API_KEY is not configured"
    def request_url(self, limit: int) -> str:
        today = datetime.now(UTC).date()
        window_start = today - timedelta(days=14)
        return f"{self.definition.api_base}?{urlencode({'limit': limit, 'postedFrom': window_start.strftime('%m/%d/%Y'), 'postedTo': today.strftime('%m/%d/%Y')})}"
    def headers(self, settings: Any) -> dict[str, str]: return {"X-Api-Key": settings.sam_api_key, **super().headers(settings)}
    def items(self, decoded: Any) -> list[dict[str, Any]]: return decoded.get("opportunitiesData", [])


class UsaSpendingAdapter(LiveSourceAdapter):
    definition = SourceDefinition("usaspending", "USAspending Awards", SourceTier.TIER_1_AUTHORITATIVE_STRUCTURED, "federal spending", ("defense", "space", "commercial_aerospace", "semiconductor"), (EventType.CONTRACT_AWARD, EventType.CONTRACT_MODIFICATION, EventType.GOVERNMENT_FUNDING), "daily", "award search history", "keyless", "public endpoint; bounded queries", "https://api.usaspending.gov/api/v2/search/spending_by_award/", "award_id; recipient UEI when available")
    def items(self, decoded: Any) -> list[dict[str, Any]]: return decoded.get("results", [])
    def collect(self, *, run_id: str, settings: Any, limit: int = 10) -> list[SourceObservation]:
        body = json.dumps({"filters": {"time_period": [{"start_date": "2025-01-01", "end_date": "2026-12-31"}], "award_type_codes": ["A", "B", "C", "D"]}, "fields": ["Award ID", "Description", "Award Amount", "Recipient Name", "Action Date"], "limit": limit, "page": 1, "subawards": False}).encode()
        request = Request(self.definition.api_base, data=body, headers={"content-type": "application/json", **self.headers(settings)}, method="POST")
        try:
            with urlopen(request, timeout=20) as response:  # nosec B310: fixed registry endpoint
                return self.parse(response.read(), run_id=run_id)
        except HTTPError as exc:
            if exc.code == 429:
                raise RuntimeError("RATE_LIMITED") from exc
            raise RuntimeError(f"HTTP_{exc.code}") from exc


class FederalRegisterAdapter(LiveSourceAdapter):
    definition = SourceDefinition("federal_register", "Federal Register", SourceTier.TIER_1_AUTHORITATIVE_STRUCTURED, "federal rulemaking", ("defense", "space", "medical_device", "semiconductor"), (EventType.REGULATORY_CHANGE, EventType.SOLICITATION, EventType.GOVERNMENT_FUNDING), "daily", "documents API archives", "keyless", "public API", "https://www.federalregister.gov/api/v1/documents.json", "document_number")
    def items(self, decoded: Any) -> list[dict[str, Any]]: return decoded.get("results", [])


class SecEdgarAdapter(LiveSourceAdapter):
    definition = SourceDefinition("sec_edgar", "SEC EDGAR Submissions", SourceTier.TIER_1_AUTHORITATIVE_STRUCTURED, "securities filings", ("commercial_aerospace", "defense", "space", "semiconductor", "medical_device", "robotics"), (EventType.EARNINGS_SIGNAL, EventType.BACKLOG_CHANGE, EventType.CAPITAL_INVESTMENT, EventType.M_AND_A, EventType.FACILITY_EXPANSION), "daily", "full submissions archives", "keyless", "requires descriptive User-Agent and SEC fair access", "https://data.sec.gov/submissions", "CIK/accession number")
    def items(self, decoded: Any) -> list[dict[str, Any]]: return decoded.get("filings", {}).get("recent", {}).get("accessionNumber", []) and [{"accessionNumber": value, "filingDate": decoded["filings"]["recent"]["filingDate"][index], "form": decoded["filings"]["recent"]["form"][index]} for index, value in enumerate(decoded["filings"]["recent"]["accessionNumber"])]
    def available(self, settings: Any) -> tuple[bool, str | None]: return (self.definition.api_base != "https://data.sec.gov/submissions", "verified SEC CIK from an account watch profile is required")
    def for_cik(self, cik: str, get: HttpGet | None = None) -> SecEdgarAdapter:
        adapter = SecEdgarAdapter(get or self.get)
        adapter.definition = replace(self.definition, api_base=f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json")
        return adapter


class NasaAdapter(LiveSourceAdapter):
    definition = SourceDefinition("nasa", "NASA Official News", SourceTier.TIER_2_AUTHORITATIVE_PUBLISHER, "NASA official publisher", ("space", "commercial_aerospace"), (EventType.PROGRAM_LAUNCH, EventType.CONTRACT_AWARD, EventType.GOVERNMENT_FUNDING, EventType.PARTNERSHIP), "daily", "news archive", "keyless", "RSS/API availability varies", "https://www.nasa.gov/rss/dyn/breaking_news.rss", "canonical article URL; NASA program names")
    def parse(self, payload: bytes, *, run_id: str) -> list[SourceObservation]:
        try:
            root = element_tree.fromstring(payload)
        except element_tree.ParseError as exc:
            raise ValueError("MALFORMED_SOURCE_RESPONSE") from exc
        return [self._observation({"id": item.findtext("guid") or item.findtext("link"), "title": item.findtext("title"), "url": item.findtext("link"), "publication_date": item.findtext("pubDate")}, run_id) for item in root.findall(".//item")]


class DodAdapter(LiveSourceAdapter):
    definition = SourceDefinition("dod", "US Department of Defense Contracts", SourceTier.TIER_2_AUTHORITATIVE_PUBLISHER, "DoD official publisher", ("defense", "space", "commercial_aerospace"), (EventType.CONTRACT_AWARD, EventType.CONTRACT_MODIFICATION, EventType.SUPPLIER_AWARD), "daily", "contract release archive", "keyless", "publisher layout may change", "https://www.defense.gov/News/Contracts/", "contract number; UEI/CAGE if present")


class CommerceAdapter(LiveSourceAdapter):
    definition = SourceDefinition("commerce", "Department of Commerce CHIPS", SourceTier.TIER_2_AUTHORITATIVE_PUBLISHER, "Commerce official publisher", ("semiconductor",), (EventType.GOVERNMENT_FUNDING, EventType.GRANT_AWARD, EventType.CAPACITY_EXPANSION, EventType.NEW_FACILITY), "daily", "announcement archive", "keyless", "publisher feed availability varies", "https://www.commerce.gov/news", "canonical release URL; award/project identifiers")


class FdaAdapter(LiveSourceAdapter):
    definition = SourceDefinition("fda_openfda", "FDA openFDA", SourceTier.TIER_1_AUTHORITATIVE_STRUCTURED, "FDA regulatory data", ("medical_device",), (EventType.REGULATORY_APPROVAL, EventType.REGULATORY_CHANGE, EventType.PRODUCT_LAUNCH), "daily", "API datasets", "keyless", "API limits; clearance is not commercial launch", "https://api.fda.gov/device/510k.json", "K number/PMA/recall identifiers")
    def items(self, decoded: Any) -> list[dict[str, Any]]: return decoded.get("results", [])
    def request_url(self, limit: int) -> str: return f"{self.definition.api_base}?{urlencode({'limit': limit})}"


class CompanyNewsAdapter(LiveSourceAdapter):
    definition = SourceDefinition("company_newsroom", "Official Company Newsroom", SourceTier.TIER_2_AUTHORITATIVE_PUBLISHER, "account official publisher", ("commercial_aerospace", "defense", "space", "semiconductor", "medical_device", "robotics"), tuple(EventType), "daily", "per-account archive", "keyless", "only verified watch-profile URLs; RSS preferred", "", "canonical account domain and release URL")
    def available(self, settings: Any) -> tuple[bool, str | None]: return False, "verified account-watch-profile newsroom URL is required"


class StateEconomicAdapter(LiveSourceAdapter):
    definition = SourceDefinition("state_economic_development", "State Economic Development", SourceTier.TIER_2_AUTHORITATIVE_PUBLISHER, "state/local official publisher", ("semiconductor", "robotics", "medical_device", "commercial_aerospace"), (EventType.FACILITY_EXPANSION, EventType.NEW_FACILITY, EventType.CAPITAL_INVESTMENT, EventType.GOVERNMENT_FUNDING), "weekly", "varies by state", "keyless", "adapter requires verified state publisher URL", "", "project ID/canonical release URL and facility geography")
    def available(self, settings: Any) -> tuple[bool, str | None]: return False, "verified state publisher URL is required"


REGISTRY: dict[str, LiveSourceAdapter] = {adapter.definition.source_id: adapter for adapter in (SamAdapter(), UsaSpendingAdapter(), FederalRegisterAdapter(), SecEdgarAdapter(), NasaAdapter(), DodAdapter(), CommerceAdapter(), FdaAdapter(), CompanyNewsAdapter(), StateEconomicAdapter())}
