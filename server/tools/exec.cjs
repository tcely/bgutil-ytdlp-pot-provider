const { spawnSync } = require("child_process");
const path = require("path");
const fs = require("fs");
const os = require("os");

const TARGET_VERSION = "v20.18.0";

const WIN_NODE_WRAPPER = "@echo off\r\n" +
    `if "%~1"=="--version" (echo ${TARGET_VERSION} & exit /b 0)\r\n` +
    "deno run -A %*";

const POSIX_NODE_WRAPPER = "#!/usr/bin/env sh\n" +
    `if [ "1:--version" = "$#:$1" ]; then echo "${TARGET_VERSION}"; exit 0; fi\n` +
    "exec deno run -A \"$@\"";

const isWin = "win32" === process.platform;
const args = process.argv.slice(2);
const tool = args[0];

/**
 * Generates platform-specific fallback paths for Node, Deno, Bun, and pnpm.
 */
function getFallbacks() {
    const home = os.homedir();
    
    const bunBin = path.join(process.env.BUN_INSTALL || path.join(home, ".bun"), "bin");
    const denoBin = path.join(process.env.DENO_INSTALL || path.join(home, ".deno"), "bin");
    const pnpmBin = process.env.PNPM_HOME || (isWin 
        ? path.join(home, "AppData", "Local", "pnpm") 
        : path.join(home, ".local", "share", "pnpm"));

    const commonBins = [bunBin, denoBin, pnpmBin, path.join(home, ".local", "bin")];

    if (isWin) {
        return [
            process.env.PATH || "",
            ...commonBins,
            path.join(home, "AppData", "Roaming", "npm")
        ].join(path.delimiter);
    }

    return [
        "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin",
        "/opt/homebrew/bin",
        ...commonBins
    ].join(path.delimiter);
}

/**
 * Returns normalized system paths and local node_modules/.bin paths.
 */
function getBasePaths() {
    const rawPath = process.env.PATH || getFallbacks();
    
    const systemPaths = Array.from(new Set(
        rawPath.split(path.delimiter)
            .filter(Boolean)
            .map(p => path.normalize(p))
    ));

    const localPaths = [];
    let current = path.resolve(process.cwd());
    const root = path.parse(current).root;

    while (current !== root) {
        const binDir = path.join(current, "node_modules", ".bin");
        if (fs.existsSync(binDir)) {
            localPaths.push(binDir);
        }
        current = path.dirname(current);
    }

    return { systemPaths, localPaths };
}

function canRun(cmd) {
    if (isWin) {
        try {
            return 0 === spawnSync("where", [cmd], { stdio: "ignore", shell: true }).status;
        } catch { return false; }
    }

    // const { systemPaths, localPaths } = getBasePaths();
    // canRun priority: System paths only
    const rawPath = process.env.PATH || "";
    const systemPaths = Array.from(new Set(
        rawPath.split(path.delimiter)
            .filter(Boolean)
            .map(p => path.normalize(p))
    ));
    const localPaths = [];
    for (const dir of [...systemPaths, ...localPaths]) {
        const fullPath = path.join(dir, cmd);
        try {
            const stats = fs.statSync(fullPath);
            if (stats.isFile() && (stats.mode & 0o111)) return true;
        } catch { continue; }
    }
    return false;
}

function findLocalBin(toolName) {
    const { systemPaths, localPaths } = getBasePaths();
    // findLocalBin priority: Local node_modules first
    for (const dir of [...localPaths, ...systemPaths]) {
        const binPath = path.join(dir, toolName);
        const winBinPath = `${binPath}.cmd`;

        if (fs.existsSync(binPath)) return binPath;
        if (isWin && fs.existsSync(winBinPath)) return winBinPath;
    }
    return null;
}

function writeNodeWrapper(wrapperPath) {
    let shouldUpdate = !fs.existsSync(wrapperPath);

    if (!shouldUpdate) {
        const content = fs.readFileSync(wrapperPath, "utf8");
        if (!content.includes(TARGET_VERSION)) {
            shouldUpdate = true;
        }
    }

    if (shouldUpdate) {
        const content = isWin ? WIN_NODE_WRAPPER : POSIX_NODE_WRAPPER;
        fs.writeFileSync(wrapperPath, content, { mode: 0o755 });
    }
}

function setupEnv() {
    process.env.NO_COLOR = "1";
    process.env.DO_NOT_TRACK = "1";
    process.env.DENO_NO_UPDATE_CHECK = "1";
    process.env.DENO_NO_PROMPT = "1";
    process.env.NO_UPDATE_NOTIFIER = "1";
    process.env.NPM_CONFIG_UPDATE_NOTIFIER = "false";

    const wrapperDir = path.join(process.cwd(), "node_modules", ".wrapper");
    if (!fs.existsSync(wrapperDir)) {
        fs.mkdirSync(wrapperDir, { recursive: true });
    }

    const nodeWrapperPath = path.join(wrapperDir, isWin ? "node.cmd" : "node");
    writeNodeWrapper(nodeWrapperPath);

    process.env.PATH = `${process.env.PATH}${path.delimiter}${wrapperDir}`;
}

function runLocalFallback() {
    const localBin = findLocalBin(tool);
    if (localBin) return exit(exec(localBin, args.slice(1)));
    process.exit(1);
}

function exec(cmd, params) {
    return spawnSync(cmd, params, {
        env: process.env,
        shell: isWin,
        stdio: "inherit",
    });
}

function exit(result) {
    process.exit(result.status ?? 0);
}

function run() {
    if (!tool) return;
    setupEnv();

    // 1. Priority: System npx
    if (canRun("npx")) return exit(exec("npx", ["--yes", ...args]));
    if (canRun("npm")) return exit(exec("npm", ["--yes", "exec", ...args]));

    // 2. Registry Fallbacks
    if (canRun("pnpm")) return exit(exec("pnpm", ["--", "dlx", "npm", "--yes", "exec", ...args]));

    if ("undefined" !== typeof Bun || canRun("bun")) {
        return exit(exec("bun", ["x", "--shell=bun", "--bun", "--", "npm", "--yes", "exec", ...args]));
    }

    if ("undefined" !== typeof Deno || canRun("deno")) {
        return exit(exec("deno", ["run", "-A", "--", "npm:npm", "--yes", "exec", ...args]));
    }

    // 3. Local/Monorepo Search -> Global PATH
    runLocalFallback();
}

run();
