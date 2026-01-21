from __future__ import annotations

import abc
import functools
import json
import os
import re
import shutil
import subprocess
from typing import Iterable, TypeVar

from yt_dlp.extractor.youtube.pot.provider import (
    PoTokenProviderError,
    PoTokenRequest,
    PoTokenResponse,
    register_preference,
    register_provider,
)
from yt_dlp.extractor.youtube.pot.utils import get_webpo_content_binding
from yt_dlp.utils import Popen, int_or_none

from yt_dlp_plugins.extractor.getpot_bgutil import BgUtilPTPBase

T = TypeVar('T')


class BgUtilScriptPTPBase(BgUtilPTPBase, abc.ABC):
    _SCRIPT_BASENAME: str
    _JSRT_NAME: str
    _JSRT_EXEC: str
    _JSRT_VSN_REGEX: str
    _JSRT_MIN_VER: tuple[int, ...]

    @abc.abstractmethod
    def _script_path_impl(self) -> str:
        raise NotImplementedError

    def _jsrt_warn_unavail_impl(self) -> bool:
        return False

    def _jsrt_args(self) -> Iterable[str]:
        return ()

    def _jsrt_path_impl(self) -> str | None:
        report_jsrt_unavail = self.logger.warning if self._jsrt_warn_unavail else self.logger.debug
        jsrt_path = shutil.which(self._JSRT_EXEC)
        if jsrt_path is None:
            # TODO: test if root dir works
            report_jsrt_unavail(
                f'{self._JSRT_NAME} executable not found. Please ensure {self._JSRT_NAME} is installed and available '
                'in PATH or the root directory of yt-dlp.', once=True)
            return None
        try:
            stdout, stderr, returncode = Popen.run(
                [jsrt_path, '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                timeout=int(self._GET_SERVER_VSN_TIMEOUT))
        except subprocess.TimeoutExpired:
            report_jsrt_unavail(
                f'Failed to check {self._JSRT_NAME} version: {self._JSRT_NAME} process '
                'did not finish in {int(self._GET_SERVER_VSN_TIMEOUT)} seconds', once=True)
            return None
        mobj = re.search(self._JSRT_VSN_REGEX, stdout)
        if returncode or not mobj:
            report_jsrt_unavail(
                f'Failed to check {self._JSRT_NAME} version. '
                f'{self._JSRT_NAME} returned {returncode} exit status. '
                f'Process stdout: {stdout}; stderr: {stderr}', once=True)
            return None
        if self._jsrt_has_support(mobj.group(1)):
            return jsrt_path

    def _jsrt_has_support(self, v: str) -> bool:
        report_jsrt_unavail = self.logger.warning if self._jsrt_warn_unavail else self.logger.debug
        if self._jsrt_vsn_tup(v) >= self._JSRT_MIN_VER:
            self.logger.trace(f'{self._JSRT_NAME} version: {v}')
            return True
        else:
            min_vsn_str = '.'.join(str(v_) for v_ in self._JSRT_MIN_VER)
            report_jsrt_unavail(
                f'{self._JSRT_NAME} version too low. '
                f'(got {v}, but at least {min_vsn_str} is required)', once=True)
            return False

    @functools.cached_property
    def _jsrt_warn_unavail(self) -> bool:
        return self._jsrt_warn_unavail_impl()

    @functools.cached_property
    def _script_path(self) -> str:
        return self._script_path_impl()

    @functools.cached_property
    def _jsrt_path(self) -> str | None:
        return self._jsrt_path_impl()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._check_script = functools.cache(self._check_script_impl)

    @staticmethod
    def _jsrt_vsn_tup(v: str):
        return tuple(int_or_none(x, default=0) for x in v.split('.'))

    def _base_config_arg(self, key: str, default: T = None) -> str | T:
        return self.ie._configuration_arg(
            ie_key='youtubepot-bgutilscript', key=key, default=[default])[0]

    @functools.cached_property
    def _server_home(self) -> str:
        # TODO: document this
        resolve_path = lambda *ps: os.path.abspath(
            os.path.expanduser(os.path.expandvars(os.path.join(*ps))))
        if server_home := self._base_config_arg('server_home'):
            return resolve_path(server_home)

        if script_path := self._base_config_arg('script_path'):
            return resolve_path(script_path, os.pardir, os.pardir)

        # default if no arg was passed
        default_home = resolve_path('~', 'bgutil-ytdlp-pot-provider', 'server')
        self.logger.debug(
            f'No server_home or script_path passed, defaulting to {default_home}')
        return default_home

    @functools.cached_property
    def _script_cache_dir(self) -> str:
        # don't use _HOMEDIR as the server is coded this way and accepts HOME and USERPROFILE regardless of the OS
        home_dir = os.getenv('HOME') or os.getenv('USERPROFILE')
        if (xdg_cache := os.getenv('XDG_CACHE_HOME')) is not None:
            return os.path.abspath(os.path.join(xdg_cache, 'bgutil-ytdlp-pot-provider'))
        elif home_dir:
            return os.path.abspath(os.path.join(home_dir, '.cache', 'bgutil-ytdlp-pot-provider'))
        else:
            return self._server_home

    def is_available(self) -> bool:
        return self._check_script(self._script_path)

    def _check_script_impl(self, script_path) -> bool:
        if not os.path.isfile(script_path):
            self.logger.debug(
                f"Script path doesn't exist: {script_path}")
            return False
        if os.path.basename(script_path) != self._SCRIPT_BASENAME:
            self.logger.warning(
                f'The script path passed in the extractor argument '
                f'has a wrong base name, expected {self._SCRIPT_BASENAME}.', once=True)
            return False
        if not self._jsrt_path:
            return False
        stdout, stderr, returncode = Popen.run(
            [self._jsrt_path, *self._jsrt_args(), script_path, '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            timeout=int(self._GET_SERVER_VSN_TIMEOUT))
        if returncode:
            self.logger.warning(
                f'Failed to check script version. '
                f'Script returned {returncode} exit status. '
                f'Script stdout: {stdout}; Script stderr: {stderr}',
                once=True)
            return False
        else:
            self._check_version(stdout.strip(), name='script')
            return True

    def _real_request_pot(
        self,
        request: PoTokenRequest,
    ) -> PoTokenResponse:
        # used for CI check
        self.logger.trace(
            f'Generating POT via script: {self._script_path}')

        command_args = [self._jsrt_path, *self._jsrt_args(), self._script_path]
        if proxy := request.request_proxy:
            command_args.extend(['-p', proxy])
        command_args.extend(['-c', get_webpo_content_binding(request)[0]])
        if request.bypass_cache:
            command_args.append('--bypass-cache')
        if request.request_source_address:
            command_args.extend(
                ['--source-address', request.request_source_address])
        if request.request_verify_tls is False:
            command_args.append('--disable-tls-verification')

        self.logger.info(
            f'Generating a {request.context.value} PO Token for '
            f'{request.internal_client_name} client via bgutil script',
        )
        self.logger.debug(
            f'Executing command to get POT via script: {" ".join(command_args)}')

        try:
            stdout, stderr, returncode = Popen.run(
                command_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                timeout=int(self._GETPOT_TIMEOUT))
        except subprocess.TimeoutExpired as e:
            raise PoTokenProviderError(
                f'_get_pot_via_script failed: Timeout expired when trying to run script (caused by {e!r})')
        except Exception as e:
            raise PoTokenProviderError(
                f'_get_pot_via_script failed: Unable to run script (caused by {e!r})') from e

        msg = ''
        if stdout_extra := stdout.strip().splitlines()[:-1]:
            msg = f'stdout:\n{stdout_extra}\n'
        if stderr_stripped := stderr.strip():  # Empty strings are falsy
            msg += f'stderr:\n{stderr_stripped}\n'
        msg = msg.strip()
        if msg:
            self.logger.trace(msg)
        if returncode:
            raise PoTokenProviderError(
                f'_get_pot_via_script failed with returncode {returncode}')

        try:
            json_resp = stdout.splitlines()[-1]
            self.logger.trace(f'JSON response:\n{json_resp}')
            # The JSON response is always the last line
            script_data_resp = json.loads(json_resp)
        except json.JSONDecodeError as e:
            raise PoTokenProviderError(
                f'Error parsing JSON response from _get_pot_via_script (caused by {e!r})') from e
        if 'poToken' not in script_data_resp:
            raise PoTokenProviderError(
                'The script did not respond with a po_token')
        return PoTokenResponse(po_token=script_data_resp['poToken'])


@register_provider
class BgUtilScriptNodePTP(BgUtilScriptPTPBase):
    PROVIDER_NAME = 'bgutil:script-node'
    _SCRIPT_BASENAME = 'generate_once.js'
    _JSRT_NAME = 'Node.js'
    _JSRT_EXEC = 'node'
    _JSRT_VSN_REGEX = r'^v(\S+)'
    _JSRT_MIN_VER = (20, 0, 0)

    def _jsrt_warn_unavail_impl(self) -> bool:
        return self._base_config_arg('prefer_node', 'false') != 'false'

    def _script_path_impl(self) -> str:
        return os.path.join(
            self._server_home, 'build', self._SCRIPT_BASENAME)


@register_preference(BgUtilScriptNodePTP)
def bgutil_script_node_getpot_preference(provider: BgUtilScriptNodePTP, request):
    return 10 if provider._base_config_arg('prefer_node', 'false') != 'false' else 1


@register_provider
class BgUtilScriptDenoPTP(BgUtilScriptPTPBase):
    PROVIDER_NAME = 'bgutil:script-deno'
    _SCRIPT_BASENAME = 'generate_once.ts'
    _JSRT_NAME = 'Deno'
    _JSRT_EXEC = 'deno'
    _JSRT_VSN_REGEX = r'^deno (\S+)'
    _JSRT_MIN_VER = (2, 0, 0)

    def _jsrt_warn_unavail_impl(self) -> bool:
        return self._base_config_arg('prefer_node') == 'false'

    def _script_path_impl(self) -> str:
        return os.path.join(
            self._server_home, 'src', self._SCRIPT_BASENAME)

    def _jsrt_args(self) -> Iterable[str]:
        # TODO: restrict permissions!
        return (
            'run', '--unstable-sloppy-imports',
            '--allow-env', '--allow-net',
            f'--allow-ffi={self._server_home}',
            f'--allow-write={self._script_cache_dir}',
            f'--allow-read={self._script_cache_dir}',
        )


@register_preference(BgUtilScriptDenoPTP)
def bgutil_script_deno_getpot_preference(provider: BgUtilScriptDenoPTP, request):
    return 1 if provider._base_config_arg('prefer_node', 'false') != 'false' else 10


__all__ = [
    BgUtilScriptNodePTP.__name__,
    bgutil_script_node_getpot_preference.__name__,
    BgUtilScriptDenoPTP.__name__,
    bgutil_script_deno_getpot_preference.__name__,
]
