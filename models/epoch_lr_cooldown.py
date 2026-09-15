"""Optional cosine cooldown anchored to a checkpoint's dataset row cursor."""
import json
import math
from pathlib import Path

import numpy as np


class EpochLRCooldown:
    def __init__(self, checkpoint_metadata, dataset_path, resume_step, min_ratio):
        metadata = json.loads(Path(checkpoint_metadata).read_text())
        self.start_step = int(metadata['step'])
        self.epoch = int(metadata['epoch'])
        self.start_row = int(metadata['global_row_cursor_in_epoch'])
        if Path(metadata['data_path']).resolve() != Path(dataset_path).resolve():
            raise ValueError('LR cooldown dataset differs from anchor checkpoint')
        if resume_step < self.start_step:
            raise ValueError('LR cooldown cannot resume before its anchor step')
        if not math.isfinite(min_ratio) or not 0 <= min_ratio <= 1:
            raise ValueError('LR cooldown min ratio must be between zero and one')
        self.min_ratio = min_ratio
        indices = np.load(Path(dataset_path) / f'epoch_{self.epoch - 1}' / 'inst_start.npy',
                          mmap_mode='r', allow_pickle=False)
        self.end_row = len(indices)
        if not 0 <= self.start_row < self.end_row:
            raise ValueError('LR cooldown anchor has no remaining epoch rows')

    def ratio(self, epoch, resume_info):
        if epoch < self.epoch:
            raise ValueError('LR cooldown epoch precedes anchor checkpoint')
        if epoch > self.epoch:
            return self.min_ratio
        if resume_info is None or 'global_row_end' not in resume_info:
            raise ValueError('LR cooldown requires dataset row-cursor metadata')
        row = int(resume_info['global_row_end'])
        if not self.start_row <= row <= self.end_row:
            raise ValueError('LR cooldown row cursor outside anchored epoch interval')
        progress = (row - self.start_row) / (self.end_row - self.start_row)
        return self.min_ratio + (1 - self.min_ratio) * 0.5 * (1 + math.cos(math.pi * progress))
