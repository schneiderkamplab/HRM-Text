"""Shared local paths and font selection for benchmark chart scripts."""
import os
from pathlib import Path
from PIL import ImageFont

__all__ = []
_ROOT = Path(__file__).resolve().parents[2]
_SOURCE = Path(os.environ.get("BENCHMARK_CSV", _ROOT / "summary_by_category.csv"))
_OUTPUT_ROOT = Path(os.environ.get("BENCHMARK_OUTPUT_ROOT", _ROOT / "outputs"))


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    override = os.environ.get("BENCHMARK_FONT_BOLD" if bold else "BENCHMARK_FONT_REGULAR")
    if override:
        return ImageFont.truetype(override, size)
    arial = Path("/opt/X11/share/system_fonts/Supplemental") / ("Arial Bold.ttf" if bold else "Arial.ttf")
    if arial.exists():
        return ImageFont.truetype(str(arial), size)
    return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size)
