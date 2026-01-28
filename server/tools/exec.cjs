const { spawnSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const isWin = process.platform === 'win32';
const args = process.argv.slice(2);
const tool = args[0];

function setupEnv() {
  process.env.NO_COLOR = '1';
  process.env.DO_NOT_TRACK = '1';
  process.env.DENO_NO_UPDATE_CHECK = '1';
  process.env.DENO_NO_PROMPT = '1';
  process.env.NO_UPDATE_NOTIFIER = '1';
  process.env.NPM_CONFIG_UPDATE_NOTIFIER = 'false';
}

function findLocalBin(startPath, toolName) {
  let current = path.resolve(startPath);
  const root = path.parse(current).root;

  while (true) {
    const binDir = path.join(current, 'node_modules', '.bin');
    const binPath = path.join(binDir, toolName);
    const winBinPath = `${binPath}.cmd`;

    if (fs.existsSync(binPath)) return binPath;
    if (isWin && fs.existsSync(winBinPath)) return winBinPath;
    
    if (current === root) break;
    current = path.dirname(current);
  }
  return null;
}

function runLocalFallback() {
  const localBin = findLocalBin(process.cwd(), tool);

  if (localBin) {
    return exit(exec(localBin, args.slice(1)));
  }

  if (canRun(tool)) {
    return exit(exec(tool, args.slice(1)));
  }

  process.exit(1);
}

function run() {
  if (!tool) return;
  setupEnv();

  // 1. Priority: System npx
  if (canRun('npx')) return exit(exec('npx', args));

  // 2. Registry Fallbacks
  if (canRun('pnpm')) return exit(exec('pnpm', ['dlx', 'npx', ...args]));
  
  if (typeof Bun !== 'undefined' || canRun('bun')) {
    return exit(exec('bun', ['x', 'npx', ...args]));
  }
  
  if (typeof Deno !== 'undefined' || canRun('deno')) {
    return exit(exec('deno', ['run', '-A', 'npm:npx', ...args]));
  }

  // 3. Local/Monorepo Search -> Global PATH
  runLocalFallback();
}

function canRun(cmd) {
  try {
    const checkCmd = isWin ? 'where' : 'which';
    return spawnSync(checkCmd, [cmd], { stdio: 'ignore', shell: isWin }).status === 0;
  } catch { return false; }
}

function exec(cmd, params) {
  return spawnSync(cmd, params, { stdio: 'inherit', shell: isWin });
}

function exit(result) {
  process.exit(result.status ?? 0);
}

run();
