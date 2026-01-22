import asyncio
import uuid
import json
import logging
from typing import Dict, Optional, Any, Callable, Literal
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pytauri import AppHandle
from pytauri.ipc import Channel
from pydantic import BaseModel, Field

from .models.domain import AnalysisSpec
from .models.db import AnalysisTask, AnalysisTaskEvent, LLMConfig
from .database import get_session, get_active_llm_config
from .workflows.analysis import create_analysis_workflow
from .tools.utils import get_company_basic_info
from agno.agent import Agent
from agno.models.openai import OpenAIChat,OpenAILike
from agno.run.workflow import WorkflowRunEvent
from agno.run.agent import RunEvent

logger = logging.getLogger(__name__)

class TaskResultSnapshot(BaseModel):
    recommendation: Literal["BUY", "SELL", "HOLD"] = Field(...)
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str = Field(...)

# Simple in-memory task store
_running_tasks: Dict[str, Any] = {} # Storing workflow objects

class LiveContext:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LiveContext, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self.app_handle: Optional[AppHandle] = None
        # We might need a way to map task_ids to channels if we support direct subscriptions
        # For now, we will rely on global events or assume the command passes the channel
        self.channels: Dict[str, Channel] = {} 

    def set_app_handle(self, app_handle: AppHandle):
        self.app_handle = app_handle

    def register_channel(self, task_id: str, channel: Channel):
        self.channels[task_id] = channel

    async def start_analysis(self, spec: AnalysisSpec, expected_output_language: Optional[str] = None) -> str:
        """
        Start a new analysis task.
        Returns task_id.
        """
        task_id = str(uuid.uuid4())
        
        # 1. Load Config
        fast_conf = get_active_llm_config("fast")
        slow_conf = get_active_llm_config("slow")
        
        model = self._create_model_factory(fast_conf, slow_conf)
        
        # 2. Create Workflow (Declarative)
        workflow = create_analysis_workflow(
            spec,
            model,
            expected_output_language=expected_output_language,
        )
        
        # 3. Register task
        _running_tasks[task_id] = workflow
        
        # 4. Save initial state to DB
        self._save_task_initial(task_id, spec)
        
        # 5. Run in background
        asyncio.create_task(
            self._run_workflow_wrapper(
                task_id,
                workflow,
                spec,
                model_factory=model,
                expected_output_language=expected_output_language,
            )
        )
        
        return task_id

    async def _run_workflow_wrapper(
        self,
        task_id: str,
        workflow,
        spec: AnalysisSpec,
        *,
        model_factory: Callable[[Literal["fast", "slow"], bool], Any],
        expected_output_language: Optional[str],
    ):
        try:
            # Construct input message
            symbol = spec.symbols[0]
            market = spec.markets[0].value
            basic_info = get_company_basic_info(market, symbol)
            company_name = self._extract_company_name(basic_info)
            if company_name:
                self._save_task_company_name(task_id, company_name)
            input_msg = f"Analyze {symbol} on {market} market."
            if basic_info:
                input_msg = "\n\n".join([input_msg, basic_info])
            if spec.focus_topics:
                input_msg += f" Focus on: {', '.join(spec.focus_topics)}."
            
            # Use agno's async run with streaming
            # We iterate over events to capture progress
            final_output = None
            last_run_completed_content: Optional[str] = None
            last_run_completed_agent_name: Optional[str] = None
            
            # Assuming workflow.arun returns an async iterator of events
            async for event in workflow.arun(input=input_msg, stream=True, stream_events=True):
                # Log/Emit event
                await self._emit_event(task_id, event)

                if getattr(event, "event", None) == RunEvent.run_completed.value:
                    content = getattr(event, "content", None)
                    last_run_completed_content = content if content is not None else str(event)
                    last_run_completed_agent_name = (
                        getattr(event, "agent_name", None)
                        or getattr(getattr(event, "agent", None), "name", None)
                        or getattr(getattr(event, "agent", None), "agent_name", None)
                    )

                # Capture final result if available (workflow_completed event)
                if event.event == WorkflowRunEvent.workflow_completed.value:
                    final_output = event.content if hasattr(event, "content") else str(event)

            structured = await self._structure_task_result(
                last_run_completed_content=last_run_completed_content,
                last_run_completed_agent_name=last_run_completed_agent_name,
                model_factory=model_factory,
                expected_output_language=expected_output_language,
            )

            result_snapshot = {
                **structured.model_dump(),
                "raw_run_completed_content": last_run_completed_content,
                "raw_workflow_completed_content": final_output,
                "raw_run_completed_agent_name": last_run_completed_agent_name,
            }

            # Update DB with success
            self._save_task_complete(task_id, result_snapshot)
            await self._emit_custom_payload(
                task_id,
                event_type="TaskResult",
                data=structured.model_dump(),
            )
            
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}", exc_info=True)
            self._save_task_error(task_id, str(e))
        finally:
            if task_id in _running_tasks:
                del _running_tasks[task_id]
            if task_id in self.channels:
                del self.channels[task_id]

    async def _structure_task_result(
        self,
        *,
        last_run_completed_content: Optional[str],
        last_run_completed_agent_name: Optional[str],
        model_factory: Callable[[Literal["fast", "slow"], bool], Any],
        expected_output_language: Optional[str],
    ) -> TaskResultSnapshot:
        raw = (last_run_completed_content or "").strip()
        if not raw:
            return TaskResultSnapshot(recommendation="HOLD", confidence=0.0, summary="分析完成")

        parser_agent = Agent(
            name="TaskResultParser",
            model=model_factory(mode="fast", thinking=False),
            reasoning=False,
            markdown=False,
            parse_response=True,
            output_schema=TaskResultSnapshot,
            structured_outputs=True,
            use_json_mode=True,
            instructions="\n".join(
                [
                    "You are a strict parser. Extract a trading recommendation from the input text.",
                    "Output must be valid JSON matching the provided schema with keys: recommendation, confidence, summary.",
                    "recommendation must be exactly one of: BUY, SELL, HOLD.",
                    "confidence must be between 0 and 1.",
                    "summary must be concise (<= 120 Chinese characters if Chinese, otherwise <= 250 characters).",
                    "If the input is ambiguous, choose HOLD with low confidence.",
                ]
            ),
            expected_output=(
                None
                if not expected_output_language
                else f'Please strictly use the "{expected_output_language}" language for the summary field.'
            ),
        )

        parser_input = "\n\n".join(
            [
                f"Source agent: {last_run_completed_agent_name or 'unknown'}",
                "--- INPUT ---",
                raw,
                "--- END INPUT ---",
            ]
        )

        try:
            out = await parser_agent.arun(input=parser_input, stream=False, output_schema=TaskResultSnapshot)
        except Exception as e:
            logger.error(f"Structured parse failed: {e}", exc_info=True)
            return TaskResultSnapshot(recommendation="HOLD", confidence=0.0, summary=raw[:250] or "分析完成")

        content = getattr(out, "content", None)
        if isinstance(content, TaskResultSnapshot):
            return content
        if hasattr(content, "model_validate"):
            try:
                return TaskResultSnapshot.model_validate(content)
            except Exception:
                pass
        if isinstance(content, dict):
            try:
                return TaskResultSnapshot.model_validate(content)
            except Exception:
                pass

        text = ""
        if hasattr(out, "get_content_as_string"):
            try:
                text = out.get_content_as_string()
            except Exception:
                text = ""
        if not text:
            text = str(content or "")
        try:
            data = json.loads(text)
            return TaskResultSnapshot.model_validate(data)
        except Exception:
            return TaskResultSnapshot(recommendation="HOLD", confidence=0.0, summary=raw[:250] or "分析完成")

    async def _emit_event(self, task_id: str, event: Any):
        """Forward event to frontend via Channel"""
        channel = self.channels.get(task_id)
        event_type = getattr(event, "event", "unknown")
        step_name = getattr(event, "step_name", "") or ""
        run_id = getattr(event, "run_id", None)
        parent_run_id = getattr(event, "parent_run_id", None)
        agent_name = getattr(event, "agent_name", None)
        if not agent_name:
            agent_obj = getattr(event, "agent", None)
            if agent_obj is not None:
                agent_name = (
                    getattr(agent_obj, "name", None)
                    or getattr(agent_obj, "agent_name", None)
                    or getattr(agent_obj, "id", None)
                )

        interesting_events = {
            RunEvent.run_content.value,
            RunEvent.run_completed.value,
            RunEvent.run_error.value,
            RunEvent.run_cancelled.value,
            RunEvent.tool_call_started.value,
            RunEvent.tool_call_completed.value,
            RunEvent.tool_call_error.value,
            WorkflowRunEvent.workflow_completed.value,
            WorkflowRunEvent.workflow_cancelled.value,
            WorkflowRunEvent.workflow_error.value,
        }

        if event_type not in interesting_events:
            return

        if event_type in (
            WorkflowRunEvent.workflow_completed.value,
            WorkflowRunEvent.workflow_cancelled.value,
            WorkflowRunEvent.workflow_error.value,
        ):
            run_id = None
            parent_run_id = None
            agent_name = None

        ts_ms = int(datetime.now().timestamp() * 1000)
        payload = {
            "type": event_type,
            "run_id": run_id,
            "parent_run_id": parent_run_id,
            "agent_name": agent_name,
            "step_name": step_name,
            "timestamp": ts_ms,
        }

        data: Dict[str, Any] = {}
        if event_type in (RunEvent.run_content.value, RunEvent.run_completed.value):
            data["content"] = getattr(event, "content", None)
            data["reasoning_content"] = getattr(event, "reasoning_content", None)
            data["content_type"] = getattr(event, "content_type", None)
        elif event_type == RunEvent.run_error.value:
            data["content"] = getattr(event, "content", None)
            data["error_type"] = getattr(event, "error_type", None)
            data["error_id"] = getattr(event, "error_id", None)
            data["additional_data"] = getattr(event, "additional_data", None)
        elif event_type == RunEvent.run_cancelled.value:
            data["reason"] = getattr(event, "reason", None)
        elif event_type in (
            RunEvent.tool_call_started.value,
            RunEvent.tool_call_completed.value,
            RunEvent.tool_call_error.value,
        ):
            tool_obj = getattr(event, "tool", None)
            if tool_obj is None:
                data["tool"] = {
                    "tool_call_id": getattr(event, "tool_call_id", None),
                    "tool_name": getattr(event, "tool_name", None),
                    "tool_args": getattr(event, "tool_args", None),
                    "result": getattr(event, "result", None),
                    "created_at": getattr(event, "created_at", None),
                    "error": getattr(event, "error", None),
                }
            else:
                if hasattr(tool_obj, "to_dict"):
                    data["tool"] = tool_obj.to_dict()
                elif is_dataclass(tool_obj):
                    data["tool"] = asdict(tool_obj)
                elif hasattr(tool_obj, "model_dump"):
                    data["tool"] = tool_obj.model_dump(mode="json")
                elif hasattr(tool_obj, "dict"):
                    data["tool"] = tool_obj.dict()
                else:
                    data["tool"] = {"repr": repr(tool_obj)}

            if event_type == RunEvent.tool_call_error.value:
                err = getattr(event, "error", None)
                data["error"] = err if isinstance(err, (str, int, float, bool, type(None))) else repr(err)
        elif event_type in (
            WorkflowRunEvent.workflow_completed.value,
            WorkflowRunEvent.workflow_cancelled.value,
            WorkflowRunEvent.workflow_error.value,
        ):
            data["content"] = getattr(event, "content", None)
        else:
            if hasattr(event, "model_dump"):
                data = event.model_dump(mode="json")
            elif hasattr(event, "dict"):
                data = event.dict()
            else:
                data = {"content": str(event)}

        payload["data"] = data

        self._save_task_event(task_id, event_type=event_type, step_name=step_name, timestamp_ms=ts_ms, payload=payload)

        if not channel:
            return

        from .commands import LogMessage

        try:
            msg = LogMessage(
                task_id=task_id,
                message=f"[{event_type}] {step_name}",
                data=json.dumps(payload),
            )
            channel.send_model(msg)
        except Exception as e:
            logger.error(f"Error emitting event: {e}", exc_info=True)

    async def _emit_custom_payload(self, task_id: str, *, event_type: str, data: Dict[str, Any], step_name: str = ""):
        ts_ms = int(datetime.now().timestamp() * 1000)
        payload = {
            "type": event_type,
            "run_id": None,
            "parent_run_id": None,
            "agent_name": None,
            "step_name": step_name,
            "timestamp": ts_ms,
            "data": data,
        }

        self._save_task_event(
            task_id,
            event_type=event_type,
            step_name=step_name,
            timestamp_ms=ts_ms,
            payload=payload,
        )

        channel = self.channels.get(task_id)
        if not channel:
            return

        from .commands import LogMessage

        try:
            msg = LogMessage(
                task_id=task_id,
                message=f"[{event_type}] {step_name}".strip(),
                data=json.dumps(payload, ensure_ascii=False),
            )
            channel.send_model(msg)
        except Exception as e:
            logger.error(f"Error emitting custom payload: {e}", exc_info=True)

    def _create_model(self, config: Optional[LLMConfig], thinking: bool = True):
        return OpenAILike(
            id=config.model_name,
            api_key=config.api_key,
            base_url=config.api_base,
            temperature=config.temperature,
            extra_body={"enable_thinking": thinking},
        )

    def _create_model_factory(
        self, fast_conf: Optional[LLMConfig], slow_conf: Optional[LLMConfig]
    ) -> Callable[[Literal["fast", "slow"], bool], Any]:
        cache: Dict[tuple[str, bool], Any] = {}

        def model(mode: Literal["fast", "slow"] = "fast", thinking: bool = False):
            key = (mode, thinking)
            cached = cache.get(key)
            if cached is not None:
                return cached

            conf = fast_conf if mode == "fast" else slow_conf
            created = self._create_model(conf, thinking=thinking)
            cache[key] = created
            return created

        return model

    def _save_task_initial(self, task_id: str, spec: AnalysisSpec):
        from sqlmodel import Session
        from .database import _engine
        if not _engine: return
        with Session(_engine) as session:
            task = AnalysisTask(
                task_id=task_id,
                status="running",
                spec=spec.model_dump_json()
            )
            session.add(task)
            session.commit()

    def _save_task_complete(self, task_id: str, result):
        from sqlmodel import Session
        from .database import _engine
        if not _engine: return
        with Session(_engine) as session:
            task = session.get(AnalysisTask, task_id)
            if task:
                task.status = "completed"
                # result might be complex, verify type
                if hasattr(result, "model_dump_json"):
                    task.result_snapshot = result.model_dump_json()
                elif isinstance(result, (dict, list)):
                    task.result_snapshot = json.dumps(result, ensure_ascii=False)
                else:
                    task.result_snapshot = json.dumps({"result": str(result)}, ensure_ascii=False)
                task.completed_at = datetime.now()
                session.add(task)
                session.commit()

    def _save_task_error(self, task_id: str, error: str):
        from sqlmodel import Session
        from .database import _engine
        if not _engine: 
            return
        with Session(_engine) as session:
            task = session.get(AnalysisTask, task_id)
            if task:
                task.status = "failed"
                task.error_message = error
                task.completed_at = datetime.now()
                session.add(task)
                session.commit()

    def _save_task_event(self, task_id: str, event_type: str, step_name: str, timestamp_ms: int, payload: dict):
        from sqlmodel import Session
        from .database import _engine
        if not _engine:
            return
        with Session(_engine) as session:
            row = AnalysisTaskEvent(
                task_id=task_id,
                event_type=event_type,
                step_name=step_name,
                timestamp_ms=timestamp_ms,
                payload=payload,
            )
            session.add(row)
            session.commit()

    def _extract_company_name(self, basic_info: str) -> Optional[str]:
        text = (basic_info or "").strip()
        if not text:
            return None
        keys = ["股票简称", "公司名称", "证券简称", "名称", "简称"]
        for line in text.splitlines():
            s = line.strip()
            for k in keys:
                prefix = f"{k}:"
                if s.startswith(prefix):
                    val = s[len(prefix):].strip()
                    if val and val.lower() not in ("nan", "none"):
                        return val
        return None

    def _save_task_company_name(self, task_id: str, company_name: str):
        from sqlmodel import Session
        from .database import _engine
        if not _engine:
            return
        name = (company_name or "").strip()
        if not name:
            return
        with Session(_engine) as session:
            task = session.get(AnalysisTask, task_id)
            if task:
                task.company_name = name
                task.updated_at = datetime.now()
                session.add(task)
                session.commit()

live_context = LiveContext()
