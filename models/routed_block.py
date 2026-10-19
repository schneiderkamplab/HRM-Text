"""V2-only block wrapper carrying explicit metadata bias into MLP mixtures."""

from torch import nn
from models.transformer import TransformerBlock


class RoutedBlock(TransformerBlock):
    def __init__(self, original, norm_type):
        nn.Module.__init__(self)
        self.attn, self.mlp, self.norm = original.attn, original.mlp, original.norm
        self.norm_type = norm_type

    def forward(self, x, routing_bias=None, stability_diagnostics=None, stability_scope=None, **seq_info):
        attn_kwargs = dict(stability_diagnostics=stability_diagnostics,
                           stability_scope=f'{stability_scope}/attention' if stability_scope else None)
        mlp_kwargs = dict(routing_bias=routing_bias, stability_diagnostics=stability_diagnostics,
                          stability_scope=f'{stability_scope}/mlp' if stability_scope else None)
        if self.norm_type == 'pre':
            x = x + self.attn(self.norm(x), **seq_info, **attn_kwargs)
            return x + self.mlp(self.norm(x), **mlp_kwargs)
        x = self.norm(x + self.attn(x, **seq_info, **attn_kwargs))
        return self.norm(x + self.mlp(x, **mlp_kwargs))
