import os
import pytest
from unittest.mock import patch, MagicMock

# Import the module under test
import backend.tts.engine as tts_engine


def test_synth_to_wav_raises_on_empty_text():
    with pytest.raises(ValueError):
        tts_engine.synth_to_wav("")
    with pytest.raises(ValueError):
        tts_engine.synth_to_wav("   ")


def test_synth_to_wav_success(tmp_path):
    # Mock engine and paths
    fake_path = tmp_path / "out.wav"

    with patch("backend.tts.engine.temp_unique_path", return_value=str(fake_path)), \
         patch("pyttsx3.init") as mock_init:

        mock_engine = MagicMock()
        mock_init.return_value = mock_engine

        # Simulate engine writing a file
        def _write_file(text, path):
            with open(path, "wb") as f:
                f.write(b"FAKE_WAV_DATA")

        mock_engine.save_to_file.side_effect = _write_file

        out = tts_engine.synth_to_wav("hello")
        assert out == str(fake_path)
        assert os.path.exists(out)
        assert os.path.getsize(out) > 0


def test_engine_singleton():
    # Reset for test isolation
    tts_engine._engine = None

    with patch("pyttsx3.init") as mock_init:
        mock_engine = MagicMock()
        mock_init.return_value = mock_engine

        e1 = tts_engine._get_engine()
        e2 = tts_engine._get_engine()

        assert e1 is e2
        mock_init.assert_called_once()
