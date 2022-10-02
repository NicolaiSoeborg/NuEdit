import logging
from multiprocessing.managers import DictProxy
import multiprocessing as mp
from multiprocessing.synchronize import Event as MpEvent  # for typing
import threading
from typing import Any, TypedDict
from yaml import safe_load

from .XiChannel import XiChannel
from .rpc import RpcController
from .view import GlobalView


#class SharedSettings(TypedDict):
#    settings: DictProxy[str, Any]
#    styles: DictProxy[Any, str]  # maps strings (e.g "finstrd") but also "style id" (e.g. 0) to a style (e.g. "bg:black")
#    view_channels: DictProxy[str, mp.Queue]  # {view_id: view_channel_queue}
#    focused_view: str

def editor(files: list):
    logging.debug("[MAIN] App started")

    with open('settings.yaml') as f:
        global_settings = safe_load(f)

    with mp.Manager() as manager:
        # XiChannel is a mp.Queue with a few fancy methods to put json in the right format
        rpc_channel = XiChannel(manager.Queue())

        shared_state: DictProxy[str, str|DictProxy[str|int, Any]] = manager.dict({
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

        logging.debug("[MAIN] Starting backend process")
        p = mp.Process(target=backend_process, args=(rpc_ready, shared_state, rpc_channel))
        p.start()

        logging.debug("[MAIN] Waiting for RPC")
        rpc_ready.wait()
        logging.debug("[MAIN] RPC ready")

        v = GlobalView(manager, shared_state, rpc_channel)
        v.fileman_visible = len(files) == 0
        for file in files:
            v.new_view(file)

        v.app.run()  # blocks until editor exits
        logging.debug("[MAIN] Shutting down")

        assert len(v.views) == 0, f"Views not closed: {v.views}"
        # while len(v.views) != 0:
        #    print(f"Waiting for {v.views.keys()} to shutdown.")
        #    sleep(.1)
        rpc_channel.put('kill')
        p.join()


def backend_process(rpc_ready: MpEvent, shared_state: dict, rpc_channel: XiChannel):
    rpc = RpcController(shared_state, rpc_ready)

    thread = threading.Thread(target=RpcController.bg_worker, args=(rpc, ))
    thread.start()

    rpc_ready.wait()
    rpc_channel.process_requests(rpc)  # blocking
    thread.join()
