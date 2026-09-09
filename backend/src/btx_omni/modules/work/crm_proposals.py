"""Versioned CRM proposals in the existing immutable work audit; no external writes."""
import json
import re
from dataclasses import asdict, replace
from hashlib import sha256

from btx_omni.domain.work import ActionAuditEvent, ActionStatus, ApprovalStatus
from btx_omni.integrations.hubspot.contracts import SampleHubSpotAdapter
from btx_omni.modules.work.service import ActionConflictError, ActionPolicy

VERSION = 'BTX_CRM_PROPOSAL_1'


def _hash(value):
    return sha256(json.dumps(value, sort_keys=True, default=str, allow_nan=False).encode()).hexdigest()


class CrmProposalWorkflow:
    def __init__(self, work, adapter, *, commercial_revision):
        self.work, self.adapter, self.commercial_revision = work, adapter, commercial_revision

    def _snapshot(self, action):
        # Only this existing, deliberately non-network adapter can participate.
        # An arbitrary live port is not authorization to write external CRM.
        if type(self.adapter) is not SampleHubSpotAdapter:
            raise ActionConflictError('Live CRM execution is not authorized in this SAMPLE workflow.')
        context = self.adapter.account_context(action.account_id)
        company = context.company
        if company and company.account_id != action.account_id:
            raise ActionConflictError('CRM mapping is outside the canonical account scope.')
        mapping = {'company_id': company.id if company else None, 'crm_owner_id': company.owner_id if company else None,
                   'account_id': action.account_id, 'truth_class': 'INTERNAL_SCENARIO_MAPPING', 'portal_id': None,
                   'source_mapping': company.properties if company else None}
        payload = {'title': action.title, 'description': action.description, 'local_owner_id': action.owner_id,
                   'crm_owner_id': mapping['crm_owner_id'], 'due_date': action.due_date.isoformat() if action.due_date else None,
                   'evidence_ids': list(action.evidence_ids), 'company_id': mapping['company_id']}
        blockers = []
        if action.status not in {ActionStatus.OPEN, ActionStatus.IN_PROGRESS}:
            blockers.append('Action is closed; no new follow-up execution is permitted.')
        if not action.owner_id:
            blockers.append('Assign a local Action owner before proceeding.')
        if action.approval_status in {ApprovalStatus.PENDING, ApprovalStatus.REJECTED}:
            blockers.append('The existing Action approval must be approved before proposal execution review.')
        if company is None or not company.owner_id:
            blockers.append('A scoped CRM company and owner mapping are required.')
        snapshot = {'schema_version': VERSION, 'action_id': action.id, 'action_version': action.version,
                    'account_id': action.account_id, 'commercial_revision': self.commercial_revision,
                    'action_fingerprint': _hash(asdict(action)), 'mapping': mapping, 'mapping_revision': _hash(mapping),
                    'operation': 'CREATE_FOLLOW_UP', 'payload': payload, 'blockers': blockers,
                    'destination': 'LOCAL_SAMPLE_ONLY', 'external_write': False,
                    'destination_label': 'Local HubSpot workflow demonstration — no HubSpot account will be changed'}
        return {**snapshot, 'proposal_id': 'crm-proposal-' + _hash(snapshot)}

    @staticmethod
    def _event(action, principal, now, name, metadata):
        return ActionAuditEvent(None, action.id, principal.user_id, name, now, metadata)

    @staticmethod
    def _proposal(history, proposal_id):
        return next((event.metadata for event in history if event.event == 'CRM_PROPOSED'
                     and event.metadata.get('proposal_id') == proposal_id), None)

    def preview(self, action_id, *, expected_version, principal, now):
        def operation(action, history):
            ActionPolicy.require_manage(principal, action)
            if action.version != expected_version:
                raise ActionConflictError('Action changed; refresh before preparing its exact CRM proposal.')
            proposal = self._snapshot(action)
            if self._proposal(history, proposal['proposal_id']):
                return None, proposal
            if sum(event.event == 'CRM_PROPOSED' for event in history) >= 50:
                raise ActionConflictError('The bounded proposal history limit was reached; operator review is required.')
            return self._event(action, principal, now, 'CRM_PROPOSED', proposal), proposal
        return self.work.repository.transact_audit(action_id, operation)

    def _current(self, action, history, proposal_id):
        proposal = self._proposal(history, proposal_id)
        if proposal is None:
            raise ActionConflictError('Inspect a saved proposal in this Action scope first.')
        if self._snapshot(action)['proposal_id'] != proposal_id:
            raise ActionConflictError('Action, mapping or commercial evidence changed; create and review a new proposal.')
        if proposal['blockers']:
            raise ActionConflictError(' '.join(proposal['blockers']))
        return proposal

    def decide(self, action_id, proposal_id, *, decision, expected_decision_id, principal, now):
        if decision not in {'APPROVED', 'REJECTED'}:
            raise ValueError('Unsupported CRM proposal decision.')
        def operation(action, history):
            ActionPolicy.require_manager(principal)
            ActionPolicy.require_manage(principal, action)
            self._current(action, history, proposal_id)
            decisions = [event.metadata for event in history if event.event == 'CRM_DECIDED' and event.metadata['proposal_id'] == proposal_id]
            prior = decisions[-1] if decisions else None
            identifier = 'crm-decision-' + _hash([proposal_id, principal.user_id, decision, expected_decision_id])
            replay = next((item for item in decisions if item['decision_id'] == identifier), None)
            if replay:
                return None, {**replay, 'is_current': prior['decision_id'] == identifier}
            if expected_decision_id != (prior['decision_id'] if prior else None):
                raise ActionConflictError('Proposal approval changed; inspect its latest decision.')
            result = {'proposal_id': proposal_id, 'decision_id': identifier, 'decision': decision,
                      'actor_id': principal.user_id, 'decided_at': now.isoformat(), 'external_write': False}
            return self._event(action, principal, now, 'CRM_DECIDED', result), {**result, 'is_current': True}
        return self.work.repository.transact_audit(action_id, operation)

    def execute_sample(self, action_id, proposal_id, *, expected_decision_id, idempotency_key, principal, now):
        if not re.fullmatch(r'[A-Za-z0-9._-]{8,64}', idempotency_key):
            raise ValueError('A bounded retry key is required.')
        def operation(action, history):
            ActionPolicy.require_manager(principal)
            ActionPolicy.require_manage(principal, action)
            key_hash = _hash([principal.user_id, idempotency_key])
            fingerprint = _hash([proposal_id, expected_decision_id, 'LOCAL_SAMPLE_ONLY'])
            attempts = [event.metadata for event in history if event.event == 'CRM_SAMPLE_ATTEMPT']
            replay = next((item for item in attempts if item['request_key_hash'] == key_hash), None)
            if replay:
                if replay['request_fingerprint'] != fingerprint:
                    raise ActionConflictError('Retry key belongs to a different CRM proposal request.')
                return None, {**{k: v for k, v in replay.items() if not k.startswith('request_')}, 'replayed': True}
            proposal = self._current(action, history, proposal_id)
            decisions = [event.metadata for event in history if event.event == 'CRM_DECIDED' and event.metadata['proposal_id'] == proposal_id]
            if not decisions or decisions[-1]['decision'] != 'APPROVED' or decisions[-1]['decision_id'] != expected_decision_id:
                raise ActionConflictError('Current explicit Manager approval of this exact proposal is required.')
            successful = next((item for item in attempts if item['proposal_id'] == proposal_id and item['status'] == 'SAMPLE_COMPLETED'), None)
            if successful:
                return None, {**{k: v for k, v in successful.items() if not k.startswith('request_')}, 'replayed': True}
            if len(attempts) >= 50:
                raise ActionConflictError('The bounded SAMPLE attempt limit was reached; operator review is required.')
            preview = self.adapter.preview_action(action.id, action.account_id, proposal['operation'], proposal['payload'])
            result = self.adapter.execute_action(replace(preview, confirmed=True))
            attempt = {'proposal_id': proposal_id, 'attempt_id': 'crm-attempt-' + _hash([action.id, key_hash]),
                       'decision_id': expected_decision_id, 'actor_id': principal.user_id, 'attempted_at': now.isoformat(),
                       'status': 'SAMPLE_COMPLETED' if result.executed and not result.unavailable_reason else 'SAMPLE_FAILED',
                       'detail': result.unavailable_reason or 'Local sample attempt recorded. No HubSpot record was created or updated.',
                       'external_write': False, 'destination': 'LOCAL_SAMPLE_ONLY', 'request_key_hash': key_hash,
                       'request_fingerprint': fingerprint}
            return self._event(action, principal, now, 'CRM_SAMPLE_ATTEMPT', attempt), {k: v for k, v in attempt.items() if not k.startswith('request_')}
        return self.work.repository.transact_audit(action_id, operation)

    def inspect(self, action_id, *, principal):
        def operation(action, history):
            ActionPolicy.require_manage(principal, action)
            current = self._snapshot(action)['proposal_id']
            events = [{'kind': event.event, 'actor_id': event.actor_id, 'occurred_at': event.occurred_at,
                       'data': {k: v for k, v in event.metadata.items() if not k.startswith('request_')}}
                      for event in history if event.event in {'CRM_PROPOSED', 'CRM_DECIDED', 'CRM_SAMPLE_ATTEMPT'}]
            return None, {'action_id': action.id, 'action_version': action.version, 'current_proposal_id': current,
                          'events': events[-100:], 'earlier_event_count': max(0, len(events) - 100), 'external_write': False}
        return self.work.repository.transact_audit(action_id, operation)
