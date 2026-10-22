"""CPU-only integration coverage: real ffmpeg, owned assets, no Comfy calls."""
import shutil
import subprocess
from pathlib import Path

import pytest

from app.config import Settings
from app.services.assets import probe_aligned_video

TARGET = {"width": 96, "height": 160, "length": 22, "fit": "pad", "start_seconds": 0}


@pytest.fixture
def tools():
    probe = Settings().resolve_ffprobe()
    ffmpeg = shutil.which("ffmpeg") or (str(Path(probe).with_name("ffmpeg.exe")) if probe else None)
    assert probe and ffmpeg, "Real ffmpeg/ffprobe required for normalization tests"
    return ffmpeg, probe


@pytest.fixture
def video(client, tmp_path, tools):
    path = tmp_path / "source.mp4"
    subprocess.run([tools[0], "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=160x96:rate=30:duration=2", "-c:v", "libx264", "-threads", "1", "-y", str(path)], check=True, timeout=30)
    with path.open("rb") as stream:
        asset = client.post("/api/assets", files={"file": ("source.mp4", stream, "video/mp4")}).json()
    return asset, path.read_bytes()


def test_reprepare_uses_persistent_original_after_reopen(client, app, video):
    from app.db import Database
    source, _ = video
    first = client.post(f"/api/assets/{source['id']}/prepare-guide", json=TARGET).json()
    guide = first['asset']
    assert guide['guide_provenance']['source_asset_id'] == source['id']
    reopened = Database(app.state.db.path)
    assert reopened.get_guide_provenance(guide['id'])['source_duration_seconds'] == pytest.approx(2)
    reopened.close()
    listed = next(a for a in client.get('/api/assets').json() if a['id'] == guide['id'])
    assert listed['guide_provenance'] == guide['guide_provenance']
    result = client.post(f"/api/assets/{guide['id']}/prepare-guide", json={**TARGET, 'length': 39})
    assert result.status_code == 201, result.text
    assert result.json()['verified']['frame_count'] == 39
    assert result.json()['asset']['guide_provenance']['source_asset_id'] == source['id']


def test_deleted_original_never_falls_back_to_derived_video(client, app, video):
    source, _ = video
    guide = client.post(f"/api/assets/{source['id']}/prepare-guide", json=TARGET).json()['asset']
    app.state.assets.delete(source['id'])
    result = client.post(f"/api/assets/{guide['id']}/prepare-guide", json=TARGET)
    assert result.status_code == 404
    assert result.json()['detail']['code'] == 'asset_not_found'
    assert app.state.db.get_guide_provenance(guide['id'])['source_asset_id'] == source['id']
    assert len(app.state.assets.list_assets()) == 1


def test_chain_is_flattened_and_cycle_is_rejected(client, app, video):
    source, _ = video
    first = client.post(f"/api/assets/{source['id']}/prepare-guide", json=TARGET).json()['asset']
    second = client.post(f"/api/assets/{source['id']}/prepare-guide", json=TARGET).json()['asset']
    with app.state.db._cursor() as c:
        c.execute('UPDATE guide_provenance SET source_asset_id=? WHERE asset_id=?', (first['id'], second['id']))
    result = client.post(f"/api/assets/{second['id']}/prepare-guide", json={**TARGET, 'length': 39})
    assert result.status_code == 201, result.text
    assert result.json()['asset']['guide_provenance']['source_asset_id'] == source['id']
    with app.state.db._cursor() as c:
        c.execute('UPDATE guide_provenance SET source_asset_id=? WHERE asset_id=?', (second['id'], first['id']))
    rejected = client.post(f"/api/assets/{second['id']}/prepare-guide", json=TARGET)
    assert rejected.status_code == 400
    assert rejected.json()['detail']['code'] == 'guide_invalid_provenance'


def test_prepare_creates_verified_new_asset(client, app, video, tools, comfy):
    source, original = video
    response = client.post(f"/api/assets/{source['id']}/prepare-guide", json=TARGET)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["source_asset_id"] == source["id"]
    assert body["asset"]["id"] != source["id"]
    assert body["verified"] == {"width": 96, "height": 160, "frame_count": 22, "fps": 24.0}
    assert body["asset"]["has_audio"] is False
    record = app.state.db.get_asset(body["asset"]["id"])
    output = app.state.assets.resolve_stored(record["stored_name"])
    assert probe_aligned_video(tools[1], output) == body["verified"]
    assert client.get(source["url"]).content == original
    assert comfy.submitted == []
    subprocess.run([tools[0], "-v", "error", "-xerror", "-i", str(output), "-f", "null", "-"], check=True, timeout=30)


@pytest.mark.parametrize("patch", [
    {"width": 95}, {"width": 0}, {"width": 1568}, {"height": 159},
    {"length": 23}, {"length": 3601}, {"length": 0}, {"length": True},
    {"start_seconds": -1}, {"start_seconds": 3601}, {"start_seconds": "nan"},
    {"fit": "pad; calc.exe"}, {"path": "C:/private.mp4"}, {"fps": 30},
])
def test_rejects_invalid_contract_before_processing(client, patch):
    response = client.post("/api/assets/not-a-path/prepare-guide", json={**TARGET, **patch})
    assert response.status_code == 422


def test_source_shortage_is_actionable_and_no_asset_is_created(client, app, video):
    source, _ = video
    before = app.state.assets.list_assets()
    response = client.post(f"/api/assets/{source['id']}/prepare-guide", json={**TARGET, "length": 124})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "guide_source_too_short"
    assert "Reduce la duración" in response.json()["detail"]["message"]
    assert "vídeo original desde Library" in response.json()["detail"]["message"]
    assert app.state.assets.list_assets() == before
    assert len(list(app.state.assets.uploads_dir.iterdir())) == 1


def test_missing_and_nonvideo_assets(client, png_bytes):
    assert client.post("/api/assets/unknown/prepare-guide", json=TARGET).status_code == 404
    image = client.post("/api/assets", files={"file": ("id.png", png_bytes, "image/png")}).json()
    result = client.post(f"/api/assets/{image['id']}/prepare-guide", json=TARGET)
    assert result.status_code == 400
    assert result.json()["detail"]["code"] == "guide_requires_video"


def test_busy_rejects_without_spawning_or_creating_files(client, app, video):
    from app.services.prepare_guide import _GATE
    source, _ = video
    assert _GATE.acquire(blocking=False)
    try:
        result = client.post(f"/api/assets/{source['id']}/prepare-guide", json=TARGET)
        assert result.status_code == 409
        assert result.json()["detail"]["code"] == "guide_busy"
        assert len(list(app.state.assets.uploads_dir.iterdir())) == 1
    finally:
        _GATE.release()


def test_timeout_releases_gate_and_cleans_partial_file(client, app, video, monkeypatch):
    import app.services.prepare_guide as module
    source, _ = video
    real_run = module.subprocess.run
    def timeout(argv, **kwargs):
        assert kwargs["shell"] is False
        assert kwargs["timeout"] <= 180
        if "libx264" in argv:
            assert argv[argv.index("-hwaccel") + 1] == "none"
            assert argv[argv.index("-protocol_whitelist") + 1] == "file,pipe"
            assert int(argv[argv.index("-fs") + 1]) == app.state.assets.max_bytes[next(k for k in app.state.assets.max_bytes if k.value == 'video')]
            assert "-stream_loop" not in argv and "tpad" not in ' '.join(argv)
            Path(argv[-1]).write_bytes(b"partial")
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
        return real_run(argv, **kwargs)
    monkeypatch.setattr(module.subprocess, "run", timeout)
    result = client.post(f"/api/assets/{source['id']}/prepare-guide", json=TARGET)
    assert result.status_code == 504
    assert len(list(app.state.assets.uploads_dir.iterdir())) == 1
    assert module._GATE.acquire(blocking=False)
    module._GATE.release()


@pytest.mark.parametrize("fit", ["pad", "crop"])
def test_geometry_seek_and_speed_are_verified_with_real_decode(client, app, video, tools, fit):
    source, _ = video
    result = client.post(f"/api/assets/{source['id']}/prepare-guide", json={**TARGET, "fit": fit, "start_seconds": 0.5})
    assert result.status_code == 201, result.text
    asset = result.json()["asset"]
    output = app.state.assets.resolve_stored(app.state.db.get_asset(asset["id"])["stored_name"])
    import json
    payload = json.loads(subprocess.run([tools[1], "-v", "error", "-show_streams", "-show_frames", "-of", "json", str(output)], check=True, capture_output=True, timeout=30).stdout)
    stream = payload["streams"][0]
    assert stream["avg_frame_rate"] == stream["r_frame_rate"] == "24/1"
    assert stream["sample_aspect_ratio"] == "1:1"
    timestamps = [float(frame["best_effort_timestamp_time"]) for frame in payload["frames"]]
    assert len(timestamps) == 22
    assert timestamps[-1] == pytest.approx(21 / 24, abs=0.000001)
    assert float(stream["duration"]) == pytest.approx(22 / 24, abs=0.000001)
    pixels = subprocess.run([tools[0], "-v", "error", "-i", str(output), "-frames:v", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"], capture_output=True, check=True, timeout=30).stdout
    # Landscape source fitted into portrait: top-left is black only for pad.
    if fit == "pad":
        assert max(pixels[:3]) < 8
    else:
        assert max(pixels[:3]) > 20


@pytest.mark.parametrize("variant", ["vfr", "rotated_sar", "long_audio_short_video"])
def test_real_unaligned_sources(client, app, tmp_path, tools, variant):
    import json
    base = tmp_path / "base.mp4"
    command = [tools[0], "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=160x96:rate=30:duration=2"]
    if variant == "vfr":
        command += ["-vf", "select='not(mod(n,3))+not(mod(n,5))'", "-fps_mode", "vfr"]
    if variant == "rotated_sar":
        command += ["-vf", "setsar=2"]
    if variant == "long_audio_short_video":
        command += ["-f", "lavfi", "-i", "sine=duration=4", "-c:a", "aac"]
    command += ["-c:v", "libx264", "-threads", "1", "-y", str(base)]
    subprocess.run(command, check=True, timeout=30)
    if variant == "rotated_sar":
        rotated = tmp_path / "rotated.mp4"
        subprocess.run([tools[0], "-v", "error", "-display_rotation:v:0", "90", "-i", str(base), "-c", "copy", str(rotated)], check=True, timeout=30)
        base = rotated
    with base.open("rb") as handle:
        source = client.post("/api/assets", files={"file": (base.name, handle, "video/mp4")}).json()
    target = {**TARGET, "length": 73} if variant == "long_audio_short_video" else TARGET
    result = client.post(f"/api/assets/{source['id']}/prepare-guide", json=target)
    if variant == "long_audio_short_video":
        assert result.status_code == 400
        assert result.json()["detail"]["code"] == "guide_source_too_short"
        return
    assert result.status_code == 201, result.text
    output = app.state.assets.resolve_stored(app.state.db.get_asset(result.json()["asset"]["id"])["stored_name"])
    details = json.loads(subprocess.run([tools[1], "-v", "error", "-show_streams", "-of", "json", str(output)], capture_output=True, check=True, timeout=30).stdout)["streams"][0]
    assert details["r_frame_rate"] == details["avg_frame_rate"] == "24/1"
    assert details["sample_aspect_ratio"] == "1:1"
    assert all(not side.get("rotation", 0) for side in details.get("side_data_list", []))
    if variant == "rotated_sar":
        # Autorotation + SAR=2 yields a tall display with bands at the sides.
        pixels = subprocess.run([tools[0], "-v", "error", "-i", str(output), "-frames:v", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"], capture_output=True, check=True, timeout=30).stdout
        assert max(pixels[80 * 96 * 3:80 * 96 * 3 + 3]) < 8


def test_database_owned_name_is_resolved_not_derived_from_id(client, app, video):
    source, _ = video
    assert source['stored_name'] != source['id'] + '.mp4'
    with app.state.db._cursor() as cursor:
        cursor.execute('UPDATE assets SET stored_name=? WHERE id=?', ('../private.mp4', source['id']))
    result = client.post(f"/api/assets/{source['id']}/prepare-guide", json=TARGET)
    assert result.status_code == 400
    assert result.json()['detail']['code'] == 'unsafe_name'


def test_missing_tools_is_actionable(client, app, video):
    source, _ = video
    app.state.assets.ffprobe_path = None
    result = client.post(f"/api/assets/{source['id']}/prepare-guide", json=TARGET)
    assert result.status_code == 503
    assert result.json()['detail']['code'] == 'guide_tools_unavailable'


def test_failed_verification_never_registers_an_asset(client, app, video, monkeypatch):
    import app.services.prepare_guide as module
    source, _ = video
    monkeypatch.setattr(module, 'probe_aligned_video', lambda *args: {'width': 96, 'height': 160, 'fps': 24, 'frame_count': 21})
    result = client.post(f"/api/assets/{source['id']}/prepare-guide", json=TARGET)
    assert result.status_code == 400
    assert result.json()['detail']['code'] == 'guide_verification_failed'
    assert len(app.state.assets.list_assets()) == 1
    assert len(list(app.state.assets.uploads_dir.iterdir())) == 1


def test_output_validation_reuses_the_aligned_guide_contract(client, app, video):
    from app.schemas import GenerationRequest, RefKind
    from app.workflow.validation import ResolvedAsset, validate_request
    source, _ = video
    result = client.post(f"/api/assets/{source['id']}/prepare-guide", json=TARGET).json()
    guide = result['asset']
    req = GenerationRequest.model_validate({
        'mode': 'ref2va', 'prompt': 'Preserve the motion and scene of the guide.',
        'width': 96, 'height': 160, 'length': 22, 'continuity': {'auto_split': False},
        'references': [{'asset_id': guide['id'], 'kind': 'video', 'role': 'aligned_guide', 'include_audio': False}],
    })
    resolved = {guide['id']: ResolvedAsset(id=guide['id'], kind=RefKind.video, comfy_name='validation-only.mp4', duration_seconds=22/24, **result['verified'])}
    _, issues = validate_request(req, resolved, aligned_guides_available=True)
    assert not [issue for issue in issues if issue.severity.value == 'error']
