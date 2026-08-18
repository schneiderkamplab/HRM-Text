#!/usr/bin/env python3
"""Diagnose a .npy file: header vs logical size vs physical blocks vs mmap-ability.

Run this on BOTH the original and the copy. A file browser's size column cannot tell you
which of these you have -- it may report physical or logical, and it never validates the
.npy header.

    python check_npy.py /dfm/HRM-Text/data/sampled_dfm9_mini/tokens.npy
    python check_npy.py /work/<you>/.../sampled_dfm9_mini/tokens.npy

Verdicts:
  VALID     header, logical size and mmap all agree -- file is usable
  SPARSE    logical size correct, physical blocks much smaller -- valid, holes on disk.
            Copy it with `cp --sparse=always`, `rsync -S`, or tar; a naive copy either
            explodes it to full size or truncates it.
  TRUNCATED logical size < what the header requires -- the file is incomplete/corrupt
  ODD       something else; read the numbers below
"""

from __future__ import annotations

import ast
import struct
import sys
from pathlib import Path

# numpy is OPTIONAL here. The .npy header is plain ASCII, so the decisive checks
# (header vs file size) run on a bare python with no packages installed.
try:
    import numpy as np
except ImportError:
    np = None

DTYPE_SIZE = {"i1": 1, "u1": 1, "i2": 2, "u2": 2, "i4": 4, "u4": 4,
              "i8": 8, "u8": 8, "f2": 2, "f4": 4, "f8": 8}


def read_npy_header(path: Path):
    """Parse a .npy header with the standard library only.
    Returns (shape, dtype_str, itemsize, header_len)."""
    with path.open("rb") as fh:
        magic = fh.read(6)
        if magic != b"\x93NUMPY":
            raise ValueError(f"not a .npy file (magic={magic!r})")
        major, _minor = struct.unpack("<BB", fh.read(2))
        if major == 1:
            (hlen,) = struct.unpack("<H", fh.read(2))
        else:
            (hlen,) = struct.unpack("<I", fh.read(4))
        header = fh.read(hlen).decode("latin1")
        header_len = fh.tell()
    d = ast.literal_eval(header.strip())
    descr = d["descr"]
    key = descr.lstrip("<>|=")
    if key not in DTYPE_SIZE:
        raise ValueError(f"unhandled dtype {descr!r}")
    return tuple(d["shape"]), descr, DTYPE_SIZE[key], header_len


def human(n: float) -> str:
    for u in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(n) < 1024:
            return f"{n:,.2f} {u}"
        n /= 1024
    return f"{n:,.2f} PiB"


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    p = Path(sys.argv[1])
    if not p.exists():
        print(f"FAIL: {p} does not exist")
        return 1

    st = p.stat()
    logical = st.st_size
    physical = getattr(st, "st_blocks", 0) * 512

    print(f"path              : {p}")
    print(f"logical size      : {logical:,} bytes  ({human(logical)})   <- ls / stat")
    if physical:
        print(f"physical on disk  : {physical:,} bytes  ({human(physical)})   <- st_blocks*512, what du reports")
        print(f"sparse ratio      : {logical/max(1,physical):.2f}x")

    try:
        shape, descr, itemsize, header_len = read_npy_header(p)
    except Exception as e:  # noqa: BLE001
        print(f"\nFAIL: cannot parse .npy header ({e.__class__.__name__}: {e})")
        return 1

    n = 1
    for x in shape:
        n *= x
    if not shape:
        n = 0
    need = header_len + n * itemsize
    print()
    print(f"header shape      : {shape}")
    print(f"header dtype      : {descr}  ({itemsize} bytes/element)")
    print(f"header length     : {header_len} bytes")
    print(f"elements          : {n:,}   ({n/1e9:.2f}B)")
    print(f"header requires   : {need:,} bytes  ({human(need)})")
    print(f"actual logical    : {logical:,} bytes  ({human(logical)})")
    print(f"difference        : {logical - need:+,} bytes "
          f"({100.0*logical/max(1,need):.2f}% of required)")

    ok_mmap = False
    if np is None:
        print("\nnumpy not installed -- skipping the mmap probe. The header-vs-size check "
              "above is still decisive.\n(pip install numpy  to enable the rest.)")
        print()
        if logical == need:
            print("VERDICT: header and file size AGREE -- the file is self-consistent. "
                  "Install numpy and re-run to confirm it mmaps.")
            return 0
        print(f"VERDICT: MISMATCH -- header needs {need:,} bytes, file has {logical:,}.")
        return 1
    try:
        a = np.load(p, mmap_mode="r")
        ok_mmap = True
        print(f"\nnp.load(mmap_mode='r') : OK, len={len(a):,}")
        # Touch both ends -- a hole reads as zeros rather than failing, so report it.
        head = np.asarray(a[:1024])
        tail = np.asarray(a[-1024:])
        print(f"  first 1024 elements: min={head.min()} max={head.max()} "
              f"nonzero={int((head != 0).sum())}/1024")
        print(f"  last  1024 elements: min={tail.min()} max={tail.max()} "
              f"nonzero={int((tail != 0).sum())}/1024")
        if int((tail != 0).sum()) == 0:
            print("  NOTE: the tail is all zeros -- consistent with a preallocated array "
                  "whose end was never written. Check the index arrays' max offset.")
    except Exception as e:  # noqa: BLE001
        print(f"\nnp.load(mmap_mode='r') : FAILED -- {e.__class__.__name__}: {e}")

    print()
    if ok_mmap and physical and logical / max(1, physical) > 1.5:
        verdict = ("SPARSE -- header and logical size agree and the file loads, but most of it "
                   "is holes on disk. Copy with `cp --sparse=always`, `rsync -S`, or tar; a "
                   "naive copy will either expand it to full size or truncate it.")
    elif ok_mmap and logical >= need:
        verdict = "VALID -- header, size and mmap all agree."
    elif logical < need:
        verdict = (f"TRUNCATED -- the file is {need - logical:,} bytes short of what its own "
                   f"header requires. It is not a usable .npy in this state.")
    else:
        verdict = "ODD -- read the numbers above."
    print(f"VERDICT: {verdict}")
    return 0 if ok_mmap else 1


if __name__ == "__main__":
    raise SystemExit(main())
