import asyncio
import base64
from contextvars import ContextVar
import io
from typing import Optional
from contextlib import AsyncExitStack

from PIL import Image
from planar.logging import get_logger
import asyncvnc

logger = get_logger(__name__)


class VNCManager:
    def __init__(self):
        self.client: Optional[asyncvnc.Client] = None
        self.is_connected = False
        self.host = None
        self.port = None
        self.last_screenshot_base64 = "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs="  # Transparent pixel
        self.screenshot_interval = 1
        self._update_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._connection_task: Optional[asyncio.Task] = None
        self._exit_stack: Optional[AsyncExitStack] = None

    async def connect(self, host: str, port: int, password: str = "123456"):
        if self.is_connected:
            raise ConnectionError("Already connected. Disconnect first.")

        try:
            logger.info(f"Attempting to connect to VNC server: {host}:{port}")

            # Create exit stack to manage the connection context
            self._exit_stack = AsyncExitStack()

            # Connect using the context manager
            self.client = await self._exit_stack.enter_async_context(
                asyncvnc.connect(host, port, password=password)
            )

            self.is_connected = True
            self.host = host
            self.port = port

            logger.info(f"Successfully connected to VNC: {host}:{port}")
            logger.info(f"Server info: {self.client}")

            # Start the periodic screenshot updater
            self._stop_event.clear()
            self._update_task = asyncio.create_task(self._periodic_screenshot_updater())

            return True

        except Exception as e:
            # Clean up on error
            if self._exit_stack:
                await self._exit_stack.aclose()
                self._exit_stack = None
            self.client = None
            self.is_connected = False
            logger.error(f"VNC Connection failed: {e}")
            raise ConnectionError(f"Failed to connect to {host}:{port}: {e}")

    async def disconnect(self):
        if not self.is_connected:
            logger.warning("Not connected, nothing to disconnect.")
            return False

        try:
            # Stop the updater task
            if self._update_task:
                self._stop_event.set()
                self._update_task.cancel()
                try:
                    await self._update_task
                except asyncio.CancelledError:
                    pass

            # Close the connection context
            if self._exit_stack:
                await self._exit_stack.aclose()

            logger.info("Disconnected from VNC server.")
        except Exception as e:
            logger.error(f"Error during VNC disconnect: {e}")
        finally:
            self._exit_stack = None
            self.client = None
            self.is_connected = False
            self.host = None
            self.port = None
            self.last_screenshot_base64 = (
                "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs="
            )

        return True

    async def capture_screen_pil(self):
        if not self.is_connected or not self.client:
            raise ConnectionError("Not connected to VNC server.")
        try:
            # Get screenshot as numpy array (RGBA format)
            pixels = await self.client.screenshot()

            # Get dimensions from the video buffer

            # Convert numpy array to PIL Image
            # The screenshot() method returns RGBA data
            image = Image.fromarray(pixels)
            return image
        except Exception as e:
            logger.error(f"Failed to capture screen: {e}")
            raise

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
                    self.last_screenshot_base64 = (
                        "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs="
                    )

                # Wait for the interval or until stop event is set
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=self.screenshot_interval
                    )
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            logger.info("Screenshot updater task cancelled.")
        logger.info("Screenshot updater task stopped.")

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
            # Our API: 1=left, 2=middle, 3=right
            # AsyncVNC: 0=left, 1=middle, 2=right
            button_map = {1: 0, 2: 1, 3: 2}
            vnc_button = button_map.get(button, 0)

            # Click the button
            self.client.mouse.click(vnc_button)

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
            # Type the text
            self.client.keyboard.press(*keys)

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
            # Type the text
            self.client.keyboard.write(text)

            # Ensure keystrokes are sent
            await self.client.drain()

            logger.info(f"Typed: {text}")
        except Exception as e:
            logger.error(f"VNC type failed: {e}")
            raise


instance: ContextVar[VNCManager] = ContextVar("vnc_manager", default=VNCManager())
