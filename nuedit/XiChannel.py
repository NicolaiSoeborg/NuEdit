import multiprocessing as mp
from typing import Optional, Union


class XiChannel:
    def __init__(self, rpc_channel: mp.Queue):
        self.rpc_channel = rpc_channel

    def f(self, method: str, params: dict, result: Optional[mp.Queue] = None):
        self.rpc_channel.put((method, params, result))

    def notify(self, method: str, params: dict):
        self.f('notify', {'method': method, 'params': params})

    def edit(self, method: str, params: Union[dict, list], view_id: str):
        self.f('edit', {'method': method, 'params': params, 'view_id': view_id})

    def edit_request(self, method: str, params: dict, result: mp.Queue):
        self.f('edit_request', {'method': method, 'params': params}, result)
