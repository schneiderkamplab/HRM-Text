"""Isolated exact loop-guard prototype; not installed into live streaming."""
from .calibration_streaming import LoopGuard as OriginalLoopGuard


def repeated_tail(tail):
    length = len(tail)
    maximum = min(256, length // 8)
    if maximum < 64:
        return False
    last = tail[-1]
    lower = length - 1 - maximum
    position = tail.rfind(last, lower, length - 64)
    while position >= 0:
        size = length - 1 - position
        if tail[-size:] * 8 == tail[-size * 8:]:
            return True
        # Right-to-left matches correspond to ascending candidate block sizes.
        position = tail.rfind(last, lower, position)
    return False


class LoopGuard(OriginalLoopGuard):
    def feed(self, text):
        for char in text:
            if self.quoted:
                if self.escaped:
                    self.escaped = False
                elif char == '\\':
                    self.escaped = True
                elif char == '"':
                    self.quoted = False
            elif char == '"':
                self.quoted = True
                self.whitespace = 0
            elif char.isspace():
                self.whitespace += 1
                if self.whitespace >= 128:
                    return 'structural_whitespace_loop'
            else:
                self.whitespace = 0
        self.tail = (self.tail + text)[-2048:]
        if repeated_tail(self.tail):
            return 'repeated_text_loop'
        return None
