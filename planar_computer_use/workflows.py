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
from planar_computer_use.vnc_manager import instance


@workflow()
async def perform_computer_task(goal: str) -> str:
    vnc_manager = instance.get()

    if not vnc_manager.is_connected:
        await vnc_manager.connect()

    turns = 25

    for _ in range(turns):
        screenshot_file = await take_screenshot()
        screenshot_with_prompt = ScreenshotWithPrompt(file=screenshot_file, prompt=goal)
        response = await computer_use_orchestration_agent(screenshot_with_prompt)
        next_step = response.output.strip().lower().replace(".", "")

        if next_step in ["complete", '"complete"']:
            return f"Goal of {goal} already achieved, no further action needed."

        screenshot_with_action = ScreenshotWithPrompt(
            file=screenshot_file, prompt=next_step
        )
        await computer_use_agent(screenshot_with_action)
        await sleep(1)

    raise Exception(f"Goal '{goal}' could not be completed after {turns} turns.")


@step()
async def draw_rectangle(element: str, grounding_agent: bool = False) -> PlanarFile:
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
    element: str, grounding_agent: bool = False
) -> PlanarFile:
    return await draw_rectangle(element, grounding_agent=grounding_agent)
