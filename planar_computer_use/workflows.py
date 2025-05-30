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
model = "openai:gpt-4o-mini"


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
    max_turns=2,
    system_prompt="""
    You are an AI assistant with computer use abilities.

    You can use the available tools to interact with the computer in order to complete the task.

    Always prefer to use the keyboard in order to perform the task, but you can also use the mouse if
    it is not obvious how the task could be achieved with the keyboard.

    It is possible that the computer is in a state where the action cannot be immediately performed,
    in which case you must perform an action that will drive towards the requested task.
    If you believe that the task is already complete, then just reply with "task already complete".

    Here are some examples:

    - The user asks for an application which doesn't have a visible launcher or icon, but there's an application/start menu button: Click that button (or double-click for desktop icons).
    - The user asks to open Firefox, and there's "start menu" popup open with a "internet" section. Click the "internet" section.
    - The user asks to type a command in the terminal, but no terminal window is open: Try to open one.
    - The user asks to type a command in the terminal, and a terminal window is visible but unfocused: Click on it to focus.
    - The user asks to search the web but there's no web browser open: Open the web browser.
    - The user asks to search the web and there's a web browser window visible, but the search bar is not focused: Click the search bar.
    - The user asks to open a web browser, but there's a web browser icon on the desktop, then you reply with "done".

    You should reply only with "done" if the task is done or "step" if more steps are needed.
    """,
    user_prompt="{{input.prompt}}",
    model=model,
    input_type=ScreenshotWithPrompt,
)

computer_use_orchestrator = Agent(
    name="Computer use orchestrator",
    max_turns=1,
    system_prompt="""
    You are given a screenshot of a computer screen and a goal description. 

    Your goal is to determine the next basic step necessary to complete the goal, or if the goal is already complete. You should only reply with a basic action to be performed or with "complete" if the goal is already achieved.

    Some examples:

    - The task is to search the web for "UI Grounding", and there's no web browser open. The response is "open a web browser".
    - The task is to search the web for "UI Grounding", and there's a web browser open but the search bar is not focused. The response is "click the search bar".
    - The task is to search the web for "UI Grounding", and there's a web browser open but the search bar is focused. The response should be "type "UI Grounding"".
    - The task is to search the web for "UI Grounding", and there's a web browser with search results for "UI Grounding". The response should be "complete".
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
        await vnc_manager.connect(host="10.0.204.205", port=5901, password="123456")

    turns = 15

    for _ in range(turns):
        screenshot_file = await take_screenshot()
        screenshot_with_prompt = ScreenshotWithPrompt(file=screenshot_file, prompt=goal)
        response = await computer_use_orchestrator(screenshot_with_prompt)
        next_step = response.output.strip()

        if next_step in ["complete", '"complete"']:
            return f"Goal of {goal} already achieved, no further action needed."

        for _ in range(5):
            response = await computer_user(screenshot_with_prompt)
            if response.output == "done":
                break

        await sleep(1)

    raise Exception(f"Goal '{goal}' could not be completed after {turns} turns.")
