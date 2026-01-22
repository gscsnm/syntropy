import json
from typing import Annotated, List, Optional, Any
from pytauri import Commands, AppHandle
from pytauri.ipc import Channel, JavaScriptChannelId
from pydantic import BaseModel, RootModel
from pytauri.webview import WebviewWindow

from .models.domain import AnalysisSpec
from .models.db import LLMConfig, AnalysisTask, AnalysisTaskEvent
from .live_context import live_context
from .database import get_session, init_db

commands = Commands(experimental_gen_ts=True)

# --- Models for IPC ---
class TaskIdResponse(BaseModel):
    task_id: str

class TaskListResponse(BaseModel):
    tasks: List[AnalysisTask]

class TaskEventsResponse(BaseModel):
    events: List[dict[str, Any]]

class LogMessage(BaseModel):
    task_id: str
    message: str
    data: str # JSON string

class SubscribeTaskEventsBody(BaseModel):
    channel: JavaScriptChannelId[LogMessage]
    task_id: str
    
class SetActiveLLMBody(BaseModel):
    fast_id: int
    slow_id: int

class LLMSettings(BaseModel):
    fast: Optional[LLMConfig] = None
    slow: Optional[LLMConfig] = None

class AppLanguage(BaseModel):
    language: str

class GetTasksBody(BaseModel):
    limit: int = 50
    offset: int = 0

class GetTaskEventsBody(BaseModel):
    task_id: str

# --- Commands ---

@commands.command()
async def start_analysis(body: AnalysisSpec, app_handle: AppHandle) -> TaskIdResponse:
    """Start a new analysis task"""
    # Ensure DB is initialized
    init_db()
    
    # Initialize LiveContext with AppHandle if needed
    live_context.set_app_handle(app_handle)
    
    from .database import get_app_language as db_get_lang
    expected_output_language = db_get_lang() or "en-US"
    task_id = await live_context.start_analysis(body, expected_output_language=expected_output_language)
    return TaskIdResponse(task_id=task_id)

@commands.command()
async def subscribe_task_events(
    body: SubscribeTaskEventsBody, 
    webview_window: WebviewWindow
) -> None:
    """Subscribe to events for a specific task"""
    channel = body.channel.channel_on(webview_window.as_ref_webview())
    
    # Register channel to LiveContext
    live_context.register_channel(body.task_id, channel)
    
@commands.command()
async def get_analysis_tasks(body: GetTasksBody) -> TaskListResponse:
    init_db()
    from sqlmodel import select

    tasks: List[AnalysisTask] = []
    for session in get_session():
        statement = (
            select(AnalysisTask)
            .order_by(AnalysisTask.created_at.desc())
            .offset(body.offset)
            .limit(body.limit)
        )
        tasks = list(session.exec(statement).all())
    return TaskListResponse(tasks=tasks)

@commands.command()
async def get_task_events(body: GetTaskEventsBody) -> TaskEventsResponse:
    init_db()
    from sqlmodel import select

    events: List[dict[str, Any]] = []
    for session in get_session():
        statement = (
            select(AnalysisTaskEvent)
            .where(AnalysisTaskEvent.task_id == body.task_id)
            .order_by(AnalysisTaskEvent.id.asc())
        )
        rows = session.exec(statement).all()
        events = [r.payload for r in rows]
    return TaskEventsResponse(events=events)

@commands.command()
async def get_llm_config() -> LLMSettings:
    init_db()
    from sqlmodel import select
    from .database import get_session
    
    fast: Optional[LLMConfig] = None
    slow: Optional[LLMConfig] = None
    for session in get_session():
        fast = session.exec(select(LLMConfig).where(LLMConfig.role == "fast")).first()
        slow = session.exec(select(LLMConfig).where(LLMConfig.role == "slow")).first()
    return LLMSettings(fast=fast, slow=slow)

@commands.command()
async def save_llm_config(body: LLMConfig) -> LLMConfig:
    init_db()
    from sqlmodel import Session, select
    from .database import _engine
    
    with Session(_engine) as session:
        existing = session.exec(select(LLMConfig).where(LLMConfig.role == body.role)).first()
        if existing:
            existing.name = body.name
            existing.provider = body.provider
            existing.api_key = body.api_key
            existing.model_name = body.model_name
            existing.api_base = body.api_base
            existing.temperature = body.temperature
            existing.is_active_fast = False
            existing.is_active_slow = False
            session.add(existing)
            session.commit()
            session.refresh(existing)
            return existing
        body.is_active_fast = False
        body.is_active_slow = False
        session.add(body)
        session.commit()
        session.refresh(body)
        return body

@commands.command()
async def set_active_llm(body: SetActiveLLMBody) -> bool:
    return True

@commands.command()
async def get_app_language() -> AppLanguage:
    """Get current app language setting"""
    init_db()
    from .database import get_app_language as db_get_lang
    lang = db_get_lang() or "en-US"
    return AppLanguage(language=lang)

@commands.command()
async def set_app_language(body: AppLanguage) -> AppLanguage:
    """Set app language"""
    init_db()
    from .database import set_app_language as db_set_lang
    db_set_lang(body.language)
    return body
