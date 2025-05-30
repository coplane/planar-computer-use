### Requirements

- A VM or Machine running a VNC server, ideally TigerVNC which was used during the tests.
  The Ip address and port can be specified in planar_computer_use/vnc_manager.py
- OPENAI_API_KEY env var set with Open AI env var
- HF_TOKEN env var with a huggingface token for connecting with https://huggingface.co/spaces/maxiw/OS-ATLAS for grounding model inference. Alternatively, the exact same endpoint can be run locally (code here: https://huggingface.co/spaces/maxiw/OS-ATLAS/tree/main) using an NVidia GPU with enough VRAM.

### How to run

- `uv run planar dev` to start the server.
- Open http://localhost:8000 for a basic VNC viewer.
- Open https://staging.app.coplane.dev/local-development/dev-planar-app/workflows/ to run one of the workflows.
