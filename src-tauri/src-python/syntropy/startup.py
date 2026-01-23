import locale
import logging
import os
from pathlib import Path
from pytauri import AppHandle, IS_DEV


logger = logging.getLogger(__name__)


def initialize_app_state(app_handle: AppHandle) -> None:
    try:
        if not IS_DEV:
            env_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
            if env_path and Path(env_path).exists():
                pass
            else:
                resource_dir = None
                try:
                    resource_dir = app_handle.path_resolver().resource_dir()
                except Exception:
                    resource_dir = None
                if resource_dir:
                    candidates = [
                        Path(resource_dir) / "ms-playwright",
                        Path(resource_dir) / "python" / "ms-playwright",
                        Path(resource_dir)
                        / "lib"
                        / "python3.12"
                        / "site-packages"
                        / "playwright"
                        / "driver"
                        / "package"
                        / ".local-browsers",
                    ]
                    browsers_path = next(
                        (path for path in candidates if path.exists()), None
                    )
                    if browsers_path:
                        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_path)
                    else:
                        logger.warning(
                            "playwright browser path not found under resource dir"
                        )

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
