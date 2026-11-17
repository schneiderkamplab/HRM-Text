from typing import Optional, Tuple

import torch
from torch import nn
from torch import Tensor
import torch.distributed as dist
import torch.nn.functional as F
from pydantic import BaseModel

from models.layers import LinearInit, ScaledEmbeddingInit, Carry
from models.common import IGNORE_LABEL_ID, packing_sequence_sum
from models.goldfish_loss import GoldfishLossConfig, GoldfishStrategy, apply_goldfish_loss_mask


@torch.compile(dynamic=True)
def _selected_projection_loss(head,hidden,labels):
    logits=head(hidden)
    return F.cross_entropy(logits.float(),labels,reduction="sum"),logits.argmax(-1)


class LMHeadConfig(BaseModel):
    vocab_size: int
    target_head_only: bool = False
    goldfish_strategy: Optional[GoldfishStrategy] = None
    goldfish_k: int = 50
    goldfish_context_width: int = 50
    goldfish_seed: int = 0


class LMHead(nn.Module):
    def __init__(self, model: nn.Module, config_dict: dict) -> None:
        super().__init__()
        self.model = model
        # Create cache function
        self.create_cache = self.model.create_cache
        # Train extra args function
        self.compute_train_extra_args = self.model.compute_train_extra_args

        config = LMHeadConfig(**config_dict)
        self.target_head_only = config.target_head_only
        self.goldfish_config = GoldfishLossConfig(
            strategy=config.goldfish_strategy,
            k=config.goldfish_k,
            context_width=config.goldfish_context_width,
            seed=config.goldfish_seed,
        )
        self.goldfish_config.validate()
        head_hint: dict = self.model.head_hint  # pyright: ignore[reportAssignmentType]

        # LMHead input and output
        self.embed_tokens = ScaledEmbeddingInit(config.vocab_size, head_hint["in"]["dim"], init_std=head_hint["in"]["init_std"])  # pyright: ignore[reportArgumentType]
        self.lm_head = LinearInit(head_hint["out"]["dim"], config.vocab_size, bias=False, init_std=head_hint["out"]["init_std"])  # pyright: ignore[reportArgumentType]
        if config_dict.get('specialist_training', False) or config_dict.get('specialist_router_calibration', False):
            from models.specialists import configure_specialist
            configure_specialist(self, router_only=config_dict.get('specialist_router_calibration', False))

    def forward(self, carry: Carry, batch: dict[str, Tensor], **kwargs) -> Tuple[Carry, Tensor] | Tuple[Carry, Tensor, dict[str, Tuple[Tensor, Tensor]]]:
        # Token embedding
        input_embedding = self.embed_tokens(batch["inputs"])
        if getattr(self.model, 'ngram_enabled', False):
            kwargs['token_ids'] = batch['inputs']
        stability_diagnostics = kwargs.get("stability_diagnostics")
        if stability_diagnostics is not None:
            stability_diagnostics.record_tensor(
                "activation/model/input_embedding", input_embedding, record_gradient=True
            )

        # Model forward
        new_carry, logits = self.model(carry,
                                       input_embedding,
                                       **{k: v for k, v in batch.items() if k not in ("inputs", "labels")},
                                       **kwargs)
        if self.target_head_only and "labels" in batch:
            loss,metrics=self._supervised_head(logits,batch,stability_diagnostics)
            return new_carry,loss,metrics
        logits = self.lm_head(logits)
        if stability_diagnostics is not None:
            stability_diagnostics.record_tensor(
                "activation/model/logits", logits, record_gradient=True
            )

        # Loss & Metrics
        if "labels" in batch:
            # Masks & labels
            raw_labels = batch["labels"]
            labels, masks = apply_goldfish_loss_mask(
                labels=raw_labels,
                inputs=batch["inputs"],
                cu_seqlens=batch["cu_seqlens"],
                config=self.goldfish_config,
            )

            # Loss (CE in F32)
            loss = F.cross_entropy(logits.to(torch.float32), labels.to(torch.long), ignore_index=IGNORE_LABEL_ID, reduction="sum")
            # AllReduce loss divisor. Divide by mean of valid tokens across all processes, as gradient will be averaged.
            loss_divisor = masks.sum().to(torch.float32)
            if dist.is_available() and dist.is_initialized():
                dist.all_reduce(loss_divisor, op=dist.ReduceOp.AVG)

            # Accuracy
            with torch.no_grad():
                is_correct = torch.argmax(logits, dim=-1) == labels
                raw_valid_counts = (raw_labels != IGNORE_LABEL_ID).sum()
                local_valid_counts = masks.sum()
                # Sequence-level statistics
                seq_num_tokens_correct = packing_sequence_sum(is_correct, batch["cu_seqlens"])
                seq_num_valid_tokens = packing_sequence_sum(masks, batch["cu_seqlens"])
                seq_is_valid = seq_num_valid_tokens > 0
                # Metrics
                metrics = {
                    "loss": (loss.detach(), local_valid_counts),
                    "accuracy": (is_correct.sum(), local_valid_counts),
                    "exact_accuracy": (((seq_num_tokens_correct == seq_num_valid_tokens) & seq_is_valid).sum(), seq_is_valid.sum()),
                }
                if self.goldfish_config.enabled():
                    dropped = raw_valid_counts - local_valid_counts
                    metrics["goldfish_drop_rate"] = (dropped, raw_valid_counts)

            return new_carry, loss / loss_divisor, metrics

        return new_carry, logits


    @torch.compiler.disable
    def _supervised_head(self,hidden,batch,stability_diagnostics=None):
        # Keep data-dependent compaction outside Dynamo; the recurrent/transformer
        # core stays compiled and returns fixed-shape loss/metric tensors here.
        raw_labels=batch["labels"]
        labels,masks=apply_goldfish_loss_mask(labels=raw_labels,inputs=batch["inputs"],cu_seqlens=batch["cu_seqlens"],config=self.goldfish_config)
        selected_labels=labels[masks].long()
        if hidden.is_cuda and stability_diagnostics is None:
            loss,predictions=_selected_projection_loss(self.lm_head,hidden[masks],selected_labels)
        else:
            logits=self.lm_head(hidden[masks])
            if stability_diagnostics is not None:
                stability_diagnostics.record_tensor("activation/model/supervised_logits",logits,record_gradient=True)
            loss=F.cross_entropy(logits.float(),selected_labels,reduction="sum")
            predictions=logits.argmax(-1)
        divisor=masks.sum().float()
        if dist.is_available() and dist.is_initialized():dist.all_reduce(divisor,op=dist.ReduceOp.AVG)
        with torch.no_grad():
            correct=torch.zeros_like(masks).masked_scatter(masks,predictions==selected_labels)
            valid_counts=masks.sum();per_valid=packing_sequence_sum(masks,batch["cu_seqlens"]);per_correct=packing_sequence_sum(correct,batch["cu_seqlens"]);active=per_valid>0
            metrics={"loss":(loss.detach(),valid_counts),"accuracy":(correct.sum(),valid_counts),"exact_accuracy":(((per_correct==per_valid)&active).sum(),active.sum())}
            if self.goldfish_config.enabled():
                raw_valid=(raw_labels!=IGNORE_LABEL_ID).sum();metrics["goldfish_drop_rate"]=(raw_valid-valid_counts,raw_valid)
        return loss/divisor.clamp_min(1),metrics
