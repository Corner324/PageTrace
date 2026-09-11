# Example traces

Two small JSONL captures of the same three-page run, used by the golden tests so the README
commands cannot rot.

```bash
uv run pagetrace check examples/clean-cursor.jsonl --total '$.total'
uv run pagetrace check examples/broken-cursor.jsonl --total '$.total'
```

`clean-cursor.jsonl` violates nothing and exits 0. `broken-cursor.jsonl` asks for page 2 with a
token page 1 never returned, and repeats one item; it exits 1.
