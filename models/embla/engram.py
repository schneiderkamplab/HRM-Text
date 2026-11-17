"""Trainable device-resident Embla Engram, retaining the official hash/read math."""
import torch
from torch import nn
from torch.nn import functional as F
from .upstream.modeling_embla import Engram


class TrainableEngram(Engram):
    def __init__(self, config):
        super().__init__(config)
        self.table = nn.Parameter(torch.empty(config.engram_table_rows, config.engram_head_dim))
        nn.init.normal_(self.table, std=config.engram_init_std)

    def lookup(self, ids, dtype, position_ids=None, cache=None):
        if cache is None:
            rows = self.rows_of(ids, position_ids)
        else:
            full = ids if cache.engram_ids is None else torch.cat((cache.engram_ids, ids), dim=1)
            history = max(self.orders) - 1
            cache.engram_ids = full[:, -history:] if history else full[:, :0]
            rows = self.rows_of(full)[:, -ids.shape[1]:]
        return F.embedding(rows, self.table).to(dtype)

    def load_table(self, path):
        from safetensors.torch import load_file
        tensors = load_file(str(path))
        if 'weight' not in tensors:
            raise ValueError('Training requires an unquantized Engram table')
        if tensors['weight'].shape != self.table.shape:
            raise ValueError('Engram table shape mismatch')
        with torch.no_grad():
            self.table.copy_(tensors['weight'])
