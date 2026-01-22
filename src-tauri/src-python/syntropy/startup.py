import locale
import logging


logger = logging.getLogger(__name__)


def initialize_app_state() -> None:
    try:
        from .database import init_db
        from .database import stop_incomplete_analysis_tasks
        from .database import get_app_language as db_get_lang
        from .database import set_app_language as db_set_lang

        init_db()
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
