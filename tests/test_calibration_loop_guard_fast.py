import random

import pytest

from dfm12.calibration_streaming import LoopGuard as Original
from dfm12.calibration_loop_guard_fast import LoopGuard, repeated_tail


def compare(chunks):
    old, new = Original(), LoopGuard()
    for chunk in chunks:
        assert old.feed(chunk) == new.feed(chunk)
        assert vars(old) == vars(new)


@pytest.mark.parametrize('size', [63, 64, 65, 127, 128, 193, 255, 256, 257])
def test_block_boundaries(size):
    rng = random.Random(size)
    block = ''.join(rng.choice('abcdef0123456789') for _ in range(size))
    for copies in [7, 8, 9]:
        text = 'prefix' + block * copies
        compare([text])
        compare([text[i:i+7] for i in range(0, len(text), 7)])


def test_quote_escape_whitespace_and_early_return():
    compare(['{"text":"a\\', '"b', ' ' * 200, '"}', ' ' * 127, '\n', '', 'x'])
    compare([' ' * 128 + '"', 'x', '\\', '"'])
    compare(['"', '\\', '\\', '"', '\t' * 128])


def test_random_stream_equivalence():
    rng = random.Random(20261004)
    alphabet = 'abcde {}[],:"\\\n\t0123456789' + '\u0101\u017e\u2003\U0001f600'
    for case in range(1000):
        if case % 3 == 0:
            block = ''.join(rng.choice(alphabet) for _ in range(rng.randint(1, 300)))
            text = block * rng.randint(1, 12)
        else:
            text = ''.join(rng.choice(alphabet) for _ in range(rng.randint(0, 3000)))
        chunks = ['']
        while text:
            size = rng.randint(1, 100)
            chunks.append(text[:size])
            text = text[size:]
        compare(chunks)


def test_tail_predicate_random_equivalence():
    rng = random.Random(42)
    for _ in range(3000):
        block = ''.join(rng.choice('aab012\u0101') for _ in range(rng.randint(1, 300)))
        tail = (block * rng.randint(1, 12))[-2048:]
        expected = any(len(tail) >= n*8 and tail[-n:]*8 == tail[-n*8:]
                       for n in range(64, 257))
        assert repeated_tail(tail) == expected


def test_candidates_remain_in_ascending_order():
    class Tail(str):
        def __getitem__(self, key):
            if isinstance(key, slice) and key.stop is None and -256 <= key.start <= -64:
                checked.append(-key.start)
            return super().__getitem__(key)

    rng = random.Random(54)
    checked = []
    tail = Tail(''.join(rng.choice('abcde') for _ in range(2048)))
    assert repeated_tail(tail) is False
    assert checked == [size for size in range(64, 257) if tail[-1-size] == tail[-1]]
