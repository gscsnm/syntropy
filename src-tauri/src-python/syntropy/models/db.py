from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel, JSON, UniqueConstraint

class LLMConfig(SQLModel, table=True):
    """
    LLM 配置模型
    存储不同模型的连接信息，如 OpenAI, Anthropic, Ollama 等
    """
    __tablename__ = "llm_config"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, description="配置名称，如 'GPT-4 Turbo'")
    provider: str = Field(description="提供商，如 'openai', 'anthropic', 'ollama'")
    api_base: Optional[str] = Field(default=None, description="API 基础 URL")
    api_key: Optional[str] = Field(default=None, description="API 密钥")
    model_name: str = Field(description="模型名称，如 'gpt-4-turbo'")
    temperature: float = Field(default=0.3, description="温度参数")
    is_active_fast: bool = Field(default=False)
    is_active_slow: bool = Field(default=False)
    role: str = Field(default="fast", description="模型角色：'fast' 或 'slow'", sa_column_kwargs={"unique": True})
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class AnalysisTask(SQLModel, table=True):
    """
    分析任务模型
    存储每次分析任务的状态、参数和结果快照
    """
    __tablename__ = "analysis_task"

    task_id: str = Field(primary_key=True, description="任务唯一标识符 (UUID)")
    status: str = Field(default="pending", index=True, description="任务状态: pending, running, completed, failed, stopped")
    
    # 使用 JSON 类型存储复杂结构
    spec: str = Field(description="分析规格 (AnalysisSpec) 的 JSON 字符串")
    company_name: Optional[str] = Field(default=None, index=True, description="公司名称/简称")
    result_snapshot: Optional[str] = Field(default=None, sa_type=JSON, description="分析结果快照")
    
    error_message: Optional[str] = Field(default=None, description="错误信息")
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = Field(default=None)

class AnalysisTaskEvent(SQLModel, table=True):
    __tablename__ = "analysis_task_event"

    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: str = Field(index=True, foreign_key="analysis_task.task_id")

    event_type: str = Field(index=True)
    step_name: str = Field(default="")
    timestamp_ms: int = Field(index=True)

    payload: dict = Field(sa_type=JSON)

    created_at: datetime = Field(default_factory=datetime.now)

class AppSetting(SQLModel, table=True):
    """
    应用设置
    存储键值类型的应用级设置，如语言等
    """
    __tablename__ = "app_setting"
    __table_args__ = (UniqueConstraint("key"), )

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True, description="设置键", sa_column_kwargs={"unique": True})
    value: str = Field(description="设置值")
    updated_at: datetime = Field(default_factory=datetime.now)
