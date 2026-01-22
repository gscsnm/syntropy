from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from agno.workflow import Workflow, Step, Parallel, Loop
from agno.agent import Agent
from agno.workflow.types import StepOutput, StepInput
from agno.run.agent import RunEvent
from agno.run import RunContext

from ..models.domain import AnalysisSpec, ResearchDepth, MarketEnum
from ..agents.analysts import (
    create_market_analyst,
    create_news_analyst,
    create_fundamentals_analyst,
)
from ..agents.researchers import (
    create_bull_researcher,
    create_bear_researcher,
    create_research_manager,
    create_evidence_auditor,
)
from ..agents.trader import create_trader
from ..agents.risk import (
    create_risk_manager,
    create_risky_debator,
    create_safe_debator,
    create_neutral_debator,
)

ANALYSIS_TEAM_REPORT_SESSION_KEY = "analysis_team_report"
EVIDENCE_AUDIT_SESSION_KEY = "evidence_audit"

# --- Helper Functions for Workflow Steps ---

def _grounding_contract() -> str:
    return "\n".join(
        [
            "--- GROUNDING RULES ---",
            "- You may only use facts that appear in the provided analysis report(s).",
            "- Do not introduce numbers, dates, names, events, or metrics not present in the report(s).",
            '- For every factual bullet, include at least one verbatim quote copied from the report(s) using: [[quote: ...]].',
            '- If you cannot find support in the report(s), write "UNSUPPORTED" and stop asserting it as fact.',
            "--- END GROUNDING RULES ---",
        ]
    )

def _get_analysis_team_report(run_context: Optional[RunContext], fallback: str = "") -> str:
    if run_context is None:
        return fallback
    try:
        report = run_context.session_state.get(ANALYSIS_TEAM_REPORT_SESSION_KEY)
        return str(report or fallback)
    except Exception:
        return fallback

def _get_evidence_audit(run_context: Optional[RunContext]) -> str:
    if run_context is None:
        return ""
    try:
        audit = run_context.session_state.get(EVIDENCE_AUDIT_SESSION_KEY)
        return str(audit or "")
    except Exception:
        return ""

def aggregate_reports(step_input: StepInput) -> str:
    """
    Aggregates reports from parallel analysis steps into a single context string.
    Expects step_input.previous_step_content to be a list of results from Parallel execution.
    """
    reports = []
    # For Parallel steps, the output is typically a list of results in previous_step_content
    # or previous_step_output. Let's check previous_step_content first which is more standard.
    results = step_input.previous_step_content
    
    # If results is None, try previous_step_output just in case, though content is preferred for strings
    if results is None and hasattr(step_input, 'previous_step_output'):
         results = step_input.previous_step_output

    if isinstance(results, list):
        for res in results:
            if isinstance(res, StepOutput) and res.content:
                reports.append(res.content)
            elif isinstance(res, str):
                reports.append(res)
            # If the parallel step returned raw objects, handle them here
    elif isinstance(results, str):
        reports.append(results)
    
    combined = "\n\n".join(reports)
    return f"--- ANALYSIS REPORTS ---\n{combined}\n--- END ANALYSIS REPORTS ---"

def format_debate_context(step_input: StepInput) -> str:
    """
    Passes the debate history/context to the next speaker.
    Agno Loop passes the output of the last step to the first step of the next iteration.
    """
    # Simply return previous content to pass it forward
    return str(step_input.previous_step_content or "")

def _analysis_executor_factory(
    market_agent: Agent,
    news_agent: Agent,
    fund_agent: Agent,
):
    async def _executor(step_input: StepInput,run_context: RunContext):
        input_msg = str(step_input.input or "")
        outputs = []
        for agent in (news_agent, market_agent, fund_agent):
            stream = agent.arun(input=input_msg, stream=True, stream_events=True,debug_mode=True)
            final_text = ""
            async for event in stream:
                yield event
                if getattr(event, "event", None) == RunEvent.run_completed.value:
                    content = getattr(event, "content", None)
                    final_text = content if content is not None else str(event)
            text = final_text if isinstance(final_text, str) else str(final_text)
            outputs.append((agent.name, text))
        combined_sections = []
        for name, text in outputs:
            if name == "NewsAnalyst":
                combined_sections.append(f"Latest World Affairs Report (Analyst name: NewsAnalyst): {text}")
            elif name == "MarketAnalyst":
                combined_sections.append(f"Market Research Report (Analyst name: MarketAnalyst): {text}")
            elif name == "FundamentalAnalyst":
                combined_sections.append(f"Company Fundamentals Report (Analyst name: FundamentalAnalyst): {text}")
            else:
                combined_sections.append(f"### {name} Report: {text}")
        combined_text = "\n\n".join(combined_sections)
        # combined_text = f"--- ANALYSIS TEAM REPORTS ---\n{combined_text}\n--- END ANALYSIS TEAM REPORTS ---"
        try:
            run_context.session_state[ANALYSIS_TEAM_REPORT_SESSION_KEY] = combined_text
        except Exception:
            pass
        yield StepOutput(content=combined_text)
    return _executor

def _debate_executor_factory(bull_agent: Agent, bear_agent: Agent, iterations: int):
    async def _executor(step_input: StepInput, run_context: RunContext):
        analysis_team_report = _get_analysis_team_report(
            run_context, fallback=str(step_input.previous_step_content or "")
        )
        initial_context = "\n\n".join(
            [
                # _grounding_contract(),
                "The following is a data report from the analysis team:",
                "--- ANALYSIS TEAM REPORTS ---",
                analysis_team_report,
                "--- END ANALYSIS TEAM REPORTS ---",
            ]
        )
        history_parts: List[str] = []
        context_so_far = initial_context
        for i in range(iterations):
            bull_input = context_so_far
            if i == 0:
                bull_input = "\n\n".join(
                    [
                        "You are the first speaker in this research debate (Bull). Open with your core thesis and the most important supporting evidence, and proactively challenge likely Bear objections.",
                        context_so_far,
                    ]
                )
            bull_stream = bull_agent.arun(input=bull_input, stream=True, stream_events=True,debug_mode=True)
            bull_text = ""
            async for event in bull_stream:
                yield event
                if getattr(event, "event", None) == RunEvent.run_completed.value:
                    content = getattr(event, "content", None)
                    bull_text = content if content is not None else str(event)
            history_parts.append(f"Round {i+1} - BullResearcher: {bull_text}")
            context_so_far = "\n".join([initial_context,"The following is the history of debate:"] + history_parts)
            bear_stream = bear_agent.arun(input=context_so_far, stream=True, stream_events=True,debug_mode=True)
            bear_text = ""
            async for event in bear_stream:
                yield event
                if getattr(event, "event", None) == RunEvent.run_completed.value:
                    content = getattr(event, "content", None)
                    bear_text = content if content is not None else str(event)
            history_parts.append(f"Round {i+1} - BearResearcher: {bear_text}")
            context_so_far = "\n".join([initial_context,"The following is the history of debate:"] + history_parts)
        yield StepOutput(content="\n\n".join(history_parts))
    return _executor


def _agent_step_executor_factory(agent: Agent, section_name: str):
    async def _executor(step_input: StepInput):
        input_msg = str(step_input.previous_step_content)
        stream = agent.arun(input=input_msg, stream=True, stream_events=True,debug_mode=True)
        final_text = ""
        async for event in stream:
            yield event
            if getattr(event, "event", None) == RunEvent.run_completed.value:
                content = getattr(event, "content", None)
                final_text = content if content is not None else str(event)
        text = final_text if isinstance(final_text, str) else str(final_text)
        combined = "\n\n".join([ f"--- {section_name} ---", text, f"--- END {section_name} ---"])
        yield StepOutput(content=combined)
    return _executor


def _evidence_audit_executor_factory(auditor_agent: Agent):
    async def _executor(step_input: StepInput, run_context: RunContext):
        analysis_team_report = _get_analysis_team_report(run_context)
        debate_transcript = str(step_input.previous_step_content or "")
        audit_input = "\n\n".join(
            [
                "The following is a data report from the analysis team:"
                "--- ANALYSIS TEAM REPORTS ---",
                analysis_team_report,
                "--- END ANALYSIS TEAM REPORTS ---",
                "The following is the history of debate:",
                "--- DEBATE TRANSCRIPT ---",
                debate_transcript,
                "--- END DEBATE TRANSCRIPT ---",
            ]
        )
        stream = auditor_agent.arun(
            input=audit_input, stream=True, stream_events=True, debug_mode=True
        )
        final_text = ""
        async for event in stream:
            yield event
            if getattr(event, "event", None) == RunEvent.run_completed.value:
                content = getattr(event, "content", None)
                final_text = content if content is not None else str(event)
        text = final_text if isinstance(final_text, str) else str(final_text)
        # combined = "\n\n".join(
        #     [
        #         "The following is the audited evidence:",
        #         "--- EVIDENCE AUDIT ---",
        #         text,
        #         "--- END EVIDENCE AUDIT ---",
        #     ]
        # )
        try:
            run_context.session_state[EVIDENCE_AUDIT_SESSION_KEY] = text
        except Exception:
            pass
        yield StepOutput(content="\n\n".join(
            [
                "The following is the audited evidence (From EvidenceAuditor):",
                "--- EVIDENCE AUDIT ---",
                text,
                "--- END EVIDENCE AUDIT ---",
                 "The following is the history of debate:",
                "--- DEBATE TRANSCRIPT ---",
                debate_transcript,
                "--- END DEBATE TRANSCRIPT ---",
            ]
        ))

    return _executor


def _risk_debate_executor_factory(
    risky_agent: Agent,
    safe_agent: Agent,
    neutral_agent: Agent,
    iterations: int,
):
    async def _executor(step_input: StepInput, run_context: RunContext):
        previous_context = str(step_input.previous_step_content or "")
        analysis_team_report = _get_analysis_team_report(run_context)
        # evidence_audit = _get_evidence_audit(run_context)

        initial_context = "\n\n".join(
            [
                # _grounding_contract(),
                # "--- Trader Plan ---",
                "Here is the trader's decision (From TraderAgent):",
                previous_context,
                # "--- END Trader Plan ---",
                "The following is a research report from the analysis team:",
                analysis_team_report,
                # evidence_audit,
            ]
        )

        history_parts: List[str] = []
        context_so_far = initial_context

        for i in range(iterations):
            risky_stream = risky_agent.arun(input=context_so_far, stream=True, stream_events=True,debug_mode=True)
            risky_text = ""
            async for event in risky_stream:
                yield event
                if getattr(event, "event", None) == RunEvent.run_completed.value:
                    content = getattr(event, "content", None)
                    risky_text = content if content is not None else str(event)
            history_parts.append(f"Round {i+1} - RiskyDebator: {risky_text}")
            context_so_far = "\n".join([initial_context] + history_parts)

            safe_stream = safe_agent.arun(input=context_so_far, stream=True, stream_events=True,debug_mode=True)
            safe_text = ""
            async for event in safe_stream:
                yield event
                if getattr(event, "event", None) == RunEvent.run_completed.value:
                    content = getattr(event, "content", None)
                    safe_text = content if content is not None else str(event)
            history_parts.append(f"Round {i+1} - SafeDebator: {safe_text}")
            context_so_far = "\n".join([initial_context] + history_parts)

            neutral_stream = neutral_agent.arun(input=context_so_far, stream=True, stream_events=True,debug_mode=True)
            neutral_text = ""
            async for event in neutral_stream:
                yield event
                if getattr(event, "event", None) == RunEvent.run_completed.value:
                    content = getattr(event, "content", None)
                    neutral_text = content if content is not None else str(event)
            history_parts.append(f"Round {i+1} - NeutralDebator: {neutral_text}")
            context_so_far = "\n".join([initial_context] + history_parts)

        yield StepOutput(
            content="\n\n".join(
                [
                    "Here is the trader's original decision (From TraderAgent):",
                    "--- TRADER PLAN ---",
                    previous_context,
                    "--- TRADER PLAN ---"
                    "Analysts Debate History:"
                    "--- RISK DEBATE ---",
                    "\n\n".join(history_parts),
                    "--- END RISK DEBATE ---",
                ]
            )
        )

    return _executor

# --- Workflow Factory ---
def create_analysis_workflow(
    spec: AnalysisSpec,
    model=None,
    expected_output_language: Optional[str] = None,
) -> Workflow:
    """
    Creates an Agno Workflow instance configured with the specific analysis spec.
    """
    
    # 1. Initialize Agents
    market = spec.markets[0] if spec.markets else MarketEnum.US

    market_agent = create_market_analyst(
        model=model,
        market=market,
        expected_output_language=expected_output_language,
    )
    news_agent = create_news_analyst(
        model=model,
        market=market,
        expected_output_language=expected_output_language,
    )

    fund_agent = create_fundamentals_analyst(
        model=model,
        market=market,
        expected_output_language=expected_output_language,
    )

    bull_agent = create_bull_researcher(
        model=model,
        market=market,
        expected_output_language=expected_output_language,
    )
    bear_agent = create_bear_researcher(
        model=model,
        market=market,
        expected_output_language=expected_output_language,
    )
    manager_agent = create_research_manager(
        model=model,
        market=market,
        expected_output_language=expected_output_language,
    )
    auditor_agent = create_evidence_auditor(
        model=model,
        market=market,
        expected_output_language=expected_output_language,
    )

    trader_agent = create_trader(
        model=model,
        market=market,
        expected_output_language=expected_output_language,
    )
    risk_agent = create_risk_manager(
        model=model,
        market=market,
        expected_output_language=expected_output_language,
    )
    risky_agent = create_risky_debator(
        model=model,
        market=market,
        expected_output_language=expected_output_language,
    )
    safe_agent = create_safe_debator(
        model=model,
        market=market,
        expected_output_language=expected_output_language,
    )
    neutral_agent = create_neutral_debator(
        model=model,
        market=market,
        expected_output_language=expected_output_language,
    )

    # 2. Determine Loop Iterations
    iterations = 1
    if spec.research_depth == ResearchDepth.MEDIUM:
        iterations = 3
    elif spec.research_depth == ResearchDepth.HIGH:
        iterations = 5

    risk_iterations = 1
    if spec.research_depth == ResearchDepth.MEDIUM:
        risk_iterations = 2
    elif spec.research_depth == ResearchDepth.HIGH:
        risk_iterations = 3

    # 3. Define Workflow Structure
    
    # Phase 1: Sequential Analysis + Aggregation
    analysis_step = Step(
        name="Phase 1: Sequential Analysis",
        executor=_analysis_executor_factory(market_agent, news_agent, fund_agent),
        description="Run analysts sequentially and combine reports."
    )

    # Phase 2: Research Debate Loop
    # The Loop will run Bull -> Bear repeatedly.
    # Note: The first iteration needs the "Aggregated Reports" as input.
    # Subsequent iterations receive the previous output (Bear's argument).
    debate_step = Step(
        name="Phase 2: Research Debate",
        executor=_debate_executor_factory(bull_agent, bear_agent, iterations),
        description=f"Debate between Bull and Bear for {iterations} rounds."
    )

    audit_step = Step(
        name="Phase 2.5: Evidence Audit",
        executor=_evidence_audit_executor_factory(auditor_agent),
        description="Audit debate claims against analysis reports and flag unsupported claims.",
    )

    # Phase 3: Manager Decision
    manager_step = Step(
        name="Phase 3: Manager Decision",
        executor=_agent_step_executor_factory(manager_agent, "MANAGER DECISION"),
        description="Research Manager reviews the debate and makes a decision."
    )

    # Phase 4: Trading Plan
    trader_step = Step(
        name="Phase 4: Trading Plan",
        executor=_agent_step_executor_factory(trader_agent, "TRADING PLAN"),
        description="Trader generates specific execution plan."
    )

    risk_debate_step = Step(
        name="Phase 5: Risk Debate",
        executor=_risk_debate_executor_factory(
            risky_agent,
            safe_agent,
            neutral_agent,
            risk_iterations,
        ),
        description=f"Debate between Risky, Safe, and Neutral for {risk_iterations} rounds.",
    )

    risk_step = Step(
        name="Phase 6: Risk Review",
        agent=risk_agent,
        description="Risk Manager reviews the plan and debate output.",
    )

    # 4. Create Workflow
    workflow = Workflow(
        name=f"Analysis Workflow: {spec.symbols[0]}",
        description="Automated stock analysis pipeline.",
        steps=[
            analysis_step,
            debate_step,
            audit_step,
            manager_step,
            trader_step,
            risk_debate_step,
            risk_step
        ],
        debug_mode=True
    )
    
    return workflow
