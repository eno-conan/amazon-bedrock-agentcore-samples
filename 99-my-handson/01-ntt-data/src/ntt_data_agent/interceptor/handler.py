"""AgentCore Gateway Interceptor Lambda。

AgentCore Gateway のドキュメントに従い、REQUEST / RESPONSE の
パススルーを行う。本番利用では REQUEST 側でユーザーコンテキスト注入や
OAuth ヘッダー変換を追加する。

参考: amazon-bedrock-agentcore-samples/01-features/07-.../01-gateway/
       01-attach-targets/mcp/mcp-servers/lambda-intercept.py
"""

import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: dict, context: object) -> dict:
    mcp = event.get("mcp") or {}
    gateway_request = mcp.get("gatewayRequest") or {}
    gateway_response = mcp.get("gatewayResponse")

    if gateway_response is not None:
        return _handle_response(gateway_request, gateway_response)
    return _handle_request(gateway_request)


def _handle_request(gateway_request: dict) -> dict:
    body = gateway_request.get("body") or {}
    method = body.get("method") if isinstance(body, dict) else None
    msg_id = body.get("id") if isinstance(body, dict) else None

    kind = "request"
    if isinstance(body, dict):
        if "result" in body:
            kind = "response"
        elif "error" in body:
            kind = "error"

    logger.info(
        "REQUEST interceptor: kind=%s method=%r id=%r — passing through",
        kind,
        method,
        msg_id,
    )

    return {
        "interceptorOutputVersion": "1.0",
        "mcp": {"transformedGatewayRequest": {"body": body}},
    }


def _handle_response(gateway_request: dict, gateway_response: dict) -> dict:
    body = gateway_response.get("body") or {}
    is_streaming = bool(gateway_response.get("isStreamingResponse"))
    has_status = "statusCode" in gateway_response
    has_headers = "headers" in gateway_response

    inbound_method = (gateway_request.get("body") or {}).get("method")
    msg_id = body.get("id") if isinstance(body, dict) else None

    if not is_streaming:
        logger.info(
            "RESPONSE interceptor (non-streaming): inbound=%r id=%r — passing through",
            inbound_method,
            msg_id,
        )
        out: dict = {"body": body}
        if has_status:
            out["statusCode"] = gateway_response.get("statusCode", 200)
        if has_headers:
            out["headers"] = gateway_response.get("headers", {})
        return {
            "interceptorOutputVersion": "1.0",
            "mcp": {"transformedGatewayResponse": out},
        }

    is_first_event = has_status
    if is_first_event:
        logger.info(
            "RESPONSE interceptor (streaming, first event): "
            "inbound=%r id=%r — passing through",
            inbound_method,
            msg_id,
        )
        return {
            "interceptorOutputVersion": "1.0",
            "mcp": {
                "transformedGatewayResponse": {
                    "body": body,
                    "statusCode": gateway_response.get("statusCode", 200),
                    "headers": gateway_response.get("headers", {}),
                }
            },
        }

    logger.info(
        "RESPONSE interceptor (streaming, subsequent): inbound=%r id=%r — body only",
        inbound_method,
        msg_id,
    )
    return {
        "interceptorOutputVersion": "1.0",
        "mcp": {"transformedGatewayResponse": {"body": body}},
    }
