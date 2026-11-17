from dataclasses import dataclass, fields
from typing import Optional, Any
import os
import json

import numpy as np
import pydantic

import torch
from torch.utils.data import IterableDataset, get_worker_info

from models.common import IGNORE_LABEL_ID
from models.flash_attention_prefixlm_v2 import compute_aux_seq_tensors_scalars
from models.layers import find_multiple
from multipack_sampler import MultipackDistributedBatchSampler


class V1DatasetConfig(pydantic.BaseModel):
    seed: int
    dataset_path: str
    batch_max_length: int
    drop_last_batch: bool

    target_only: bool
    mixed_lm: bool = False

    rank: int
    num_replicas: int
    homogeneous_categories: bool = False
    routing_categories: bool = False


class V1DatasetMeta(pydantic.BaseModel):
    tokenizer_info: dict[str, Any] = {}
    vocab_size: Optional[int] = None
    max_seq_len: int
    total_length: int


@dataclass
class V1DatasetIndices:
    inst_start: np.ndarray
    inst_len: np.ndarray
    resp_start: np.ndarray
    resp_len: np.ndarray


class V1Dataset(IterableDataset):
    def __init__(self, config: V1DatasetConfig):
        super().__init__()
        self.config = config
        self.metadata = self._load_metadata()
        if config.mixed_lm:
            if not config.target_only:
                raise ValueError("MixedLM requires target_only=true")
            from tokenizers import Tokenizer
            tokenizer = Tokenizer.from_file(self.metadata.tokenizer_info['tokenizer_path'])
            self._mixed_header = tokenizer.encode('<|turn>model\n', add_special_tokens=False).ids
            self._mixed_tools = [tokenizer.token_to_id(t) for t in ('<|tool_call>', '<|tool_response>')]
            if any(t is None for t in self._mixed_tools):
                raise ValueError("MixedLM requires the verified Gemma4 chat-token protocol")

        # State
        self._data: Optional[np.ndarray] = None
        self._data_indices: Optional[V1DatasetIndices] = None
        self._sampler: Optional[MultipackDistributedBatchSampler] = None
        self._epoch = 0
        self._start_batch = 0
        self._start_row_cursor: Optional[int] = None

    def _load_metadata(self) -> V1DatasetMeta:
        with open(os.path.join(self.config.dataset_path, "metadata.json"), "r") as f:
            metadata = V1DatasetMeta(**json.load(f))
            # Account for autoregressive shift
            metadata.max_seq_len -= 1
            # Compute vocab size from tokenizer info
            assert metadata.vocab_size is None
            metadata.vocab_size = find_multiple(metadata.tokenizer_info.pop("vocab_size"), 256)

            return metadata

    def set_epoch(self, epoch: int):
        if epoch < 0:
            raise ValueError(f"Dataset epoch must be non-negative, got {epoch}")
        if self._sampler is not None:
            raise RuntimeError("Cannot change dataset epoch after iteration has started")
        self._epoch = epoch

    def set_start_batch(self, start_batch: int):
        if start_batch < 0:
            raise ValueError(f"Dataset start batch must be non-negative, got {start_batch}")
        if self._sampler is not None:
            raise RuntimeError("Cannot change dataset start batch after iteration has started")
        self._start_batch = start_batch

    def set_start_row_cursor(self, start_row_cursor: int):
        if start_row_cursor < 0:
            raise ValueError(f"Dataset start row cursor must be non-negative, got {start_row_cursor}")
        if self._sampler is not None:
            raise RuntimeError("Cannot change dataset start row cursor after iteration has started")
        self._start_row_cursor = start_row_cursor

    def _load_dataset_before_epoch_begin(self):
        # Load tokens (only if not loaded)
        if self._data is None:
            self._data = np.load(os.path.join(self.config.dataset_path, "tokens.npy"), mmap_mode="r")

        # Load indices
        self._data_indices = V1DatasetIndices(**{f.name: np.load(os.path.join(self.config.dataset_path, f"epoch_{self._epoch}", f"{f.name}.npy"), mmap_mode="r")
                                                 for f in fields(V1DatasetIndices)})
        if self.config.homogeneous_categories or self.config.routing_categories:
            self._categories = np.load(os.path.join(self.config.dataset_path, f'epoch_{self._epoch}',
                                                    'category_id.npy'), mmap_mode='r')
            if (self._categories.ndim != 1 or self._categories.dtype.kind not in 'iu'
                    or len(self._categories) != len(self._data_indices.inst_len)):
                raise ValueError('category_id.npy must be an integer vector aligned with epoch rows')
        self._epoch += 1

        # Re-create sampler
        self._sampler = MultipackDistributedBatchSampler(
            lengths=self._data_indices.inst_len + self._data_indices.resp_len - 1,  # Account for autoregressive shift
            batch_max_length=self.config.batch_max_length,
            drop_last_batch=self.config.drop_last_batch,

            rank=self.config.rank,
            num_replicas=self.config.num_replicas
        )
        if self.config.homogeneous_categories:
            from homogeneous_sampler import HomogeneousSampler
            self._sampler = HomogeneousSampler(
                categories=self._categories, seed=self.config.seed + self._epoch - 1,
                lengths=self._data_indices.inst_len + self._data_indices.resp_len - 1,
                batch_max_length=self.config.batch_max_length,
                drop_last_batch=self.config.drop_last_batch,
                rank=self.config.rank, num_replicas=self.config.num_replicas)

    def _load_batch(self, indices: np.ndarray):
        # Load instructions and responses
        assert self._data is not None and self._data_indices is not None
        raw = {k: [] for k in ["inst", "resp"]}
        for k, v in raw.items():
            start = getattr(self._data_indices, f"{k}_start")[indices]
            end = start + getattr(self._data_indices, f"{k}_len")[indices]
            for i in range(len(start)):
                v.append(self._data[start[i]: end[i]].astype(np.int32))

        # Form batch
        batch = {k: [] for k in ["inputs", "labels", "position_ids"]}
        seqlens_i, seqlens_o = [], []
        for i, o in zip(raw["inst"], raw["resp"]):
            # PrefixLM: last input token predict first output token, for compatibility with Causal LM frameworks (prefill-phase)
            # Inputs
            batch["inputs"].append(i)
            batch["inputs"].append(o[:-1])
            # Labels
            batch["labels"].append(np.full(len(i) - 1, dtype=i.dtype, fill_value=IGNORE_LABEL_ID) if self.config.target_only else i[1:])
            batch["labels"].append(o)
            # Position IDs
            batch["position_ids"].append(np.arange(len(i), dtype=np.int32))
            batch["position_ids"].append(np.arange(len(i), len(i) + len(o) - 1, dtype=np.int32))
            # Seqlens
            seqlens_i.append(len(i))
            seqlens_o.append(len(o) - 1)

        # Concat
        batch = {k: np.concatenate(v, dtype=np.int32) for k, v in batch.items()}
        # pad to fixed len
        pad_len = self.config.batch_max_length - batch["inputs"].shape[0]
        if pad_len > 0:
            pad_values = {
                "inputs": 0,  # FIXME: Pad with an arbitary token.
                "labels": IGNORE_LABEL_ID,
                "position_ids": 0,
            }
            for k in pad_values.keys():
                batch[k] = np.pad(batch[k], (0, pad_len), mode="constant", constant_values=pad_values[k])

        # Compute cu_seqlens
        seqlen_i, seqlen_o = np.array(seqlens_i, dtype=np.int32), np.array(seqlens_o, dtype=np.int32)
        tensors, scalars = compute_aux_seq_tensors_scalars(seqlen_i, seqlen_o, self.config.batch_max_length)

        # to tensor
        result = {k: torch.from_numpy(v) for k, v in (batch | tensors).items()}
        if self.config.homogeneous_categories:
            categories = self._categories[indices]
            if len(categories) == 0 or np.any(categories != categories[0]):
                raise ValueError('Expected a nonempty homogeneous microbatch')
            result['routing_category'] = torch.tensor(int(categories[0]))
        elif self.config.routing_categories:
            categories = self._categories[indices]
            if np.any(categories < 0):
                raise ValueError('Routing categories must be nonnegative')
            lengths = (self._data_indices.inst_len[indices]
                       + self._data_indices.resp_len[indices] - 1)
            # Preserve normal sampling/packing; all tokens of an example share
            # its source label. Padding uses neutral category zero.
            routed = np.repeat(categories.astype(np.int64), lengths.astype(np.int64))
            if pad_len > 0:
                routed = np.pad(routed, (0, pad_len), constant_values=0)
            result['routing_category'] = torch.from_numpy(routed)
        if self.config.mixed_lm:
            from models.mixedlm import routing
            result.update(routing(raw['inst'], [len(o)-1 for o in raw['resp']], self._mixed_header, self._mixed_tools))
        return result, scalars

    def __iter__(self):
        worker_info = get_worker_info()
        assert worker_info is None or worker_info.num_workers == 1
        # TODO: Feature (Low Priority): Multithreaded data loading

        self._load_dataset_before_epoch_begin()

        assert self._sampler is not None
        start_batch = self._start_batch
        self._start_batch = 0
        start_row_cursor = self._start_row_cursor
        self._start_row_cursor = None
        if start_row_cursor is not None:
            iterator = self._sampler.iter_with_info(start_index=start_row_cursor)
        else:
            iterator = self._sampler.iter_with_info()

        for batch_idx, (indices, resume_info) in enumerate(iterator, start=1):
            if start_row_cursor is None and batch_idx <= start_batch:
                continue
            batch, scalars = self._load_batch(indices)
            yield batch, scalars | {"resume_info": resume_info}
