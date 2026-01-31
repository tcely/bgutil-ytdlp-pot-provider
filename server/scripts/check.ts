// https://github.com/yt-dlp/ejs/blob/main/check.py
import * as path from "node:path";
import * as fs from "node:fs";

const serverHome = path.resolve(import.meta.dirname, "..");

function getDenoPkgs() {
    let pkgs: Record<string, string> = {};
    const { version, npm } = JSON.parse(fs.readFileSync(path.resolve(
        serverHome, "deno.lock")).toString());
    if (version < 4 || version > 5)
        throw new Error(`Unsupported deno.lock lockfile version ${version}`);

    for (const name in npm) {
        const { integrity } = npm[name];
        const other = pkgs[integrity];
        if (other && other !== name)
            throw new Error(
                `Duplicate integrity for ${name} and ${other}: ${integrity}`);
        pkgs[integrity] = name;
    }
    return pkgs;
}

function getNodePkgs() {
    let pkgs: Record<string, string> = {};
    const { lockfileVersion: version , packages: npm } = JSON.parse(fs.readFileSync(
        path.resolve(serverHome, "package-lock.json")).toString());
    if (version !== 3)
        throw new Error(
            `Unsupported package-lock.json lockfile version ${version}`);

    for (const name in npm) {
        if (!name.length) continue;
        const module = name.split("node_modules/").pop();
        const { version, integrity } = npm[name];
        const pkgSpec = `${module}@${version}`;
        const other = pkgs[integrity];
        if (other && other !== pkgSpec)
            throw new Error(
                `Duplicate integrity for ${pkgSpec} and ${other}: ${integrity}`);
        pkgs[integrity] = pkgSpec;
    }
    return pkgs;
}

try {
    const denoPkgs = getDenoPkgs();
    const nodePkgs = getNodePkgs();

    for (const denoIt in denoPkgs)
        if (!(denoIt in nodePkgs))
            console.log(`Deno extra: ${denoPkgs[denoIt]}, integrity ${denoIt}`);

    for (const nodeIt in nodePkgs)
        if (!(nodeIt in denoPkgs))
            console.log(`Node extra: ${nodePkgs[nodeIt]}, integrity ${nodeIt}`);
} catch (e) {
    console.error(`ERROR: ${e.message}`);
}
