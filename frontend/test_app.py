"""Tests for Streamlit frontend."""

import os
import sys
from unittest.mock import MagicMock, patch

# Mock streamlit before importing app
sys.modules["streamlit"] = MagicMock()
sys.modules["audio_recorder_streamlit"] = MagicMock()

import pytest


@pytest.fixture
def mock_session_state():
    """Mock Streamlit session state."""
    state = {}
    return state


@pytest.fixture
def mock_st(mock_session_state):
    """Mock Streamlit module."""
    st = MagicMock()
    st.session_state = mock_session_state
    return st


class TestInitSession:
    """Test session initialization."""

    def test_init_session_defaults(self, mock_st):
        """Test that session state is initialized with correct defaults."""
        with patch.dict("sys.modules", {"streamlit": mock_st}):
            # Import and run init_session logic
            from app import init_session

            mock_st.session_state = {}
            init_session()

            assert mock_st.session_state.get("session_id") is None
            assert mock_st.session_state.get("target_language") is None
            assert mock_st.session_state.get("recording") is False


class TestStartSession:
    """Test session start API calls."""

    @patch("app.requests.post")
    def test_start_session_success(self, mock_post):
        """Test successful session start."""
        mock_post.return_value.json.return_value = {"session_id": "test-123"}
        mock_post.return_value.raise_for_status = MagicMock()

        from app import start_session

        session_id = start_session("es", "Test meeting")
        assert session_id == "test-123"

    @patch("app.requests.post")
    def test_start_session_failure(self, mock_post):
        """Test failed session start."""
        mock_post.side_effect = Exception("Connection error")

        from app import start_session, init_session

        init_session()
        session_id = start_session("es", "Test meeting")
        assert session_id is None


class TestUploadChunk:
    """Test audio chunk upload."""

    @patch("app.requests.post")
    def test_upload_chunk_success(self, mock_post):
        """Test successful chunk upload."""
        mock_post.return_value.json.return_value = {
            "chunk_index": 0,
            "status": "processed",
            "segments": [],
        }
        mock_post.return_value.raise_for_status = MagicMock()

        from app import upload_chunk, init_session

        init_session()
        import app

        app.st.session_state.session_id = "test-123"

        result = upload_chunk(b"fake audio bytes", 0)
        assert result is not None
        assert result["chunk_index"] == 0


class TestFetchTranscript:
    """Test transcript fetching."""

    @patch("app.requests.get")
    def test_fetch_transcript_success(self, mock_get):
        """Test successful transcript fetch."""
        mock_get.return_value.json.return_value = {
            "session_id": "test-123",
            "segments": [
                {
                    "segment_id": "seg-1",
                    "reconstructed_ko": "안녕하세요",
                    "translated_text": "Hello",
                    "confidence": "high",
                }
            ],
        }
        mock_get.return_value.raise_for_status = MagicMock()

        from app import fetch_transcript, init_session

        init_session()
        import app

        app.st.session_state.session_id = "test-123"

        segments = fetch_transcript()
        assert len(segments) == 1
        assert segments[0]["translated_text"] == "Hello"


class TestGenerateSummary:
    """Test summary generation."""

    @patch("app.requests.post")
    def test_generate_summary_success(self, mock_post):
        """Test successful summary generation."""
        mock_post.return_value.json.return_value = {
            "status": "generated",
            "download_url": "/api/session/test-123/summary.md",
        }
        mock_post.return_value.raise_for_status = MagicMock()

        from app import generate_summary, init_session

        init_session()
        import app

        app.st.session_state.session_id = "test-123"

        url = generate_summary()
        assert url == "/api/session/test-123/summary.md"
