# Setup and operation

## Install

Use Node.js 24.21.0 and npm 12.2.0, matching Dewbow. Node.js is pinned in .node-version, and npm is pinned in package.json's packageManager field. Run all commands from the repository root:

```sh
npm ci
npm run build
```

package-lock.json fixes development dependencies: TypeScript 7.0.2, @types/node 24.19.2, and ws 8.22.0 for simulated WebSocket tests. The running bot uses Node's built-in fetch, WebSocket, and environment parser; it has no runtime npm dependencies. npm 12 blocks unapproved dependency installation scripts, and this project needs none. Reuse the lock; do not upgrade dependencies during a normal startup.

Source files live in src/. The strict ESM build uses NodeNext resolution and .js import suffixes, and writes ignored dist/ files. Tests use Node's built-in test runner, following Dewbow's service tooling without introducing a monorepo.

## Private configuration

On PowerShell, copy the template once (skip this if .env already exists):

```powershell
Copy-Item -LiteralPath .env.example -Destination .env
```

Edit .env locally and replace both placeholders using the credentials from your DingTalk application. The variable names are DINGTALK_CLIENT_ID and DINGTALK_CLIENT_SECRET. Client ID is also called AppKey; Client Secret is also called AppSecret. The file supports UTF-8 with or without a BOM. Process environment variables take precedence over .env.

The compiled bot loads .env at the repository root even if launched from another directory. Do not send the secret in chat, put it in command arguments, or commit .env. This version needs no robotCode, fixed group webhook, database, public callback URL, or AI API key. The migration preserves the same variable names; an existing .env can be reused.

## Check and start

```sh
npm run check
npm start
```

After building, the compiled CLI can also be invoked directly:

```sh
node dist/cli.js --check
node dist/cli.js
```

--check verifies that credentials are present and no longer template values. It makes no network request and does not authenticate with DingTalk. Missing configuration or invalid arguments exit with code 2. npm run check builds first; npm start runs the existing build.

Wait for "Stream connected. Send the robot a text message." before testing. This confirms a WebSocket handshake, while a returned echo confirms message delivery. A connection failure retries after 3 seconds. Keep one bot instance running for this application. Stop with Ctrl+C (SIGINT) or SIGTERM. Shutdown cancels in-progress replies, stops reconnecting, and closes the socket; it does not install a background service.

## Behavior and limits

- Direct chat echoes text without trimming, interpreting, or adding a prefix. Unicode, spaces, and line breaks are preserved as delivered by DingTalk; the client may render them differently.
- An addressed group message follows the same path. Unaddressed group messages are ignored.
- Pictures, rich text, and other non-text messages receive the fixed text defined by nonTextReply: a Chinese message saying that only text is supported. No attachment is downloaded.
- Replies use the incoming sessionWebhook immediately. HTTP status and DingTalk errcode are checked. Gateway and reply requests have a 10-second timeout, including response-body reads; redirects are refused. WebSocket handshakes have a 10-second timeout.
- Successful replies receive a Stream status 200 ACK correlated to the incoming callback ID. Malformed callback payloads return 400. Reply failures return 500 and are not cached as successful; later delivery may retry them. Unparseable frames cannot be safely correlated and are ignored. Platform redelivery is not guaranteed.
- In-memory deduplication retains at most 1,024 successful message IDs, scoped to conversations, for 10 minutes. Reconnection keeps this cache; process restart loses it. This does not guarantee exactly-once delivery: a response can be lost after a reply was accepted, and restarting or running multiple instances can produce duplicates.
- At most 32 callbacks run concurrently. Excess callbacks are left unacknowledged for possible platform redelivery. In-flight duplicates share one reply operation, and each delivery receives its own ACK.
- Logs contain operation status, not message bodies, credentials, session webhook URLs, connection tickets, raw exceptions, or response bodies. No chat history is persisted.

The transport follows the [official DingTalk Stream protocol](https://open-dingtalk.github.io/developerpedia/docs/learn/stream/protocol/): register a connection ticket over HTTPS, open its WebSocket endpoint, subscribe only to the robot callback topic, acknowledge system pings, and reconnect after disconnection. The official Node SDK 2.1.5 was inspected during migration; its default connection requests lack timeouts, and its callback reply helper always emits a success ACK. The small built-in transport keeps timeout, cancellation, and failed-reply ACK behavior explicit. HTTPS/WSS certificate verification remains enabled. Plain HTTP/WS is accepted only for 127.0.0.1 loopback tests; the CLI uses the fixed official HTTPS gateway.

## Local validation

```sh
npm run typecheck
npm test
git diff --check
```

The eight top-level tests (14 cases including failure subtests) cover exact text and ACKs, non-text behavior, group addressing, concurrent duplicates, bounded cache lifetime, failed replies and later retry, malformed callbacks, private .env loading and environment precedence, and log privacy. The integration test uses actual HTTP and WebSocket connections only on 127.0.0.1: it simulates gateway failure, verifies echo and ping ACKs, forces reconnection, checks duplicate suppression across connections, and cancels the loop cleanly. Synthetic temporary files live in ignored work/.

Python source, tests, pyproject.toml, .python-version, and uv.lock have been removed from the tracked project. Historical ignored .venv/ and .uv-cache/ directories may remain locally; the TypeScript bot does not use them. Preserve private .env, local results, and any unrelated files during cleanup.

Successful local tests do not establish that a real DingTalk application is published, visible, authenticated, or delivering messages. Complete the [live acceptance steps](dingtalk.md) after configuring the application.
