import logging
import multiprocessing as mp
from multiprocessing.synchronize import Event as MpEvent  # for typing
import threading
from typing import Any, Dict, Optional, Union
from yaml import safe_load

from .rpc import RpcController
from .view import View


def editor(files: list):
    logging.debug("[MAIN] App started")

    with open('settings.yaml') as f:
        global_settings = safe_load(f)

    with mp.Manager() as manager:
        rpc_channel = manager.Queue()

        # monkey patch rpc_channel to support often used "put operations"
        def _f(method: str, params: dict = {}, result: Optional[mp.Queue] = None):
            rpc_channel.put((method, params, result))
        rpc_channel.f = _f

        def _notify(method: str, params: Optional[dict] = {}):
            rpc_channel.f('notify', {'method': method, 'params': params})
        rpc_channel.notify = _notify

        def _edit(method: str, params: Union[dict, list] = {}, view_id: Optional[str] = None):
            rpc_channel.f('edit', {'method': method, 'params': params, 'view_id': view_id})
        rpc_channel.edit = _edit

        def _edit_request(method: str, params: Optional[dict], result: mp.Queue):
            rpc_channel.f('edit_request', {'method': method, 'params': params}, result)
        rpc_channel.edit_request = _edit_request

        shared_state: dict[str, Any] = manager.dict({
            'settings': manager.dict(global_settings),
            'styles': manager.dict({
                'cursor': 'reverse underline',
                'selection': 'reverse',           0: 'reverse',
                'find': 'fg:ansiyellow bg:black', 1: 'fg:ansiyellow bg:black',
            }),
            'view_channels': manager.dict(), # {view_id: view-channel-queue}
            'focused_view': 'filemanager',
        })
        rpc_ready = manager.Event()

        p = mp.Process(target=backend_process, args=(rpc_ready, shared_state, rpc_channel))
        p.start()

        logging.debug("[MAIN] Waiting for RPC")
        rpc_ready.wait()
        logging.debug("[MAIN] RPC ready")

        v = View(manager, shared_state, rpc_channel)
        v.fileman_visible = len(files) == 0
        for file in files:
            v.new_view(file)

        v.app.run()  # blocks until editor exits
        logging.debug("[MAIN] Shutting down")

        assert len(v.views) == 0, "Views not closed: {}".format(v.views)
        # while len(v.views) != 0:
        #    print("Waiting for {} to shutdown.".format(v.views.keys()))
        #    sleep(.1)
        rpc_channel.f('kill')
        p.join()


def backend_process(rpc_ready: MpEvent, shared_state: dict, rpc_channel: mp.Queue):
    rpc = RpcController(shared_state, rpc_ready)

    thread = threading.Thread(target=RpcController.bg_worker, args=(rpc, ))
    thread.start()

    rpc_ready.wait()
    while True:
        (method, params, result) = rpc_channel.get()
        assert hasattr(rpc, method), "[RPC] Unknown task: {}".format(method)
        if method == 'kill':
            rpc.kill()
            break
        elif result is None:
            getattr(rpc, method)(**params)
        else:
            getattr(rpc, method)(**params, result=result)
    thread.join()
