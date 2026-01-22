from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import date

class MarketEnum(str, Enum):
    US = "US"     # 美股
    HK = "HK"     # 港股
    CN = "CN"     # A股
    CRYPTO = "CRYPTO" # 加密货币

class ResearchDepth(str, Enum):
    LOW = "low"       # 快速分析 (1轮辩论)
    MEDIUM = "medium" # 标准分析 (3轮辩论)
    HIGH = "high"     # 深度分析 (5轮辩论)

class AnalysisSpec(BaseModel):
    """
    分析任务规格说明书
    前端传递给后端的启动参数
    """
    symbols: List[str] = Field(..., description="股票代码列表，如 ['AAPL', 'NVDA']")
    markets: List[MarketEnum] = Field(..., description="市场列表")
    research_depth: ResearchDepth = Field(default=ResearchDepth.MEDIUM, description="研究深度")
    
    # 可选的高级参数
    start_date: Optional[str] = Field(None, description="分析起始日期 YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="分析结束日期 YYYY-MM-DD")
    focus_topics: List[str] = Field(default_factory=list, description="特定关注的主题，如 'AI Revenue', 'Regulatory Risk'")

class ReportSection(BaseModel):
    title: str
    content: str
    data_points: Optional[Dict[str, Any]] = None

class AnalysisReport(BaseModel):
    """
    单只股票的分析报告结构
    """
    symbol: str
    market: str
    summary: str
    technical_analysis: Optional[str] = None
    fundamental_analysis: Optional[str] = None
    news_sentiment: Optional[str] = None
    final_signal: str = Field(description="BUY, SELL, HOLD")
    confidence: float = Field(description="置信度 0-1")
    created_at: str
