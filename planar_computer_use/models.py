from planar.files.models import PlanarFile
from pydantic import BaseModel


class ScreenshotWithPrompt(BaseModel):
    file: PlanarFile
    prompt: str
