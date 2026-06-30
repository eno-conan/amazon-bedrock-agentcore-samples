"""ローカル AgentCore サーバーへのテストリクエスト送信スクリプト。

Usage:
    uv run --env-file .env python scripts/invoke.py "顧客一覧を教えて"
    uv run --env-file .env python scripts/invoke.py  # デフォルトクエリ
"""

import json
import sys
import urllib.request

URL = "http://localhost:8080/invocations"
DEFAULT_QUERY = "顧客一覧を教えて"


def invoke(prompt: str) -> None:
    body = json.dumps({"prompt": prompt}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        URL,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    print(f"→ {prompt!r}")
    print()
    with urllib.request.urlopen(req) as resp:
        content_type = resp.headers.get("Content-Type", "")
        if "event-stream" in content_type:
            for line in resp:
                line = line.decode("utf-8").strip()
                if line.startswith("data:"):
                    data = line[5:].strip()
                    if data:
                        try:
                            obj = json.loads(data)
                            if isinstance(obj, dict):
                                print(
                                    obj.get(
                                        "data", json.dumps(obj, ensure_ascii=False)
                                    ),
                                    end="",
                                    flush=True,
                                )
                            else:
                                print(obj, end="", flush=True)
                        except json.JSONDecodeError:
                            print(data, end="", flush=True)
            print()
        else:
            result = json.loads(resp.read().decode("utf-8"))
            print(result)


if __name__ == "__main__":
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else DEFAULT_QUERY
    invoke(prompt)
