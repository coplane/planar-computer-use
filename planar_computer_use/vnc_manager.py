import asyncio
import base64
from contextvars import ContextVar, Token
import io
from typing import Optional
from contextlib import AsyncExitStack, asynccontextmanager

from PIL import Image
from planar.logging import get_logger
import asyncvnc

logger = get_logger(__name__)

vnc_instance_cv: ContextVar[Optional["VNCManager"]] = ContextVar(
    "vnc_instance_cv", default=None
)


class VNCManager:
    def __init__(self, host: str, port: int, password: str):
        self.host = host
        self.port = port
        self.password = password
        self.client: Optional[asyncvnc.Client] = None
        self.is_connected = False
        self.last_screenshot_base64 = "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs="  # Transparent pixel
        self._screenshot_interval = 1
        self._update_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._exit_stack: Optional[AsyncExitStack] = None
        self._cm_token: Optional[Token] = None

    @classmethod
    def get(cls) -> Optional["VNCManager"]:
        """Gets the VNCManager instance from the context variable."""
        return vnc_instance_cv.get()

    @classmethod
    @asynccontextmanager
    async def connect(cls, host_port_str: str, password: str):
        try:
            host, port_str = host_port_str.split(":")
            port = int(port_str)
        except ValueError:
            raise ValueError(
                f"Invalid host:port format: {host_port_str}. Expected 'host:port'."
            )

        manager = cls(host, port, password)

        original_token = vnc_instance_cv.set(manager)
        manager._cm_token = original_token

        try:
            logger.info(
                f"Attempting to connect to VNC server: {manager.host}:{manager.port}"
            )
            manager._exit_stack = AsyncExitStack()
            manager.client = await manager._exit_stack.enter_async_context(
                asyncvnc.connect(manager.host, manager.port, password=manager.password)
            )
            manager.is_connected = True
            logger.info(f"Successfully connected to VNC: {manager.host}:{manager.port}")
            logger.info(f"Server info: {manager.client}")

            manager._stop_event.clear()
            manager._update_task = asyncio.create_task(
                manager._periodic_screenshot_updater()
            )

            yield manager
        except Exception as e:
            logger.error(
                f"VNC Connection failed for {manager.host}:{manager.port}: {e}",
                exc_info=True,
            )
            # Ensure partial cleanup if connection fails mid-way
            if manager._update_task and not manager._update_task.done():
                manager._stop_event.set()
                manager._update_task.cancel()
                try:
                    await manager._update_task
                except asyncio.CancelledError:
                    pass
            if manager._exit_stack:
                await manager._exit_stack.aclose()
            manager.client = None
            manager.is_connected = False
            raise  # Re-raise the exception after cleanup
        finally:
            logger.info(f"Disconnecting from VNC server: {manager.host}:{manager.port}")
            if manager._update_task:
                manager._stop_event.set()
                if not manager._update_task.done():
                    manager._update_task.cancel()
                    try:
                        await manager._update_task
                    except asyncio.CancelledError:
                        logger.info(
                            f"Screenshot updater task cancelled for {manager.host}:{manager.port}."
                        )
                    except Exception as e_task:
                        logger.error(
                            f"Error stopping screenshot updater for {manager.host}:{manager.port}: {e_task}",
                            exc_info=True,
                        )
                manager._update_task = None

            if manager._exit_stack:
                try:
                    await manager._exit_stack.aclose()
                except Exception as e_stack:
                    logger.error(
                        f"Error closing VNC exit stack for {manager.host}:{manager.port}: {e_stack}",
                        exc_info=True,
                    )
                manager._exit_stack = None

            manager.client = None
            manager.is_connected = False
            manager.last_screenshot_base64 = (
                "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs="
            )

            if manager._cm_token:
                vnc_instance_cv.reset(manager._cm_token)
                manager._cm_token = None
            logger.info(
                f"Disconnected and cleaned up for VNC server: {manager.host}:{manager.port}"
            )

    async def capture_screen_pil(self):
        if not self.is_connected or not self.client:
            raise ConnectionError("Not connected to VNC server.")
        for _ in range(10):
            try:
                pixels = await self.client.screenshot()
                image = Image.fromarray(pixels)
                return image
            except Exception as e:
                logger.error(f"Failed to capture screen: {e}")
        raise Exception("Failed to capture screen after multiple attempts.")

    async def capture_screen(self) -> bytes:
        pil_image = await self.capture_screen_pil()
        buffered = io.BytesIO()
        pil_image.save(buffered, format="PNG")
        return buffered.getvalue()

    async def capture_screen_base64(self) -> str:
        if not self.is_connected:
            return "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs="  # Placeholder
        try:
            image_bytes = await self.capture_screen()
            img_str = base64.b64encode(image_bytes).decode("utf-8")
            return f"data:image/png;base64,{img_str}"
        except Exception as e:
            logger.error(f"Error capturing screen to base64: {e}")
            return "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs="  # Error placeholder

    async def _periodic_screenshot_updater(self):
        logger.info("Screenshot updater task started.")
        try:
            while not self._stop_event.is_set():
                if self.is_connected and self.client:
                    try:
                        new_screenshot = await self.capture_screen_base64()
                        if new_screenshot:
                            self.last_screenshot_base64 = new_screenshot
                    except Exception as e:
                        logger.error(f"Periodic screenshot update failed: {e}")
                else:
                    # This case should ideally not be hit if _stop_event is managed correctly
                    # with is_connected status.
                    self.last_screenshot_base64 = (
                        "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs="
                    )
                    break  # If not connected, stop trying to update.

                await asyncio.sleep(self._screenshot_interval)

        except asyncio.CancelledError:
            logger.info(
                f"Screenshot updater task cancelled for {self.host}:{self.port}."
            )
        except Exception as e:
            logger.error(
                f"Error in periodic screenshot updater for {self.host}:{self.port}: {e}",
                exc_info=True,
            )
            self.is_connected = False  # Assume connection is lost
            self.last_screenshot_base64 = (
                "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs="
            )
        finally:
            logger.info(f"Screenshot updater task stopped for {self.host}:{self.port}.")

    async def mouse_move(self, x: int, y: int):
        if not self.is_connected or not self.client:
            raise ConnectionError("Not connected to VNC server.")
        try:
            # Move mouse to position
            self.client.mouse.move(x, y)
            # Ensure events are sent
            await self.client.drain()
        except Exception as e:
            logger.error(f"VNC mouse move failed: {e}")
            raise

    async def click(self, x: int, y: int, button: int = 0):
        if not self.is_connected or not self.client:
            raise ConnectionError("Not connected to VNC server.")
        try:
            # Move mouse to position
            self.client.mouse.move(x, y)

            # Map our button numbers to AsyncVNC button indices
            # Our API: 0=left, 1=middle, 2=right (standard for many libraries)
            # AsyncVNC: 0=left, 1=middle, 2=right
            # The existing code uses button=0 for left, button=2 for right.
            # Let's assume button parameter means: 0 for left, 1 for middle, 2 for right.
            # Default is 0 (left).

            # Click the button
            self.client.mouse.click(button)

            # Ensure events are sent
            await self.client.drain()

            logger.info(f"Clicked at ({x},{y}) with button {button}")
        except Exception as e:
            logger.error(f"VNC click failed: {e}")
            raise

    async def press_keys(self, keys: list[str]):
        if not self.is_connected or not self.client:
            raise ConnectionError("Not connected to VNC server.")
        try:
            translated_keys = []
            for key in keys:
                match key.lower():
                    case "enter":
                        translated_keys.append("Return")
                    case "control":
                        translated_keys.append("Ctrl")
                    case _:
                        translated_keys.append(key.capitalize())
            # Type the text
            self.client.keyboard.press(*translated_keys)

            # Ensure keystrokes are sent
            await self.client.drain()

            logger.info(f"Pressed keys: {' + '.join(keys)}")
        except Exception as e:
            logger.error(f"VNC press keys failed: {e}")
            raise

    async def type_string(self, text: str):
        if not self.is_connected or not self.client:
            raise ConnectionError("Not connected to VNC server.")
        try:
            for piece in text.split("\n"):
                # Type the text
                self.client.keyboard.write(piece)

                # Ensure keystrokes are sent
                await self.client.drain()

                await self.press_keys(["Return"])  # This sends a key press for "Return"

            logger.info(f"Typed: {text}")  # Log after loop if successful
        except Exception as e:
            logger.error(f"VNC type failed: {e}")
            raise
