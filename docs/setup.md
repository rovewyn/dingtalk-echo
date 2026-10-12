# Setup and operation

## Install

Use Python 3.13.16 and uv 0.13.0. Run all commands from the repository root:

```sh
uv sync --locked
```

uv creates the ignored .venv/ environment. uv.lock fixes direct and transitive dependency versions, including dingtalk-stream 0.24.3, python-dotenv 1.2.4, requests 2.34.2, and websockets 17.2. Reuse the lock; do not upgrade dependencies during a normal startup.

## Private configuration

On PowerShell, copy the template once (skip this if .env already exists):

```powershell
Copy-Item -LiteralPath .env.example -Destination .env
```

Edit .env locally and replace both placeholders using the credentials from your DingTalk application. The variable names are DINGTALK_CLIENT_ID and DINGTALK_CLIENT_SECRET. Client ID is also called AppKey; Client Secret is also called AppSecret. The file supports UTF-8 with or without a BOM. Process environment variables take precedence over .env.

The bot loads .env beside echo_bot.py even if launched from another directory. Do not send the secret in chat, put it in command arguments, or commit .env. This version needs no robotCode, fixed group webhook, database, public callback URL, or AI API key.

## Check and start

```sh
uv run --locked python echo_bot.py --check
uv run --locked python echo_bot.py
```

If the environment is already installed, PowerShell can invoke its interpreter directly:

```powershell
& .\.venv\Scripts\python.exe echo_bot.py --check
& .\.venv\Scripts\python.exe echo_bot.py
```

--check verifies that credentials are present and no longer template values, and registers the SDK handler. It makes no network request and does not authenticate with DingTalk. Missing configuration exits with code 2.

Wait for "Stream connected. Send the robot a text message." before testing. This confirms a WebSocket handshake, while a returned echo confirms message delivery. A connection or routing failure retries after 3 seconds. Keep one bot instance running for this application. Stop with Ctrl+C; an in-progress HTTP request may need to finish or time out before exit.

## Behavior and limits

- Direct chat echoes text without trimming, interpreting, or adding a prefix. Unicode, spaces, and line breaks are preserved as delivered by the SDK; the DingTalk client may render them differently.
- An addressed group message follows the same path. Unaddressed group messages are ignored.
- Pictures, rich text, and other non-text messages receive the fixed text defined by NON_TEXT_REPLY: a Chinese message saying that only text is supported. No attachment is downloaded.
- Replies use the incoming sessionWebhook immediately. HTTP status and DingTalk errcode are checked. Both gateway and reply requests use a 3-second connection timeout and a 10-second read timeout; redirects are refused.
- Successful replies are acknowledged with SDK status 200. Malformed callbacks return 400. Reply failures return 500 and are not cached as successful; later delivery may retry them. Platform redelivery is not guaranteed.
- In-memory deduplication retains at most 1,024 successful message IDs, scoped to conversations, for 10 minutes. Reconnection keeps this cache; process restart loses it. This does not guarantee exactly-once delivery: a response can be lost after a reply was accepted, and restarting or running multiple instances can produce duplicates.
- Logs contain operation status, not message bodies, credentials, session webhook URLs, or connection tickets. SDK diagnostic text is reduced to severity-only messages. No chat history is persisted.

The official SDK supplies credentials, callback parsing, routing, and ACK construction. A small wrapper supplies gateway timeouts and a cancellable connection loop because SDK 0.24.3's default startup lacks those safeguards. See the [official SDK](https://github.com/open-dingtalk/dingtalk-stream-sdk-python) and [Stream protocol](https://open-dingtalk.github.io/developerpedia/docs/learn/stream/protocol/).

## Local validation

```sh
uv run --locked python -m unittest discover -s tests -v
uv run --locked python -m compileall -q echo_bot.py tests
git diff --check
```

The eight tests cover exact text and SDK ACKs, non-text behavior, group addressing, concurrent duplicates and bounded cache lifetime, failed replies and later retry, malformed callbacks, private .env loading and environment precedence, and log privacy. The integration test uses actual HTTP and WebSocket connections only on 127.0.0.1: it simulates a rejected gateway request followed by reconnection, delivers a callback, verifies the echo and ACK, and cancels the loop cleanly. Test files use synthetic data in ignored .tmp/.

Successful local tests do not establish that a real DingTalk application is published, visible, authenticated, or delivering messages. Complete the [live acceptance steps](dingtalk.md) after configuring the application.
