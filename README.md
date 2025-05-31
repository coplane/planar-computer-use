### Requirements

- A VM or Machine running a VNC server (e.g., TigerVNC). VNC server details (host, port, password) are configured when connecting via the UI or when running workflows.
- `OPENAI_API_KEY` environment variable set with your OpenAI API key.
- `HF_TOKEN` environment variable set with a Hugging Face token. This is used for the grounding model inference.
- (Optional) `OSATLAS_ENDPOINT_OVERRIDE` environment variable to specify a custom OS-ATLAS endpoint. If not set, it defaults to the public Hugging Face Space `maxiw/OS-ATLAS` or a pre-configured local URL if you've modified the source.
    - The OS-ATLAS model can be run locally using an NVIDIA GPU with sufficient VRAM (see original Hugging Face Space for details: https://huggingface.co/spaces/maxiw/OS-ATLAS/tree/main).
    - For Apple Silicon users, a local inference option is available in the `os_atlas_run_local` directory (see below).

### Running a Linux Desktop with VNC (using Docker or Podman)

You can use the provided `Dockerfile` to build and run a Debian-based Linux desktop environment with XFCE and TigerVNC. This is useful for testing or if you don't have a separate VNC server.

1.  **Build the Docker image:**
    ```bash
    podman build -t linux-vnc-desktop .
    ```
    (You can replace `podman` with `docker` if you prefer)

2.  **Run the Docker container:**
    ```bash
    podman run -d --rm --name linux-vnc -p 5901:5901 -e VNC_PASSWORD=123456 linux-vnc-desktop
    ```
    - This command starts the container in detached mode (`-d`), removes the container when it exits (`--rm`), names the container `linux-vnc`, maps port `5901` on your host to port `5901` in the container, and sets the VNC password to `123456`.
    - You can then connect to this VNC server at `127.0.0.1:5901` with the password `123456`.

### How to run

- Start the server: `uv run planar dev`
- **VNC Viewer**: Open http://localhost:8000 in your browser.
    - Enter your VNC server details (e.g., `127.0.0.1:5901`) and password (if any, defaults are often used if not specified in UI).
    - Click "Start Stream" to connect and view the VNC session.
- **Local OS-ATLAS Inference (for Apple Silicon)**:
    - Navigate to the `os_atlas_run_local` directory.
    - Ensure you have a Mac with Apple Silicon and sufficient VRAM (approx. 20GB).
    - Run the local Gradio app: `uv run app.py`
    - This will start a local server listening on all addresses(http://0.0.0.0:7080) that can be used as the `OSATLAS_ENDPOINT_OVERRIDE`.
- **Workflows**: Open your Planar development environment (e.g., https://staging.app.coplane.dev/local-development/dev-planar-app/workflows/) to run workflows like `perform_computer_task` or `highlight_ui_element`.
    - These workflows will prompt for VNC server details (host:port and password) when executed.
    - If using the local OS-ATLAS server, ensure `OSATLAS_ENDPOINT_OVERRIDE` is set accordingly (e.g., `http://127.0.0.1:7080`) in your environment where the Planar app is running, or modify `planar_computer_use/grounding.py` to use this endpoint.
