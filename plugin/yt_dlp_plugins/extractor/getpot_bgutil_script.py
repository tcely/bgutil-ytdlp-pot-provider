from __future__ import annotations

import abc
import functools
import json
import os.path
import re
import shutil
import subprocess
from typing import Iterable, TypeVar

from yt_dlp.extractor.youtube.pot.provider import (
    PoTokenProvider,
    PoTokenProviderError,
    PoTokenRequest,
    PoTokenResponse,
    register_preference,
    register_provider,
)
from yt_dlp.extractor.youtube.pot.utils import get_webpo_content_binding
from yt_dlp.utils import Popen

from yt_dlp_plugins.extractor.getpot_bgutil import BgUtilPTPBase

T = TypeVar('T')


class BgUtilScriptPTPBase(BgUtilPTPBase, abc.ABC):
    _SCRIPT_BASENAME: str

    @abc.abstractmethod
    def _script_path_impl(self) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def _jsrt_args(self) -> Iterable[str]:
        return ()

    @abc.abstractmethod
    def _jsrt_path_impl(self) -> str | None:
        return None

    _MIN_NODE_VSN = (20, 0, 0)
    _HOMEDIR = os.path.expanduser('~')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._check_script = functools.cache(self._check_script_impl)

    def _base_config_arg(self, key: str, default: T = None) -> str | T:
        return self.ie._configuration_arg(
            ie_key='youtubepot-bgutilscript', key=key, default=[default])[0]

    @functools.cached_property
    def _script_path(self) -> str:
        return self._script_path_impl()

    @functools.cached_property
    def _jsrt_path(self) -> str | None:
        return self._jsrt_path_impl()

    def is_available(self):
        return self._check_script(self._script_path)

    def _check_script_impl(self, script_path):
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
            timeout=self._GET_SERVER_VSN_TIMEOUT)
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
                timeout=self._GETPOT_TIMEOUT)
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

    def _script_path_impl(self) -> str:
        if script_path := self._base_config_arg('script_path'):
            return os.path.expandvars(script_path)

        # default if no arg was passed
        default_path = os.path.join(
            self._HOMEDIR, 'bgutil-ytdlp-pot-provider', 'server', 'build', self._SCRIPT_BASENAME)
        self.logger.debug(
            f'No script path passed, defaulting to {default_path}')
        return default_path

    def _jsrt_path_impl(self) -> str | None:
        node_path = shutil.which('node')
        if node_path is None:
            self.logger.error('Node.js executable not found. Please ensure Node.js is installed and available in PATH.')
            return None
        try:
            stdout, stderr, returncode = Popen.run(
                [node_path, '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                timeout=self._GET_SERVER_VSN_TIMEOUT)
            stdout = stdout.strip()
            mobj = re.match(r'v(\d+)\.(\d+)\.(\d+)', stdout)
            if returncode or not mobj:
                raise ValueError
            node_vsn = tuple(map(int, mobj.groups()))
            if node_vsn >= self._MIN_NODE_VSN:
                self.logger.trace(f'Node version: {node_vsn}')
                return node_path
            raise RuntimeError
        except RuntimeError:
            min_vsn_str = 'v' + '.'.join(str(v) for v in self._MIN_NODE_VSN)
            self.logger.warning(
                f'Node version too low. '
                f'(got {stdout}, but at least {min_vsn_str} is required)')
        except (subprocess.TimeoutExpired, ValueError):
            self.logger.warning(
                f'Failed to check node version. '
                f'Node returned {returncode} exit status. '
                f'Node stdout: {stdout}; Node stderr: {stderr}')


@register_preference(BgUtilScriptNodePTP)
def bgutil_script_node_getpot_preference(provider: PoTokenProvider, request):
    return 10 if provider._base_config_arg('prefer_node', 'false') != 'false' else 1


@register_provider
class BgUtilScriptDenoPTP(BgUtilScriptPTPBase):
    PROVIDER_NAME = 'bgutil:script-deno'

    _SCRIPT_BASENAME = 'generate_once.ts'


@register_preference(BgUtilScriptDenoPTP)
def bgutil_script_deno_getpot_preference(provider: BgUtilScriptDenoPTP, request):
    return 1 if provider._base_config_arg('prefer_node', 'false') != 'false' else 10


__all__ = [
    BgUtilScriptNodePTP.__name__,
    bgutil_script_node_getpot_preference.__name__,
    BgUtilScriptDenoPTP.__name__,
    bgutil_script_deno_getpot_preference.__name__,
]
