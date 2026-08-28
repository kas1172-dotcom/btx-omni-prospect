"""Build the allow-listed normalized reference fixture from local XLSX inputs."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse
from zipfile import ZipFile

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PACKAGE_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
TOP_100_FILE = "Copy of btx top 100 customers 0726.xlsx"
FILES = (
    "Copy of commercial aero map template.xlsx", "Copy of Defense Map Template.xlsx",
    "Copy of UAV Map Template.xlsx", "Copy of semiconductor template map.xlsx",
    "Copy of medical device and bots map template.xlsx", TOP_100_FILE,
)
PROHIBITED = {
    "btx direct customer revenue (in 000's) ttm may2026",
    "active btx bu's with sales ttm", "btx targeting notes",
}
EXCLUDED = PROHIBITED | {"btx classification", "priority score", "visit priority score (1-10) 10=highest"}
ALLOWED = {
    "company name", "street address", "city", "state/province", "country", "latitude", "longitude",
    "corporate website", "main phone", "facility type", "employee count range", "company revenue range",
    "parent company", "subsidiaries / brands", "naics code", "naics description", "region tag",
    "detailed industry classification",
}
MARKET_BY_FILE = {
    "Copy of commercial aero map template.xlsx": "Commercial Aerospace",
    "Copy of Defense Map Template.xlsx": "Defense",
    "Copy of semiconductor template map.xlsx": "Semiconductor",
}
MEDICAL_NAICS = {"surgical appliance mfg", "electromedical apparatus", "surgical instrument mfg", "irradiation apparatus"}
PLACEHOLDERS = {"", "-", "–", "—", "n/a", "na", "none"}


def clean(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def normalized(value: object) -> str:
    value = unicodedata.normalize("NFKD", clean(value)).encode("ascii", "ignore").decode().casefold()
    return re.sub(r"[^a-z0-9]+", "", value)


def header(value: object) -> str:
    return " ".join(clean(value).casefold().split())


def slug(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().casefold()
    return re.sub(r"(^-|-$)", "", re.sub(r"[^a-z0-9]+", "-", value))


def host(value: object) -> str:
    raw = clean(value).casefold()
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    return parsed.netloc.removeprefix("www.").split(":")[0]


def root_domain(value: object) -> str:
    parts = host(value).split(".")
    if len(parts) <= 2:
        return ".".join(parts)
    compound = ".".join(parts[-2:]) in {"co.uk", "com.au", "co.jp", "co.nz"}
    return ".".join(parts[-3:] if compound else parts[-2:])


def assert_prohibited_fields_blank(*, workbook: str, sheet: str, headers: list[str], rows: list[tuple[int, list[str]]]) -> None:
    """Fail closed without returning or logging any prohibited cell value."""
    for prohibited in PROHIBITED:
        if prohibited not in headers:
            continue
        column = headers.index(prohibited)
        offenders = [number for number, row in rows if column < len(row) and clean(row[column])]
        if offenders:
            raise ValueError(f"prohibited field is nonblank: {workbook}/{sheet}/{prohibited}/rows {offenders}")


def column_index(reference: str) -> int:
    result = 0
    for letter in re.match(r"[A-Z]+", reference).group(0):
        result = result * 26 + ord(letter) - 64
    return result - 1


def workbook_rows(path: Path) -> list[tuple[str, int, dict[str, str]]]:
    result = []
    with ZipFile(path) as archive:
        try:
            strings_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            strings = ["".join(node.text or "" for node in item.iter(f"{{{NS_MAIN}}}t")) for item in strings_root]
        except KeyError:
            strings = []
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {item.attrib["Id"]: item.attrib["Target"] for item in relationships.findall(f"{{{NS_PACKAGE_REL}}}Relationship")}
        for sheet in workbook.find(f"{{{NS_MAIN}}}sheets"):
            name = sheet.attrib["name"]
            target = targets[sheet.attrib[f"{{{NS_REL}}}id"]].lstrip("/")
            target = target if target.startswith("xl/") else f"xl/{target}"
            xml = ET.fromstring(archive.read(target))
            rows = []
            for row in xml.findall(f".//{{{NS_MAIN}}}row"):
                values = {}
                for cell in row.findall(f"{{{NS_MAIN}}}c"):
                    index, kind = column_index(cell.attrib["r"]), cell.attrib.get("t")
                    value, inline = cell.find(f"{{{NS_MAIN}}}v"), cell.find(f"{{{NS_MAIN}}}is")
                    if kind == "s" and value is not None:
                        parsed = strings[int(value.text or 0)]
                    elif kind == "inlineStr" and inline is not None:
                        parsed = "".join(node.text or "" for node in inline.iter(f"{{{NS_MAIN}}}t"))
                    else:
                        parsed = value.text if value is not None else ""
                    values[index] = clean(parsed)
                rows.append((int(row.attrib["r"]), [values.get(index, "") for index in range(max(values, default=-1) + 1)]))
            candidates = []
            for offset, (_, row) in enumerate(rows[:40]):
                names = {header(value) for value in row if header(value)}
                candidates.append((len(names) + 20 * len(names & PROHIBITED) + (10 if "company name" in names else 0), offset))
            _, offset = max(candidates)
            header_row = rows[offset][1]
            if not header_row[0] and path.name == "Copy of semiconductor template map.xlsx":
                header_row[0] = "Company Name"
            normalized_headers = [header(value) for value in header_row]
            assert_prohibited_fields_blank(workbook=path.name, sheet=name, headers=normalized_headers, rows=rows[offset + 1:])
            unknown = {value for value in normalized_headers if value and value not in ALLOWED | EXCLUDED}
            if unknown:
                raise ValueError(f"unreviewed workbook columns: {path.name}/{name}/{sorted(unknown)}")
            for number, row in rows[offset + 1:]:
                record = {key: clean(row[index]) if index < len(row) else "" for index, key in enumerate(normalized_headers) if key in ALLOWED}
                if record.get("company name"):
                    result.append((name, number, record))
    return result


def build(input_dir: Path, existing_file: Path) -> dict[str, object]:
    missing = [name for name in FILES if not (input_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"missing sanitized reference workbooks: {missing}")
    existing_doc = json.loads(existing_file.read_text(encoding="utf-8"))
    existing = existing_doc["accounts"]
    existing_domains = {root_domain(item.get("official_domain")): item for item in existing if root_domain(item.get("official_domain"))}
    source_rows, source_manifest = [], []
    for file_index, filename in enumerate(FILES, start=1):
        rows = workbook_rows(input_dir / filename)
        source_id = f"sanitized-reference-{file_index:02d}"
        sheets = sorted({sheet for sheet, _, _ in rows})
        source_manifest.append({"source_id": source_id, "workbook": filename, "sheets": sheets, "row_count": len(rows), "sanitation_gate": "PASS_PROHIBITED_FIELDS_BLANK", "excluded_field_categories": ["BTX_INTERNAL_COLUMNS", "BTX_CLASSIFICATION", "SCORES"]})
        for sheet, row, record in rows:
            domain = root_domain(record["corporate website"])
            if not domain:
                raise ValueError(f"organization is missing corporate website: {filename}/{sheet}/{row}")
            source_rows.append({**record, "source_id": source_id, "workbook": filename, "sheet": sheet, "row": row, "source_reference": f"{source_id}:{sheet}:{row}", "domain": domain})

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in source_rows:
        grouped[row["domain"]].append(row)
    parent_domains: dict[str, set[str]] = defaultdict(set)
    for row in source_rows:
        parent = normalized(row.get("parent company"))
        if parent and clean(row.get("parent company")).casefold() not in PLACEHOLDERS:
            parent_domains[parent].add(row["domain"])
    domain_parent = {domain: domain for domain in grouped}

    def find(domain: str) -> str:
        while domain_parent[domain] != domain:
            domain_parent[domain] = domain_parent[domain_parent[domain]]
            domain = domain_parent[domain]
        return domain

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            domain_parent[max(left_root, right_root)] = min(left_root, right_root)

    ambiguous_parent_groups: set[str] = set()
    for parent, domains in parent_domains.items():
        existing_ids = {existing_domains[domain]["research_account_id"] for domain in domains if domain in existing_domains}
        if len(existing_ids) > 1:
            ambiguous_parent_groups.add(parent)
            continue
        first, *rest = sorted(domains)
        for domain in rest:
            union(first, domain)
    clustered: dict[str, list[dict[str, str]]] = defaultdict(list)
    for domain, rows in grouped.items():
        clustered[find(domain)].extend(rows)
    used_ids = {item["research_account_id"] for item in existing}
    accounts, identity_audit, domain_to_id = [], [], {}
    for _, rows in sorted(clustered.items()):
        domains = sorted({row["domain"] for row in rows})
        existing_matches = {existing_domains[domain]["research_account_id"]: existing_domains[domain] for domain in domains if domain in existing_domains}
        if len(existing_matches) > 1:
            raise ValueError(f"identity cluster maps to multiple canonical Customers: {domains}")
        existing_item = next(iter(existing_matches.values()), None)
        top_rows = [row for row in rows if row["workbook"] == TOP_100_FILE]
        parents = [clean(row.get("parent company")) for row in rows if clean(row.get("parent company")).casefold() not in PLACEHOLDERS]
        if existing_item:
            account_id, display_name, disposition = existing_item["research_account_id"], existing_item["display_name"], "MATCHED_EXISTING_CUSTOMER"
        else:
            top_names = {normalized(row["company name"]): clean(row["company name"]) for row in top_rows}
            eligible_parents = [parent for parent in parents if normalized(parent) not in ambiguous_parent_groups]
            explicit_root = next((parent for parent, _ in Counter(eligible_parents).most_common() if normalized(parent) in top_names), None)
            candidate = explicit_root or (clean(top_rows[0]["company name"]) if top_rows else (Counter(parents).most_common(1)[0][0] if parents else min((clean(row["company name"]) for row in rows), key=lambda value: (len(value), value.casefold()))))
            if normalized(candidate) in ambiguous_parent_groups:
                candidate = min((clean(row["company name"]) for row in rows), key=lambda value: (len(value), value.casefold()))
            account_id, display_name, disposition = slug(candidate), candidate, "NEW_CANONICAL_CUSTOMER"
            if account_id in used_ids:
                account_id = f"{account_id}-{hashlib.sha256('|'.join(domains).encode()).hexdigest()[:8]}"
            used_ids.add(account_id)
        for domain in domains:
            domain_to_id[domain] = account_id
        industries = set()
        segments = set()
        for row in rows:
            if market := MARKET_BY_FILE.get(row["workbook"]):
                industries.add(market)
            elif row["workbook"] == "Copy of medical device and bots map template.xlsx" and clean(row.get("naics description")).casefold() in MEDICAL_NAICS:
                industries.add("Medical")
            elif row["workbook"] == "Copy of UAV Map Template.xlsx":
                segments.add("UAV_REFERENCE_SEGMENT")
        references = sorted({row["source_reference"] for row in rows})
        top_references = sorted({row["source_reference"] for row in top_rows})
        aliases = sorted({clean(row["company name"]) for row in rows} | set(parents), key=lambda value: (value.casefold(), value))
        preferred_row = next((row for row in top_rows if normalized(row["company name"]) == normalized(display_name)), None) or next((row for row in rows if existing_item and root_domain(existing_item.get("official_domain")) == row["domain"]), None) or rows[0]
        domain, website = preferred_row["domain"], clean(preferred_row["corporate website"])
        accounts.append({"canonical_account_id": account_id, "display_name": display_name, "domain": domain, "website": website, "aliases": aliases, "industries": sorted(industries), "source_segments": sorted(segments), "source_references": references, "btx_top_100": bool(top_references), "btx_top_100_references": top_references, "existing_customer": bool(existing_item)})
        for row in rows:
            row_disposition = disposition if normalized(row["company name"]) == normalized(display_name) else "FACILITY_OR_SUBSIDIARY_OF_CANONICAL_CUSTOMER"
            identity_audit.append({"source_reference": row["source_reference"], "source_organization": clean(row["company name"]), "disposition": row_disposition, "canonical_account_id": account_id, "identity_evidence": "EXACT_CORPORATE_DOMAIN"})

    facilities_by_key: dict[tuple[object, ...], dict[str, object]] = {}
    excluded_locations = []
    for row in source_rows:
        latitude, longitude = clean(row.get("latitude")), clean(row.get("longitude"))
        if not latitude or not longitude:
            excluded_locations.append({"source_reference": row["source_reference"], "reason": "MISSING_COORDINATES"})
            continue
        try:
            lat, lon = float(latitude), float(longitude)
        except ValueError as exc:
            raise ValueError(f"invalid coordinates: {row['source_reference']}") from exc
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError(f"out-of-range coordinates: {row['source_reference']}")
        account_id = domain_to_id[row["domain"]]
        key = (account_id, round(lat, 6), round(lon, 6), normalized(row.get("city")), normalized(row.get("state/province")))
        if key not in facilities_by_key:
            stable = "|".join(map(str, key))
            facilities_by_key[key] = {"facility_id": f"reference-{account_id}-{hashlib.sha256(stable.encode()).hexdigest()[:12]}", "canonical_account_id": account_id, "name": clean(row["company name"]), "street_address": clean(row.get("street address")), "city": clean(row.get("city")), "region": clean(row.get("state/province")), "country": clean(row.get("country")), "latitude": latitude, "longitude": longitude, "website": clean(row.get("corporate website")), "facility_type": clean(row.get("facility type")) or "Reference facility", "source_references": []}
        facilities_by_key[key]["source_references"].append(row["source_reference"])
    facilities = sorted(facilities_by_key.values(), key=lambda item: item["facility_id"])
    for facility in facilities:
        facility["source_references"] = sorted(set(facility["source_references"]))
    return {"schema_version": "1.0", "observed_at": "2026-07-26T00:00:00", "sources": source_manifest, "accounts": accounts, "facilities": facilities, "identity_audit": identity_audit, "excluded_locations": excluded_locations, "unsupported_classifications": {"industry_top_100": "No authoritative complete ranking field is present.", "strategic_partnership": "No canonical source is present.", "uav_primary_market": "Retained as source-native segment; workbook does not authorize a canonical primary market."}}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--existing", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    document = build(args.input_dir, args.existing)
    args.output.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"accounts": len(document["accounts"]), "facilities": len(document["facilities"]), "audit_rows": len(document["identity_audit"]), "top_100_members": sum(item["btx_top_100"] for item in document["accounts"]), "excluded_locations": len(document["excluded_locations"])}, indent=2))


if __name__ == "__main__":
    main()
