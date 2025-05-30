import re
from gradio_client import Client, handle_file

import os

from planar.utils import asyncify

from planar_computer_use.vnc_manager import instance

BBOX_PATTERN = re.compile(r"<\|box_start\|>(.*?)<\|box_end\|>")
COORDS_PATTERN = re.compile(r"\d+\.\d+|\d+")

OSATLAS_HUGGINGFACE_SOURCE = "maxiw/OS-ATLAS"
OSATLAS_HUGGINGFACE_MODEL = "OS-Copilot/OS-Atlas-Base-7B"
OSATLAS_HUGGINGFACE_API = "/run_example"

HF_TOKEN = os.getenv("HF_TOKEN")


def extract_bbox_midpoint(bbox_response: str):
    match = BBOX_PATTERN.search(bbox_response)
    inner_text = match.group(1) if match else bbox_response
    numbers = [float(num) for num in COORDS_PATTERN.findall(inner_text)]
    if len(numbers) == 2:
        return int(numbers[0]), int(numbers[1])
    elif len(numbers) >= 4:
        return int((numbers[0] + numbers[2]) // 2), int((numbers[1] + numbers[3]) // 2)
    else:
        raise Exception(f"Unexpected bbox format: {bbox_response}")


@asyncify
def _os_atlas_query(prompt: str, image_data_url: str):
    client = Client(OSATLAS_HUGGINGFACE_SOURCE, hf_token=HF_TOKEN)
    result = client.predict(
        image=handle_file(image_data_url),
        text_input=prompt + "\nReturn the response in the form of a bbox",
        model_id=OSATLAS_HUGGINGFACE_MODEL,
        api_name=OSATLAS_HUGGINGFACE_API,
    )
    position = extract_bbox_midpoint(result[1])
    image_url = result[2]
    print(image_url)
    return position


async def os_atlas_query(prompt: str):
    vnc_manager = instance.get()
    image_bytes = await vnc_manager.capture_screen()
    with open("temp_screenshot.png", "wb") as f:
        f.write(image_bytes)
    return await _os_atlas_query(prompt, "temp_screenshot.png")
