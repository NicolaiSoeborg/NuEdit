import logging
import json
import threading
import multiprocessing as mp
from multiprocessing.synchronize import Event as MpEvent
from time import sleep
from typing import Any, Dict, Optional, Union
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

    def kill(self) -> None:
        stdout, stderr = self.core.communicate('')  # TODO save buffers, etc?
        if self.core.returncode != 0:
            logging.warning(f"[RPC] Killing Xi-core with exit code {self.core.returncode}\n{stdout=}\n{stderr=}")

    def request(self, method: str, params: dict, result: Optional[mp.Queue] = None) -> None:
        """Send {method, params} to Xi. Results of the request will be posted to `result` queue
        """
        data: dict[str, Any] = {'method': method, 'params': params}
        if result:
            self.id += 1
            data['id'] = self.id
            self.backlog[self.id] = result
        else:
            assert result is None, f"Can't get result without request id"

        return self.send_raw_dict(data)

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
                    # If the channel hasn't propegated to shared_state, then spawn a thread and wait for it to appear
                    threading.Thread(target=put_when_ready, args=(self.shared_state, view_id, method, params)).start()

                case data:
                    logging.warning(f"Unhandled message: {data}")

    # RPC STUFF BELOW
    def rpc_available_themes(self, themes: list = []):
        self.shared_state['settings']['available_themes'] = themes

    def rpc_available_languages(self, languages: list = []):
        self.shared_state['settings']['available_languages'] = languages


def put_when_ready(shared_state, view_id: str, method: str, params: dict):
    #logging.debug(f"[BG] Unknown view id ({view_id}) not in {self.shared_state['view_channels']}. Spawning put_when_ready")
    while view_id not in shared_state['view_channels']:
        sleep(.05)
    shared_state['view_channels'][view_id].put((method, params))
