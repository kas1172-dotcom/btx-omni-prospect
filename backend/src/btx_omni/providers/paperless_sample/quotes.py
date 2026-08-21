from __future__ import annotations

from datetime import date

from btx_omni.core.classification import Classification
from btx_omni.domain.quotes import (
    CommercialQuote,
    CommercialQuoteLineItem,
    PaperlessAccount,
    QuoteStatus,
)
from btx_omni.providers.research._catalog_support import document, source_provenance

_STATUS = {"OUTSTANDING": QuoteStatus.OPEN, "CONVERTED": QuoteStatus.WON, "LOST": QuoteStatus.LOST, "EXPIRED": QuoteStatus.EXPIRED, "CANCELLED": QuoteStatus.CANCELLED}


def load_paperless_quotes(*, accounts_by_id: dict[str, object], business_unit_ids: set[str], program_ids: set[str], component_ids: set[str]) -> tuple[tuple[PaperlessAccount, ...], tuple[CommercialQuote, ...]]:
    payload = document("btx_sample_paperless_quotes.json")
    paperless_accounts: dict[str, PaperlessAccount] = {}
    quotes = []
    for row in payload["quotes"]:
        account_id = row["research_account_id"]
        if account_id not in accounts_by_id or row["business_unit_id"] not in business_unit_ids or row["program_id"] not in program_ids:
            raise ValueError(f"quote {row['paperless_quote_id']} has an unknown foreign key")
        if row["status"] not in _STATUS:
            raise ValueError(f"quote {row['paperless_quote_id']} has unknown status")
        provenance = source_provenance(row, classification=Classification.INTERNAL_COMMERCIAL)
        account_key = f"paperless-{account_id}"
        paperless_accounts.setdefault(account_key, PaperlessAccount(account_key, account_id, accounts_by_id[account_id].legal_name, provenance))
        lines = []
        for item in row["line_items"]:
            if item["component_class_id"] not in component_ids:
                raise ValueError(f"quote {row['paperless_quote_id']} references unknown component")
            lines.append(CommercialQuoteLineItem(item["paperless_quote_item_id"], item["part_number"], item["component_class_id"], item["quantity"], item["unit_price_cents"], item.get("lead_time_days"), provenance))
        quotes.append(CommercialQuote(row["paperless_quote_id"], account_id, row["business_unit_id"], _STATUS[row["status"]], date.fromisoformat(row["sent_at"]), row.get("total_price_cents"), row["currency"], row.get("paperless_contact_id"), None, lines[0].component_class_id if lines else None, provenance, program_id=row["program_id"], component_class_ids=tuple(item.component_class_id for item in lines), paperless_account_id=account_key, paperless_contact_id=row.get("paperless_contact_id"), line_items=tuple(lines)))
    return tuple(paperless_accounts.values()), tuple(quotes)
