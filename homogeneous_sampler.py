"""Deterministic, category-homogeneous multipacking with replayable row cursors."""

import numpy as np
from multipack_sampler import MultipackDistributedBatchSampler, allocate


class HomogeneousSampler(MultipackDistributedBatchSampler):
    def __init__(self, *, categories, seed=0, **kwargs):
        super().__init__(**kwargs)
        if categories.shape != self.lengths.shape or categories.dtype.kind not in 'iu':
            raise ValueError('category_id.npy must be an integer vector aligned with epoch rows')
        if np.any(categories < 0) or np.any(self.lengths > self.batch_max_length):
            raise ValueError('Invalid category or overlength example')
        self.categories = categories
        keys = np.unique(categories)
        np.random.default_rng(seed).shuffle(keys)
        # Preserve the sampled epoch's random order within each category.
        order = np.argsort(categories, kind='stable')
        sorted_categories = categories[order]
        self.groups = [order[np.searchsorted(sorted_categories, key, 'left'):
                             np.searchsorted(sorted_categories, key, 'right')] for key in keys]
        self.group_lengths = [self.lengths[indices] for indices in self.groups]

    def iter_with_info(self, start_index=0):
        if start_index < 0:
            raise ValueError('Negative row cursor')
        heap = np.empty(self.num_replicas + 1, dtype=self.lengths.dtype)
        positions = [0] * len(self.groups)
        cursor = 0
        # Round-robin whole homogeneous global microbatches. Resume replays the
        # deterministic CPU allocation, not token reads; cursor is virtual here.
        active = True
        while active:
            active = False
            for group_id, indices in enumerate(self.groups):
                pos = positions[group_id]
                if pos >= len(indices):
                    continue
                active = True
                full, used, selected, tokens = allocate(heap, pos, self.group_lengths[group_id],
                                                       self.rank, self.batch_max_length, self.num_replicas)
                positions[group_id] += used
                before, cursor = cursor, cursor + used
                if not full:
                    positions[group_id] = len(indices)
                    continue
                if before < start_index < cursor:
                    raise ValueError('Resume cursor falls inside a homogeneous batch')
                if before < start_index:
                    continue
                self.eff_total_used += tokens
                self.eff_total_slots += self.num_replicas * self.batch_max_length
                yield indices[selected], dict(global_row_start=before, global_row_end=cursor,
                                              global_numseq=int(used), global_batch_totlen=int(tokens))
