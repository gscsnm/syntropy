import locale
import logging
import os
from pathlib import Path
from pytauri import AppHandle, IS_DEV


logger = logging.getLogger(__name__)


def initialize_app_state(app_handle: AppHandle) -> None:
    try:
        if not IS_DEV and "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
            resource_dir = None
            try:
                resource_dir = app_handle.path_resolver().resource_dir()
            except Exception:
                resource_dir = None
            if resource_dir:
                browsers_path = Path(resource_dir) / "python" / "ms-playwright"
                os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_path)

        from .database import init_db
        from .database import stop_incomplete_analysis_tasks
        from .database import get_app_language as db_get_lang
        from .database import set_app_language as db_set_lang

        init_db(app_handle)
        stop_incomplete_analysis_tasks()

        current_lang = db_get_lang()
        if not current_lang:
            try:
                sys_locale = locale.getdefaultlocale()[0] or ""
            except Exception:
                sys_locale = ""
            default_lang = "zh-CN" if sys_locale.lower().startswith("zh") else "en-US"
            db_set_lang(default_lang)
    except Exception as e:
        logger.error(f"语言初始化异常: {e}", exc_info=True)
