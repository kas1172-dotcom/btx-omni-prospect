"""Private chat history and validated SSE delivery. No business mutations."""
import asyncio
import json
from datetime import UTC, datetime
from threading import Event
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError

from btx_omni.api.accounts import get_runtime
from btx_omni.api.omni import OmniQuestion, answer_chat
from btx_omni.api.runtime import PocRuntime
from btx_omni.api.session import principal
from btx_omni.domain.work import Principal
from btx_omni.persistence.omni_conversations import ConversationRepository

router = APIRouter(prefix='/omni', tags=['omni'])


def repository(runtime):
    return ConversationRepository(runtime.omni_runs.engine, retention_days=runtime.settings.omni_chat_retention_days)


class StreamQuestion(OmniQuestion):
    conversation_id: str | None = Field(default=None, min_length=36, max_length=36)


class Rename(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=80)


class Rating(BaseModel):
    model_config = ConfigDict(extra='forbid')
    run_id: str = Field(min_length=36, max_length=36)
    rating: Literal['up', 'down']
    reason: str = Field(default='', max_length=500)


@router.get('/conversations')
def list_conversations(runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)):
    return {'items': repository(runtime).list(current, datetime.now(UTC)), 'retention_days': runtime.settings.omni_chat_retention_days}


@router.get('/conversations/{identifier}')
def get_conversation(identifier: str, runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)):
    try:
        return repository(runtime).get(identifier, current, datetime.now(UTC))
    except KeyError:
        raise HTTPException(404, 'Conversation unavailable.') from None


@router.patch('/conversations/{identifier}')
def rename_conversation(identifier: str, body: Rename, runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)):
    try:
        return repository(runtime).rename(identifier, current, datetime.now(UTC), body.title)
    except KeyError:
        raise HTTPException(404, 'Conversation unavailable.') from None
    except ValueError:
        raise HTTPException(422, 'Use a nonempty title.') from None


@router.delete('/conversations/{identifier}')
def delete_conversation(identifier: str, runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)):
    try:
        repository(runtime).delete(identifier, current, datetime.now(UTC))
    except KeyError:
        raise HTTPException(404, 'Conversation unavailable.') from None
    return {'deleted': True}


@router.post('/conversations/{identifier}/feedback')
def rate_answer(identifier: str, body: Rating, runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)):
    try:
        return repository(runtime).rate(identifier, current, datetime.now(UTC), body.run_id, body.rating, body.reason)
    except (KeyError, ValueError):
        raise HTTPException(404, 'Answer unavailable in this conversation.') from None


@router.post('/chat/stream')
async def stream_chat(body: StreamQuestion, request: Request, runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)):
    repo, now = repository(runtime), datetime.now(UTC)
    try:
        thread = await asyncio.to_thread(repo.get, body.conversation_id, current, now) if body.conversation_id else await asyncio.to_thread(repo.create, current, now)
    except KeyError:
        raise HTTPException(404, 'Conversation unavailable.') from None
    except SQLAlchemyError:
        raise HTTPException(503, 'Conversation storage is unavailable.') from None
    context = body.context.model_dump(exclude_none=True) if body.context else {}
    context['prior_turns'] = '\n'.join(t['role'] + ': ' + t['text'] for t in thread['turns'][-6:])[-1600:]
    previous = next((t.get('response', {}).get('conversation_referent') for t in reversed(thread['turns']) if t.get('response')), None)
    if previous:
        context['conversation_referent'] = previous
    question = OmniQuestion(question=body.question, account_id=body.account_id, context=context)
    queue = asyncio.Queue()
    stopped = Event()
    loop = asyncio.get_running_loop()

    def progress(message):
        loop.call_soon_threadsafe(queue.put_nowait, ('progress', {'text': message}))

    async def run():
        try:
            answer = await asyncio.to_thread(answer_chat, question, runtime, current, progress=progress, canceled=stopped.is_set)
            if stopped.is_set():
                return
            encoded = jsonable_encoder(answer)
            await asyncio.to_thread(repo.append, thread['id'], current, datetime.now(UTC), version=thread['version'],
                turns=[{'role': 'user', 'text': body.question}, {'role': 'assistant', 'text': answer.content, 'response': encoded}])
            # Only validated text leaves the server; progress is streamed during tools.
            for paragraph in answer.content.split('\n\n'):
                await queue.put(('delta', {'text': paragraph + '\n\n'}))
            await queue.put(('answer', {'response': encoded, 'conversation_id': thread['id']}))
        except (HTTPException, SQLAlchemyError, KeyError, ValueError, RuntimeError):
            await queue.put(('error', {'message': "I couldn't finish or save this answer. Please retry."}))
        finally:
            await queue.put(('done', {}))

    async def events():
        task = asyncio.create_task(run())
        try:
            yield 'event: conversation\ndata: ' + json.dumps({'id': thread['id']}) + '\n\n'
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event, data = await asyncio.wait_for(queue.get(), timeout=.25)
                except TimeoutError:
                    continue
                yield 'event: ' + event + '\ndata: ' + json.dumps(data) + '\n\n'
                if event == 'done':
                    break
        finally:
            stopped.set()
            # Let the bounded worker complete its private audit; it cannot write business data.
            task.add_done_callback(lambda finished: finished.exception() if not finished.cancelled() else None)
    return StreamingResponse(events(), media_type='text/event-stream', headers={'Cache-Control': 'private, no-store', 'X-Accel-Buffering': 'no'})
