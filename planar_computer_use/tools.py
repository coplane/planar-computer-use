from asyncio import sleep

from planar.logging import get_logger
from planar_computer_use.vnc_manager import instance

from pydantic import Field

from planar_computer_use.osatlas import os_atlas_query

logger = get_logger(__name__)


async def click_element(
    element: str = Field(
        description="short description of which UI element should be clicked"
    ),
):
    """Click on a visible UI element."""
    logger.info(f"Clicking on element: {element}")
    x, y = await os_atlas_query(element)
    logger.debug(f"Coordinates for {element}: ({x}, {y})")
    vnc_manager = instance.get()
    await vnc_manager.click(x, y)
    return f"clicked on {element}"


async def double_click_element(
    element: str = Field(
        description="short description of which UI element should be double-clicked"
    ),
):
    """Double-click on a visible UI element."""
    logger.info(f"Double-clicking on element: {element}")
    x, y = await os_atlas_query(element)
    logger.debug(f"Coordinates for {element}: ({x}, {y})")
    vnc_manager = instance.get()
    await vnc_manager.click(x, y)
    await sleep(0.1)  # Small delay between clicks
    await vnc_manager.click(x, y)
    return f"double-clicked on {element}"


async def right_click_element(
    element: str = Field(
        description="short description of which UI element should be right-clicked"
    ),
):
    """Right-click on a visible UI element."""
    logger.info(f"Right-clicking on element: {element}")
    x, y = await os_atlas_query(element)
    logger.debug(f"Coordinates for {element}: ({x}, {y})")
    vnc_manager = instance.get()
    await vnc_manager.click(x, y, button=2)
    return f"right-clicked on {element}"


async def type_text(
    text: str = Field(description="Text to type"),
):
    """Type text into the focused UI element."""
    logger.info(f"Typing text: {text}")
    vnc_manager = instance.get()
    await vnc_manager.type_string(text)
    return f"typed text {text}"


async def press_keys(
    keys: list[str] = Field(description="List of keys to press"),
):
    """Press a sequence of keys and then release in reverse order. Can be used to invoke keyboard shortcuts."""
    logger.info(f"Pressing keys: {', '.join(keys)}")
    vnc_manager = instance.get()
    await vnc_manager.press_keys(keys)
    return f"pressed keys {', '.join(keys)}"
