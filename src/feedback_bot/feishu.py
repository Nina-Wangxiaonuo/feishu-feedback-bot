from __future__ import annotations

import base64
import hashlib
import hmac
import json
import mimetypes
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class FeishuError(RuntimeError):
    pass


def _request_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request_headers = {"Content-Type": "application/json; charset=utf-8", **(headers or {})}
    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise FeishuError(f"飞书接口 HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise FeishuError(f"飞书接口连接失败: {exc.reason}") from exc

    result = json.loads(body)
    code = result.get("code", result.get("StatusCode", 0))
    if code not in (0, None):
        raise FeishuError(f"飞书接口错误 {code}: {result.get('msg') or result.get('StatusMessage')}")
    return result


class BitableClient:
    def __init__(self, app_id: str, app_secret: str, app_token: str, table_id: str) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.app_token = app_token
        self.table_id = table_id
        self._token: str | None = None
        self._token_expires_at = 0.0

    def _tenant_token(self) -> str:
        if self._token and time.time() < self._token_expires_at:
            return self._token
        result = _request_json(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            method="POST",
            payload={"app_id": self.app_id, "app_secret": self.app_secret},
        )
        self._token = result["tenant_access_token"]
        self._token_expires_at = time.time() + int(result.get("expire", 7200)) - 120
        return self._token

    def list_tables(self) -> list[dict[str, Any]]:
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{urllib.parse.quote(self.app_token)}/tables?page_size=100"
        return _request_json(url, headers={"Authorization": f"Bearer {self._tenant_token()}"}).get("data", {}).get("items", [])

    def create_table(self, name: str) -> dict[str, Any]:
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{urllib.parse.quote(self.app_token)}/tables"
        result = _request_json(url, method="POST", payload={"table": {"name": name}}, headers={"Authorization": f"Bearer {self._tenant_token()}"})
        return result.get("data", {})

    def list_fields(self, table_id: str | None = None) -> list[dict[str, Any]]:
        target = table_id or self.table_id
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{urllib.parse.quote(self.app_token)}/tables/{urllib.parse.quote(target)}/fields?page_size=100"
        return _request_json(url, headers={"Authorization": f"Bearer {self._tenant_token()}"}).get("data", {}).get("items", [])

    def create_field(self, table_id: str, field_name: str, field_type: int, property_data: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{urllib.parse.quote(self.app_token)}/tables/{urllib.parse.quote(table_id)}/fields"
        payload: dict[str, Any] = {"field_name": field_name, "type": field_type}
        if property_data:
            payload["property"] = property_data
        return _request_json(url, method="POST", payload=payload, headers={"Authorization": f"Bearer {self._tenant_token()}"}).get("data", {})

    def update_field(self, table_id: str, field_id: str, field_name: str, field_type: int) -> dict[str, Any]:
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{urllib.parse.quote(self.app_token)}/tables/{urllib.parse.quote(table_id)}/fields/{urllib.parse.quote(field_id)}"
        return _request_json(url, method="PUT", payload={"field_name": field_name, "type": field_type}, headers={"Authorization": f"Bearer {self._tenant_token()}"}).get("data", {})

    def list_records(self, page_size: int = 500, table_id: str | None = None) -> list[dict[str, Any]]:
        target = table_id or self.table_id
        records: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            query = {"page_size": str(page_size), "automatic_fields": "true"}
            if page_token:
                query["page_token"] = page_token
            url = (
                "https://open.feishu.cn/open-apis/bitable/v1/apps/"
                f"{urllib.parse.quote(self.app_token)}/tables/{urllib.parse.quote(target)}/records?"
                + urllib.parse.urlencode(query)
            )
            result = _request_json(
                url,
                headers={"Authorization": f"Bearer {self._tenant_token()}"},
            )
            data = result.get("data", {})
            records.extend(data.get("items", []))
            if not data.get("has_more"):
                break
            page_token = data.get("page_token")
            if not page_token:
                break
        return records

    def create_record(self, table_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{urllib.parse.quote(self.app_token)}/tables/{urllib.parse.quote(table_id)}/records"
        return _request_json(url, method="POST", payload={"fields": fields}, headers={"Authorization": f"Bearer {self._tenant_token()}"}).get("data", {}).get("record", {})

    def update_record(self, table_id: str, record_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{urllib.parse.quote(self.app_token)}/tables/{urllib.parse.quote(table_id)}/records/{urllib.parse.quote(record_id)}"
        return _request_json(url, method="PUT", payload={"fields": fields}, headers={"Authorization": f"Bearer {self._tenant_token()}"}).get("data", {}).get("record", {})

    def delete_record(self, table_id: str, record_id: str) -> None:
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{urllib.parse.quote(self.app_token)}/tables/{urllib.parse.quote(table_id)}/records/{urllib.parse.quote(record_id)}"
        _request_json(url, method="DELETE", headers={"Authorization": f"Bearer {self._tenant_token()}"})


def _request_multipart(
    url: str,
    *,
    fields: dict[str, str],
    file_field: str,
    file_path: str,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    boundary = f"----dsh{uuid.uuid4().hex}"
    body = bytearray()
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
    filename = file_path.rsplit("/", 1)[-1]
    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    body.extend(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field}\"; filename=\"{filename}\"\r\nContent-Type: {mime}\r\n\r\n".encode()
    )
    with open(file_path, "rb") as file:
        body.extend(file.read())
    body.extend(f"\r\n--{boundary}--\r\n".encode())
    request = urllib.request.Request(
        url,
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", **(headers or {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise FeishuError(f"飞书接口 HTTP {exc.code}: {detail}") from exc
    if result.get("code", 0) != 0:
        raise FeishuError(f"飞书接口错误 {result.get('code')}: {result.get('msg')}")
    return result


class AppBotClient:
    def __init__(self, app_id: str, app_secret: str, chat_id: str) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.chat_id = chat_id

    def _tenant_token(self) -> str:
        result = _request_json(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            method="POST",
            payload={"app_id": self.app_id, "app_secret": self.app_secret},
        )
        return result["tenant_access_token"]

    def upload_image(self, file_path: str) -> str:
        result = _request_multipart(
            "https://open.feishu.cn/open-apis/im/v1/images",
            fields={"image_type": "message"},
            file_field="image",
            file_path=file_path,
            headers={"Authorization": f"Bearer {self._tenant_token()}"},
        )
        return result["data"]["image_key"]

    def update_card_message(self, message_id: str, card: dict[str, Any]) -> dict[str, Any]:
        url = f"https://open.feishu.cn/open-apis/im/v1/messages/{urllib.parse.quote(message_id)}"
        return _request_json(
            url,
            method="PATCH",
            payload={"content": json.dumps(card, ensure_ascii=False), "msg_type": "interactive"},
            headers={"Authorization": f"Bearer {self._tenant_token()}"},
        )

    def send_card(self, card: dict[str, Any]) -> dict[str, Any]:
        url = (
            "https://open.feishu.cn/open-apis/im/v1/messages?"
            + urllib.parse.urlencode({"receive_id_type": "chat_id"})
        )
        return _request_json(
            url,
            method="POST",
            payload={
                "receive_id": self.chat_id,
                "msg_type": "interactive",
                "content": json.dumps(card, ensure_ascii=False),
            },
            headers={"Authorization": f"Bearer {self._tenant_token()}"},
        )


class WebhookClient:
    def __init__(self, webhook_url: str, secret: str | None = None) -> None:
        self.webhook_url = webhook_url
        self.secret = secret

    def send_card(self, card: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {"msg_type": "interactive", "card": card}
        if self.secret:
            timestamp = str(int(time.time()))
            string_to_sign = f"{timestamp}\n{self.secret}".encode("utf-8")
            signature = base64.b64encode(
                hmac.new(string_to_sign, digestmod=hashlib.sha256).digest()
            ).decode("utf-8")
            payload.update({"timestamp": timestamp, "sign": signature})
        return _request_json(self.webhook_url, method="POST", payload=payload)
