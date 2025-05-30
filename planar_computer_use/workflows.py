from asyncio import sleep
import io
from PIL import Image
from planar.logging import get_logger
from planar.utils import utc_now

from planar.ai import Agent
from planar.files.models import BaseModel, PlanarFile
from planar.workflows.decorators import workflow

from planar_computer_use.tools import (
    click_element,
    double_click_element,
    press_keys,
    right_click_element,
    type_text,
)
from planar_computer_use.vnc_manager import instance


logger = get_logger(__name__)
# model="openai:hf/google/gemma-3-27b-it-qat-q4_0-gguf/q4_0"
model = "openai:gpt-4o"


class ScreenshotWithPrompt(BaseModel):
    file: PlanarFile
    prompt: str


computer_user = Agent(
    name="Computer user",
    tools=[
        press_keys,
        type_text,
        click_element,
        right_click_element,
        double_click_element,
    ],
    max_turns=25,
    system_prompt="""
    You are an AI assistant with computer use abilities.

    You can use the available tools to complete simple actions requested by the user.

    If the user asks you to press a certain key N times, you should call the press_keys tool N times instead of doing in a single call.

    For key combinations, it is fine to use a single call to press_keys.
    """,
    user_prompt="{{input.prompt}}",
    model=model,
    input_type=ScreenshotWithPrompt,
    output_type=str,
)

computer_use_orchestrator = Agent(
    name="Computer use orchestrator",
    max_turns=1,
    system_prompt="""
    You are given a screenshot of a computer screen and a goal description. 

    Your goal is to determine the next basic step necessary to complete the goal, or if the goal is already complete. You should only reply with a basic action to be performed or with "complete" if the goal is already achieved.

    Always prefer to use the keyboard in order to perform the task, but you can also use the mouse if
    it is not obvious how the task could be achieved with the keyboard.

    Some examples:

    - The task is to search the web for "UI Grounding", and there's no web browser open and there's a visible Google Chrome icon in the desktop. The response is "double click Google Chrome icon". (Remember that desktop icons must ALWAYS be double-clicked, while other UI elements can be clicked once.)
    - The task is to search the web for "cat videos", there's no web browser open and there's another window visibible which must be minimized. The response is "press super + d". (use mac equivalent shortcuts if you are seeing a mac desktop).
    - The task is to search the web for "dog pictures", and there's no web browser open and there are no visible windows or icons to open a web browser, but there's an applications/start menu button. The response is "press the applications button".
    - The task asks to open Firefox, and there's "start menu" popup open with a "internet" section. The response should be "click the internet section".
    - The task is to search the web for "UI Grounding", and there's a web browser open but the search bar is not focused. The response is "click the search bar".
    - The task is to search the web for "UI Grounding", and there's a web browser open and the search bar is focused. The response should be "type "UI Grounding"".
    - The task is to search the web for "UI Grounding", and there's a web browser open and the search bar is focused and it has "UI Grounding" in it. The response should be "press enter".
    - The task is to search the web for "UI Grounding", and there's a web browser open and the search bar is focused and it has some text different than "UI Grounding" in it. The text should be erased in the most efficient manner:
        - If you see a "clear" button in the textbox, the response should be "click the "clear button" in the search box"
        - Otherwise the response should be "press Backspace N times" (where N is the number of characters in the existing text).
    - The task is to search the web for "UI Grounding", and there's a web browser with search results for "UI Grounding". The response should be "complete".
    - The task is to search the web for "UI Grounding", and there's a web browser with search results for "UI Grounding". The response should be "complete".
    - The task is to open some application, but there's another application in the foreground and all windows should be minimized. The response should be "press super + d".
    - The goal is to "htop" in a terminal window and there's a terminal window in the foreground with "htop" open. The response should be "complete"
    """,
    user_prompt="""{{input.prompt}}""",
    model=model,
    input_type=ScreenshotWithPrompt,
)


def image_bytes(image: Image.Image) -> bytes:
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return buffered.getvalue()


async def take_screenshot():
    vnc_manager = instance.get()
    screenshot_pil = await vnc_manager.capture_screen_pil()
    return await PlanarFile.upload(
        content=image_bytes(screenshot_pil),
        content_type="image/png",
        filename=f"desktop-screenshot-{str(utc_now()).replace(' ', '-')}.png",
    )


@workflow()
async def perform_action(goal: str) -> str:
    vnc_manager = instance.get()

    if not vnc_manager.is_connected:
        await vnc_manager.connect()

    turns = 25

    for _ in range(turns):
        screenshot_file = await take_screenshot()
        screenshot_with_prompt = ScreenshotWithPrompt(file=screenshot_file, prompt=goal)
        response = await computer_use_orchestrator(screenshot_with_prompt)
        next_step = response.output.strip().lower().replace(".", "")

        if next_step in ["complete", '"complete"']:
            return f"Goal of {goal} already achieved, no further action needed."

        screenshot_with_action = ScreenshotWithPrompt(
            file=screenshot_file, prompt=next_step
        )
        await computer_user(screenshot_with_action)
        await sleep(1)

    raise Exception(f"Goal '{goal}' could not be completed after {turns} turns.")
