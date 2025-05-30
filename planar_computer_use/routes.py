import asyncio
import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from planar.logging import get_logger
from pydantic import BaseModel
from .vnc_manager import instance as vnc_manager

# Configure logging
logger = get_logger(__name__)


router = APIRouter()
pkg_dir = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(pkg_dir, "templates"))


# --- Pydantic Models for Request Bodies ---
class VNCConnectRequest(BaseModel):
    host: str = "10.0.204.205"
    port: int = 5901
    password: str = "123456"


class VNCClickRequest(BaseModel):
    x: int
    y: int
    button: int = 1


class VNCTypeRequest(BaseModel):
    text: str


# --- API Endpoints ---
@router.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@router.post("/api/vnc/connect")
async def connect_vnc(params: VNCConnectRequest):
    try:
        await vnc_manager.get().connect(params.host, params.port, params.password)
        return {"message": f"Connected to VNC server {params.host}:{params.port}"}
    except ConnectionError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during connect: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.post("/api/vnc/disconnect")
async def disconnect_vnc():
    if not vnc_manager.get().is_connected:
        return {"message": "Not currently connected."}
    try:
        await vnc_manager.get().disconnect()
        return {"message": "Disconnected from VNC server."}
    except Exception as e:
        logger.error(f"Error during disconnect: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error disconnecting: {str(e)}")


@router.get("/api/vnc/status")
async def vnc_status():
    manager = vnc_manager.get()
    return {
        "connected": manager.is_connected,
        "host": manager.host,
        "port": manager.port,
        "last_screenshot_available": manager.last_screenshot_base64
        != "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=",
    }


@router.post("/api/vnc/click")
async def click_vnc(params: VNCClickRequest):
    manager = vnc_manager.get()
    if not manager.is_connected:
        raise HTTPException(status_code=400, detail="Not connected to VNC server.")
    try:
        await manager.click(params.x, params.y, params.button)
        return {"message": f"Clicked at ({params.x},{params.y})"}
    except ConnectionError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error during click: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error performing click: {str(e)}")


@router.post("/api/vnc/type")
async def type_vnc(params: VNCTypeRequest):
    manager = vnc_manager.get()
    if not manager.is_connected:
        raise HTTPException(status_code=400, detail="Not connected to VNC server.")
    try:
        await manager.type_string(params.text)
        return {"message": f"Typed: {params.text}"}
    except ConnectionError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error during type: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error typing: {str(e)}")


@router.get("/api/vnc/screenshot")
async def get_screenshot():
    manager = vnc_manager.get()
    if not manager.is_connected:
        raise HTTPException(
            status_code=400,
            detail="Not connected to VNC server to take a fresh screenshot.",
        )
    try:
        img_base64 = await manager.capture_screen_base64()
        if img_base64 == "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=":
            raise HTTPException(status_code=500, detail="Failed to capture screenshot.")
        return {"screenshot_base64": img_base64}
    except ConnectionError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error during get_screenshot: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error getting screenshot: {str(e)}"
        )


@router.get("/api/vnc/stream")
async def stream_vnc(request: Request):
    manager = vnc_manager.get()

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
