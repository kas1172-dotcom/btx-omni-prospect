"""Curated aggregate research, not account allegations or live monitoring."""
from btx_omni.core.clock import as_of_date, evidence_state

FDA_URL = 'https://www.fda.gov/regulatory-information/search-fda-guidance-documents/electronic-submission-template-premarket-approval-applications-pma'
FDA_NEWS = 'https://www.fda.gov/medical-devices/medical-devices-news-and-events/cdrh-new-news-and-updates'


def medical_regulatory_context(*, anchor=None):
    return {
        'signal_id': 'curated-fda-pma-template-2026-09-17',
        'entity': 'US Food and Drug Administration', 'market': 'Medical Device',
        'source_url': FDA_URL, 'date_verification_url': FDA_NEWS,
        'publisher': 'US Food and Drug Administration', 'event_date': '2026-09-17',
        'retrieval_date': '2026-09-20', 'record_id': 'FDA-2026-D-9429',
        'signal_type': 'REGULATORY_CONTEXT', 'event_type': 'DRAFT_GUIDANCE',
        'affected_scope': 'PMA applications and certain supplements submitted to CDRH and CBER',
        'source_tier': 1, 'independent_origin_ids': ['FDA-2026-D-9429'],
        'excerpt_paraphrase': 'FDA describes electronic submission templates for PMA submissions. The document is a draft, not an implemented requirement.',
        'effective_date': None, 'report_date': '2026-09-17',
        'evidence_state': evidence_state('2026-09-17', window_days=30, as_of=as_of_date(anchor)),
        'freshness_window_days': 30, 'seed_type': 'curated_monitor_style',
        'synthetic': False, 'data_mode': 'SAMPLE',
        'applicability': 'AGGREGATE_ONLY_NOT_ACCOUNT_EVIDENCE',
        'need_gate': 'UNKNOWN', 'account_ids': [], 'risk_score': None,
        'missing_information': ['Final implementation date', 'Any applicability to a specific BTX customer or component'],
        'what_would_change_result': 'A final dated requirement and verified account-specific applicability would support a separate review; neither is inferred from this draft.',
    }
