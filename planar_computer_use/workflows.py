from asyncio import sleep
from planar.rules.decorator import step
from planar.utils import utc_now

from planar.files.models import PlanarFile
from planar.workflows.decorators import workflow

from planar_computer_use.agents import (
    ScreenshotWithPrompt,
    computer_use_orchestration_agent,
    computer_use_agent,
)
from planar_computer_use.grounding import query_element_bbox
from planar_computer_use.pil_utilities import draw_bounding_box
from planar_computer_use.utils import image_bytes, take_screenshot
from planar_computer_use.vnc_manager import VNCManager


@workflow()
async def perform_computer_task(
    goal: str,
    vnc_host_port: str = "127.0.0.1:5905",
    vnc_password: str = "123456",
) -> str:
    async with VNCManager.connect(vnc_host_port, vnc_password) as vnc_manager:
        if not vnc_manager.is_connected:
            # This should not happen if context manager is working
            return f"Failed to connect to VNC server at {vnc_host_port}."

        turns = 25
        for i in range(turns):
            screenshot_file = await take_screenshot()
            screenshot_with_prompt = ScreenshotWithPrompt(
                file=screenshot_file, prompt=goal
            )
            response = await computer_use_orchestration_agent(screenshot_with_prompt)
            next_step = response.output.strip().lower().replace(".", "")

            if next_step in ["complete", '"complete"']:
                return f"Goal '{goal}' achieved."

            screenshot_with_action = ScreenshotWithPrompt(
                file=screenshot_file, prompt=next_step
            )
            await computer_use_agent(screenshot_with_action)
            await sleep(1)  # Allow time for action to reflect on screen

        raise Exception(f"Goal '{goal}' could not be completed after {turns} turns.")


@step()
async def draw_rectangle(element: str, grounding_agent: bool = False) -> PlanarFile:
    # This step will be called within a workflow that has an active VNCManager context
    target_rect, screenshot_pil = await query_element_bbox(element, grounding_agent)

    img = draw_bounding_box(screenshot_pil, target_rect)
    screenshot_file = await PlanarFile.upload(
        content=image_bytes(img),
        content_type="image/png",
        filename=f"bounding-box-{str(utc_now()).replace(' ', '-')}.png",
    )
    return screenshot_file


@workflow()
async def highlight_ui_element(
    element: str,
    grounding_agent: bool = False,
    vnc_host_port: str = "127.0.0.1:5905",
    vnc_password: str = "123456",
) -> PlanarFile:
    async with VNCManager.connect(vnc_host_port, vnc_password) as vnc_manager:
        if not vnc_manager.is_connected:
            raise ConnectionError(
                f"Failed to connect to VNC server at {vnc_host_port} for highlighting."
            )
        return await draw_rectangle(element, grounding_agent=grounding_agent)
