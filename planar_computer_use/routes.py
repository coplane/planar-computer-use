import asyncio
import os

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from planar.logging import get_logger
from pydantic import BaseModel
from .vnc_manager import instance as vnc_manager

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
async def stream_vnc(request: Request):
    manager = vnc_manager.get()
    if not manager.is_connected:
        await manager.connect()

    async def event_generator():
        try:
            last_screenshot_sent = None
            while True:
                if await request.is_disconnected():
                    logger.info("Client disconnected from SSE stream.")
                    break

                if manager.is_connected:
                    screenshot_data = manager.last_screenshot_base64
                    if screenshot_data != last_screenshot_sent:
                        last_screenshot_sent = screenshot_data
                        yield f"data: {screenshot_data}\n\n"
                else:
                    yield "data: data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=\n\n"
                    yield 'event: status\ndata: {"connected": false, "message": "VNC not connected."}\n\n'

                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logger.info("SSE stream cancelled.")
        except Exception as e:
            logger.error(f"Error in SSE stream: {e}", exc_info=True)
            yield f'event: error\ndata: {{"message": "Stream error: {str(e)}"}}\n\n'
        finally:
            logger.info("SSE stream generator finished.")

    return StreamingResponse(event_generator(), media_type="text/event-stream")
