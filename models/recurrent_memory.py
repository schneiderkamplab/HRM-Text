"""Depth-recurrent memory branches with one expensive stack call per update."""

import torch
from models.residual_branches import ResidualConnection


class RecurrentMemory(ResidualConnection):
    def __init__(self, branches, hidden_size):
        super().__init__(branches, hidden_size, 0, .1, input_dependent=True)
        self.register_buffer('alpha', torch.tensor(0.0))

    def initialize(self, x):
        return x.unsqueeze(-2).expand(*x.shape[:-1], self.branches, x.shape[-1])

    def read_state(self, states):
        return self.read(states, self.alpha)

    def update(self, states, candidate):
        # At alpha=0 every branch is exactly replaced, emulating v1. Increasing
        # alpha lets branches retain different portions of their previous state.
        weights = self.weights(states, self.alpha, 'write')
        retain = self.alpha * (1 - weights)
        return (retain * states.float() + (1 - retain) * candidate.float().unsqueeze(-2)).to(candidate.dtype)
