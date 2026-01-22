import os
from pathlib import Path
from typing import Optional
from sqlmodel import SQLModel, create_engine, Session, select
from pytauri import AppHandle
from datetime import datetime

from .models.db import LLMConfig, AnalysisTask, AppSetting

# 全局引擎实例
_engine = None

def get_db_path() -> Path:
    """
    获取数据库文件路径
    在开发环境使用项目根目录下的 app_data
    在生产环境使用 Tauri 的 App Data 目录
    """
    # 简单的判断逻辑，实际可根据环境变量或 AppHandle 获取
    # 这里为了开发方便，先硬编码到项目目录的 app_data
    base_dir = Path(__file__).parent.parent.parent.parent / "app_data"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "syntropy.db"

def init_db():
    """初始化数据库连接和表结构"""
    global _engine
    db_path = get_db_path()
    sqlite_url = f"sqlite:///{db_path}"
    
    # check_same_thread=False 是为了让 SQLite 在多线程环境下 (Python async) 正常工作
    _engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
    
    # 创建表
    SQLModel.metadata.create_all(_engine)
    try:
        with _engine.connect() as conn:
            rows = conn.exec_driver_sql("PRAGMA table_info(analysis_task)").fetchall()
            col_names = {str(r[1]) for r in rows}
            if "company_name" not in col_names:
                conn.exec_driver_sql("ALTER TABLE analysis_task ADD COLUMN company_name TEXT")
                conn.commit()
    except Exception:
        pass
    print(f"Database initialized at {db_path}")

def get_session():
    """获取数据库会话生成器"""
    if _engine is None:
        init_db()
    with Session(_engine) as session:
        yield session

def stop_incomplete_analysis_tasks() -> int:
    if _engine is None:
        init_db()
    now = datetime.now()
    with Session(_engine) as session:
        statement = select(AnalysisTask).where(AnalysisTask.status.in_(("pending", "running")))
        tasks = list(session.exec(statement).all())
        for task in tasks:
            task.status = "stopped"
            task.updated_at = now
            if task.completed_at is None:
                task.completed_at = now
            session.add(task)
        session.commit()
        return len(tasks)

def get_active_llm_config(typ: str = "fast") -> Optional[LLMConfig]:
    if _engine is None:
        init_db()
        
    with Session(_engine) as session:
        statement = select(LLMConfig).where(LLMConfig.role == typ)
        print(statement)
        return session.exec(statement).first()

def get_app_language() -> Optional[str]:
    """获取应用语言设置"""
    if _engine is None:
        init_db()
    with Session(_engine) as session:
        statement = select(AppSetting).where(AppSetting.key == "language")
        setting = session.exec(statement).first()
        return setting.value if setting else None

def set_app_language(lang: str) -> None:
    """设置应用语言"""
    if _engine is None:
        init_db()
    with Session(_engine) as session:
        setting = session.exec(select(AppSetting).where(AppSetting.key == "language")).first()
        if setting:
            setting.value = lang
            setting.updated_at = datetime.now()
            session.add(setting)
        else:
            setting = AppSetting(key="language", value=lang)
            session.add(setting)
        session.commit()
