import logging
import json
import threading
import multiprocessing as mp
from multiprocessing.synchronize import Event as MpEvent
from time import sleep
from typing import Dict, Optional, Union
from subprocess import Popen, PIPE, DEVNULL

#from prompt_toolkit.patch_stdout import patch_stdout

#from enum import Enum, unique
#@unique
#class TasksEnum(Enum):
#    DEBUG = auto()
#    SOMETHING = 2


class RpcController:
    def __init__(self, shared_state: dict, rpc_ready: MpEvent):
        self.id = 0
        self.shared_state = shared_state
        self.backlog: dict[int, mp.Queue] = {}
        self.core = Popen(["/tmp/xi-core"],
            stdin=PIPE, stdout=PIPE, stderr=DEVNULL,
            universal_newlines=True, bufsize=1
        )
        self.send_raw_dict({"method": "client_started", "params": {}})
        rpc_ready.set()

    def request(self, method: str, params: dict, result: Optional[mp.Queue] = None) -> None:
        self.id += 1
        if result:
            self.backlog[self.id] = result
        self.send_raw_dict({'id': self.id, 'method': method, 'params': params})

    def notify(self, method: str, params: dict = {}) -> None:
        """ Like 'request' but w/o request-id """
        self.send_raw_dict({'method': method, 'params': params})

    def edit(self, method: str, params: Union[dict, list] = {}, view_id: Optional[str] = None) -> None:
        view_id = self.shared_state['focused_view'] if view_id is None else view_id
        self.notify('edit', {'method': method, 'params': params, 'view_id': view_id})

    def edit_request(self, method: str, params: dict, result: mp.Queue) -> None:
        """ Special handling of some 'edit' methods (copy/cut/etc). """
        assert result is not None, "edit_request will return a result"
        self.request(method, params, result)

    def kill(self, result = None) -> None:
        assert result is None
        stdout, stderr = self.core.communicate('')  # TODO save buffers, etc?
        if self.core.returncode != 0:
            logging.warning(f"[RPC] Killing Xi-core with exit code {self.core.returncode}\n{stdout=}\n{stderr=}")

    def send_raw_dict(self, d: dict) -> None:
        logging.debug(f"[RPC] Sending {json.dumps(d)}")
        assert self.core.stdin is not None
        self.core.stdin.write(json.dumps(d) + "\n")
        self.core.stdin.flush()

    def _receive(self) -> dict:
        assert self.core.stdout is not None
        raw = self.core.stdout.readline()
        logging.debug("[RPC] Receiving: " + (raw or "[none] ")[:-1])
        return json.loads(raw or '{"todo":"kill_bg_worker"}')

    @staticmethod
    def bg_worker(self) -> None:
        while True:
            match self._receive():
                case {"todo": "kill_bg_worker"}:
                    return

                case {'error': error}:
                    logging.error(f'Got err from Xi: {error}')

                # Xi -> General view result
                case {'id': _id, 'result': result}:
                    self.backlog[_id].put(result)
                    del self.backlog[_id]

                # Xi -> RPC (settings, configs, etc)
                case {'method': method, "params": params} if hasattr(self, f'rpc_{method}'):
                    getattr(self, f'rpc_{method}')(**params)

                # Xi -> View specific settings
                case {'method': method, "params": {"view_id": view_id, **params}} if view_id in self.shared_state['view_channels']:
                    self.shared_state['view_channels'][view_id].put((method, params))
                case {'method': method, "params": {"view_id": view_id, **params}}:
                    # Unknown view id (view-id-1) not in {'view-id-1': <AutoProxy[Queue] object, typeid 'Queue' at 0x7fa676198190>}
                    logging.debug(f"[BG] Unknown view id ({view_id}) not in {self.shared_state['view_channels']}. Spawning put_when_ready")
                    threading.Thread(target=put_when_ready, args=(self.shared_state, view_id, method, params)).start()

                case data:
                    logging.warning(f"Unhandled message: {data}")

    # RPC STUFF BELOW
    def rpc_available_themes(self, themes: list = []):
        self.shared_state['settings']['available_themes'] = themes

    def rpc_available_languages(self, languages: list = []):
        self.shared_state['settings']['available_languages'] = languages


def put_when_ready(shared_state, view_id: str, method: str, params: dict):
    while view_id not in shared_state['view_channels']:
        sleep(.05)
    shared_state['view_channels'][view_id].put((method, params))
