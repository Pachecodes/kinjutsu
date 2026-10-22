import subprocess
from pathlib import Path
from unittest.mock import patch
from app.services.assets import probe_aligned_video, probe_media
from app.services.prepare_guide import _run


def test_aligned_validation_hides_ffprobe_console():
    with patch('subprocess.run', return_value=subprocess.CompletedProcess([],0,b'{"streams":[]}')) as run:
        probe_aligned_video('ffprobe',Path('dummy.mp4'))
        assert run.call_args.kwargs.get('creationflags',0)==getattr(subprocess,'CREATE_NO_WINDOW',0)


def test_metadata_probe_hides_ffprobe_console():
    with patch('subprocess.run', return_value=subprocess.CompletedProcess([],0,b'{}')) as run:
        probe_media('ffprobe',Path('dummy.mp4'))
        assert run.call_args.kwargs.get('creationflags',0)==getattr(subprocess,'CREATE_NO_WINDOW',0)


def test_guide_conversion_hides_ffmpeg_console():
    with patch('subprocess.run', return_value=subprocess.CompletedProcess([],0,b'')) as run:
        _run(['ffmpeg','-version'])
        assert run.call_args.kwargs.get('creationflags',0)==getattr(subprocess,'CREATE_NO_WINDOW',0)
