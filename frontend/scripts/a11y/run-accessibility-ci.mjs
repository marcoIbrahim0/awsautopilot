#!/usr/bin/env node

import { spawn } from 'node:child_process';
import process from 'node:process';
import { setTimeout as delay } from 'node:timers/promises';

const PORT = process.env.A11Y_PORT ?? '3300';
const BASE_URL = process.env.A11Y_BASE_URL ?? `http://127.0.0.1:${PORT}`;
const npmCmd = process.platform === 'win32' ? 'npm.cmd' : 'npm';

function spawnCommand(args, extraEnv = {}, options = {}) {
  return spawn(npmCmd, args, {
    stdio: 'inherit',
    env: { ...process.env, ...extraEnv },
    detached: Boolean(options.detached),
  });
}

function runCommand(args, extraEnv = {}) {
  return new Promise((resolve, reject) => {
    const child = spawnCommand(args, extraEnv);
    child.on('error', reject);
    child.on('exit', (code) => {
      if (code === 0) {
        resolve();
        return;
      }
      reject(new Error(`Command failed (${npmCmd} ${args.join(' ')}), exit code ${code}`));
    });
  });
}

async function waitForServer(url, serverProcess, timeoutMs = 120000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (serverProcess.exitCode !== null) {
      throw new Error(`Next.js server exited before scan (exit code ${serverProcess.exitCode}).`);
    }
    try {
      const response = await fetch(url, { method: 'GET' });
      if (response.ok || response.status < 500) return;
    } catch {
      // keep polling
    }
    await delay(1000);
  }
  throw new Error(`Timed out waiting for ${url} to become ready.`);
}

async function stopServer(serverProcess) {
  if (serverProcess.exitCode !== null) return;
  if (process.platform === 'win32') {
    serverProcess.kill('SIGTERM');
    await delay(3000);
    if (serverProcess.exitCode === null) serverProcess.kill('SIGKILL');
    return;
  }
  try {
    process.kill(-serverProcess.pid, 'SIGTERM');
  } catch {
    serverProcess.kill('SIGTERM');
  }
  await delay(3000);
  if (serverProcess.exitCode === null) {
    try {
      process.kill(-serverProcess.pid, 'SIGKILL');
    } catch {
      serverProcess.kill('SIGKILL');
    }
  }
}

async function main() {
  await runCommand(['run', 'build']);
  const server = spawnCommand(['run', 'start'], { PORT, HOSTNAME: '127.0.0.1' }, { detached: true });
  try {
    await waitForServer(BASE_URL, server);
    await runCommand(['run', 'a11y:scan'], { A11Y_BASE_URL: BASE_URL });
  } finally {
    await stopServer(server);
  }
}

main().catch((error) => {
  console.error('CI accessibility orchestration failed:', error);
  process.exit(1);
});
