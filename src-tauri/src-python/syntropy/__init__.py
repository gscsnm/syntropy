from pathlib import Path

from anyio.from_thread import start_blocking_portal
from pydantic.alias_generators import to_camel
from pytauri import (
    Manager,
    builder_factory,
    context_factory,
    IS_DEV
)

from pytauri_utils.async_tools import AsyncTools
import logging

# Import commands from the commands module
from .commands import commands
from .startup import initialize_app_state

logger = logging.getLogger(__name__)

PYTAURI_GEN_TS = IS_DEV

def main() -> int:
    with start_blocking_portal("asyncio") as portal, AsyncTools(portal) as async_tools:  # or `trio`
        if PYTAURI_GEN_TS:
            # ⭐ Generate TypeScript Client to your frontend `src/client` directory
            output_dir = Path(__file__).parent.parent.parent.parent / "src" / "client"
            # ⭐ The CLI to run `json-schema-to-typescript`,
            # `--format=false` is optional to improve performance
            json2ts_cmd = "npm exec -- json2ts --format=false"

            # ⭐ Start the background task to generate TypeScript types
            portal.start_task_soon(
                lambda: commands.experimental_gen_ts_background(
                    output_dir, json2ts_cmd, cmd_alias=to_camel
                )
            )

        app = builder_factory().build(
            context=context_factory(),
            invoke_handler=commands.generate_handler(portal),
        )
        Manager.manage(app, async_tools)

        initialize_app_state(app.handle())

        exit_code = app.run_return()
        return exit_code
