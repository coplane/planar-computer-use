from planar.ai import Agent
from planar_computer_use.models import ScreenshotWithPrompt

from planar_computer_use.tools import (
    click_element,
    double_click_element,
    press_keys,
    right_click_element,
    type_text,
)


# model="openai:hf/google/gemma-3-27b-it-qat-q4_0-gguf/q4_0"
model = "openai:gpt-4o"

computer_use_agent = Agent(
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

computer_use_orchestration_agent = Agent(
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


grounding_agent = Agent(
    name="Grounding agent",
    tools=[],
    max_turns=1,
    system_prompt="""
    You are an AI assistant and will be given:

    - A screenshot of a computer desktop session.
    - An UI element description

    The screenshot will have a grid drawn on top of it, with each cell containing a number.

    Your task is to identify the grid cell that has the greatest intersection with the UI element.

    If the element cannot be seen in the screenshot, you should reply with -1.

    You should reply only with a cell number or -1 (no other text other than the number).
    """,
    user_prompt="{{input.prompt}}",
    model=model,
    input_type=ScreenshotWithPrompt,
    output_type=str,
)
