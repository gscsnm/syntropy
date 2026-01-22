from agno.agent import Agent
from typing import Optional, Any

from ..models.domain import MarketEnum

def _expected_output(expected_output_language: Optional[str]) -> Optional[str]:
    if not expected_output_language:
        return None
    return f'Please strictly use the "{expected_output_language}" language when outputting replies.'

def _resolve_model(model: Any, *, mode: str, thinking: bool) -> Any:
    if callable(model):
        return model(mode=mode, thinking=thinking)
    return model

def create_trader(
    model=None,
    market: MarketEnum = MarketEnum.US,
    expected_output_language: Optional[str] = None,
) -> Agent:
    return Agent(
        name="TraderAgent",
        role="Trading Agent",
        model=_resolve_model(model, mode="slow", thinking=True),
        expected_output=_expected_output(expected_output_language),
        add_datetime_to_context=True,
        instructions="""
        You are a trading agent analyzing market data to make investment decisions. Based on your analysis, provide a specific recommendation to buy, sell, or hold. End with a firm decision and always conclude your response with 'FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**' to confirm your recommendation. 

        Based on a comprehensive analysis by a team of analysts. This plan incorporates insights from current technical market trends, macroeconomic indicators. Use this plan as a foundation for evaluating your next trading decision.Leverage these insights to make an informed and strategic decision.

        Grounding rules (must follow):
        - You may only use facts explicitly present in the provided input context.
        - Do not introduce numbers, dates, names, events, or metrics that are not present in the input.
        - For any factual claim, include at least one verbatim quote from the input using: [[quote: ...]].
        - If you cannot find supporting text in the input, write "UNSUPPORTED" and do not assert it as fact.
        """,
    )
