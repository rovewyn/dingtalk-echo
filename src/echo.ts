export const robotTopic = '/v1.0/im/bot/messages/get';
export const nonTextReply = '目前只支持文本消息。';

export interface StreamFrame {
  type: string;
  headers: { messageId: string; topic: string };
  data: string;
}

export interface Ack {
  code: number;
  headers: { messageId: string; contentType: string };
  message: string;
  data: string;
}

export type Log = (message: string) => void;

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function makeAck(frame: StreamFrame, code: number, message: string): Ack {
  return {
    code,
    headers: { messageId: frame.headers.messageId, contentType: 'application/json' },
    message,
    data: JSON.stringify({ response: message }),
  };
}

async function sendText(webhook: string, text: string, signal?: AbortSignal): Promise<void> {
  const timeout = AbortSignal.timeout(10_000);
  const response = await fetch(webhook, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ msgtype: 'text', text: { content: text } }),
    redirect: 'error',
    signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
  });
  const result: unknown = await response.json();
  if (response.status !== 200 || !isRecord(result) || result.errcode !== 0) {
    throw new Error('Reply was not accepted');
  }
}

export function createEchoHandler(log: Log = () => {}, now = Date.now) {
  const completed = new Map<string, number>();
  const inflight = new Map<string, Promise<boolean>>();

  return async (frame: StreamFrame, signal?: AbortSignal): Promise<Ack> => {
    let incoming: Record<string, unknown>;
    let text = nonTextReply;
    let messageId: string;
    let webhook: string;
    try {
      const parsed: unknown = JSON.parse(frame.data);
      if (!isRecord(parsed)) throw new Error('Invalid payload');
      incoming = parsed;
      if (incoming.conversationType !== '1' && incoming.conversationType !== '2') {
        throw new Error('Invalid conversation type');
      }
      if (incoming.conversationType === '2' && incoming.isInAtList !== true) {
        return makeAck(frame, 200, 'Ignored unaddressed group message');
      }
      if (typeof incoming.conversationId !== 'string' || !incoming.conversationId
        || typeof incoming.sessionWebhook !== 'string' || !incoming.sessionWebhook) {
        throw new Error('Missing conversation or webhook');
      }
      webhook = incoming.sessionWebhook;
      const url = new URL(webhook);
      const localHttp = url.protocol === 'http:' && url.hostname === '127.0.0.1';
      if (url.protocol !== 'https:' && !localHttp) throw new Error('Invalid webhook protocol');
      messageId = typeof incoming.msgId === 'string' && incoming.msgId
        ? incoming.msgId : frame.headers.messageId;
      if (!messageId) throw new Error('Missing message ID');
      if (incoming.msgtype === 'text') {
        if (!isRecord(incoming.text) || typeof incoming.text.content !== 'string') {
          throw new Error('Invalid text');
        }
        text = incoming.text.content;
      }
    } catch {
      log('Rejected a malformed callback.');
      return makeAck(frame, 400, 'Invalid callback');
    }

    for (const [key, expiry] of completed) {
      if (expiry > now()) break;
      completed.delete(key);
    }
    const key = JSON.stringify([incoming.conversationId, messageId]);
    if (completed.has(key)) {
      log('Skipped a duplicate callback.');
      return makeAck(frame, 200, 'Already replied');
    }
    let pending = inflight.get(key);
    if (!pending) {
      pending = sendText(webhook, text, signal)
        .then(() => {
          completed.set(key, now() + 600_000);
          if (completed.size > 1024) {
            const oldest = completed.keys().next().value;
            if (oldest !== undefined) completed.delete(oldest);
          }
          log('Reply accepted by DingTalk.');
          return true;
        })
        .catch(() => {
          // Exception text can contain private URLs or server response bodies.
          log('Reply failed; a later callback delivery may retry it.');
          return false;
        });
      inflight.set(key, pending);
    }
    const success = await pending;
    if (inflight.get(key) === pending) inflight.delete(key);
    return makeAck(frame, success ? 200 : 500, success ? 'OK' : 'Reply failed');
  };
}
