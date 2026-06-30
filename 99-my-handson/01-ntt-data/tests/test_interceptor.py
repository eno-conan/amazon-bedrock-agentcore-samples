"""Gateway Interceptor Lambda の単体テスト。"""

import pytest

from ntt_data_agent.interceptor.handler import lambda_handler


def _call(event: dict) -> dict:
    return lambda_handler(event, object())


# ---- REQUEST interceptor ----


def test_request_passthrough() -> None:
    body = {"jsonrpc": "2.0", "method": "tools/call", "id": 1, "params": {}}
    event = {"mcp": {"gatewayRequest": {"body": body}}}
    result = _call(event)
    assert result["interceptorOutputVersion"] == "1.0"
    assert result["mcp"]["transformedGatewayRequest"]["body"] == body


def test_request_empty_body() -> None:
    event = {"mcp": {"gatewayRequest": {}}}
    result = _call(event)
    assert result["mcp"]["transformedGatewayRequest"]["body"] == {}


# ---- RESPONSE interceptor (non-streaming) ----


def test_response_non_streaming_with_status_and_headers() -> None:
    body = {"jsonrpc": "2.0", "result": {"content": []}, "id": 1}
    event = {
        "mcp": {
            "gatewayRequest": {"body": {"method": "tools/call"}},
            "gatewayResponse": {"body": body, "statusCode": 200, "headers": {"x-foo": "bar"}},
        }
    }
    result = _call(event)
    resp = result["mcp"]["transformedGatewayResponse"]
    assert resp["body"] == body
    assert resp["statusCode"] == 200
    assert resp["headers"] == {"x-foo": "bar"}


def test_response_non_streaming_without_status() -> None:
    body = {"jsonrpc": "2.0", "result": {}, "id": 2}
    event = {
        "mcp": {
            "gatewayRequest": {},
            "gatewayResponse": {"body": body},
        }
    }
    result = _call(event)
    resp = result["mcp"]["transformedGatewayResponse"]
    assert resp["body"] == body
    assert "statusCode" not in resp


# ---- RESPONSE interceptor (streaming) ----


def test_response_streaming_first_event() -> None:
    body = {"chunk": "hello"}
    event = {
        "mcp": {
            "gatewayRequest": {},
            "gatewayResponse": {
                "body": body,
                "statusCode": 200,
                "headers": {},
                "isStreamingResponse": True,
            },
        }
    }
    result = _call(event)
    resp = result["mcp"]["transformedGatewayResponse"]
    assert resp["body"] == body
    assert resp["statusCode"] == 200


def test_response_streaming_subsequent_event() -> None:
    body = {"chunk": "world"}
    event = {
        "mcp": {
            "gatewayRequest": {},
            "gatewayResponse": {
                "body": body,
                "isStreamingResponse": True,
                # statusCode なし → subsequent event
            },
        }
    }
    result = _call(event)
    resp = result["mcp"]["transformedGatewayResponse"]
    assert resp["body"] == body
    assert "statusCode" not in resp
    assert "headers" not in resp
