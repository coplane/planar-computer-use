import re
from gradio_client import Client, handle_file

import os

from planar.utils import asyncify

from planar_computer_use.models import ScreenshotWithPrompt
from planar_computer_use.pil_utilities import draw_annotated_grid
from planar_computer_use.vnc_manager import VNCManager
from planar_computer_use.utils import image_bytes, upload_screenshot

BBOX_PATTERN = re.compile(r"<\|box_start\|>(.*?)<\|box_end\|>")
COORDS_PATTERN = re.compile(r"\d+\.\d+|\d+")

OSATLAS_HUGGINGFACE_SOURCE = "maxiw/OS-ATLAS"
osatlas_endpoint_override = os.getenv("OSATLAS_ENDPOINT_OVERRIDE")
if osatlas_endpoint_override:
    OSATLAS_HUGGINGFACE_SOURCE = osatlas_endpoint_override
OSATLAS_HUGGINGFACE_SOURCE = "http://192.168.1.221:7080"
OSATLAS_HUGGINGFACE_MODEL = "OS-Copilot/OS-Atlas-Base-7B"
OSATLAS_HUGGINGFACE_API = "/run_example"

HF_TOKEN = os.getenv("HF_TOKEN")


def extract_bbox_midpoint(bbox: tuple[int, int, int, int]) -> tuple[int, int]:
    return int((bbox[0] + bbox[2]) // 2), int((bbox[1] + bbox[3]) // 2)


@asyncify
def _os_atlas_query_element_bbox(
    element: str, image_data_url: str
) -> tuple[int, int, int, int]:
    client = Client(OSATLAS_HUGGINGFACE_SOURCE, hf_token=HF_TOKEN)
    result = client.predict(
        image=handle_file(image_data_url),
        text_input=element + "\nReturn the response in the form of a bbox",
        model_id=OSATLAS_HUGGINGFACE_MODEL,
        api_name=OSATLAS_HUGGINGFACE_API,
    )

    match = BBOX_PATTERN.search(result[1])
    inner_text = match.group(1) if match else result[1]
    bbox = [int(round(float(num))) for num in COORDS_PATTERN.findall(inner_text)]
    if len(bbox) == 4:
        return (bbox[0], bbox[1], bbox[2], bbox[3])
    raise Exception(f"Unexpected bbox format: {result[1]}")


async def os_atlas_query_element_bbox(element: str):
    vnc_manager = VNCManager.get()
    if not vnc_manager or not vnc_manager.is_connected:
        raise ConnectionError("VNC manager not available or not connected.")
    screenshot_pil = await vnc_manager.capture_screen_pil()
    # Using a temporary file like this is not ideal, especially in async code.
    # Consider passing bytes directly if possible, or ensure unique filenames if concurrent use.
    # For now, retaining existing logic but noting this.
    temp_file_path = "temp_screenshot_os_atlas.png"  # Make filename more specific
    with open(temp_file_path, "wb") as f:
        f.write(image_bytes(screenshot_pil))
    bbox = await _os_atlas_query_element_bbox(element, temp_file_path)
    # It's good practice to clean up temporary files.
    # os.remove(temp_file_path) # Add this if appropriate for your environment
    return bbox, screenshot_pil


async def grounding_agent_query_element_bbox(element: str, steps: int = 2):
    from planar_computer_use.agents import grounding_agent

    vnc_manager = VNCManager.get()
    if not vnc_manager or not vnc_manager.is_connected:
        raise ConnectionError(
            "VNC manager not available or not connected for grounding_agent_query_element_bbox."
        )

    screenshot_pil = await vnc_manager.capture_screen_pil()  # Initial screenshot
    target_rect = None  # Initialize target_rect

    # steps = 2 # Parameter is already defaulted and can be overridden by caller

    for _ in range(steps):
        annotated_screenshot, cells = draw_annotated_grid(
            screenshot_pil, num_rows=4, num_cols=4, target_rect=target_rect
        )
        screenshot_file = await upload_screenshot(annotated_screenshot)
        screenshot_with_prompt = ScreenshotWithPrompt(
            file=screenshot_file, prompt=element
        )
        response = await grounding_agent(screenshot_with_prompt)
        cell_number = int(response.output.strip())
        target_rect = cells[cell_number]

    assert target_rect
    return target_rect, screenshot_pil


async def query_element_bbox(element: str, grounding_agent: bool = False):
    if grounding_agent:
        return await grounding_agent_query_element_bbox(element)
    else:
        return await os_atlas_query_element_bbox(element)


async def query_element_position(element: str, vlm: bool = False):
    bbox, _ = await query_element_bbox(element, grounding_agent=vlm)
    x, y = extract_bbox_midpoint(bbox)
    return x, y
