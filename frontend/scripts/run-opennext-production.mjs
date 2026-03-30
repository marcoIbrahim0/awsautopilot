#!/usr/bin/env node

import { spawn } from 'node:child_process';
import { execFile } from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { promisify } from 'node:util';

const cwd = process.cwd();
const command = process.argv[2];
const allowedCommands = new Set(['build', 'preview', 'deploy', 'upload']);
const guardedCommands = new Set(['preview', 'deploy', 'upload']);
const envLocalPath = path.resolve(cwd, '.env.local');
const envLocalBackupPath = path.resolve(cwd, '.env.local.opennext-backup');
const nextEnvPath = path.resolve(cwd, '.open-next', 'cloudflare', 'next-env.mjs');
const npxCommand = process.platform === 'win32' ? 'npx.cmd' : 'npx';
const localHostnames = new Set(['localhost', '127.0.0.1']);
const execFileAsync = promisify(execFile);

function buildChildEnv() {
  const childEnv = { ...process.env };
  for (const key of Object.keys(childEnv)) {
    if (key.startsWith('NEXT_PUBLIC_')) delete childEnv[key];
  }
  return childEnv;
}

function runCommand(args, env) {
  return new Promise((resolve, reject) => {
    const child = spawn(npxCommand, args, { cwd, env, stdio: 'inherit' });
    child.on('error', reject);
    child.on('exit', (code) => {
      if (code === 0) {
        resolve();
        return;
      }
      reject(new Error(`Command failed (${npxCommand} ${args.join(' ')}), exit code ${code}.`));
    });
  });
}

async function runGit(args, targetCwd = cwd) {
  const { stdout } = await execFileAsync('git', args, { cwd: targetCwd });
  return stdout.trim();
}

async function pathExists(targetPath) {
  try {
    await fs.access(targetPath);
    return true;
  } catch {
    return false;
  }
}

async function isDirectory(targetPath) {
  try {
    return (await fs.stat(targetPath)).isDirectory();
  } catch {
    return false;
  }
}

function createGuardrailError(reason) {
  const details = [
    'Refusing to run a production-style OpenNext command from an unsafe frontend checkout.',
    `Reason: ${reason}`,
    'Required state:',
    '- run from the root repo frontend/ directory',
    '- the root repo must be on branch master, not detached HEAD',
    '- the root checkout must be clean and use a normal .git directory',
    '- frontend must be tracked as ordinary files with no frontend/.git metadata',
    'Remediation:',
    '- switch the root repo onto master',
    '- commit or discard any pending repo changes before deploying',
    '- remove any nested frontend/.git metadata or standalone frontend checkout',
    '- rerun npm run preview, npm run deploy, or npm run upload from root/frontend only',
  ];
  return new Error(details.join('\n'));
}

async function getNamedBranch(repoRoot) {
  try {
    return await runGit(['symbolic-ref', '--quiet', '--short', 'HEAD'], repoRoot);
  } catch {
    return null;
  }
}

async function assertCleanWorkingTree(repoRoot) {
  const status = await runGit(['status', '--porcelain'], repoRoot);
  if (!status) return;
  const preview = status
    .split('\n')
    .filter(Boolean)
    .slice(0, 5)
    .join('\n');
  throw createGuardrailError(`root repo has uncommitted changes:\n${preview}`);
}

async function validateGuardedCommandContext() {
  const repoRoot = await fs.realpath(await runGit(['rev-parse', '--show-toplevel']));
  const frontendRoot = path.resolve(repoRoot, 'frontend');
  const currentDir = await fs.realpath(cwd);
  if (currentDir !== frontendRoot) {
    throw createGuardrailError('command is not running from the root repo frontend/ directory');
  }
  const branch = await getNamedBranch(repoRoot);
  if (!branch) throw createGuardrailError('root repo is detached HEAD');
  if (branch !== 'master') {
    throw createGuardrailError(`root repo is on ${branch}, expected master`);
  }
  if (!(await isDirectory(path.resolve(repoRoot, '.git')))) {
    throw createGuardrailError('root repo is a linked worktree or missing a normal .git directory');
  }
  if (await pathExists(path.resolve(frontendRoot, '.git'))) {
    throw createGuardrailError('frontend/.git exists; nested frontend git metadata is not allowed');
  }
  const frontendTree = await runGit(['ls-tree', 'HEAD', 'frontend'], repoRoot);
  if (!frontendTree.startsWith('040000 tree ')) {
    throw createGuardrailError('root repo HEAD does not track frontend as ordinary files');
  }
  await assertCleanWorkingTree(repoRoot);
}

async function hideEnvLocal() {
  try {
    await fs.access(envLocalPath);
  } catch {
    return null;
  }
  try {
    await fs.unlink(envLocalBackupPath);
  } catch {}
  await fs.rename(envLocalPath, envLocalBackupPath);
  return envLocalBackupPath;
}

async function restoreEnvLocal(hiddenPath) {
  if (!hiddenPath) return;
  await fs.rename(hiddenPath, envLocalPath);
}

function parseProductionEnv(fileContents) {
  const match = fileContents.match(/^export const production = (\{.*\});$/m);
  if (!match) throw new Error('OpenNext did not emit a production env block.');
  return JSON.parse(match[1]);
}

function validateApiUrl(apiUrl) {
  if (!apiUrl) throw new Error('Production build is missing NEXT_PUBLIC_API_URL.');
  const parsed = new URL(apiUrl);
  if (localHostnames.has(parsed.hostname)) {
    throw new Error(`Production build is contaminated with a local API URL: ${apiUrl}`);
  }
}

async function validateProductionEnv() {
  const fileContents = await fs.readFile(nextEnvPath, 'utf8');
  const productionEnv = parseProductionEnv(fileContents);
  validateApiUrl(String(productionEnv.NEXT_PUBLIC_API_URL ?? '').trim());
}

async function main() {
  if (!allowedCommands.has(command)) {
    throw new Error(`Expected one of ${Array.from(allowedCommands).join(', ')}.`);
  }
  if (guardedCommands.has(command)) {
    await validateGuardedCommandContext();
  }
  const childEnv = buildChildEnv();
  let hiddenPath = null;
  try {
    hiddenPath = await hideEnvLocal();
    await runCommand(['opennextjs-cloudflare', 'build'], childEnv);
    await validateProductionEnv();
    if (command !== 'build') await runCommand(['opennextjs-cloudflare', command], childEnv);
  } finally {
    await restoreEnvLocal(hiddenPath);
  }
}

main().catch((error) => {
  console.error('OpenNext production build orchestration failed:', error);
  process.exit(1);
});
