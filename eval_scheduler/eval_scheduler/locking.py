from __future__ import annotations

import fcntl
from pathlib import Path
from types import TracebackType


class PlanLock:
    """Advisory interprocess lock for a scheduler plan directory."""

    def __init__(self, plan_dir: Path, *, exclusive: bool = True, blocking: bool = True) -> None:
        self.plan_dir = plan_dir
        self.path = plan_dir / "plan.lock"
        self.exclusive = exclusive
        self.blocking = blocking
        self._file = None

    def __enter__(self) -> PlanLock:
        self.plan_dir.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("a+")
        mode = fcntl.LOCK_EX if self.exclusive else fcntl.LOCK_SH
        if not self.blocking:
            mode |= fcntl.LOCK_NB
        fcntl.flock(self._file.fileno(), mode)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._file is None:
            return
        try:
            fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
        finally:
            self._file.close()
            self._file = None
