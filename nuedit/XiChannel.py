import logging
import multiprocessing as mp
from typing import Optional, Tuple, Union, TypedDict

#class XiParams(TypedDict):
#    result: Optional[mp.Queue]
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .rpc import RpcController


class XiChannel:
    def __init__(self, rpc_channel: mp.Queue):
        self._channel = rpc_channel

    def put(self, method: str, params: dict = {}, result: Optional[mp.Queue] = None):
        self._channel.put((method, params, result))

    def edit(self, method: str, params: dict, view_id: str):
        """ Helper for creating:
        {"method": "edit", "params": {"method": REAL_METHOD, "params": REAL_PARAMS}, "view_id": id}
        """
        req = {'method': method, 'params': params, 'view_id': view_id}
        self.put('edit', req)

    def process_requests(self, rpc: 'RpcController') -> None:
        while True:
            (method, params, result) = self._channel.get()
            logging.debug(f"process_requests: {method=} {params=} {result=}")
            if method == 'kill':
                logging.debug(f"process_requests Killing")
                rpc.kill()
                return
            rpc.request(method, params, result)
