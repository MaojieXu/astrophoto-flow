"""EXR outputs stay downloadable and previewable through the retained /view route."""

import io
import json
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import pytest
import torch
import websocket
from PIL import Image

from comfy_execution.graph_utils import GraphBuilder
from comfy_extras.nodes_images import _encode_image


@pytest.fixture(scope="module")
def server(args_pytest, tmp_path_factory):
    work = tmp_path_factory.mktemp("exr-previews")
    log = (work / "server.log").open("w")
    # Its own port: a server another module hasn't finished killing must not answer for this one.
    with socket.socket() as probe:
        probe.bind((args_pytest["listen"], 0))
        port = probe.getsockname()[1]
    process = subprocess.Popen([
        sys.executable, "main.py",
        "--output-directory", args_pytest["output_dir"],
        "--listen", args_pytest["listen"],
        "--port", str(port),
        "--extra-model-paths-config", "tests/execution/extra_model_paths.yaml",
        "--cpu",
    ], stdout=log, stderr=subprocess.STDOUT)
    base = f"http://{args_pytest['listen']}:{port}"
    try:
        for _ in range(120):
            if process.poll() is not None:
                pytest.fail(f"server exited with {process.returncode}:\n{(work / 'server.log').read_text()[-4000:]}")
            try:
                urllib.request.urlopen(f"{base}/system_stats", timeout=2)
                break
            except OSError:
                time.sleep(1)
        else:
            pytest.fail(f"server never answered:\n{(work / 'server.log').read_text()[-4000:]}")
        yield base
    finally:
        process.kill()
        process.wait(timeout=10)
        log.close()


def _run(base: str, prompt: dict, *, include_history: bool = True) -> tuple[dict, str]:
    """Queue a prompt and return its executed messages by node id, and its prompt id."""
    client_id = str(uuid.uuid4())
    ws = websocket.WebSocket()
    ws.settimeout(120)
    ws.connect(f"ws://{base.removeprefix('http://')}/ws?clientId={client_id}")
    request = urllib.request.Request(f"{base}/prompt", data=json.dumps({"prompt": prompt, "client_id": client_id}).encode())
    prompt_id = json.loads(urllib.request.urlopen(request).read())["prompt_id"]
    executed = {}
    while True:
        message = ws.recv()
        if not isinstance(message, str):
            continue
        message = json.loads(message)
        data = message.get("data", {})
        if data.get("prompt_id") != prompt_id:
            continue
        if message["type"] == "execution_error":
            raise AssertionError(data)
        if message["type"] == "executed":
            executed[data["node"]] = data["output"]
        if message["type"] == "executing" and data["node"] is None:
            ws.close()
            if include_history:
                # History is the retained API the UI reads, including cached reruns.
                history = json.loads(urllib.request.urlopen(f"{base}/history/{prompt_id}").read())
                for node, output in history.get(prompt_id, {}).get("outputs", {}).items():
                    executed.setdefault(node, output)
            return executed, prompt_id


def _exr_save_graph(prefix: str, batch_size: int) -> tuple[dict, str]:
    g = GraphBuilder(prefix=prefix)
    # Small frames: decode speed is the unit tests' business, not this one's.
    image = g.node("StubImage", content="WHITE", height=60, width=200, batch_size=batch_size)
    save = g.node(
        "SaveImageAdvanced",
        images=image.out(0),
        filename_prefix=f"exr_previews/{prefix}",
        format="exr",
        **{"format.bit_depth": "16-bit float", "format.input_color_space": "sRGB"},
    )
    return g.finalize(), save.id


def _fetch(base: str, filename: str, **query: str) -> bytes:
    url = f"{base}/view?{urllib.parse.urlencode({'filename': filename, 'type': 'output', **query})}"
    with urllib.request.urlopen(url) as response:
        return response.read()


@pytest.mark.execution
def test_saved_exr_frames_are_downloadable_and_previewable(server):
    base = server
    prefix = f"exr_{uuid.uuid4().hex[:8]}"
    prompt, save_id = _exr_save_graph(prefix, batch_size=3)
    executed, _ = _run(base, prompt)

    entries = executed[save_id]["images"]
    assert len(entries) == 3
    for entry in entries:
        assert entry["filename"].endswith(".exr")
        original = _fetch(base, entry["filename"], subfolder=entry.get("subfolder", ""))
        assert original[:4] == b"\x76\x2f\x31\x01", "the original is still an OpenEXR file"

        preview = Image.open(io.BytesIO(
            _fetch(base, entry["filename"], subfolder=entry.get("subfolder", ""), preview="webp")
        ))
        assert preview.format == "WEBP"
        assert preview.size == (200, 60)


@pytest.mark.execution
def test_cached_rerun_replays_executed_outputs(server):
    base = server
    prefix = f"exr_cached_{uuid.uuid4().hex[:8]}"
    prompt, save_id = _exr_save_graph(prefix, batch_size=2)

    first, _ = _run(base, prompt, include_history=False)
    second, _ = _run(base, prompt, include_history=False)

    assert save_id in second
    assert [entry["filename"] for entry in second[save_id]["images"]] == [
        entry["filename"] for entry in first[save_id]["images"]
    ]


@pytest.mark.execution
def test_load_image_accepts_exr(server):
    base = server
    prefix = f"exr_load_{uuid.uuid4().hex[:8]}"
    prompt, save_id = _exr_save_graph(prefix, batch_size=1)
    executed, _ = _run(base, prompt)
    entry = executed[save_id]["images"][0]

    input_name = f"{prefix}.exr"
    input_path = Path("input") / input_name
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_bytes(
        _fetch(base, entry["filename"], subfolder=entry.get("subfolder", ""))
    )

    try:
        g = GraphBuilder(prefix=prefix)
        load = g.node("LoadImage", image=input_name)
        preview = g.node("PreviewImage", images=load.out(0))
        executed, _ = _run(base, g.finalize())

        preview_entry = executed[preview.id]["images"][0]
        rendered = Image.open(io.BytesIO(_fetch(
            base, preview_entry["filename"],
            subfolder=preview_entry.get("subfolder", ""),
            type=preview_entry.get("type", "output"),
        )))
        assert rendered.size == (200, 60)
    finally:
        input_path.unlink(missing_ok=True)


@pytest.mark.execution
def test_gray_exr_preview_keeps_linear_brightness(server, args_pytest):
    base = server
    prefix = f"exr_gray_{uuid.uuid4().hex[:8]}"
    output_dir = Path(args_pytest["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = {}
    for channels in (1, 3):
        name = f"{prefix}_{channels}.exr"
        paths[channels] = output_dir / name
        paths[channels].write_bytes(_encode_image(
            torch.full((8, 8, channels), 0.18, dtype=torch.float32),
            "exr",
            "32-bit float",
            "linear",
        ))

    try:
        pixels = {}
        for channels, path in paths.items():
            preview = Image.open(io.BytesIO(
                _fetch(base, path.name, preview="webp")
            )).convert("RGB")
            pixels[channels] = preview.getpixel((4, 4))

        assert abs(pixels[1][0] - pixels[3][0]) <= 2
    finally:
        for path in paths.values():
            path.unlink(missing_ok=True)

