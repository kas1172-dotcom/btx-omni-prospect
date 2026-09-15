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
from time import sleep
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote, urlencode

from btx_omni.monitor.contracts import (
    RawEvidenceReference,
    SourceIdentity,
    SourceObservation,
    SourceVersion,
)
from btx_omni.monitor.ontology import EventType
from btx_omni.providers.research.http import public_request


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
    content_structure: str = "STRUCTURED_API"
    freshness_threshold_hours: int = 26
    seller_promotion_permitted: bool = True
    targeting_mode: str = "BROAD_PUBLIC_FEED"
    consumes_strategic_targets: bool = False


@dataclass(frozen=True)
class GovernedPublisher:
    """A bounded operator-approved publisher, never a crawl target."""

    id: str
    url: str
    owner_account_id: str | None = None
    owner_label: str | None = None
    source_type: str = "RSS"
    enabled: bool = True


DEFAULT_COMPANY_PUBLISHERS = (
    GovernedPublisher(
        "boeing-investor-press",
        "https://investors.boeing.com/rss/pressrelease.aspx",
        "boeing",
        "Boeing investor press releases",
    ),
    GovernedPublisher(
        "lockheed-news-releases",
        "https://news.lockheedmartin.com/news-releases?pagetemplate=rss",
        "lockheed-martin",
        "Lockheed Martin news releases",
    ),
    GovernedPublisher(
        "emerson-investor-news",
        "https://ir.emerson.com/news-events/press-releases/rss",
        "emerson",
        "Emerson investor news",
    ),
)


def _governed_publishers(
    value: str, *, required_owner: bool
) -> tuple[GovernedPublisher, ...]:
    if required_owner and value.strip().upper() == "DEFAULT":
        return DEFAULT_COMPANY_PUBLISHERS
    try:
        raw = json.loads(value or "[]")
    except json.JSONDecodeError as exc:
        raise ValueError("MALFORMED_GOVERNED_SOURCE_REGISTRY") from exc
    if not isinstance(raw, list):
        raise TypeError("MALFORMED_GOVERNED_SOURCE_REGISTRY")
    publishers: list[GovernedPublisher] = []
    for item in raw:
        if not isinstance(item, dict):
            raise TypeError("MALFORMED_GOVERNED_SOURCE_REGISTRY")
        identifier, url, owner = (
            item.get("id"),
            item.get("url"),
            item.get("canonical_account_id"),
        )
        if (
            not isinstance(identifier, str)
            or not identifier.strip()
            or not isinstance(url, str)
            or not url.startswith("https://")
        ):
            raise ValueError("MALFORMED_GOVERNED_SOURCE_REGISTRY")
        if required_owner and (not isinstance(owner, str) or not owner.strip()):
            raise ValueError("MALFORMED_GOVERNED_SOURCE_REGISTRY")
        source_type = str(item.get("source_type", "RSS")).upper()
        if source_type not in {"RSS", "ATOM"}:
            raise ValueError("UNSUPPORTED_GOVERNED_SOURCE_TYPE")
        publishers.append(
            GovernedPublisher(
                identifier.strip(),
                url,
                owner.strip() if isinstance(owner, str) and owner.strip() else None,
                str(item.get("owner_label") or "").strip() or None,
                source_type,
                bool(item.get("enabled", True)),
            )
        )
    return tuple(item for item in publishers if item.enabled)


HttpGet = Callable[[str, dict[str, str]], tuple[int, bytes, dict[str, str]]]
HttpPost = Callable[[str, bytes, dict[str, str]], tuple[int, bytes, dict[str, str]]]


def default_get(url: str, headers: dict[str, str]) -> tuple[int, bytes, dict[str, str]]:
    response = public_request(url, headers=headers)
    return (
        response.status,
        response.body,
        {**response.headers, "x-btx-resolved-url": response.final_url},
    )


def default_post(
    url: str, body: bytes, headers: dict[str, str]
) -> tuple[int, bytes, dict[str, str]]:
    response = public_request(url, headers=headers, body=body)
    return response.status, response.body, response.headers


class LiveSourceAdapter:
    definition: SourceDefinition

    def __init__(self, get: HttpGet = default_get) -> None:
        self.get = get

    def available(self, settings: Any) -> tuple[bool, str | None]:
        return True, None

    def collection_warnings(self) -> tuple[str, ...]:
        """Bounded non-fatal source-unit outcomes from the last collection."""
        return ()

    def request_url(self, limit: int, *, collected_at: datetime | None = None) -> str:
        return self.definition.api_base

    def collect(
        self,
        *,
        run_id: str,
        settings: Any,
        limit: int = 10,
        collected_at: datetime | None = None,
    ) -> list[SourceObservation]:
        allowed, reason = self.available(settings)
        if not allowed:
            raise PermissionError(reason or "source credentials unavailable")
        status, payload, _headers = self.get(
            self.request_url(limit, collected_at=collected_at), self.headers(settings)
        )
        if status == 429:
            raise RuntimeError("RATE_LIMITED")
        if status >= 400:
            raise RuntimeError(f"HTTP_{status}")
        return self.parse(payload, run_id=run_id, collected_at=collected_at)[:limit]

    def headers(self, settings: Any) -> dict[str, str]:
        return {"User-Agent": "OmniProspectMonitor/2.0 contact=monitor@localhost"}

    def parse(
        self,
        payload: bytes,
        *,
        run_id: str,
        collected_at: datetime | None = None,
    ) -> list[SourceObservation]:
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("MALFORMED_SOURCE_RESPONSE") from exc
        return [
            self._observation(item, run_id, collected_at=collected_at)
            for item in self.items(decoded)
        ]

    def items(self, decoded: Any) -> list[dict[str, Any]]:
        return decoded if isinstance(decoded, list) else []

    def record_id(self, item: dict[str, Any]) -> str:
        return str(
            item.get("id")
            or item.get("noticeId")
            or item.get("accessionNumber")
            or item.get("document_number")
            or item.get("Award ID")
            or item.get("k_number")
            or item.get("url")
            or hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest()
        )

    def title(self, item: dict[str, Any]) -> str:
        return str(
            item.get("title")
            or item.get("description")
            or item.get("Description")
            or item.get("device_name")
            or item.get("name")
            or self.record_id(item)
        )

    def url(self, item: dict[str, Any]) -> str:
        return str(
            item.get("url")
            or item.get("link")
            or item.get("uiLink")
            or item.get("html_url")
            or self.definition.api_base
        )

    def published(self, item: dict[str, Any]) -> datetime | None:
        for key in (
            "publication_date",
            "publish_date",
            "postedDate",
            "date",
            "filingDate",
            "Action Date",
            "decision_date",
            "clearance_date",
        ):
            value = item.get(key)
            if value:
                try:
                    parsed = datetime.fromisoformat(str(value))
                    return (
                        parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
                    ).astimezone(UTC)
                except ValueError:
                    try:
                        return parsedate_to_datetime(str(value)).astimezone(UTC)
                    except (TypeError, ValueError):
                        return None
        return None

    def _observation(
        self,
        item: dict[str, Any],
        run_id: str,
        *,
        collected_at: datetime | None = None,
    ) -> SourceObservation:
        now = collected_at or datetime.now(UTC)
        record_id = self.record_id(item)
        content = json.dumps(item, sort_keys=True, separators=(",", ":"))
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        identity = SourceIdentity(self.definition.source_id, record_id)
        version = SourceVersion(
            record_id,
            str(item.get("version") or item.get("lastModifiedDate") or ""),
            content_hash,
            now,
            now,
        )
        evidence_id = f"evidence-{self.definition.source_id}-{content_hash[:16]}"
        evidence = RawEvidenceReference(
            evidence_id,
            identity,
            version,
            self.url(item),
            now,
            self.title(item),
            "application/json",
        )
        return SourceObservation(
            f"observation-{self.definition.source_id}-{content_hash[:16]}",
            identity,
            version,
            now,
            self.title(item),
            evidence,
            self.published(item),
            self.url(item),
            self.definition.source_tier.value,
            run_id,
            content,
        )


def _rss_observations(
    adapter: LiveSourceAdapter,
    payload: bytes,
    *,
    run_id: str,
    collected_at: datetime | None = None,
    owner: GovernedPublisher | None = None,
) -> list[SourceObservation]:
    """Parse RSS/Atom only; a registry entry is not permission to crawl HTML."""
    try:
        root = element_tree.fromstring(payload)
    except element_tree.ParseError as exc:
        raise ValueError("MALFORMED_SOURCE_RESPONSE") from exc
    rows: list[dict[str, Any]] = []
    for item in root.findall(".//item"):
        link = item.findtext("link")
        if owner and link and link.startswith("http://"):
            link = "https://" + link.removeprefix("http://")
        rows.append(
            {
                "id": item.findtext("guid") or link,
                "title": item.findtext("title"),
                "url": link,
                "publication_date": item.findtext("pubDate"),
                "publisher_owner": owner.owner_account_id if owner else None,
                "publisher_id": owner.id if owner else None,
            }
        )
    atom = "{http://www.w3.org/2005/Atom}"
    for item in root.findall(f".//{atom}entry"):
        link = next(
            (
                entry.attrib.get("href")
                for entry in item.findall(f"{atom}link")
                if entry.attrib.get("href")
            ),
            None,
        )
        rows.append(
            {
                "id": item.findtext(f"{atom}id") or link,
                "title": item.findtext(f"{atom}title"),
                "url": link,
                "publication_date": item.findtext(f"{atom}published")
                or item.findtext(f"{atom}updated"),
                "publisher_owner": owner.owner_account_id if owner else None,
                "publisher_id": owner.id if owner else None,
            }
        )
    observations = []
    for row in rows:
        observation = adapter._observation(row, run_id, collected_at=collected_at)
        if owner and owner.owner_account_id:
            observation = replace(
                observation,
                source_identity=SourceIdentity(
                    adapter.definition.source_id,
                    observation.source_identity.source_record_id,
                    (
                        ("governed_source_owner", owner.owner_account_id),
                        ("governed_publisher", owner.id),
                    ),
                ),
            )
        observations.append(observation)
    return observations


class SamAdapter(LiveSourceAdapter):
    definition = SourceDefinition(
        "sam_gov",
        "SAM.gov Contract Opportunities",
        SourceTier.TIER_1_AUTHORITATIVE_STRUCTURED,
        "federal procurement",
        ("Defense", "Space", "Commercial Aerospace"),
        (
            EventType.SOLICITATION,
            EventType.CONTRACT_AWARD,
            EventType.CONTRACT_MODIFICATION,
        ),
        "hourly",
        "search date range",
        "SAM_API_KEY required",
        "API key; obey published rate limits",
        "https://api.sam.gov/prod/opportunities/v2/search",
        "noticeId; UEI/CAGE when published",
        freshness_threshold_hours=2,
    )

    def available(self, settings: Any) -> tuple[bool, str | None]:
        return bool(settings.sam_api_key), "SAM_API_KEY is not configured"

    def request_url(self, limit: int, *, collected_at: datetime | None = None) -> str:
        today = (collected_at or datetime.now(UTC)).date()
        window_start = today - timedelta(days=getattr(self, "_lookback_days", 14))
        query: dict[str, object] = {
            "limit": limit,
            "offset": 0,
            "postedFrom": window_start.strftime("%m/%d/%Y"),
            "postedTo": today.strftime("%m/%d/%Y"),
        }
        # Do not apply unverified classifications to a production query.
        naics = tuple(
            code.strip() for code in getattr(self, "_sam_naics", ()) if code.strip()
        )
        if naics:
            # SAM's public opportunity API documents ncode as one six-digit
            # string, so this diagnostic URL represents the first governed
            # target. collect() executes the bounded multi-code plan.
            query["ncode"] = naics[0]
        return f"{self.definition.api_base}?{urlencode(query)}"

    def collect(
        self,
        *,
        run_id: str,
        settings: Any,
        limit: int = 10,
        collected_at: datetime | None = None,
    ) -> list[SourceObservation]:
        self._sam_naics = (
            tuple(
                value.strip()
                for value in settings.monitor_sam_naics.split(",")
                if value.strip()
            )
            if settings.monitor_sam_naics_verification_state == "VERIFIED"
            else ()
        )
        self._lookback_days = min(
            60, max(1, int(getattr(settings, "monitor_public_lookback_days", 14)))
        )
        allowed, reason = self.available(settings)
        if not allowed:
            raise PermissionError(reason or "SAM.gov is not configured")
        observations: list[SourceObservation] = []
        today = (collected_at or datetime.now(UTC)).date()
        if self._sam_naics:
            # The official endpoint accepts one ncode per request. Search each
            # governed code in stable order with an explicit total request cap;
            # do not send an undocumented comma-separated value.
            per_code = max(
                1, min(100, (limit + len(self._sam_naics) - 1) // len(self._sam_naics))
            )
            seen: set[str] = set()
            for code in sorted(self._sam_naics)[:32]:
                query: dict[str, object] = {
                    "limit": per_code,
                    "offset": 0,
                    "api_key": settings.sam_api_key,
                    "postedFrom": (
                        today - timedelta(days=self._lookback_days)
                    ).strftime("%m/%d/%Y"),
                    "postedTo": today.strftime("%m/%d/%Y"),
                    "ncode": code,
                }
                status, payload, _headers = self.get(
                    f"{self.definition.api_base}?{urlencode(query)}",
                    self.headers(settings),
                )
                if status == 429:
                    raise RuntimeError("RATE_LIMITED")
                if status >= 400:
                    raise RuntimeError(f"HTTP_{status}")
                try:
                    rows = self.items(json.loads(payload))
                except json.JSONDecodeError as exc:
                    raise ValueError("MALFORMED_SOURCE_RESPONSE") from exc
                for row in rows:
                    observation = self._observation(
                        row, run_id, collected_at=collected_at
                    )
                    if observation.source_identity.source_record_id not in seen:
                        seen.add(observation.source_identity.source_record_id)
                        observations.append(observation)
            return observations[:limit]
        offset = 0
        while len(observations) < limit:
            query: dict[str, object] = {
                "limit": min(limit - len(observations), 100),
                "offset": offset,
                "api_key": settings.sam_api_key,
                "postedFrom": (today - timedelta(days=self._lookback_days)).strftime(
                    "%m/%d/%Y"
                ),
                "postedTo": today.strftime("%m/%d/%Y"),
            }
            if self._sam_naics:
                query["ncode"] = ",".join(self._sam_naics)
            status, payload, _headers = self.get(
                f"{self.definition.api_base}?{urlencode(query)}", self.headers(settings)
            )
            if status == 429:
                raise RuntimeError("RATE_LIMITED")
            if status >= 400:
                raise RuntimeError(f"HTTP_{status}")
            try:
                decoded = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise ValueError("MALFORMED_SOURCE_RESPONSE") from exc
            rows = self.items(decoded)
            observations.extend(
                self._observation(row, run_id, collected_at=collected_at)
                for row in rows
            )
            offset += len(rows)
            if not rows or offset >= int(decoded.get("totalRecords", offset)):
                break
        return observations[:limit]

    def items(self, decoded: Any) -> list[dict[str, Any]]:
        return decoded.get("opportunitiesData", [])


class UsaSpendingAdapter(LiveSourceAdapter):
    definition = SourceDefinition(
        "usaspending",
        "USAspending Awards",
        SourceTier.TIER_1_AUTHORITATIVE_STRUCTURED,
        "federal spending",
        (
            "Commercial Aerospace",
            "Defense",
            "Space",
            "Robotics",
            "Semiconductor",
            "Medical",
            "Energy",
        ),
        (
            EventType.CONTRACT_AWARD,
            EventType.CONTRACT_MODIFICATION,
            EventType.GOVERNMENT_FUNDING,
        ),
        "daily",
        "award search history",
        "keyless",
        "public endpoint; bounded recipient queries plus transaction detail",
        "https://api.usaspending.gov/api/v2/search/spending_by_award/",
        "generated_internal_id; exact verified recipient legal name",
        targeting_mode="ACCOUNT_TARGETED",
        consumes_strategic_targets=True,
    )

    def __init__(
        self,
        get: HttpGet = default_get,
        *,
        recipient_names: tuple[str, ...] = (),
        post: HttpPost = default_post,
    ) -> None:
        super().__init__(get)
        self.recipient_names = recipient_names
        self.post = post

    def available(self, settings: Any) -> tuple[bool, str | None]:
        return bool(
            self.recipient_names
        ), "verified USAspending recipient targets are required"

    def items(self, decoded: Any) -> list[dict[str, Any]]:
        return decoded.get("results", [])

    def record_id(self, item: dict[str, Any]) -> str:
        generated_id = item.get("generated_internal_id")
        if generated_id:
            return str(generated_id)
        if item.get("Award ID"):
            return str(item["Award ID"])
        return (
            "missing-generated-award-id-"
            + hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest()[:24]
        )

    def url(self, item: dict[str, Any]) -> str:
        award_id = item.get("generated_internal_id")
        return (
            f"https://api.usaspending.gov/api/v2/awards/{quote(str(award_id), safe='')}/"
            if award_id
            else self.definition.api_base
        )

    def collect(
        self,
        *,
        run_id: str,
        settings: Any,
        limit: int = 10,
        collected_at: datetime | None = None,
    ) -> list[SourceObservation]:
        if not self.recipient_names:
            raise PermissionError("USASPENDING_TARGET_RECIPIENTS_REQUIRED")
        today = (collected_at or datetime.now(UTC)).date()
        start = today - timedelta(days=90)
        per_target = max(1, limit // len(self.recipient_names))
        observations: list[SourceObservation] = []
        for recipient_name in self.recipient_names:
            body = json.dumps(
                {
                    "filters": {
                        "time_period": [
                            {
                                "start_date": start.isoformat(),
                                "end_date": today.isoformat(),
                            }
                        ],
                        "award_type_codes": ["A", "B", "C", "D"],
                        "recipient_search_text": [recipient_name],
                    },
                    "fields": [
                        "Award ID",
                        "Description",
                        "Award Amount",
                        "Recipient Name",
                        "Awarding Agency",
                        "Awarding Sub Agency",
                        "Award Type",
                    ],
                    "limit": per_target,
                    "page": 1,
                    "subawards": False,
                }
            ).encode()
            try:
                status, payload, _headers = self.post(
                    self.definition.api_base,
                    body,
                    {"content-type": "application/json", **self.headers(settings)},
                )
                if status == 429:
                    raise RuntimeError("RATE_LIMITED")
                if status >= 400:
                    raise RuntimeError(f"HTTP_{status}")
                award_rows = self.items(json.loads(payload))
                for award in award_rows:
                    generated_id = award.get("generated_internal_id")
                    transaction = self._latest_transaction(generated_id, settings)
                    observations.append(
                        self._observation(
                            self._combine_award_and_transaction(award, transaction),
                            run_id,
                            collected_at=collected_at,
                        )
                    )
            except HTTPError as exc:
                if exc.code == 429:
                    raise RuntimeError("RATE_LIMITED") from exc
                raise RuntimeError(f"HTTP_{exc.code}") from exc
        # `limit` is apportioned per targeted recipient. Do not silently omit a
        # researched target merely because the roster is larger than one page.
        return observations

    def _latest_transaction(
        self, generated_id: object, settings: Any
    ) -> dict[str, Any] | None:
        if not generated_id:
            return None
        body = json.dumps(
            {
                "award_id": str(generated_id),
                "page": 1,
                "limit": 1,
                "sort": "action_date",
                "order": "desc",
            }
        ).encode()
        status, payload, _headers = self.post(
            "https://api.usaspending.gov/api/v2/transactions/",
            body,
            {"content-type": "application/json", **self.headers(settings)},
        )
        if status == 429:
            raise RuntimeError("RATE_LIMITED")
        if status >= 400:
            raise RuntimeError(f"HTTP_{status}")
        rows = json.loads(payload).get("results", [])
        return rows[0] if rows else None

    @staticmethod
    def _combine_award_and_transaction(
        award: dict[str, Any], transaction: dict[str, Any] | None
    ) -> dict[str, Any]:
        combined = dict(award)
        if transaction:
            combined["Action Date"] = transaction.get("action_date")
            combined["Description"] = transaction.get("description") or combined.get(
                "Description"
            )
            combined["Award Type Code"] = transaction.get("type") or combined.get(
                "Award Type"
            )
            combined["Transaction Amount"] = transaction.get(
                "federal_action_obligation"
            )
        return combined


class FederalRegisterAdapter(LiveSourceAdapter):
    definition = SourceDefinition(
        "federal_register",
        "Federal Register",
        SourceTier.TIER_1_AUTHORITATIVE_STRUCTURED,
        "federal rulemaking",
        ("Defense", "Space", "Medical", "Semiconductor", "Energy"),
        (
            EventType.REGULATORY_CHANGE,
            EventType.SOLICITATION,
            EventType.GOVERNMENT_FUNDING,
        ),
        "daily",
        "documents API archives",
        "keyless",
        "public API",
        "https://www.federalregister.gov/api/v1/documents.json",
        "document_number",
    )

    def request_url(self, limit: int, *, collected_at: datetime | None = None) -> str:
        return f"{self.definition.api_base}?{urlencode({'per_page': limit, 'order': 'newest'})}"

    def items(self, decoded: Any) -> list[dict[str, Any]]:
        return decoded.get("results", [])


class SecEdgarAdapter(LiveSourceAdapter):
    definition = SourceDefinition(
        "sec_edgar",
        "SEC EDGAR Submissions",
        SourceTier.TIER_1_AUTHORITATIVE_STRUCTURED,
        "securities filings",
        (
            "Commercial Aerospace",
            "Defense",
            "Space",
            "Semiconductor",
            "Medical",
            "Energy",
        ),
        (
            EventType.EARNINGS_SIGNAL,
            EventType.BACKLOG_CHANGE,
            EventType.CAPITAL_INVESTMENT,
            EventType.M_AND_A,
            EventType.FACILITY_EXPANSION,
        ),
        "daily",
        "full submissions archives",
        "keyless",
        "requires descriptive User-Agent and SEC fair access",
        "https://data.sec.gov/submissions",
        "CIK/accession number",
    )

    def __init__(
        self, get: HttpGet = default_get, *, targets: tuple[tuple[str, str], ...] = ()
    ) -> None:
        super().__init__(get)
        self.targets = targets

    def available(self, settings: Any) -> tuple[bool, str | None]:
        if not self.targets:
            return False, "verified SEC CIK targets are required"
        if not settings.sec_user_agent:
            return False, "BTX_SEC_USER_AGENT with organization and contact is required"
        return True, None

    def headers(self, settings: Any) -> dict[str, str]:
        return {
            "User-Agent": settings.sec_user_agent,
            "Accept-Encoding": "gzip, deflate",
        }

    def collect(
        self,
        *,
        run_id: str,
        settings: Any,
        limit: int = 10,
        collected_at: datetime | None = None,
    ) -> list[SourceObservation]:
        allowed, reason = self.available(settings)
        if not allowed:
            raise PermissionError(reason or "SEC EDGAR is not configured")
        per_target = max(1, limit // len(self.targets))
        observations: list[SourceObservation] = []
        for index, (cik, account_name) in enumerate(self.targets):
            url = f"{self.definition.api_base}/CIK{cik.zfill(10)}.json"
            status, payload, _headers = self.get(url, self.headers(settings))
            if status == 429:
                raise RuntimeError("RATE_LIMITED")
            if status >= 400:
                raise RuntimeError(f"HTTP_{status}")
            observations.extend(
                self._parse_submissions(
                    payload,
                    cik=cik,
                    account_name=account_name,
                    run_id=run_id,
                    collected_at=collected_at,
                )[:per_target]
            )
            # Four requests/second is deliberately below the SEC's published
            # 10 requests/second ceiling and preserves a bounded worker load.
            if index + 1 < len(self.targets):
                sleep(0.25)
        return observations

    def _parse_submissions(
        self,
        payload: bytes,
        *,
        cik: str,
        account_name: str,
        run_id: str,
        collected_at: datetime | None,
    ) -> list[SourceObservation]:
        try:
            recent = json.loads(payload).get("filings", {}).get("recent", {})
        except json.JSONDecodeError as exc:
            raise ValueError("MALFORMED_SOURCE_RESPONSE") from exc
        forms = recent.get("form", [])
        filings: list[SourceObservation] = []
        for index, form in enumerate(forms):
            if form not in {"10-K", "10-Q"}:
                continue
            accession = str(recent.get("accessionNumber", [])[index])
            primary_document = str(recent.get("primaryDocument", [""])[index])
            filing_date = recent.get("filingDate", [None])[index]
            item = {
                "accessionNumber": accession,
                "filingDate": filing_date,
                "form": form,
                "primaryDocument": primary_document,
                "issuer_name": account_name,
                "cik": cik,
                "title": f"{account_name} {form} filing",
            }
            filings.append(self._observation(item, run_id, collected_at=collected_at))
        return filings

    def url(self, item: dict[str, Any]) -> str:
        accession = str(item.get("accessionNumber", "")).replace("-", "")
        primary_document = str(item.get("primaryDocument", ""))
        cik = str(item.get("cik", "")).lstrip("0")
        if accession and primary_document and cik:
            return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{primary_document}"
        return self.definition.api_base

    def _observation(
        self, item: dict[str, Any], run_id: str, *, collected_at: datetime | None = None
    ) -> SourceObservation:
        observation = super()._observation(item, run_id, collected_at=collected_at)
        return replace(
            observation,
            source_identity=SourceIdentity(
                self.definition.source_id,
                observation.source_identity.source_record_id,
                (("sec_cik", str(item["cik"]).zfill(10)),),
            ),
        )


class NasaAdapter(LiveSourceAdapter):
    definition = SourceDefinition(
        "nasa",
        "NASA Official News",
        SourceTier.TIER_2_AUTHORITATIVE_PUBLISHER,
        "NASA official publisher",
        ("Space", "Commercial Aerospace"),
        (
            EventType.PROGRAM_LAUNCH,
            EventType.CONTRACT_AWARD,
            EventType.GOVERNMENT_FUNDING,
            EventType.PARTNERSHIP,
        ),
        "daily",
        "news archive",
        "keyless",
        "RSS/API availability varies",
        "https://www.nasa.gov/rss/dyn/breaking_news.rss",
        "canonical article URL; NASA program names",
        content_structure="OFFICIAL_RSS_WITH_UNSTRUCTURED_TEXT",
    )

    def parse(
        self,
        payload: bytes,
        *,
        run_id: str,
        collected_at: datetime | None = None,
    ) -> list[SourceObservation]:
        try:
            root = element_tree.fromstring(payload)
        except element_tree.ParseError as exc:
            raise ValueError("MALFORMED_SOURCE_RESPONSE") from exc
        return [
            self._observation(
                {
                    "id": item.findtext("guid") or item.findtext("link"),
                    "title": item.findtext("title"),
                    "url": item.findtext("link"),
                    "publication_date": item.findtext("pubDate"),
                },
                run_id,
                collected_at=collected_at,
            )
            for item in root.findall(".//item")
        ]


class DodAdapter(LiveSourceAdapter):
    definition = SourceDefinition(
        "dod",
        "US Department of Defense Contract Announcements",
        SourceTier.TIER_2_AUTHORITATIVE_PUBLISHER,
        "DoD official RSS publisher",
        ("Defense", "Space"),
        (
            EventType.CONTRACT_AWARD,
            EventType.CONTRACT_MODIFICATION,
            EventType.SUPPLIER_AWARD,
        ),
        "daily",
        "official contract-announcement RSS",
        "keyless",
        "bounded official RSS; no general-site crawling",
        "https://www.war.gov/DesktopModules/ArticleCS/RSS.ashx?ContentType=400&Site=945&max=10",
        "canonical official article URL",
        content_structure="OFFICIAL_RSS",
        seller_promotion_permitted=False,
    )

    def parse(
        self, payload: bytes, *, run_id: str, collected_at: datetime | None = None
    ) -> list[SourceObservation]:
        return _rss_observations(
            self, payload, run_id=run_id, collected_at=collected_at
        )


class CommerceAdapter(LiveSourceAdapter):
    definition = SourceDefinition(
        "commerce",
        "Department of Commerce News",
        SourceTier.TIER_1_AUTHORITATIVE_STRUCTURED,
        "Commerce official content API",
        ("Semiconductor", "Commercial Aerospace", "Energy"),
        (
            EventType.GOVERNMENT_FUNDING,
            EventType.GRANT_AWARD,
            EventType.CAPACITY_EXPANSION,
            EventType.NEW_FACILITY,
        ),
        "daily",
        "official news API",
        "COMMERCE_API_KEY required",
        "data.gov API key; bounded pagination",
        "https://api.commerce.gov/api/news",
        "Commerce content ID and canonical release URL",
        content_structure="OFFICIAL_JSON_API",
        seller_promotion_permitted=False,
    )
    _terms = (
        "chip",
        "semiconductor",
        "manufactur",
        "aerospace",
        "industrial",
        "facility",
        "supply chain",
        "investment",
        "production",
        "grant",
        "funding",
    )

    def available(self, settings: Any) -> tuple[bool, str | None]:
        return bool(settings.commerce_api_key), "BTX_COMMERCE_API_KEY is not configured"

    def request_url(self, limit: int, *, collected_at: datetime | None = None) -> str:
        return f"{self.definition.api_base}?{urlencode({'api_key': 'configured', 'page[limit]': limit, 'page[offset]': 0})}"

    def collect(
        self,
        *,
        run_id: str,
        settings: Any,
        limit: int = 10,
        collected_at: datetime | None = None,
    ) -> list[SourceObservation]:
        allowed, reason = self.available(settings)
        if not allowed:
            raise PermissionError(reason or "Commerce is not configured")
        status, payload, _headers = self.get(
            f"{self.definition.api_base}?{urlencode({'api_key': settings.commerce_api_key, 'page[limit]': min(limit, 50), 'page[offset]': 0})}",
            self.headers(settings),
        )
        if status == 429:
            raise RuntimeError("RATE_LIMITED")
        if status >= 400:
            raise RuntimeError(f"HTTP_{status}")
        try:
            rows = json.loads(payload).get("data", [])
        except json.JSONDecodeError as exc:
            raise ValueError("MALFORMED_SOURCE_RESPONSE") from exc
        return [
            self._observation(item, run_id, collected_at=collected_at)
            for item in rows
            if any(term in json.dumps(item).casefold() for term in self._terms)
        ][:limit]

    def record_id(self, item: dict[str, Any]) -> str:
        return str(item.get("id") or item.get("uuid") or super().record_id(item))

    def title(self, item: dict[str, Any]) -> str:
        return str(
            item.get("title")
            or item.get("name")
            or item.get("attributes", {}).get("title")
            or super().title(item)
        )

    def url(self, item: dict[str, Any]) -> str:
        return str(
            item.get("url")
            or item.get("links", {}).get("self")
            or item.get("attributes", {}).get("url")
            or self.definition.api_base
        )

    def published(self, item: dict[str, Any]) -> datetime | None:
        return super().published({**item, **item.get("attributes", {})})


class FdaAdapter(LiveSourceAdapter):
    definition = SourceDefinition(
        "fda_openfda",
        "FDA openFDA",
        SourceTier.TIER_1_AUTHORITATIVE_STRUCTURED,
        "FDA regulatory data",
        ("Medical",),
        (
            EventType.REGULATORY_APPROVAL,
            EventType.REGULATORY_CHANGE,
            EventType.PRODUCT_LAUNCH,
        ),
        "daily",
        "API datasets",
        "keyless",
        "API limits; clearance is not commercial launch",
        "https://api.fda.gov/device/510k.json",
        "K number/PMA/recall identifiers",
    )

    def items(self, decoded: Any) -> list[dict[str, Any]]:
        return decoded.get("results", [])

    def request_url(self, limit: int, *, collected_at: datetime | None = None) -> str:
        return f"{self.definition.api_base}?{urlencode({'limit': limit, 'sort': 'decision_date:desc'})}"


class CompanyNewsAdapter(LiveSourceAdapter):
    definition = SourceDefinition(
        "company_newsroom",
        "Official Company Newsroom",
        SourceTier.TIER_2_AUTHORITATIVE_PUBLISHER,
        "account official publisher",
        (
            "Commercial Aerospace",
            "Defense",
            "Space",
            "Robotics",
            "Semiconductor",
            "Medical",
            "Energy",
        ),
        tuple(EventType),
        "daily",
        "per-account archive",
        "keyless",
        "only verified watch-profile URLs; RSS preferred",
        "",
        "canonical account domain and release URL",
        content_structure="UNCONFIGURED_ACCOUNT_FEED",
        seller_promotion_permitted=False,
    )

    def _publishers(self, settings: Any) -> tuple[GovernedPublisher, ...]:
        return _governed_publishers(
            settings.monitor_company_feed_registry, required_owner=True
        )

    def available(self, settings: Any) -> tuple[bool, str | None]:
        try:
            publishers = self._publishers(settings)
        except ValueError as exc:
            return False, str(exc)
        return bool(
            publishers
        ), "BTX_MONITOR_COMPANY_FEED_REGISTRY has no enabled governed official feeds"

    def collect(
        self,
        *,
        run_id: str,
        settings: Any,
        limit: int = 10,
        collected_at: datetime | None = None,
    ) -> list[SourceObservation]:
        publishers = self._publishers(settings)
        if not publishers:
            raise PermissionError(
                "BTX_MONITOR_COMPANY_FEED_REGISTRY has no enabled governed official feeds"
            )
        observations: list[SourceObservation] = []
        failures: list[tuple[str, Exception]] = []
        self._last_collection_warnings = ()
        per_publisher = max(1, limit // len(publishers))
        for publisher in publishers:
            try:
                status, payload, _headers = self.get(
                    publisher.url, self.headers(settings)
                )
                if status == 429:
                    raise RuntimeError("RATE_LIMITED")
                if status >= 400:
                    raise RuntimeError(f"HTTP_{status}")
                observations.extend(
                    _rss_observations(
                        self,
                        payload,
                        run_id=run_id,
                        collected_at=collected_at,
                        owner=publisher,
                    )[:per_publisher]
                )
            except Exception as exc:  # noqa: BLE001 - per-publisher isolation boundary
                # Isolate one governed customer's broken feed; successful feeds
                # remain durable. If every feed fails, the source reports it.
                failures.append((publisher.id, exc))
        self._last_collection_warnings = tuple(
            f"{publisher_id}:{str(error)[:80]}"
            if str(error) in {"RATE_LIMITED", "MALFORMED_SOURCE_RESPONSE"}
            or str(error).startswith("HTTP_")
            else f"{publisher_id}:{type(error).__name__}: collection failed"
            for publisher_id, error in failures
        )
        if not observations and failures:
            raise failures[0][1]
        return observations[:limit]

    def collection_warnings(self) -> tuple[str, ...]:
        return getattr(self, "_last_collection_warnings", ())


class StateEconomicAdapter(LiveSourceAdapter):
    definition = SourceDefinition(
        "state_economic_development",
        "State Economic Development",
        SourceTier.TIER_2_AUTHORITATIVE_PUBLISHER,
        "state/local official publisher",
        ("Semiconductor", "Robotics", "Medical", "Commercial Aerospace", "Energy"),
        (
            EventType.FACILITY_EXPANSION,
            EventType.NEW_FACILITY,
            EventType.CAPITAL_INVESTMENT,
            EventType.GOVERNMENT_FUNDING,
        ),
        "weekly",
        "varies by state",
        "keyless",
        "adapter requires verified state publisher URL",
        "",
        "project ID/canonical release URL and facility geography",
        content_structure="UNCONFIGURED_PUBLISHER_FEED",
        freshness_threshold_hours=192,
        seller_promotion_permitted=False,
    )

    def _publishers(self, settings: Any) -> tuple[GovernedPublisher, ...]:
        return _governed_publishers(
            settings.monitor_state_source_registry, required_owner=False
        )

    def available(self, settings: Any) -> tuple[bool, str | None]:
        try:
            publishers = self._publishers(settings)
        except ValueError as exc:
            return False, str(exc)
        return bool(
            publishers
        ), "BTX_MONITOR_STATE_SOURCE_REGISTRY has no enabled official feeds"

    def collect(
        self,
        *,
        run_id: str,
        settings: Any,
        limit: int = 10,
        collected_at: datetime | None = None,
    ) -> list[SourceObservation]:
        publishers = self._publishers(settings)
        if not publishers:
            raise PermissionError(
                "BTX_MONITOR_STATE_SOURCE_REGISTRY has no enabled official feeds"
            )
        observations: list[SourceObservation] = []
        for publisher in publishers:
            status, payload, _headers = self.get(publisher.url, self.headers(settings))
            if status == 429:
                raise RuntimeError("RATE_LIMITED")
            if status >= 400:
                raise RuntimeError(f"HTTP_{status}")
            observations.extend(
                _rss_observations(
                    self,
                    payload,
                    run_id=run_id,
                    collected_at=collected_at,
                    owner=publisher,
                )
            )
        return observations[:limit]


REGISTRY: dict[str, LiveSourceAdapter] = {
    adapter.definition.source_id: adapter
    for adapter in (
        SamAdapter(),
        UsaSpendingAdapter(),
        FederalRegisterAdapter(),
        SecEdgarAdapter(),
        NasaAdapter(),
        DodAdapter(),
        CommerceAdapter(),
        FdaAdapter(),
        CompanyNewsAdapter(),
        StateEconomicAdapter(),
    )
}
