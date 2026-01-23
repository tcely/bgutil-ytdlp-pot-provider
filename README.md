# BgUtils POT Provider

> [!CAUTION]
> Providing a PO token does not guarantee bypassing 403 errors or bot checks, but it _may_ help your traffic seem more legitimate.

[![Docker Image Version (tag)](https://img.shields.io/docker/v/brainicism/bgutil-ytdlp-pot-provider/latest?style=for-the-badge&label=docker)](https://hub.docker.com/r/brainicism/bgutil-ytdlp-pot-provider)
[![GitHub Release](https://img.shields.io/github/v/release/Brainicism/bgutil-ytdlp-pot-provider?style=for-the-badge)](//github.com/Brainicism/bgutil-ytdlp-pot-provider/releases)
[![PyPI - Version](https://img.shields.io/pypi/v/bgutil-ytdlp-pot-provider?style=for-the-badge)](https://pypi.org/project/bgutil-ytdlp-pot-provider/)
[![CI Status](https://img.shields.io/github/actions/workflow/status/Brainicism/bgutil-ytdlp-pot-provider/test.yml?branch=master&label=Tests&style=for-the-badge)](//github.com/Brainicism/bgutil-ytdlp-pot-provider/actions/workflows/test.yml)

[Frequently Asked Questions](//github.com/Brainicism/bgutil-ytdlp-pot-provider?tab=readme-ov-file#faq)

A proof-of-origin token (POT) provider for [`yt-dlp`](//github.com/yt-dlp/yt-dlp). We use [LuanRT's Botguard interfacing library](//github.com/LuanRT/BgUtils) to generate the token.
This is used to bypass the "Sign in to confirm you're not a bot" message when invoking `yt-dlp` from an IP address flagged by YouTube. See _[PO Token Guide](//github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide)_ for more details.

The system consists of two parts:

1. **Provider**: Two options -
   - (a) An HTTP server that generates the POT, and provides interfaces for the plugin to retrieve data from (easy setup + docker image provided)
   - (b) A POT generation script, which provides command line options for the plugin to invoke (the script requires transpiling before the plugin uses it)
2. **Provider plugin**: uses the POT plugin framework to retrieve data from the provider, allowing `yt-dlp` to simulate having passed the 'bot check'.

## Installation

### Base Requirements

1. Requires [`yt-dlp`](//github.com/yt-dlp/yt-dlp) `2025.05.22` or newer.

2. If using the Docker image for option (a) for the provider, the Docker runtime is required.  
   Otherwise, Node.js (>= 20) is required.

3. To obtain the provider and plugin files you will need one of these options:
   - a compressed archive and a utility to extract that archive
   - `git` to clone the repository

### 1. Set up the provider

There are two options for the provider; an always running POT generation HTTP server, and a POT generation script invoked when needed. The HTTP server option is simpler, faster, and comes with a prebuilt Docker image. **You only need to choose one option.**

#### (a) HTTP Server Option

The provider is a Node.js HTTP server. You can run it as a prebuilt Docker image or manually as a Node.js application.

**Docker:**

```shell
docker run --name bgutil-pot-provider --init -d -p 4416:4416 brainicism/bgutil-ytdlp-pot-provider
```

> [!IMPORTANT]
> Note that the Docker container's network is isolated from your local network by default. If you are using a local proxy server, it will not be accessible from within the container unless you pass `--net=host` as well.

**Native:**

```shell
# Replace 1.2.2 with the latest version or the one that matches the plugin
git clone --single-branch --branch 1.2.2 https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git
cd bgutil-ytdlp-pot-provider/server/
npm install
npx tsc
node build/main.js
```

**Server Command Line Options**

- `-p, --port <PORT>`: The port (default: 4416) on which the server listens.

#### (b) Generation Script Option

> [!IMPORTANT]
> This method is not recommended for high concurrency usage. Every `yt-dlp` call incurs the overhead of spawning a new node process to run the script. This method also handles cache concurrency poorly.

1. Transpile the generation script to JavaScript:

```shell
# If you want to use this method without specifying `script_path` extractor argument
# on each yt-dlp invocation, clone/extract the source code into your home directory.
# Replace `~` with `%USERPROFILE%` if using Windows
cd ~
# Replace 1.2.2 with the latest version or the one that matches the plugin
git clone --single-branch --branch 1.2.2 https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git
cd bgutil-ytdlp-pot-provider/server/
npm install
npx tsc
```

2. Make sure `node` is available in your `PATH`.

### 2. Install the plugin

#### PyPI:

If `yt-dlp` is installed through `pip` or `pipx`, you can install the plugin with the following:

```shell
python3 -m pip install -U bgutil-ytdlp-pot-provider
```

#### Manual:

1. Download the plugin [archive](//github.com/Brainicism/bgutil-ytdlp-pot-provider/releases/latest/download/bgutil-ytdlp-pot-provider.zip) file from the [latest release](//github.com/Brainicism/bgutil-ytdlp-pot-provider/releases/latest).
2. Install it by placing the zip file into one of the [plugin folders](//github.com/yt-dlp/yt-dlp#installing-plugins) used by `yt-dlp`.

## Usage

If using option (a) HTTP Server for the provider, and the default IP/port number, you can use `yt-dlp` like normal 🙂.

If you want to change the port number used by the provider server, use the `--port` option.

```shell
node build/main.js --port 8080
```

If changing the port or IP used for the provider server, pass it to `yt-dlp` via `base_url`

```shell
--extractor-args "youtubepot-bgutilhttp:base_url=http://127.0.0.1:8080"
```

If the tokens are no longer working, passing `disable_innertube=1` to `yt-dlp` restores the legacy behaviour and _might_ help

```shell
--extractor-args "youtubepot-bgutilhttp:base_url=http://127.0.0.1:8080;disable_innertube=1"
```

Note that when you pass multiple extractor arguments to one provider or extractor (in this case: `youtubepot-bgutilhttp`), they are to be separated by semicolons (`;`) as shown above. Multiple `--extractor-args` will **NOT** work for the same provider/extractor.

---

If using option (b) generation script for the provider, with the default script location in your home directory (i.e: `~/bgutil-ytdlp-pot-provider` or `%USERPROFILE%\bgutil-ytdlp-pot-provider`), you can also use `yt-dlp` like normal.

If you installed the script in a different location, pass it as the extractor argument `script_path` to `youtube-bgutilscript` for each `yt-dlp` call.

```shell
--extractor-args "youtubepot-bgutilscript:script_path=/path/to/bgutil-ytdlp-pot-provider/server/build/generate_once.js"
```

---

We use a cache internally for all generated tokens when option (b) generation script is used. You can change the TTL (time to live) for the token cache with the environment variable `TOKEN_TTL` (in hours; default: 6). It's not currently possible to use different TTLs for different token contexts (can be `gvs`, `player`, or `subs`, see [Technical Details](//github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide#technical-details) from the PO Token Guide).  
That is, when using the script method, you can set a `TOKEN_TTL` before calling `yt-dlp` to use a custom TTL for PO Tokens.

---

If both methods are available for use, the option (a) HTTP server will be prioritized.

### Verification

To check if the plugin was installed correctly, you should see the `bgutil` providers in the verbose output from `yt-dlp`: `yt-dlp -v YOUTUBE_URL`.

```
[debug] [youtube] [pot] PO Token Providers: bgutil:http-1.2.2 (external), bgutil:script-1.2.2 (external)
```

### FAQ

#### I'm getting errors during `npm install` on Termux

For provider versions >=1.2.0, you may have issues while installing the `canvas` dependency on Termux. The Termux environment is missing a `android_ndk_path` and two packages by default. Run the following commands to setup the dependencies correctly.

1. Install the packages.
```shell
pkg install libvips xorgproto
```

2. Create the shell function to adjust `~/.gyp/include.gypi` for us.
```shell
update_gyp_config() (
  set -eu
  mkdir -p ~/.gyp
  cd ~/.gyp
  tmp_dir="$(mktemp -d ./tmp.XXXXXX)"
  if [ -s include.gypi ]; then
    cp -p include.gypi "${tmp_dir}/old"
    cp -p "${tmp_dir}/old" "${tmp_dir}/new"
    if ! grep -q 'android_ndk_path' "${tmp_dir}/new"; then
      if grep -q "'variables':[[:space:]]*{" "${tmp_dir}/new"; then
        sed "s/'variables':[[:space:]]*{/'variables':{'android_ndk_path':'',/" "${tmp_dir}/old" > "${tmp_dir}/new"
      else
        sed "1s/{/{'variables':{'android_ndk_path':''},/" "${tmp_dir}/old" > "${tmp_dir}/new"
      fi
    fi
  else
    printf > "${tmp_dir}/old" -- ''
    printf > "${tmp_dir}/new" -- "{'variables':{'android_ndk_path':''}}\n"
  fi
  if cmp -s "${tmp_dir}/old" "${tmp_dir}/new"; then
    printf 'No changes to apply.\n'
    rm -rf "${tmp_dir}"
  else
    printf 'Status of changes for ~/.gyp/include.gypi:\n'
    diff -su "${tmp_dir}/old" "${tmp_dir}/new" || true
    if mv -v -i "${tmp_dir}/new" include.gypi; then
      rm -rf "${tmp_dir}"
    else
      printf 'Changes not applied. Workspace preserved at: ~/.gyp/%s\n' "${tmp_dir#./}"
    fi
  fi
  if ! [ -d "${tmp_dir}" ]; then
    printf 'Cleanup complete.\n'
  fi
)

```

3. Call the newly created `update_gyp_config` function to actually adjust the `~/.gyp/include.gypi` file.
```shell
update_gyp_config
```

Alternatively, you can handle the modification with Python instead of using `sed` to perform text manipulation.

1. Open the Python REPL:
```shell
python3
```

2. Define the Python function to adjust the file.
```py
import ast, shutil, tempfile, subprocess
from pathlib import Path

def update_gyp_config():
  try:
    g_dir = Path.home() / '.gyp'
    g_dir.mkdir(parents=True, exist_ok=True)
    target = g_dir / 'include.gypi'

    with tempfile.TemporaryDirectory(dir=g_dir, prefix='tmp.') as t:
      t_p = Path(t)
      old, new = t_p / 'old', t_p / 'new'
      
      if target.exists() and 0 < target.stat().st_size:
        shutil.copy2(target, old)
        data = ast.literal_eval(old.read_text())
        if 'android_ndk_path' in data.get('variables', {}):
          print('No changes to apply.'); return
        
        data.setdefault('variables', {})['android_ndk_path'] = ''
        new.write_text(repr(data))
      else:
        old.touch()
        new.write_text("{'variables':{'android_ndk_path':''}}")

      print('Status of changes:')
      subprocess.run(['diff', '-su', old, new])
      if 0 == subprocess.run(['mv', '-v', '-i', new, target]).returncode:
        print('Changes applied.')
  except Exception as e:
    print(f'Error: {e}')

# Press Enter again if the prompt is still indented

```

3. When you are ready, and there were no errors, call that function with:
```py
update_gyp_config()
```

4. Close the Python REPL and return to your shell with:
```py
exit()
```
