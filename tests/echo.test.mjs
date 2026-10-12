import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { mkdir, mkdtemp, writeFile, rm } from 'node:fs/promises';
import { createServer } from 'node:http';
import { dirname, resolve } from 'node:path';
import { test } from 'node:test';
import { pathToFileURL } from 'node:url';
import { WebSocketServer } from 'ws';
import { createEchoHandler, nonTextReply, robotTopic } from '../dist/echo.js';
import { readCredentials } from '../dist/cli.js';
import { runStream } from '../dist/stream.js';

const originalText = ' 你好\nEcho 🙂\n ';
const credentials = { clientId: 'example-client', clientSecret: 'example-secret' };

function frame(webhook, changes = {}, callbackId = 'example-callback') {
  return {
    type: 'CALLBACK', headers: { messageId: callbackId, topic: robotTopic },
    data: JSON.stringify({
      msgId: 'example-message', conversationId: 'example-conversation', conversationType: '1',
      msgtype: 'text', text: { content: originalText }, sessionWebhook: webhook, ...changes,
    }),
  };
}

async function httpServer(t, responder = () => ({ errcode: 0 })) {
  const received = [];
  const server = createServer(async (request, response) => {
    const chunks = [];
    for await (const chunk of request) chunks.push(chunk);
    const payload = JSON.parse(Buffer.concat(chunks).toString());
    received.push({ path: request.url, payload });
    const body = responder(payload, response, request);
    response.end(typeof body === 'string' ? body : JSON.stringify(body));
  });
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  t.after(async () => {
    server.closeAllConnections();
    await new Promise((done) => server.close(done));
  });
  return { url: `http://127.0.0.1:${server.address().port}`, received };
}

test('echo preserves text and correlates ACKs in direct and addressed group chat', async (t) => {
  const server = await httpServer(t);
  const handle = createEchoHandler();
  for (const conversationType of ['1', '2']) {
    const ack = await handle(frame(server.url, { conversationType, isInAtList: true, msgId: conversationType }));
    assert.equal(ack.code, 200);
    assert.equal(ack.headers.messageId, 'example-callback');
    assert.equal(server.received.at(-1).payload.text.content, originalText);
  }
});

test('non-text notice, unaddressed groups and malformed callbacks', async (t) => {
  const server = await httpServer(t);
  const handle = createEchoHandler();
  assert.equal((await handle(frame(server.url, { msgtype: 'picture' }))).code, 200);
  assert.equal(server.received[0].payload.text.content, nonTextReply);
  assert.equal((await handle(frame(server.url, { conversationType: '2', isInAtList: false }))).code, 200);
  for (const changes of [{ text: {} }, { conversationId: [] }, { sessionWebhook: '' }, { text: { content: 7 } }]) {
    assert.equal((await handle(frame(server.url, changes))).code, 400);
  }
  assert.equal((await handle({ ...frame(server.url), data: 'invalid JSON' })).code, 400);
  assert.equal(server.received.length, 1);
});

test('concurrent duplicate delivery is coalesced and successful IDs expire', async (t) => {
  const server = await httpServer(t);
  let clock = 0;
  const handle = createEchoHandler(() => {}, () => clock);
  const acks = await Promise.all([
    handle(frame(server.url, {}, 'callback-a')), handle(frame(server.url, {}, 'callback-b')),
  ]);
  assert.deepEqual(acks.map((ack) => ack.headers.messageId), ['callback-a', 'callback-b']);
  assert(acks.every((ack) => ack.code === 200));
  assert.equal(server.received.length, 1);
  clock = 600_001;
  assert.equal((await handle(frame(server.url))).code, 200);
  assert.equal(server.received.length, 2);
});

test('HTTP, platform, JSON, redirect and cancelled replies return 500 and allow retry', async (t) => {
  for (const kind of ['http', 'platform', 'json', 'missing-code', 'redirect', 'abort']) {
    await t.test(kind, async (t) => {
      let first = true;
      const server = await httpServer(t, (_payload, response) => {
        if (first) {
          first = false;
          if (kind === 'http') response.statusCode = 503;
          if (kind === 'platform') return { errcode: 1, errmsg: 'example-private-error' };
          if (kind === 'json') return 'invalid JSON';
          if (kind === 'missing-code') return {};
          if (kind === 'redirect') {
            response.statusCode = 302;
            response.setHeader('Location', '/elsewhere');
          }
        }
        return { errcode: 0 };
      });
      const logs = [];
      const handle = createEchoHandler((message) => logs.push(message));
      const signal = kind === 'abort' ? AbortSignal.abort('example-private-reason') : undefined;
      assert.equal((await handle(frame(server.url), signal)).code, 500);
      if (kind === 'abort') first = false;
      assert.equal((await handle(frame(server.url))).code, 200);
      assert(!logs.join('\n').includes('example-private'));
      assert(!logs.join('\n').includes(server.url));
      assert.equal(server.received.filter((entry) => entry.path === '/elsewhere').length, 0);
    });
  }
});

test('successful ID cache stays bounded', async (t) => {
  const server = await httpServer(t);
  const handle = createEchoHandler();
  for (let i = 0; i < 1025; i++) {
    assert.equal((await handle(frame(server.url, { msgId: `synthetic-${i}` }))).code, 200);
  }
  await handle(frame(server.url, { msgId: 'synthetic-1024' }));
  assert.equal(server.received.length, 1025);
  await handle(frame(server.url, { msgId: 'synthetic-0' }));
  assert.equal(server.received.length, 1026);
});

test('private UTF-8 BOM env file, environment precedence and placeholder rejection', async (t) => {
  const scratchRoot = resolve('work');
  await mkdir(scratchRoot, { recursive: true });
  const directory = await mkdtemp(resolve(scratchRoot, 'env-test-'));
  t.after(() => {
    assert.equal(dirname(resolve(directory)), scratchRoot);
    return rm(directory, { recursive: true, force: true });
  });
  const envPath = pathToFileURL(resolve(directory, '.env'));
  await writeFile(envPath, '\uFEFFDINGTALK_CLIENT_ID=example-file-client\nDINGTALK_CLIENT_SECRET=example-file-secret\n');
  assert.deepEqual(readCredentials(envPath, {}), { clientId: 'example-file-client', clientSecret: 'example-file-secret' });
  assert.equal(readCredentials(envPath, { DINGTALK_CLIENT_ID: 'example-env-client' }).clientId, 'example-env-client');
  assert.throws(() => readCredentials(envPath, { DINGTALK_CLIENT_ID: '' }));
  assert.throws(() => readCredentials(envPath, { DINGTALK_CLIENT_SECRET: 'replace-with-client-secret' }));
});

test('Stream retry, real echo and ping ACK, reconnect deduplication and prompt cancellation', async (t) => {
  let attempts = 0;
  let endpoint;
  const server = await httpServer(t, (_payload, response, request) => {
    if (request.url === '/gateway') {
      attempts++;
      if (attempts === 1) response.statusCode = 503;
      return { endpoint, ticket: 'example-private-ticket' };
    }
    return { errcode: 0 };
  });
  const websocket = new WebSocketServer({ host: '127.0.0.1', port: 0 });
  await once(websocket, 'listening');
  endpoint = `ws://127.0.0.1:${websocket.address().port}`;
  t.after(() => new Promise((done) => websocket.close(done)));
  const acks = [];
  const done = Promise.withResolvers();
  websocket.on('connection', (socket) => {
    socket.on('message', (raw) => {
      acks.push(JSON.parse(raw.toString()));
      if (acks.length === 2) {
        socket.send(JSON.stringify({ type: 'SYSTEM', headers: { messageId: 'disconnect-id', topic: 'disconnect' }, data: '{}' }));
      }
      if (acks.length === 4) done.resolve();
    });
    socket.send(JSON.stringify({ type: 'SYSTEM', headers: { messageId: 'ping-id', topic: 'ping' }, data: '{"opaque":"example"}' }));
    socket.send(JSON.stringify(frame(`${server.url}/reply`)));
  });
  const stop = new AbortController();
  const logs = [];
  const running = runStream(credentials, {
    signal: stop.signal, log: (message) => logs.push(message), gatewayUrl: `${server.url}/gateway`, retryDelayMs: 20,
  });
  try {
    await Promise.race([done.promise, new Promise((_, reject) => setTimeout(() => reject(new Error('Test timed out')), 5000).unref())]);
    assert.equal(attempts, 3);
    assert(acks.every((ack) => ack.code === 200));
    assert.equal(acks.find((ack) => ack.headers.messageId === 'ping-id').data, '{"opaque":"example"}');
    assert.equal(server.received.find((entry) => entry.path === '/reply').payload.text.content, originalText);
    assert.equal(server.received.filter((entry) => entry.path === '/reply').length, 1);
    const gateway = server.received.find((entry) => entry.path === '/gateway').payload;
    assert.deepEqual(gateway.subscriptions, [{ type: 'CALLBACK', topic: robotTopic }]);
    assert.equal(gateway.clientId, credentials.clientId);
    assert(!logs.join('\n').includes('example-private'));
  } finally {
    stop.abort();
    await running;
  }
});

test('compiled CLI check has no network or credential output, and rejects missing configuration', async () => {
  for (const valid of [true, false]) {
    const child = spawn(process.execPath, ['dist/cli.js', '--check'], {
      env: { ...process.env, DINGTALK_CLIENT_ID: valid ? 'example-client' : '', DINGTALK_CLIENT_SECRET: 'example-secret' },
    });
    let output = '';
    child.stdout.on('data', (data) => { output += data; });
    child.stderr.on('data', (data) => { output += data; });
    const [code] = await once(child, 'close');
    assert.equal(code, valid ? 0 : 2);
    assert(!output.includes('example-secret'));
    assert(!output.includes('Starting Stream connection'));
  }
});
