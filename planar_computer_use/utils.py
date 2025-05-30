import io
from PIL import Image
from planar.utils import utc_now

from planar.files.models import PlanarFile

from planar_computer_use.vnc_manager import VNCManager


def image_bytes(image: Image.Image) -> bytes:
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return buffered.getvalue()


async def upload_screenshot(screenshot_pil: Image.Image) -> PlanarFile:
    return await PlanarFile.upload(
        content=image_bytes(screenshot_pil),
        content_type="image/png",
        filename=f"desktop-screenshot-{str(utc_now()).replace(' ', '-')}.png",
    )


async def take_screenshot():
    vnc_manager = VNCManager.get()
    if not vnc_manager or not vnc_manager.is_connected:
        raise ConnectionError(
            "VNC manager not available or not connected for take_screenshot."
        )
    screenshot_pil = await vnc_manager.capture_screen_pil()
    return await upload_screenshot(screenshot_pil)
