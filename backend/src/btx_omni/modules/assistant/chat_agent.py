"""Bounded conversational control plane; only ChatTools can read business facts."""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from hashlib import sha256
from time import monotonic

from btx_omni.ai.contracts import LanguageProviderError
from btx_omni.modules.assistant.chat_validation import (
    GENERAL_FACTS,
    plain_fallback,
    violations,
)
from btx_omni.modules.assistant.orchestration import OmniCitation, OmniResponse

DEGRADED = "The AI service isn't available right now, so I can only do basic lookups."


@dataclass(frozen=True)
class ChatLimits:
    steps: int = 6
    seconds: float = 60
    tool_seconds: float = 8
    input_characters: int = 48000
    output_tokens: int = 1200


def refusal(question):
    q = question.casefold()
    if "linkedin" in q and re.search(r"scrap|crawl|behind|login|log in|bypass", q):
        return "I can't scrape LinkedIn or access pages behind a login. I can help research publicly available company information."
    if re.search(r"\b(?:should we acquire|should we buy|value this acquisition|valuation|acquisition recommendation)\b", q):
        return "I can support acquisition research, but I can't recommend an acquisition or provide a valuation. I can help organize public facts and questions for review."
    email_command = re.search(r'(?:^|[.;]|\band)\s*(?:please\s+)?email\b', q)
    if email_command or (re.search(r"\b(?:send|update|delete|create|approve|mark|set|change|pay|invoice|transfer|remember|save)\b", q) and re.search(r"\b(?:crm|hubspot|owner|score|attractiveness|won|payment|invoice|money|action|email|memory|preference|classification)\b", q)):
        return "I can't change CRM records or scores, send messages, or carry out transactions. I can draft an Action or message for you to review and save in the app."
    return None


def explicit_name(question):
    patterns = [r"^(?:tell me about|summarize|find (?:the )?(?:organization|company))\s+(.+?)[?.!]*$",
                r"^(?:does|did|has)\s+(.+?)\s+(?:have|had|got)\b",
                r"^(?:show|explain)\s+(.+?)(?:'s|’s)\s+(?:quotes|orders|history|score|actions)"]
    for pattern in patterns:
        found = re.search(pattern, question, re.IGNORECASE)
        if found:
            text = found.group(1).strip()
            if text.casefold() not in {"this", "that", "it", "this organization", "this company", "the company", "the account"} and text[:1].isupper():
                return text[:160]
    return None


class ChatAgent:
    def __init__(self, provider, tools, *, limits=None, progress=None, canceled=None):
        self.provider, self.tools = provider, tools
        self.limits = limits or ChatLimits()
        self.progress = progress or (lambda _: None)
        self.canceled = canceled or (lambda: False)
        self.reads, self.steps = [], []
        self.validation = {'status': 'NOT_MODEL_WRITTEN', 'attempts': []}
        self.started = monotonic()

    def bounded(self, call, seconds):
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(call)
        deadline = min(monotonic() + seconds, self.started + self.limits.seconds)
        try:
            while True:
                if self.canceled():
                    raise InterruptedError('Canceled')
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise TimeoutError('The request limit was reached.')
                try:
                    return future.result(timeout=min(.1, remaining))
                except TimeoutError:
                    if future.done():
                        raise
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def read(self, name, arguments):
        if self.canceled():
            raise InterruptedError("Canceled")
        if len(self.steps) >= self.limits.steps or monotonic() - self.started >= self.limits.seconds:
            raise TimeoutError("The lookup limit was reached.")
        self.progress("Checking " + name.removeprefix("get_").replace("_", " ") + "…")
        start = monotonic()
        try:
            result = self.bounded(lambda: self.tools.execute(name, arguments), self.limits.tool_seconds)
        except (ValueError, TypeError, KeyError, PermissionError, TimeoutError, InterruptedError) as error:
            # Failed and denied attempts belong in the private audit too; never
            # copy exception text, arguments or denied business rows into it.
            failure = {"status": "error", "data": {"message": "Lookup unavailable."}, "source_ids": [],
                       "as_of": self.tools.observed_at.date().isoformat(), "data_mode": "UNAVAILABLE"}
            encoded_failure = json.dumps(failure)
            self.steps.append({"step": len(self.steps) + 1, "tool": name, "evidence_ids": [],
                               "argument_hash": sha256(json.dumps(arguments, sort_keys=True).encode()).hexdigest(),
                               "result_checksum": sha256(encoded_failure.encode()).hexdigest(),
                               "result_characters": len(encoded_failure), "latency_ms": round((monotonic() - start) * 1000, 2),
                               "status": "error", "failure_class": type(error).__name__})
            self.reads.append({"tool": name, "result": failure})
            raise
        elapsed = monotonic() - start
        if elapsed > self.limits.tool_seconds:
            result = {"status": "timeout", "data": {"message": "That lookup took too long. Try a narrower question."}, "source_ids": [], "as_of": self.tools.observed_at.date().isoformat(), "data_mode": "SAMPLE"}
        encoded = json.dumps(result, default=str)
        self.steps.append({"step": len(self.steps) + 1, "tool": name,
                           "evidence_ids": result.get("source_ids", []), "result_checksum": sha256(encoded.encode()).hexdigest(),
                           "argument_hash": sha256(json.dumps(arguments, sort_keys=True).encode()).hexdigest(),
                           "result_characters": len(encoded), "latency_ms": round(elapsed * 1000, 2), "status": result["status"]})
        self.reads.append({"tool": name, "result": result})
        return result

    def answer(self, question, *, account_id=None, recent_turns=()):
        self.question = question
        self.resolved = None
        boundary = refusal(question)
        named = self.tools.named(question)
        portfolio_question = bool(re.search(r'\b(?:which|what|list|show|compare|rank|summarize)\b.*\b(?:accounts|organizations|companies|portfolio)\b', question, re.IGNORECASE))
        if portfolio_question and not named:
            self.tools.context = {key: value for key, value in self.tools.context.items() if key not in {
                'conversation_referent', 'selected_account_id', 'session_account_id', 'selected_event_id',
                'selected_facility_id', 'selected_assessment', 'relationship_selection'}}
        referent = self.tools.context.get("conversation_referent") or {}
        if len(named) == 1 and re.search(r"\bcompare\s+(?:it|that one|this)\b", question, re.IGNORECASE):
            previous = referent.get("account_id") or self.tools.context.get("selected_account_id")
            if previous in self.tools.accounts and previous != named[0]:
                named = (previous, *named)
        self.tools.named_scope = frozenset(named)
        if len(named) == 1:
            self.resolved = named[0]
        elif not named and not portfolio_question:
            followup = re.search(r'\b(?:it|its|that one|why)\b', question, re.IGNORECASE)
            candidate = (referent.get("account_id") if followup else None) or account_id or referent.get("account_id") or self.tools.context.get("selected_account_id") or self.tools.context.get("session_account_id")
            if candidate in self.tools.accounts:
                self.resolved = candidate
        if boundary:
            return self.response(boundary, "REFUSED")
        requested_name = explicit_name(question)
        if requested_name and not named:
            result = self.read("find_organization", {"name": requested_name})["data"]
            if result["status"] != "matched":
                matches = ", ".join(x["name"] for x in result["candidates"])
                return self.response(f"I can't find {requested_name} in this workspace." + (f" Did you mean {matches}?" if matches else " Check the name or open the organization's profile."), "NOT_FOUND")
            self.resolved = result["candidates"][0]["id"]
            self.tools.named_scope = frozenset({self.resolved})
        if not getattr(self.provider, "configured", False):
            return self.fallback(question, degraded=True)
        if self.tools.general_enabled and not named:
            for trigger, fact in GENERAL_FACTS.items():
                if trigger in question.casefold():
                    self.reads.append({'tool': 'general_knowledge', 'result': {'status': 'ok', 'data_mode': 'GENERAL_KNOWLEDGE', 'data': {'fact': fact}, 'source_ids': [], 'as_of': self.tools.observed_at.date().isoformat()}})
        try:
            for _ in range(self.limits.steps + 1):
                if self.canceled():
                    raise InterruptedError("Canceled")
                payload = {"question": question, "recent_turns": list(recent_turns)[-6:],
                           "general_knowledge_enabled": self.tools.general_enabled,
                           "web_search_enabled": self.tools.web_enabled,
                           "screen_context": self.tools.context, "resolved_account_id": self.resolved,
                           "named_account_ids": named, "tools": self.tools.declarations,
                           "results": self.reads, "remaining_steps": self.limits.steps - len(self.steps)}
                if len(json.dumps(payload, default=str)) > self.limits.input_characters:
                    return self.response("I've reached the context limit. Please narrow the question to one record.", "CONTEXT_LIMIT")
                if monotonic() - self.started >= self.limits.seconds:
                    raise TimeoutError()
                decision = self.bounded(lambda request=payload: self.provider.chat_turn(request, max_output_tokens=self.limits.output_tokens), self.limits.seconds)
                if isinstance(decision, dict) and set(decision) == {"answer"} and isinstance(decision["answer"], str):
                    if not self.reads and not self.tools.general_enabled:
                        return self.response("General questions are turned off in this workspace. I can help with BTX data.", "GENERAL_DISABLED")
                    content = decision['answer']
                    issues = violations(content, question, self.reads)
                    self.validation['attempts'].append(issues)
                    if issues:
                        retry_payload = {**payload, 'validation_feedback': issues,
                                         'instruction': 'Return a corrected answer only. No further tools.'}
                        retry = self.bounded(lambda request=retry_payload: self.provider.chat_turn(request, max_output_tokens=self.limits.output_tokens), self.limits.seconds)
                        content = retry.get('answer', '') if isinstance(retry, dict) else ''
                        issues = violations(content, question, self.reads) if content else ['No corrected answer']
                        self.validation['attempts'].append(issues)
                    if issues:
                        self.validation['status'] = 'FALLBACK'
                        return self.response(plain_fallback(self.reads), 'VALIDATION_FALLBACK')
                    self.validation['status'] = 'PASSED'
                    return self.response(content, "ANSWERED", model=True)
                if not isinstance(decision, dict) or set(decision) != {"tool", "arguments"}:
                    raise ValueError("Invalid chat decision")
                result = self.read(decision["tool"], decision["arguments"])
                if decision["tool"] == "find_organization":
                    found = result["data"]
                    if found["status"] != "matched":
                        return self.response("I can't find " + decision["arguments"]["name"] + " in this workspace.", "NOT_FOUND")
                    self.resolved = found["candidates"][0]["id"]
            return self.response("I've reached the lookup limit. Please ask a narrower follow-up.", "STEP_LIMIT")
        except InterruptedError:
            return self.response("Stopped. No business data was changed.", "CANCELED")
        except LanguageProviderError as error:
            if error.status.value == 'QUOTA':
                return self.response("The AI usage limit has been reached. Try again later; no business data was changed.", 'USAGE_LIMIT')
            return self.fallback(question, degraded=True)
        except (TimeoutError, ValueError, TypeError, KeyError, PermissionError, StopIteration, RuntimeError):
            return self.fallback(question, degraded=True)

    def fallback(self, question, *, degraded=False):
        prefix = DEGRADED + "\n\n" if degraded else ""
        q = question.casefold()
        try:
            if self.resolved:
                tool = "get_commercial_history" if re.search(r"quote|order|shipment|backlog|history", q) else "get_customer_360"
                if "action" in q:
                    tool = "get_actions"
                result = self.read(tool, {"account_id": self.resolved})["data"]
                name = self.tools.accounts[self.resolved].legal_name
                if tool == "get_commercial_history":
                    text = f"{'Yes' if result['quote_count'] else 'No'}—{name} has {result['quote_count']} recorded quotes and {result['order_count']} orders in the sample data. Open the profile to inspect the individual records."
                elif tool == "get_actions":
                    text = f"{name} has {len(result['actions'])} visible Actions in this sample data. " + " ".join(w["title"] if isinstance(w, dict) else w.title for w in result['actions'][:3])
                else:
                    text = f"{name}: {', '.join(result['industries'])}. {result['organization']['classification_basis']} BTX commercial information here is sample data."
            elif "action" in q or "priorit" in q or "today" in q:
                tool = "get_actions" if "action" in q else "get_today_priorities"
                data = self.read(tool, {})["data"]
                text = "There are no visible Actions." if tool == "get_actions" and not data["actions"] else "Open Today to review the current sample-data priorities and their supporting records."
            else:
                text = "I can look up an organization, open Actions, or today's priorities. Name an organization to get started."
            return self.response(prefix + text, "DEGRADED")
        except (ValueError, KeyError, PermissionError, TimeoutError):
            return self.response(prefix + "I couldn't complete that lookup. Try one organization or a narrower question.", "LIMIT_OR_UNAVAILABLE")

    def response(self, content, status, *, model=False):
        public = [f for read in self.reads if read['tool'] == 'web_search' for f in read['result']['data'].get('findings', [])]
        return OmniResponse(content=content, account_id=self.resolved or "",
                            account_name=self.tools.accounts[self.resolved].legal_name if self.resolved else None,
                            citations=tuple(dict.fromkeys(s for r in self.reads for s in r["result"].get("source_ids", []))),
                            provenance=(), missingness=(),
                            citation_links=tuple(OmniCitation(f['publisher'] + ': ' + f['title'], f['url']) for f in public),
                            public_research_permitted=self.tools.web_enabled,
                            recommended_action=f"Review the available records for {self.tools.accounts[self.resolved].legal_name}" if self.resolved and status not in {'CANCELED', 'USAGE_LIMIT'} else None,
                            conversation_referent={"account_id": self.resolved, "route": "ACCOUNT"} if self.resolved else None,
                            language_provider="gemini" if model else "deterministic",
                            language_model=getattr(getattr(self.provider, "config", None), "model", None) if model else None,
                            provider_status="AVAILABLE" if model else "NOT_CONFIGURED",
                            context_used={"chat_v2": True, "status": status, 'synthesis_validation': self.validation},
                            structured_reads={"steps": self.steps, "reads": self.reads,
                                              "outbound_queries": self.tools.outbound_queries,
                                              "configuration_version": "OMNI_CHAT_V2", "elapsed_ms": round((monotonic()-self.started)*1000, 2),
                                              "revision": self.tools.sample.commercial_revision, "model_requested_stop": status == "ANSWERED"})
