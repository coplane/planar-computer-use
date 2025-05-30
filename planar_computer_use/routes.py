import asyncio
import os

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from planar.logging import get_logger
from pydantic import BaseModel
from .vnc_manager import VNCManager  # Changed import

# Configure logging
logger = get_logger(__name__)


router = APIRouter()
pkg_dir = os.path.dirname(os.path.abspath(__file__))


class VNCTypeRequest(BaseModel):
    text: str


index_location = os.path.join(pkg_dir, "static", "index.html")
with open(index_location, "r") as f:
    index_page = f.read()


@router.get("/", response_class=HTMLResponse)
async def get_index():
    return index_page


@router.get("/api/vnc/stream")
async def stream_vnc(
    request: Request,
    host_port: str = Query(
        "127.0.0.1:5905", description="VNC server address as host:port"
    ),
    password: str = Query(
        "123456", description="VNC server password"
    ),  # Added password
):
    async def event_generator():
        logger.info(f"Attempting to start VNC stream for {host_port}")
        try:
            async with VNCManager.connect(host_port, password) as manager:
                logger.info(f"Successfully connected to {host_port} for streaming.")
                last_screenshot_sent = None
                while True:
                    if await request.is_disconnected():
                        logger.info(
                            f"Client disconnected from SSE stream for {host_port}."
                        )
                        break

                    if manager.is_connected:
                        screenshot_data = manager.last_screenshot_base64
                        if screenshot_data != last_screenshot_sent:
                            last_screenshot_sent = screenshot_data
                            yield f"data: {screenshot_data}\n\n"
                    else:
                        # This state should ideally be handled by the VNCManager context exiting
                        logger.warning(
                            f"VNC manager for {host_port} reported not connected during stream."
                        )
                        yield "data: data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=\n\n"
                        yield f'event: status\ndata: {{"connected": false, "message": "VNC not connected to {host_port}."}}\n\n'
                        break  # Stop streaming if connection lost

                    await asyncio.sleep(
                        0.1
                    )  # Interval for checking for new screenshots
        except ConnectionError as ce:
            logger.error(
                f"ConnectionError for VNC stream {host_port}: {ce}", exc_info=True
            )
            yield f'event: error\ndata: {{"message": "VNC Connection Error for {host_port}: {str(ce)}"}}\n\n'
        except asyncio.CancelledError:
            logger.info(f"SSE stream cancelled for {host_port}.")
        except Exception as e:
            logger.error(f"Error in SSE stream for {host_port}: {e}", exc_info=True)
            yield f'event: error\ndata: {{"message": "Stream error for {host_port}: {str(e)}"}}\n\n'
        finally:
            logger.info(f"SSE stream generator for {host_port} finished.")

    return StreamingResponse(event_generator(), media_type="text/event-stream")
