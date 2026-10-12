"""Receive DingTalk Stream callbacks and echo their text without storing messages."""

import argparse
import asyncio
import json
import logging
import os
import time
from collections import OrderedDict
from pathlib import Path
from urllib.parse import quote_plus

import dingtalk_stream
import requests
import websockets
from dotenv import load_dotenv

LOGGER = logging.getLogger("dingtalk_echo")
NON_TEXT_REPLY = "目前只支持文本消息。"
REPLY_TIMEOUT = (3, 10)
DEDUP_TTL_SECONDS = 600
DEDUP_MAX_MESSAGES = 1024


class PrivateSdkLogs(logging.Filter):
    """SDK diagnostics may contain payloads or URLs; expose only their severity."""

    def filter(self, record):
        record.msg = "DingTalk SDK event."
        if record.levelno >= logging.WARNING:
            record.msg = "DingTalk SDK reported a problem; check credentials and connectivity."
        record.args = ()
        record.exc_info = record.exc_text = record.stack_info = None
        return True


def configure_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOGGER.handlers = [handler]
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False
    sdk_logger = logging.getLogger("dingtalk_echo.sdk")
    sdk_logger.handlers = []
    sdk_logger.filters = [PrivateSdkLogs()]
    sdk_logger.setLevel(logging.INFO)
    return sdk_logger


def send_text(text, message):
    """Use the callback's session webhook, with a bounded wait and checked result."""
    payload = {"msgtype": "text", "text": {"content": text}}
    with requests.post(
        message.session_webhook,
        json=payload,
        timeout=REPLY_TIMEOUT,
        allow_redirects=False,
    ) as response:
        if response.status_code != 200:
            raise ValueError("Reply HTTP status was not successful")
        result = response.json()
        if not isinstance(result, dict) or type(result.get("errcode")) is not int:
            raise ValueError("Reply response did not contain an error code")
        if result["errcode"] != 0:
            raise ValueError("DingTalk rejected the reply")


class EchoHandler(dingtalk_stream.ChatbotHandler):
    def __init__(self):
        super().__init__()
        self._completed = OrderedDict()
        self._lock = asyncio.Lock()

    async def process(self, callback):
        try:
            incoming = dingtalk_stream.ChatbotMessage.from_dict(callback.data)
            if incoming.conversation_type not in ("1", "2"):
                raise ValueError("Unknown conversation type")
            if incoming.conversation_type == "2" and not incoming.is_in_at_list:
                return dingtalk_stream.AckMessage.STATUS_OK, "Ignored unaddressed group message"
            if not isinstance(incoming.session_webhook, str) or not incoming.session_webhook:
                raise ValueError("Missing session webhook")
            message_id = incoming.message_id or callback.headers.message_id
            if not isinstance(message_id, str) or not message_id:
                raise ValueError("Missing message ID")
            if not isinstance(incoming.conversation_id, str) or not incoming.conversation_id:
                raise ValueError("Missing conversation ID")
            text = NON_TEXT_REPLY
            if incoming.message_type == "text":
                text = incoming.text.content
                if not isinstance(text, str):
                    raise ValueError("Invalid text content")
        except (AttributeError, KeyError, TypeError, ValueError):
            LOGGER.warning("Rejected a malformed callback.")
            return dingtalk_stream.AckMessage.STATUS_BAD_REQUEST, "Invalid callback"

        # Serialize replies for this small bot, including concurrent duplicate callbacks.
        async with self._lock:
            now = time.monotonic()
            while self._completed and next(iter(self._completed.values())) <= now:
                self._completed.popitem(last=False)
            key = (incoming.conversation_id, message_id)
            if key in self._completed:
                LOGGER.info("Skipped a duplicate callback.")
                return dingtalk_stream.AckMessage.STATUS_OK, "Already replied"
            try:
                await asyncio.to_thread(send_text, text, incoming)
            except Exception:
                # Exception strings and response bodies can contain private webhook URLs.
                LOGGER.error("Reply failed; a later callback delivery may retry it.")
                return dingtalk_stream.AckMessage.STATUS_SYSTEM_EXCEPTION, "Reply failed"
            self._completed[key] = time.monotonic() + DEDUP_TTL_SECONDS
            while len(self._completed) > DEDUP_MAX_MESSAGES:
                self._completed.popitem(last=False)
            LOGGER.info("Reply accepted by DingTalk.")
            return dingtalk_stream.AckMessage.STATUS_OK, "OK"


class EchoStreamClient(dingtalk_stream.DingTalkStreamClient):
    def open_connection(self):
        # SDK 0.24.3 omits a timeout here; use its gateway request contract.
        payload = {
            "clientId": self.credential.client_id,
            "clientSecret": self.credential.client_secret,
            "subscriptions": [{"type": "CALLBACK", "topic": dingtalk_stream.ChatbotMessage.TOPIC}],
            "ua": "dingtalk-echo/0.1.0",
        }
        with requests.post(
            self.OPEN_CONNECTION_API, json=payload, timeout=REPLY_TIMEOUT, allow_redirects=False
        ) as response:
            if response.status_code != 200:
                raise ValueError("Stream gateway rejected the connection")
            return response.json()


async def run_stream(client):
    """Keep SDK callback routing while allowing cancellation on Ctrl+C."""
    client.pre_start()
    while True:
        try:
            connection = await asyncio.to_thread(client.open_connection)
            uri = f'{connection["endpoint"]}?ticket={quote_plus(connection["ticket"])}'
            async with websockets.connect(uri, logger=client.logger) as websocket:
                client.websocket = websocket
                LOGGER.info("Stream connected. Send the robot a text message.")
                async for raw_message in websocket:
                    result = await client.route_message(json.loads(raw_message))
                    if result == client.TAG_DISCONNECT:
                        break
        except Exception:
            LOGGER.warning("Stream connection or callback failed; retrying in 3 seconds.")
        finally:
            client.websocket = None
        await asyncio.sleep(3)


def create_client(client_id, client_secret, sdk_logger):
    client = EchoStreamClient(
        dingtalk_stream.Credential(client_id, client_secret), logger=sdk_logger
    )
    client.register_callback_handler(dingtalk_stream.ChatbotMessage.TOPIC, EchoHandler())
    return client


def main():
    parser = argparse.ArgumentParser(description="DingTalk Stream text echo bot")
    parser.add_argument("--check", action="store_true", help="Check local configuration without connecting")
    args = parser.parse_args()
    sdk_logger = configure_logging()
    load_dotenv(Path(__file__).with_name(".env"), override=False, encoding="utf-8-sig")
    values = [os.getenv(name, "").strip() for name in ("DINGTALK_CLIENT_ID", "DINGTALK_CLIENT_SECRET")]
    if any(not value or value.startswith("replace-with-") for value in values):
        LOGGER.error("Set DINGTALK_CLIENT_ID and DINGTALK_CLIENT_SECRET in .env or the environment.")
        return 2
    client = create_client(*values, sdk_logger)
    if args.check:
        LOGGER.info("Local configuration and SDK handler registration are valid; no connection attempted.")
        return 0
    LOGGER.info("Starting Stream connection; this does not confirm authentication or readiness.")
    try:
        asyncio.run(run_stream(client))
    except KeyboardInterrupt:
        pass
    except Exception:
        LOGGER.error("Stream client stopped unexpectedly; check credentials and connectivity.")
        return 1
    LOGGER.info("Bot stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
