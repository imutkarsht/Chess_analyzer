"""Tests for shared HTTP status handling and avatar validation."""

import pytest
import requests

from src.backend.api.base_api import MAX_AVATAR_BYTES, BaseChessAPI


def _response(mocker, status_code=200, ok=True, json_value=None, json_error=False):
    response = mocker.Mock()
    response.status_code = status_code
    response.ok = ok
    if json_error:
        response.json.side_effect = ValueError("no json")
    else:
        response.json.return_value = json_value
    return response


class TestRequestJsonStatuses:
    def test_success_returns_payload(self, mocker):
        response = _response(mocker, json_value={"username": "alice"})
        mocker.patch("requests.get", return_value=response)

        assert BaseChessAPI._request_json("https://example.com") == (
            {"username": "alice"},
            "ok",
        )

    @pytest.mark.parametrize(
        ("status_code", "expected"),
        [
            (404, "not_found"),
            (429, "rate_limited"),
            (401, "unauthorized"),
            (403, "unauthorized"),
            (500, "error"),
        ],
    )
    def test_http_statuses_are_classified(self, mocker, status_code, expected):
        response = _response(mocker, status_code=status_code, ok=status_code < 400)
        mocker.patch("requests.get", return_value=response)

        assert BaseChessAPI._request_json("https://example.com") == (None, expected)

    @pytest.mark.parametrize(
        ("exception", "expected"),
        [
            (requests.exceptions.Timeout(), "offline"),
            (requests.exceptions.ConnectionError(), "offline"),
            (requests.exceptions.RequestException(), "error"),
        ],
    )
    def test_transport_failures_are_classified(self, mocker, exception, expected):
        mocker.patch("requests.get", side_effect=exception)

        assert BaseChessAPI._request_json("https://example.com") == (None, expected)

    def test_invalid_json_is_an_error(self, mocker):
        response = _response(mocker, json_error=True)
        mocker.patch("requests.get", return_value=response)

        assert BaseChessAPI._request_json("https://example.com") == (None, "error")

    def test_default_headers_and_params_are_sent(self, mocker):
        response = _response(mocker, json_value={})
        get = mocker.patch("requests.get", return_value=response)

        BaseChessAPI._request_json(
            "https://example.com", headers={"X-Test": "1"}, params={"q": "x"}, timeout=7
        )

        kwargs = get.call_args.kwargs
        assert kwargs["headers"]["X-Test"] == "1"
        assert "User-Agent" in kwargs["headers"]
        assert kwargs["params"] == {"q": "x"}
        assert kwargs["timeout"] == 7


class TestMakeRequest:
    def test_success_raises_for_status_and_returns_response(self, mocker):
        response = _response(mocker)
        get = mocker.patch("requests.get", return_value=response)

        assert BaseChessAPI._make_request("https://example.com") is response

        response.raise_for_status.assert_called_once()
        assert "User-Agent" in get.call_args.kwargs["headers"]

    @pytest.mark.parametrize(
        "exception",
        [
            requests.exceptions.Timeout(),
            requests.exceptions.ConnectionError(),
            requests.exceptions.RequestException(),
        ],
    )
    def test_transport_failure_returns_none(self, mocker, exception):
        mocker.patch("requests.get", side_effect=exception)

        assert BaseChessAPI._make_request("https://example.com") is None


class TestFetchAvatar:
    def _stream_response(
        self, mocker, chunks, status=200, content_type="image/png"
    ):
        response = mocker.MagicMock()
        response.status_code = status
        response.headers = {"Content-Type": content_type}
        response.iter_content.return_value = chunks
        response.__enter__.return_value = response
        mocker.patch("requests.get", return_value=response)
        return response

    def test_missing_url_is_a_noop(self, mocker):
        get = mocker.patch("requests.get")

        assert BaseChessAPI.fetch_avatar(None) == (None, None)
        assert BaseChessAPI.fetch_avatar("") == (None, None)
        get.assert_not_called()

    def test_image_bytes_and_mime_are_returned(self, mocker):
        self._stream_response(
            mocker, [b"abc", b"def"], content_type="image/jpeg; charset=binary"
        )

        assert BaseChessAPI.fetch_avatar("https://example.com/a.jpg") == (
            b"abcdef",
            "image/jpeg",
        )

    @pytest.mark.parametrize(
        ("status", "content_type", "chunks"),
        [
            (404, "image/png", [b"data"]),
            (200, "text/html", [b"data"]),
            (200, "image/png", [b""]),
        ],
    )
    def test_invalid_responses_are_rejected(
        self, mocker, status, content_type, chunks
    ):
        self._stream_response(mocker, chunks, status=status, content_type=content_type)

        assert BaseChessAPI.fetch_avatar("https://example.com/a.png") == (None, None)

    def test_oversized_avatar_is_rejected(self, mocker):
        self._stream_response(mocker, [b"x" * MAX_AVATAR_BYTES, b"extra"])

        assert BaseChessAPI.fetch_avatar("https://example.com/big.png") == (None, None)

    def test_request_error_is_non_fatal(self, mocker):
        mocker.patch("requests.get", side_effect=requests.exceptions.Timeout())

        assert BaseChessAPI.fetch_avatar("https://example.com/a.png") == (None, None)


def test_safe_json_handles_invalid_payload(mocker):
    response = _response(mocker, json_error=True)
    assert BaseChessAPI._safe_json(response) is None

    response = _response(mocker, json_value={"a": 1})
    assert BaseChessAPI._safe_json(response) == {"a": 1}
