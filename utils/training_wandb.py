"""Preserve optimizer-step spacing without rewinding W&B's history cursor."""
from __future__ import annotations


class TrainingWandbLogger:
    def __init__(self, wandb_module):
        self.wandb = wandb_module
        self.registered = {'train/step'}
        self.logging_offset = None
        self.wandb.define_metric('train/step')

    def log(self, metrics, optimizer_step):
        if type(optimizer_step) is not int or optimizer_step < 0:
            raise ValueError('Nonnegative integer optimizer step required')
        if 'train/step' in metrics and metrics['train/step'] != optimizer_step:
            raise ValueError('Conflicting optimizer step in metrics')
        for key in sorted(metrics):
            if key not in self.registered:
                self.wandb.define_metric(key, step_metric='train/step')
                self.registered.add(key)
        run = self.wandb.run
        if run is None or type(run.step) is not int or run.step < 0:
            raise RuntimeError('An initialized W&B run with a valid history cursor is required')
        if self.logging_offset is None:
            self.logging_offset = max(0, run.step - optimizer_step)
        # Preserve existing _step panel spacing; extra same-step rows must still
        # append after the cursor. This offset never enters the training state.
        history_step = max(optimizer_step + self.logging_offset, run.step)
        self.wandb.log(dict(metrics) | {'train/step': optimizer_step},
                       step=history_step, commit=True)
