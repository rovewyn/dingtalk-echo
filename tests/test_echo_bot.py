import asyncio
import io
import json
import logging
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import dingtalk_stream
import requests
from websockets.asyncio.server import serve

import echo_bot


def frame(text=" 你好\nEcho 🙂\n ", **changes):
    data = {
        "msgId": "example-message",
        "conversationId": "example-conversation",
        "conversationType": "1",
        "msgtype": "text",
        "text": {"content": text},
        "sessionWebhook": "https://example.invalid/private-webhook",
    }
    data.update(changes)
    return {
        "type": "CALLBACK",
        "headers": {"messageId": "example-callback", "topic": dingtalk_stream.ChatbotMessage.TOPIC},
        "data": json.dumps(data, ensure_ascii=False),
    }


def response(body=b'{"errcode": 0}', status=200):
    result = requests.Response()
    result.status_code = status
    result._content = body
    return result


class AckSocket:
    def __init__(self):
        self.acks = []

    async def send(self, value):
        self.acks.append(json.loads(value))


class CallbackTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = echo_bot.create_client("example-id", "example-secret", logging.getLogger("test-sdk"))
        self.client.websocket = AckSocket()

    async def test_echo_preserves_text_and_sdk_ack(self):
        for conversation in ("1", "2"):
            with self.subTest(conversation=conversation), patch("echo_bot.requests.post", return_value=response()) as post:
                message = frame(conversationType=conversation, isInAtList=True, msgId=f"message-{conversation}")
                await self.client.route_message(message)
                self.assertEqual(post.call_args.kwargs["json"]["text"]["content"], " 你好\nEcho 🙂\n ")
                self.assertEqual(post.call_args.kwargs["timeout"], echo_bot.REPLY_TIMEOUT)
                self.assertFalse(post.call_args.kwargs["allow_redirects"])
                self.assertEqual(self.client.websocket.acks[-1]["code"], 200)
                self.assertEqual(self.client.websocket.acks[-1]["headers"]["messageId"], "example-callback")

    async def test_non_text_and_unaddressed_group(self):
        with patch("echo_bot.requests.post", return_value=response()) as post:
            await self.client.route_message(frame(msgtype="picture", content={"downloadCode": "example-download"}))
            self.assertEqual(post.call_args.kwargs["json"]["text"]["content"], echo_bot.NON_TEXT_REPLY)
            await self.client.route_message(frame(conversationType="2", isInAtList=False, msgId="unaddressed"))
            self.assertEqual(post.call_count, 1)
            self.assertEqual(self.client.websocket.acks[-1]["code"], 200)

    async def test_concurrent_duplicates_and_cache_expiry(self):
        with patch("echo_bot.requests.post", side_effect=lambda *a, **k: response()) as post:
            await asyncio.gather(self.client.route_message(frame()), self.client.route_message(frame()))
            self.assertEqual(post.call_count, 1)
            handler = self.client.callback_handler_map[dingtalk_stream.ChatbotMessage.TOPIC]
            handler._completed[("example-conversation", "example-message")] = 0
            await self.client.route_message(frame())
            self.assertEqual(post.call_count, 2)
            self.assertTrue(all(ack["code"] == 200 for ack in self.client.websocket.acks))
            with patch("echo_bot.DEDUP_MAX_MESSAGES", 1):
                await self.client.route_message(frame(msgId="second-message"))
                self.assertEqual(len(handler._completed), 1)

    async def test_reply_failure_is_not_success_or_cached(self):
        failures = [
            response(status=503), response(b'{"errcode": 1, "errmsg": "example-private-error"}'),
            response(b"not JSON"), response(b"{}"), response(b"null"),
            requests.Timeout("example-private-webhook"),
        ]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                with patch("echo_bot.requests.post", side_effect=[failure, response()]):
                    await self.client.route_message(frame(msgId=f"failure-{id(failure)}"))
                    self.assertEqual(self.client.websocket.acks[-1]["code"], 500)
                    await self.client.route_message(frame(msgId=f"failure-{id(failure)}"))
                    self.assertEqual(self.client.websocket.acks[-1]["code"], 200)

    async def test_malformed_callback_is_rejected_without_reply(self):
        with patch("echo_bot.requests.post") as post:
            for change in ({"text": {}}, {"text": {"content": 7}}, {"sessionWebhook": ""}, {"conversationId": []}):
                await self.client.route_message(frame(**change))
                self.assertEqual(self.client.websocket.acks[-1]["code"], 400)
            post.assert_not_called()


class LocalStreamTest(unittest.IsolatedAsyncioTestCase):
    async def test_real_http_and_websocket_round_trip_and_shutdown(self):
        received = []
        gateway_requests = []
        endpoint = {}

        class HttpHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                if self.path == "/gateway":
                    gateway_requests.append(payload)
                    body = json.dumps(endpoint).encode()
                    status = 503 if len(gateway_requests) == 1 else 200
                else:
                    received.append(payload)
                    body = b'{"errcode": 0, "errmsg": "ok"}'
                    status = 200
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        http = ThreadingHTTPServer(("127.0.0.1", 0), HttpHandler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        ack_future = asyncio.get_running_loop().create_future()

        async def stream_connection(socket):
            await socket.send(json.dumps(frame(sessionWebhook=f"http://127.0.0.1:{http.server_port}/reply")))
            ack_future.set_result(json.loads(await socket.recv()))
            await socket.wait_closed()

        try:
            async with serve(stream_connection, "127.0.0.1", 0) as server:
                port = server.sockets[0].getsockname()[1]
                endpoint.update(endpoint=f"ws://127.0.0.1:{port}", ticket="example-ticket")
                client = echo_bot.create_client("example-id", "example-secret", logging.getLogger("test-sdk"))
                client.OPEN_CONNECTION_API = f"http://127.0.0.1:{http.server_port}/gateway"
                task = asyncio.create_task(echo_bot.run_stream(client))
                try:
                    ack = await asyncio.wait_for(ack_future, 5)
                    self.assertEqual(ack["code"], 200)
                    self.assertEqual(received, [{"msgtype": "text", "text": {"content": " 你好\nEcho 🙂\n "}}])
                    self.assertEqual(gateway_requests[0]["clientId"], "example-id")
                    self.assertEqual(len(gateway_requests), 2)
                    self.assertEqual(gateway_requests[0]["subscriptions"], [
                        {"type": "CALLBACK", "topic": dingtalk_stream.ChatbotMessage.TOPIC}
                    ])
                finally:
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await asyncio.wait_for(task, 2)
                self.assertIsNone(client.websocket)
        finally:
            await asyncio.to_thread(http.shutdown)
            http.server_close()
            thread.join(timeout=2)


class StartupAndPrivacyTests(unittest.TestCase):
    def test_check_has_no_network_and_environment_wins(self):
        scratch = Path(".tmp")
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text("DINGTALK_CLIENT_ID=example-file-id\nDINGTALK_CLIENT_SECRET=example-file-secret\n", encoding="utf-8-sig")
            with (
                patch("echo_bot.__file__", str(env_path.with_name("echo_bot.py"))),
                patch("sys.argv", ["echo_bot.py", "--check"]),
                patch.dict(os.environ, {}, clear=True),
                patch("echo_bot.requests.post") as post,
            ):
                with patch("echo_bot.create_client", wraps=echo_bot.create_client) as create:
                    self.assertEqual(echo_bot.main(), 0)
                    self.assertEqual(create.call_args.args[:2], ("example-file-id", "example-file-secret"))
                    os.environ["DINGTALK_CLIENT_ID"] = "example-env-id"
                    self.assertEqual(echo_bot.main(), 0)
                    self.assertEqual(create.call_args.args[:2], ("example-env-id", "example-file-secret"))
                    post.assert_not_called()
        with patch("sys.argv", ["echo_bot.py", "--check"]), patch.dict(os.environ, {
            "DINGTALK_CLIENT_ID": "", "DINGTALK_CLIENT_SECRET": "replace-with-client-secret",
        }), patch("echo_bot.load_dotenv"):
            self.assertEqual(echo_bot.main(), 2)

    def test_sdk_and_reply_errors_do_not_expose_private_values(self):
        sdk_logger = echo_bot.configure_logging()
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        with patch.object(echo_bot.LOGGER, "handlers", [handler]):
            try:
                raise ValueError("example-secret")
            except ValueError:
                sdk_logger.exception("example-private-payload %s", "example-ticket")
            sdk_logger.error("endpoint=%s", {"ticket": "example-ticket"})
            client = echo_bot.create_client("example-id", "example-secret", sdk_logger)
            client.websocket = AckSocket()
            with patch("echo_bot.requests.post", side_effect=requests.Timeout("example-private-webhook")):
                asyncio.run(client.route_message(frame(text="example-message-content")))
        for private in ("example-secret", "example-ticket", "example-private-payload", "example-private-webhook", "example-message-content"):
            self.assertNotIn(private, output.getvalue())
        self.assertIn("Reply failed", output.getvalue())


if __name__ == "__main__":
    unittest.main()
