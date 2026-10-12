import { readFileSync } from 'node:fs';
import { parseArgs, parseEnv } from 'node:util';
import { pathToFileURL } from 'node:url';
import { runStream } from './stream.js';
import type { Credentials } from './stream.js';

export function readCredentials(
  envPath: URL = new URL('../.env', import.meta.url),
  environment: NodeJS.ProcessEnv = process.env,
): Credentials {
  let fileEnvironment: NodeJS.ProcessEnv = {};
  try {
    fileEnvironment = parseEnv(readFileSync(envPath, 'utf8').replace(/^\uFEFF/, ''));
  } catch (error) {
    if (!(error instanceof Error && 'code' in error && error.code === 'ENOENT')) {
      throw new Error('Cannot read .env configuration.');
    }
  }
  const clientId = (environment.DINGTALK_CLIENT_ID ?? fileEnvironment.DINGTALK_CLIENT_ID ?? '').trim();
  const clientSecret = (environment.DINGTALK_CLIENT_SECRET ?? fileEnvironment.DINGTALK_CLIENT_SECRET ?? '').trim();
  if (!clientId || !clientSecret || clientId.startsWith('replace-with-') || clientSecret.startsWith('replace-with-')) {
    throw new Error('Set DINGTALK_CLIENT_ID and DINGTALK_CLIENT_SECRET in .env or the environment.');
  }
  return { clientId, clientSecret };
}

export async function main(args = process.argv.slice(2)): Promise<number> {
  const log = (message: string) => console.log(`${new Date().toISOString()} ${message}`);
  let credentials: Credentials;
  try {
    const { values } = parseArgs({ args, options: { check: { type: 'boolean' }, help: { type: 'boolean', short: 'h' } } });
    if (values.help) {
      console.log('Usage: npm start -- [--check]\n--check validates local configuration without connecting.');
      return 0;
    }
    credentials = readCredentials();
    if (values.check) {
      log('Local configuration is valid; no connection attempted.');
      return 0;
    }
  } catch {
    console.error('Check arguments and set DINGTALK_CLIENT_ID and DINGTALK_CLIENT_SECRET in .env or the environment.');
    return 2;
  }
  const stop = new AbortController();
  const onStop = () => stop.abort();
  process.once('SIGINT', onStop);
  process.once('SIGTERM', onStop);
  try {
    log('Starting Stream connection; this does not confirm authentication or readiness.');
    await runStream(credentials, { signal: stop.signal, log });
    log('Bot stopped.');
    return 0;
  } catch {
    console.error('Stream client stopped unexpectedly.');
    return 1;
  } finally {
    process.removeListener('SIGINT', onStop);
    process.removeListener('SIGTERM', onStop);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exitCode = await main();
}
