import json
import subprocess
import pytest
from tecs_h.claude_io.client import claude_call, extract_json, ClaudeCliError


class TestExtractJson:
    def test_pure_json(self):
        raw = '{"beta0": 1, "beta1": 3}'
        assert extract_json(raw) == {"beta0": 1, "beta1": 3}

    def test_json_in_code_block(self):
        raw = 'Here is the result:\n```json\n{"beta0": 1}\n```\nDone.'
        assert extract_json(raw) == {"beta0": 1}

    def test_json_with_surrounding_text(self):
        raw = 'Sure! {"beta0": 1, "beta1": 2} hope that helps'
        assert extract_json(raw) == {"beta0": 1, "beta1": 2}

    def test_no_json_raises(self):
        with pytest.raises(ValueError, match="No JSON found"):
            extract_json("no json here at all")

    def test_nested_json(self):
        raw = '{"a": {"b": 1}, "c": [1, 2]}'
        assert extract_json(raw) == {"a": {"b": 1}, "c": [1, 2]}


class TestClaudeCall:
    def test_successful_call(self, mocker):
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout='{"beta0": 1}', stderr=""
        )
        result = claude_call("test prompt")
        assert result == {"beta0": 1}
        call_args = mock_run.call_args
        assert "claude" in call_args[0][0]

    def test_nonzero_exit_raises(self, mocker):
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1,
            stdout="", stderr="error"
        )
        with pytest.raises(ClaudeCliError):
            claude_call("test prompt")

    def test_timeout_raises(self, mocker):
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=120)
        with pytest.raises(TimeoutError):
            claude_call("test prompt")

    def test_retry_on_parse_failure(self, mocker):
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout="not json", stderr=""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout='{"ok": true}', stderr=""),
        ]
        result = claude_call("test prompt")
        assert result == {"ok": True}
        assert mock_run.call_count == 2

    def test_max_retries_exceeded(self, mocker):
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="still not json", stderr=""
        )
        with pytest.raises(ValueError, match="No JSON found"):
            claude_call("test prompt")
        assert mock_run.call_count == 3  # 1 original + 2 retries

    def test_json_suffix_appended(self, mocker):
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"ok": true}', stderr=""
        )
        claude_call("my prompt")
        prompt_sent = mock_run.call_args[0][0]
        assert "-p" in prompt_sent
