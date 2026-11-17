"""Native packed-batch adapter for the Embla architecture comparisons."""
import torch
from torch import nn
from torch.nn import functional as F
import torch.distributed as dist
from models.common import IGNORE_LABEL_ID, packing_sequence_sum, unwrap_tensor
from models.embla.model import EmblaTrainingModel
from models.embla.upstream.configuration_embla import EmblaConfig


class Embla(EmblaTrainingModel):
    is_embla = True
    def __init__(self, config_dict):
        fields = dict(config_dict.get('embla_config', {}))
        if not fields:
            raise ValueError('Embla requires an explicit calibrated embla_config')
        fields['vocab_size'] = config_dict['vocab_size']
        super().__init__(EmblaConfig(**fields),decoder_loops=config_dict.get('decoder_loops',1),
                         prefix_lm=config_dict.get('attn_type','causal') == 'prefixlm',
                         attention_backend=config_dict.get('embla_attention_backend','tiled'),
                         compile_attention=config_dict.get('embla_compile_attention',False),
                         fa4_window=config_dict.get('embla_fa4_window',False),
                         fused_relu=config_dict.get('embla_fused_relu',False),
                         single_topk=config_dict.get('embla_single_topk',False),
                         fused_sparse=config_dict.get('embla_fused_sparse',False),
                         batched_windows=config_dict.get('embla_batched_windows',False),
                         fused_residual=config_dict.get('embla_fused_residual',False),
                         relu_tile_m=config_dict.get('embla_relu_tile_m',16))

    def initial_carry(self, batch_size, dtype):
        return None

    def compute_train_extra_args(self, train_state):
        return {}

    def create_cache(self, **kwargs):
        raise NotImplementedError('Embla native incremental cache is not integrated yet')


class EmblaLMHead(nn.Module):
    """Embla owns embedding/head; preserve the trainer's already-shifted labels."""
    def __init__(self, model, config_dict):
        super().__init__()
        if config_dict.get('goldfish_strategy'):
            raise ValueError('Goldfish masking is outside the Embla experiment recipe')
        self.model = model
        self.target_head_only = config_dict.get("embla_target_head_only",False)
        self.compute_train_extra_args = model.compute_train_extra_args
        self.create_cache = model.create_cache
        from models.embla.balancing import RouterBalanceAccumulator
        from models.embla.upstream.modeling_embla import MoE
        self._router_balancers = [RouterBalanceAccumulator(m) for m in model.modules() if isinstance(m,MoE)]

    def begin_optimizer_step(self):
        for balance in self._router_balancers:
            balance.begin()

    def end_optimizer_step(self, *, success):
        for balance in self._router_balancers:
            if success:
                balance.apply()
            else:
                balance.discard()

    def forward(self, carry, batch, **kwargs):
        if carry is not None:
            raise ValueError('Embla training is stateless')
        batch = {k:unwrap_tensor(v) for k,v in batch.items()}
        inputs = batch['inputs']
        if inputs.ndim != 1:
            raise ValueError('Native Embla expects flat packed batches')
        # Padding must not enter router statistics, hash memory, or attention.
        count = int(batch['total_seqlen'].item()) if 'total_seqlen' in batch else inputs.numel()
        nseq = int(batch['numseqs'].item()) if 'numseqs' in batch else batch['cu_seqlens'].numel()-1
        boundaries = batch['cu_seqlens'][:nseq+1].long()
        positions = batch['position_ids'][:count].long()[None]
        prompt = None
        if self.model.prefix_lm:
            sequence = torch.bucketize(torch.arange(count,device=inputs.device),boundaries[1:],right=True)
            prompt = positions < batch['prefix_lens'][sequence][None]
        if 'labels' not in batch:
            logits = self.model(inputs[:count].long()[None],position_ids=positions,prompt_mask=prompt)[0]
            return None, F.pad(logits,(0,0,0,inputs.numel()-count))
        hidden = self.model(inputs[:count].long()[None],position_ids=positions,prompt_mask=prompt,return_hidden=True)[0]
        labels = batch['labels'][:count].long()
        valid = labels != IGNORE_LABEL_ID
        head_hidden = hidden[valid] if self.target_head_only else hidden
        head_labels = labels[valid] if self.target_head_only else labels
        logits = self.model.lm_head(head_hidden)
        from models.embla.loss import softcapped_cross_entropy
        loss, predictions = softcapped_cross_entropy(logits,head_labels,self.model.config.final_logit_softcapping)
        divisor = valid.sum().float()
        if dist.is_available() and dist.is_initialized():
            dist.all_reduce(divisor,op=dist.ReduceOp.AVG)
        with torch.no_grad():
            correct = torch.zeros_like(valid).masked_scatter(valid,predictions==head_labels) if self.target_head_only else (predictions == labels) & valid
            # Native routing metadata may include a final padding sequence.
            correct = F.pad(correct,(0,inputs.numel()-count))
            valid_padded = F.pad(valid,(0,inputs.numel()-count))
            per_valid = packing_sequence_sum(valid_padded,boundaries)
            per_correct = packing_sequence_sum(correct,boundaries)
            active = per_valid > 0
            metrics = {'loss':(loss.detach(),valid.sum()),
                       'accuracy':(correct.sum(),valid.sum()),
                       'exact_accuracy':(((per_correct==per_valid)&active).sum(),active.sum())}
        return None, loss/divisor.clamp_min(1), metrics
