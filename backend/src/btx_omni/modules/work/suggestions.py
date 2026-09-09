"""Stable recommendation identity, separate from mutable ordering and work state."""
import json
import re
from hashlib import sha256

VERSION = 'BTX_SUGGESTION_IDENTITY_2'


def project_suggestions(alerts, *, actions=(), visible_action_ids=frozenset(), commercial_revision=''):
    result = {}
    for alert in alerts:
        key = [VERSION, alert.account_id, alert.type.value, alert.business_unit, alert.subject_id,
               sorted(set(alert.evidence_ids))]
        identifier = 'suggestion-v2-' + sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()[:32]
        legacy_prefix = f'alert-{alert.type.value.lower()}-{alert.account_id}-{alert.business_unit}'
        if alert.type.value == 'CROSS_BU_COORDINATION':
            legacy_prefix = f'alert-cross_bu_coordination-{alert.account_id}'
        if alert.type.value == 'OVERDUE_ORDER':
            legacy_prefix = alert.id
        matched = [action for action in actions if action.source_suggestion_id and action.account_id == alert.account_id and (
            action.source_suggestion_id == identifier or (
                re.fullmatch(re.escape(legacy_prefix) + r':[0-9]+', action.source_suggestion_id)
                and set(action.evidence_ids) == set(alert.evidence_ids)
            ))]
        accessible = [action for action in matched if action.id in visible_action_ids]
        revision = sha256(json.dumps([key, alert.recommended_action, alert.trigger_reason, alert.severity,
                                      alert.actual_value, alert.threshold, commercial_revision], default=str, sort_keys=True).encode()).hexdigest()
        item = {'id': identifier, 'account_id': alert.account_id, 'title': alert.recommended_action,
                'rationale': alert.trigger_reason, 'priority': alert.severity, 'evidence_ids': alert.evidence_ids,
                'source': 'SAMPLE_COMMERCIAL_ALERT', 'observed_at': alert.observed_at, 'dismissed': False,
                'revision': revision, 'identity_version': VERSION, 'source_alert_id': alert.id,
                'converted_action_id': accessible[0].id if len(matched) == len(accessible) == 1 else None,
                'conversion_blocked': bool(matched) and not (len(matched) == len(accessible) == 1),
                'legacy_work_match': bool(len(matched) == 1 and matched[0].source_suggestion_id != identifier)}
        if identifier in result and result[identifier] != item:
            raise ValueError('Conflicting canonical suggestion evidence requires review.')
        result[identifier] = item
    return sorted(result.values(), key=lambda item: item['id'])
