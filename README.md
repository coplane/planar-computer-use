### Requirements

- A VM or Machine running a VNC server (e.g., TigerVNC). VNC server details (host, port, password) are configured when connecting via the UI or when running workflows.
- `OPENAI_API_KEY` environment variable set with your OpenAI API key.
- `HF_TOKEN` environment variable set with a Hugging Face token. This is used for the grounding model inference.
- (Optional) `OSATLAS_ENDPOINT_OVERRIDE` environment variable to specify a custom OS-ATLAS endpoint. If not set, it defaults to the public Hugging Face Space `maxiw/OS-ATLAS` or a pre-configured local URL if you've modified the source. The OS-ATLAS model can also be run locally (see code: https://huggingface.co/spaces/maxiw/OS-ATLAS/tree/main) using an NVIDIA GPU with sufficient VRAM.

### How to run

- Start the server: `uv run planar dev`
- **VNC Viewer**: Open http://localhost:8000 in your browser.
    - Enter your VNC server details (e.g., `127.0.0.1:5901`) and password (if any, defaults are often used if not specified in UI).
    - Click "Start Stream" to connect and view the VNC session.
- **Workflows**: Open your Planar development environment (e.g., https://staging.app.coplane.dev/local-development/dev-planar-app/workflows/) to run workflows like `perform_computer_task` or `highlight_ui_element`.
    - These workflows will prompt for VNC server details (host:port and password) when executed.
