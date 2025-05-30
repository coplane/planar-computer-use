from planar.logging import get_logger
from planar import PlanarApp

from planar_computer_use.routes import router
from planar_computer_use.workflows import perform_computer_task, highlight_ui_element

# Configure logging
logger = get_logger(__name__)


app = (
    PlanarApp(
        title="Planar Computer Use",
        description="Workflows for automating computer use with planar",
    )
    .register_router(router=router, prefix="")
    .register_workflow(perform_computer_task)
    .register_workflow(highlight_ui_element)
)
