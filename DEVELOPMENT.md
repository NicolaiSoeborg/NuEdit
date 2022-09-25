# Initial setup

```bash
# Create a virtual env:
$ python3 -m venv env

# Activate env:
$ source env/bin/activate

# Install pip packages in env:
$ pip3 install -r requirements.txt

# Setup package "nuedit" in develop mode:
$ python3 setup.py develop

# Build Xi core and copy to checkout:
$ make nuedit/xi-core
```

# Development

```bash
# Activete virtual env:
$ source env/bin/activate

```

## Updating Xi

```bash
# Update git submodule
$ git submodule foreach git pull  # .. something?

# Rebuild Xi:
$ make dist/xi-core
```

## Code structure

### RPC Channel

To call an function on the RpcController use `rpc_channel.f(method: str, params: dict = {}, result: mp.Queue = None)`

To send a command to Xi core use `rpc_channel.edit = def (method: str, params: Union[dict, list] = {})`

### Design decisions

The lock `views_lock` is there due to a small race-condition between:

1. `new_view`
   1.1 `rpc_channel.put(new_view, ..., channel)`
   1.2 `view_id = channel.get()`
   1.3. `shared_state['views'][view_id] = channel`
2. `bg_worker`
   2.1 `_receive(): {'id': ..., 'result': 'view-id-1'}`
       2.1.1 Put on "channel"-queue (1.2 waiting for it)
   2.2 `_receive(): {'id': ..., 'result': {..., view-id: 'view-id-1'}}`
       2.2.2 Put on `shared_state['views'][view_id]` queue
       2.2.3 KeyError: 'view-id-1'
