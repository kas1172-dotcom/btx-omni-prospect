"""Opt-in sample-only live evaluation; no key means a successful explicit skip."""
import argparse
import json
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path
from time import monotonic

from sqlalchemy import create_engine

from btx_omni.ai.config import AiConfig
from btx_omni.ai.registry import get_ai_provider
from btx_omni.core.config import Settings
from btx_omni.persistence.ai_usage import ai_call_receipts

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
from omni_eval_support import CASES, check_case, environment, run_case


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('omni-live-eval.json'))
    parser.add_argument('--fake', action='store_true', help='Offline replay; never proof of live model quality')
    parser.add_argument('--limit', type=int, default=len(CASES))
    args = parser.parse_args()
    settings = Settings()
    if not args.fake and not settings.gemini_api_key:
        print('SKIPPED: no Gemini API key is configured. No live calls or report writes were made. Fake-provider tests remain available through pytest.')
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    provider_config = None
    if not args.fake:
        # All evaluation writes go to a local private usage ledger, never the app DB.
        settings = settings.model_copy(update={'database_url': 'sqlite:///' + str(args.output.resolve().with_suffix('.usage.sqlite'))})
        engine = create_engine(settings.database_url)
        ai_call_receipts.create(engine, checkfirst=True)
        provider_config = replace(AiConfig.from_settings(settings, actor_id='manual-chat-eval', purpose='omni-live-eval'),
            model=settings.omni_chat_model or settings.gemini_model, daily_actor_limit=settings.omni_chat_daily_calls)
    rows = []
    sample = environment()
    for case in CASES[:max(1, min(args.limit, len(CASES)))]:
        started = monotonic()
        provider = get_ai_provider(provider_config) if provider_config and case['expected'].get('configured', True) else None
        answer, used_provider = run_case(case, sample, provider)
        failures = check_case(case, answer, used_provider)
        if not args.fake:
            # Real models may choose additional identity reads and different public sources.
            failures = [f for f in failures if not f.startswith('Tools differ:') and f != 'Missing public citation']
            required = set(case['expected']['tools'])
            actual = {s['tool'] for s in answer.structured_reads['steps']}
            if not required <= actual and case['category'] not in {'permission', 'degraded'}:
                failures.append('Required research tool missing')
            if case['expected'].get('public_citation') and not answer.citation_links:
                failures.append('No grounded public source')
        rows.append({'id': case['id'], 'category': case['category'], 'question': case['question'],
                     'pass': not failures, 'failures': failures, 'tools': answer.structured_reads['steps'],
                     'outbound_queries': answer.structured_reads.get('outbound_queries', []),
                     'latency_ms': round((monotonic() - started) * 1000, 2),
                     'usage': getattr(used_provider, 'usage_log', []), 'answer': answer.content,
                     'validation': answer.context_used.get('synthesis_validation'),
                     'human_tone_review': 'REQUIRED' if not args.fake else 'NOT_A_LIVE_MODEL_EVALUATION'})
    categories = {}
    for category, count in Counter(row['category'] for row in rows).items():
        passed = sum(row['pass'] for row in rows if row['category'] == category)
        categories[category] = {'passed': passed, 'total': count, 'pass_rate': passed / count}
    report = {'mode': 'OFFLINE_REPLAY' if args.fake else 'LIVE_GEMINI_SAMPLE_ONLY', 'categories': categories,
              'passed': sum(r['pass'] for r in rows), 'total': len(rows), 'cases': rows,
              'limitations': 'Behavior checks are not proof of tone, semantic entailment, live freshness or multi-tenant business isolation. Review full answer text.'}
    args.output.write_text(json.dumps(report, indent=2, default=str), encoding='utf-8')
    print(f"{report['mode']}: {report['passed']}/{report['total']} behavioral checks passed. Report: {args.output}")
    return 0 if all(r['pass'] for r in rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())
