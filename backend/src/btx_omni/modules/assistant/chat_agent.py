"""Bounded conversational control plane; only ChatTools can read business facts."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from hashlib import sha256
from time import monotonic

from btx_omni.ai.contracts import LanguageProviderError
from btx_omni.modules.assistant.orchestration import OmniResponse

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
    if re.search(r"\b(?:send|email|update|delete|create|approve|mark|set|change|pay|invoice|transfer|remember|save)\b", q) and re.search(r"\b(?:crm|hubspot|owner|score|attractiveness|won|payment|invoice|money|action|email|memory|preference|classification)\b", q):
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
        self.started = monotonic()

    def read(self, name, arguments):
        if self.canceled():
            raise InterruptedError("Canceled")
        if len(self.steps) >= self.limits.steps or monotonic() - self.started >= self.limits.seconds:
            raise TimeoutError("The lookup limit was reached.")
        self.progress("Checking " + name.removeprefix("get_").replace("_", " ") + "…")
        start = monotonic()
        result = self.tools.execute(name, arguments)
        elapsed = monotonic() - start
        if elapsed > self.limits.tool_seconds:
            result = {"status": "timeout", "data": {"message": "That lookup took too long. Try a narrower question."}, "source_ids": [], "as_of": self.tools.observed_at.date().isoformat(), "data_mode": "SAMPLE"}
        encoded = json.dumps(result, default=str)
        self.steps.append({"tool": name, "argument_hash": sha256(json.dumps(arguments, sort_keys=True).encode()).hexdigest(),
                           "result_characters": len(encoded), "latency_ms": round(elapsed * 1000, 2), "status": result["status"]})
        self.reads.append({"tool": name, "result": result})
        return result

    def answer(self, question, *, account_id=None, recent_turns=()):
        self.question = question
        self.resolved = None
        boundary = refusal(question)
        named = self.tools.named(question)
        referent = self.tools.context.get("conversation_referent") or {}
        if len(named) == 1 and re.search(r"\bcompare\s+(?:it|that one|this)\b", question, re.IGNORECASE):
            previous = referent.get("account_id") or self.tools.context.get("selected_account_id")
            if previous in self.tools.accounts and previous != named[0]:
                named = (previous, *named)
        self.tools.named_scope = frozenset(named)
        if len(named) == 1:
            self.resolved = named[0]
        elif not named:
            candidate = account_id or referent.get("account_id") or self.tools.context.get("selected_account_id") or self.tools.context.get("session_account_id")
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
        try:
            for _ in range(self.limits.steps + 1):
                if self.canceled():
                    raise InterruptedError("Canceled")
                payload = {"question": question, "recent_turns": list(recent_turns)[-6:],
                           "screen_context": self.tools.context, "resolved_account_id": self.resolved,
                           "named_account_ids": named, "tools": self.tools.declarations,
                           "results": self.reads, "remaining_steps": self.limits.steps - len(self.steps)}
                if len(json.dumps(payload, default=str)) > self.limits.input_characters:
                    return self.response("I've reached the context limit. Please narrow the question to one record.", "CONTEXT_LIMIT")
                if monotonic() - self.started >= self.limits.seconds:
                    raise TimeoutError()
                decision = self.provider.chat_turn(payload, max_output_tokens=self.limits.output_tokens)
                if isinstance(decision, dict) and set(decision) == {"answer"} and isinstance(decision["answer"], str):
                    return self.response(decision["answer"], "ANSWERED", model=True)
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
        except (LanguageProviderError, TimeoutError, ValueError, TypeError, KeyError, PermissionError):
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
        return OmniResponse(content=content, account_id=self.resolved or "",
                            account_name=self.tools.accounts[self.resolved].legal_name if self.resolved else None,
                            citations=tuple(dict.fromkeys(s for r in self.reads for s in r["result"].get("source_ids", []))),
                            provenance=(), missingness=(), recommended_action=None,
                            conversation_referent={"account_id": self.resolved, "route": "ACCOUNT"} if self.resolved else None,
                            language_provider="gemini" if model else "deterministic",
                            language_model=getattr(getattr(self.provider, "config", None), "model", None) if model else None,
                            provider_status="AVAILABLE" if model else "NOT_CONFIGURED",
                            context_used={"chat_v2": True, "status": status},
                            structured_reads={"steps": self.steps, "reads": self.reads,
                                              "configuration_version": "OMNI_CHAT_V2", "elapsed_ms": round((monotonic()-self.started)*1000, 2),
                                              "revision": self.tools.sample.commercial_revision, "model_requested_stop": status == "ANSWERED"})
