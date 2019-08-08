# TODO

**Notice:** to run the code, you will need to fix this issue with python: https://github.com/python/cpython/pull/4819

Build Xi-core and copy it to `/tmp/`:

```
git submodule update --init
cd xi-editor/rust/
cargo build
cp target/debug/xi-core /tmp/
```
