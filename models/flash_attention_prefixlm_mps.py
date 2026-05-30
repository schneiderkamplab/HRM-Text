import math
from functools import lru_cache
from typing import Any

import torch
from torch import Tensor

from models.flash_attention_prefixlm_common import prefixlm_seq_info_from_tensors

__all__ = [
    "flash_attn_varlen_prefixlm_mps",
    "flash_attn_varlen_prefixlm_mps_backward_dense_math",
    "flash_attn_varlen_prefixlm_mps_backward_parts",
    "flash_attn_varlen_prefixlm_mps_backward_context",
    "flash_attn_varlen_prefixlm_mps_backward_dk_dv_part",
    "flash_attn_varlen_prefixlm_mps_backward_dq_part",
    "flash_attn_varlen_prefixlm_mps_headblock_forward",
    "flash_attn_varlen_prefixlm_mps_matmulblock_forward",
    "flash_attn_varlen_prefixlm_mps_online_forward",
    "flash_attn_varlen_prefixlm_mps_simd32_forward",
    "flash_attn_varlen_prefixlm_mps_tiled_forward",
]


_MPS_PREFIXLM_SHADER = r"""
#include <metal_stdlib>
using namespace metal;

static inline int find_seq_id(device const int* cu_seqlens, int numseqs, int token) {
    int lo = 0;
    int hi = numseqs;
    while (lo + 1 < hi) {
        int mid = (lo + hi) >> 1;
        if (cu_seqlens[mid] <= token) {
            lo = mid;
        } else {
            hi = mid;
        }
    }
    return lo;
}

static inline bool prefixlm_allowed(int is_causal, int prefix_len, int query_pos, int key_pos) {
    if (is_causal != 0) {
        return key_pos <= query_pos;
    }
    if (query_pos < prefix_len) {
        return key_pos < prefix_len;
    }
    return key_pos <= query_pos;
}

static inline float qk_score(
    device const float* q,
    device const float* k,
    int query_token,
    int key_token,
    int head,
    int num_heads,
    int head_dim,
    float scale
) {
    int q_base = (query_token * num_heads + head) * head_dim;
    int k_base = (key_token * num_heads + head) * head_dim;
    float score = 0.0f;
    for (int d = 0; d < head_dim; ++d) {
        score += q[q_base + d] * k[k_base + d];
    }
    return score * scale;
}

static inline void reduce_sum(threadgroup float* scratch, uint lane, uint group_width) {
    threadgroup_barrier(mem_flags::mem_threadgroup);
    for (uint stride = group_width >> 1; stride > 0; stride >>= 1) {
        if (lane < stride) {
            scratch[lane] += scratch[lane + stride];
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }
}

kernel void prefixlm_forward(
    device const float* q [[buffer(0)]],
    device const float* k [[buffer(1)]],
    device const float* v [[buffer(2)]],
    device float* out [[buffer(3)]],
    device float* lse [[buffer(4)]],
    device const int* prefix_lens [[buffer(5)]],
    device const int* causal_lens [[buffer(6)]],
    device const int* cu_seqlens [[buffer(7)]],
    constant int& total_seqlen [[buffer(8)]],
    constant int& numseqs [[buffer(9)]],
    constant int& num_heads [[buffer(10)]],
    constant int& head_dim [[buffer(11)]],
    constant int& is_causal [[buffer(12)]],
    constant float& scale [[buffer(13)]],
    uint3 gid [[thread_position_in_grid]],
    uint3 threads_per_threadgroup [[threads_per_threadgroup]],
    uint3 lane_id [[thread_position_in_threadgroup]]
) {
    threadgroup float scratch[256];
    uint group_width = threads_per_threadgroup.x;
    uint lane = lane_id.x;
    int group = int(gid.x / group_width);
    int query_token = group / num_heads;
    int head = group - query_token * num_heads;
    if (query_token >= total_seqlen || head >= num_heads) {
        return;
    }

    int seq_id = find_seq_id(cu_seqlens, numseqs, query_token);
    int seq_start = cu_seqlens[seq_id];
    int seq_end = cu_seqlens[seq_id + 1];
    int query_pos = query_token - seq_start;
    int prefix_len = prefix_lens[seq_id];
    int q_base = (query_token * num_heads + head) * head_dim;

    float max_score = -INFINITY;
    for (int key_token = seq_start; key_token < seq_end; ++key_token) {
        int key_pos = key_token - seq_start;
        if (!prefixlm_allowed(is_causal, prefix_len, query_pos, key_pos)) {
            continue;
        }
        int k_base = (key_token * num_heads + head) * head_dim;
        scratch[lane] = lane < uint(head_dim) ? q[q_base + lane] * k[k_base + lane] : 0.0f;
        reduce_sum(scratch, lane, group_width);
        if (lane == 0) {
            max_score = max(max_score, scratch[0] * scale);
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }
    if (lane == 0) {
        scratch[0] = max_score;
    }
    threadgroup_barrier(mem_flags::mem_threadgroup);
    max_score = scratch[0];

    float denom = 0.0f;
    for (int key_token = seq_start; key_token < seq_end; ++key_token) {
        int key_pos = key_token - seq_start;
        if (!prefixlm_allowed(is_causal, prefix_len, query_pos, key_pos)) {
            continue;
        }
        int k_base = (key_token * num_heads + head) * head_dim;
        scratch[lane] = lane < uint(head_dim) ? q[q_base + lane] * k[k_base + lane] : 0.0f;
        reduce_sum(scratch, lane, group_width);
        if (lane == 0) {
            denom += exp(scratch[0] * scale - max_score);
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }

    if (lane == 0) {
        scratch[0] = max_score + log(denom);
        lse[query_token * num_heads + head] = scratch[0];
    }
    threadgroup_barrier(mem_flags::mem_threadgroup);
    float logsumexp = scratch[0];

    int out_base = (query_token * num_heads + head) * head_dim;
    float acc = 0.0f;
    for (int key_token = seq_start; key_token < seq_end; ++key_token) {
        int key_pos = key_token - seq_start;
        if (!prefixlm_allowed(is_causal, prefix_len, query_pos, key_pos)) {
            continue;
        }
        int kv_base = (key_token * num_heads + head) * head_dim;
        scratch[lane] = lane < uint(head_dim) ? q[q_base + lane] * k[kv_base + lane] : 0.0f;
        reduce_sum(scratch, lane, group_width);
        float prob = exp(scratch[0] * scale - logsumexp);
        threadgroup_barrier(mem_flags::mem_threadgroup);
        if (lane < uint(head_dim)) {
            acc += prob * v[kv_base + lane];
        }
    }
    if (lane < uint(head_dim)) {
        out[out_base + lane] = acc;
    }
}

kernel void prefixlm_forward_tiled_hdim128_q4(
    device const float* q [[buffer(0)]],
    device const float* k [[buffer(1)]],
    device const float* v [[buffer(2)]],
    device float* out [[buffer(3)]],
    device float* lse [[buffer(4)]],
    device const int* prefix_lens [[buffer(5)]],
    device const int* causal_lens [[buffer(6)]],
    device const int* cu_seqlens [[buffer(7)]],
    constant int& total_seqlen [[buffer(8)]],
    constant int& numseqs [[buffer(9)]],
    constant int& num_heads [[buffer(10)]],
    constant int& is_causal [[buffer(11)]],
    constant float& scale [[buffer(12)]],
    uint3 gid [[thread_position_in_grid]],
    uint3 lane_id [[thread_position_in_threadgroup]]
) {
    constexpr uint head_dim = 128;
    constexpr uint q_block = 4;
    threadgroup float scratch[q_block * head_dim];
    threadgroup float k_scratch[head_dim];
    threadgroup float row_scalar[q_block];

    uint lane = lane_id.x;
    uint row = lane_id.y;
    int block_group = int(gid.x / head_dim);
    int query_block = block_group / num_heads;
    int head = block_group - query_block * num_heads;
    int query_token = query_block * int(q_block) + int(row);
    if (head >= num_heads || row >= q_block) {
        return;
    }
    bool active_query = query_token < total_seqlen;

    int seq_id = active_query ? find_seq_id(cu_seqlens, numseqs, query_token) : 0;
    int seq_start = active_query ? cu_seqlens[seq_id] : 0;
    int seq_end = active_query ? cu_seqlens[seq_id + 1] : 0;
    int query_pos = query_token - seq_start;
    int prefix_len = active_query ? prefix_lens[seq_id] : 0;
    int q_base = (query_token * num_heads + head) * int(head_dim);
    uint scratch_base = row * head_dim;

    float max_score = -INFINITY;
    for (int key_token = seq_start; key_token < seq_end; ++key_token) {
        int key_pos = key_token - seq_start;
        bool allowed = active_query && prefixlm_allowed(is_causal, prefix_len, query_pos, key_pos);
        int k_base = (key_token * num_heads + head) * int(head_dim);
        if (row == 0) {
            k_scratch[lane] = k[k_base + int(lane)];
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
        scratch[scratch_base + lane] = allowed ? q[q_base + int(lane)] * k_scratch[lane] : 0.0f;
        threadgroup_barrier(mem_flags::mem_threadgroup);
        for (uint stride = head_dim >> 1; stride > 0; stride >>= 1) {
            if (lane < stride) {
                scratch[scratch_base + lane] += scratch[scratch_base + lane + stride];
            }
            threadgroup_barrier(mem_flags::mem_threadgroup);
        }
        if (lane == 0 && allowed) {
            max_score = max(max_score, scratch[scratch_base] * scale);
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }
    if (lane == 0) {
        row_scalar[row] = max_score;
    }
    threadgroup_barrier(mem_flags::mem_threadgroup);
    max_score = row_scalar[row];

    float denom = 0.0f;
    for (int key_token = seq_start; key_token < seq_end; ++key_token) {
        int key_pos = key_token - seq_start;
        bool allowed = active_query && prefixlm_allowed(is_causal, prefix_len, query_pos, key_pos);
        int k_base = (key_token * num_heads + head) * int(head_dim);
        if (row == 0) {
            k_scratch[lane] = k[k_base + int(lane)];
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
        scratch[scratch_base + lane] = allowed ? q[q_base + int(lane)] * k_scratch[lane] : 0.0f;
        threadgroup_barrier(mem_flags::mem_threadgroup);
        for (uint stride = head_dim >> 1; stride > 0; stride >>= 1) {
            if (lane < stride) {
                scratch[scratch_base + lane] += scratch[scratch_base + lane + stride];
            }
            threadgroup_barrier(mem_flags::mem_threadgroup);
        }
        if (lane == 0 && allowed) {
            denom += exp(scratch[scratch_base] * scale - max_score);
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }
    if (lane == 0) {
        row_scalar[row] = max_score + log(denom);
        if (active_query) {
            lse[query_token * num_heads + head] = row_scalar[row];
        }
    }
    threadgroup_barrier(mem_flags::mem_threadgroup);
    float logsumexp = row_scalar[row];

    int out_base = (query_token * num_heads + head) * int(head_dim);
    float acc = 0.0f;
    for (int key_token = seq_start; key_token < seq_end; ++key_token) {
        int key_pos = key_token - seq_start;
        bool allowed = active_query && prefixlm_allowed(is_causal, prefix_len, query_pos, key_pos);
        int kv_base = (key_token * num_heads + head) * int(head_dim);
        if (row == 0) {
            k_scratch[lane] = k[kv_base + int(lane)];
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
        scratch[scratch_base + lane] = allowed ? q[q_base + int(lane)] * k_scratch[lane] : 0.0f;
        threadgroup_barrier(mem_flags::mem_threadgroup);
        for (uint stride = head_dim >> 1; stride > 0; stride >>= 1) {
            if (lane < stride) {
                scratch[scratch_base + lane] += scratch[scratch_base + lane + stride];
            }
            threadgroup_barrier(mem_flags::mem_threadgroup);
        }
        float prob = allowed ? exp(scratch[scratch_base] * scale - logsumexp) : 0.0f;
        threadgroup_barrier(mem_flags::mem_threadgroup);
        acc += prob * v[kv_base + int(lane)];
    }
    if (active_query) {
        out[out_base + int(lane)] = acc;
    }
}

kernel void prefixlm_forward_online_hdim128(
    device const float* q [[buffer(0)]],
    device const float* k [[buffer(1)]],
    device const float* v [[buffer(2)]],
    device float* out [[buffer(3)]],
    device float* lse [[buffer(4)]],
    device const int* prefix_lens [[buffer(5)]],
    device const int* causal_lens [[buffer(6)]],
    device const int* cu_seqlens [[buffer(7)]],
    constant int& total_seqlen [[buffer(8)]],
    constant int& numseqs [[buffer(9)]],
    constant int& num_heads [[buffer(10)]],
    constant int& is_causal [[buffer(11)]],
    constant float& scale [[buffer(12)]],
    uint3 gid [[thread_position_in_grid]],
    uint3 lane_id [[thread_position_in_threadgroup]]
) {
    constexpr uint head_dim = 128;
    threadgroup float scratch[head_dim];
    threadgroup float scalar[4];

    uint lane = lane_id.x;
    int group = int(gid.x / head_dim);
    int query_token = group / num_heads;
    int head = group - query_token * num_heads;
    if (query_token >= total_seqlen || head >= num_heads) {
        return;
    }

    int seq_id = find_seq_id(cu_seqlens, numseqs, query_token);
    int seq_start = cu_seqlens[seq_id];
    int seq_end = cu_seqlens[seq_id + 1];
    int query_pos = query_token - seq_start;
    int prefix_len = prefix_lens[seq_id];
    int q_base = (query_token * num_heads + head) * int(head_dim);

    float m = -INFINITY;
    float l = 0.0f;
    float acc = 0.0f;

    for (int key_token = seq_start; key_token < seq_end; ++key_token) {
        int key_pos = key_token - seq_start;
        if (!prefixlm_allowed(is_causal, prefix_len, query_pos, key_pos)) {
            continue;
        }

        int kv_base = (key_token * num_heads + head) * int(head_dim);
        scratch[lane] = q[q_base + int(lane)] * k[kv_base + int(lane)];
        threadgroup_barrier(mem_flags::mem_threadgroup);
        for (uint stride = head_dim >> 1; stride > 0; stride >>= 1) {
            if (lane < stride) {
                scratch[lane] += scratch[lane + stride];
            }
            threadgroup_barrier(mem_flags::mem_threadgroup);
        }

        if (lane == 0) {
            float score = scratch[0] * scale;
            float m_new = max(m, score);
            float alpha = exp(m - m_new);
            float beta = exp(score - m_new);
            l = l * alpha + beta;
            m = m_new;
            scalar[0] = alpha;
            scalar[1] = beta;
            scalar[2] = m;
            scalar[3] = l;
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
        acc = acc * scalar[0] + scalar[1] * v[kv_base + int(lane)];
        m = scalar[2];
        l = scalar[3];
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }

    int out_base = (query_token * num_heads + head) * int(head_dim);
    out[out_base + int(lane)] = acc / l;
    if (lane == 0) {
        lse[query_token * num_heads + head] = m + log(l);
    }
}

kernel void prefixlm_forward_online_hdim128_simd32(
    device const float* q [[buffer(0)]],
    device const float* k [[buffer(1)]],
    device const float* v [[buffer(2)]],
    device float* out [[buffer(3)]],
    device float* lse [[buffer(4)]],
    device const int* prefix_lens [[buffer(5)]],
    device const int* causal_lens [[buffer(6)]],
    device const int* cu_seqlens [[buffer(7)]],
    constant int& total_seqlen [[buffer(8)]],
    constant int& numseqs [[buffer(9)]],
    constant int& num_heads [[buffer(10)]],
    constant int& is_causal [[buffer(11)]],
    constant float& scale [[buffer(12)]],
    uint3 gid [[thread_position_in_grid]],
    uint simd_lid [[thread_index_in_simdgroup]]
) {
    constexpr uint head_dim = 128;
    constexpr uint lanes = 32;
    constexpr uint elems_per_lane = head_dim / lanes;

    uint lane = simd_lid;
    int group = int(gid.x / lanes);
    int query_token = group / num_heads;
    int head = group - query_token * num_heads;
    if (query_token >= total_seqlen || head >= num_heads) {
        return;
    }

    int seq_id = find_seq_id(cu_seqlens, numseqs, query_token);
    int seq_start = cu_seqlens[seq_id];
    int seq_end = cu_seqlens[seq_id + 1];
    int query_pos = query_token - seq_start;
    int prefix_len = prefix_lens[seq_id];
    int q_base = (query_token * num_heads + head) * int(head_dim);

    float m = -INFINITY;
    float l = 0.0f;
    float acc[elems_per_lane];
    for (uint i = 0; i < elems_per_lane; ++i) {
        acc[i] = 0.0f;
    }

    for (int key_token = seq_start; key_token < seq_end; ++key_token) {
        int key_pos = key_token - seq_start;
        if (!prefixlm_allowed(is_causal, prefix_len, query_pos, key_pos)) {
            continue;
        }

        int kv_base = (key_token * num_heads + head) * int(head_dim);
        float score = 0.0f;
        for (uint i = 0; i < elems_per_lane; ++i) {
            uint d = lane + i * lanes;
            score += q[q_base + int(d)] * k[kv_base + int(d)];
        }
        score = simd_sum(score) * scale;

        float m_new = max(m, score);
        float alpha;
        float beta;
        if (m_new == -INFINITY) {
            alpha = 1.0f;
            beta = 0.0f;
        } else {
            alpha = metal::fast::exp(m - m_new);
            beta = metal::fast::exp(score - m_new);
        }
        l = l * alpha + beta;
        m = m_new;

        for (uint i = 0; i < elems_per_lane; ++i) {
            uint d = lane + i * lanes;
            acc[i] = acc[i] * alpha + beta * v[kv_base + int(d)];
        }
    }

    int out_base = (query_token * num_heads + head) * int(head_dim);
    float safe_l = l == 0.0f ? 1e-6f : l;
    for (uint i = 0; i < elems_per_lane; ++i) {
        uint d = lane + i * lanes;
        out[out_base + int(d)] = acc[i] / safe_l;
    }
    if (lane == 0) {
        lse[query_token * num_heads + head] = m + log(safe_l);
    }
}

kernel void prefixlm_forward_online_hdim128_headblock4(
    device const float* q [[buffer(0)]],
    device const float* k [[buffer(1)]],
    device const float* v [[buffer(2)]],
    device float* out [[buffer(3)]],
    device float* lse [[buffer(4)]],
    device const int* prefix_lens [[buffer(5)]],
    device const int* causal_lens [[buffer(6)]],
    device const int* cu_seqlens [[buffer(7)]],
    constant int& total_seqlen [[buffer(8)]],
    constant int& numseqs [[buffer(9)]],
    constant int& num_heads [[buffer(10)]],
    constant int& is_causal [[buffer(11)]],
    constant float& scale [[buffer(12)]],
    uint3 gid [[thread_position_in_grid]],
    uint3 lane_id [[thread_position_in_threadgroup]]
) {
    constexpr uint head_dim = 128;
    constexpr uint head_block = 4;
    threadgroup float scratch[head_block * head_dim];
    threadgroup float scalar[head_block * 4];

    uint lane = lane_id.x;
    uint row = lane_id.y;
    int head_blocks = (num_heads + int(head_block) - 1) / int(head_block);
    int group = int(gid.x / head_dim);
    int query_token = group / head_blocks;
    int head_block_id = group - query_token * head_blocks;
    int head = head_block_id * int(head_block) + int(row);
    if (query_token >= total_seqlen || head >= num_heads || row >= head_block) {
        return;
    }

    int seq_id = find_seq_id(cu_seqlens, numseqs, query_token);
    int seq_start = cu_seqlens[seq_id];
    int seq_end = cu_seqlens[seq_id + 1];
    int query_pos = query_token - seq_start;
    int prefix_len = prefix_lens[seq_id];
    int q_base = (query_token * num_heads + head) * int(head_dim);
    uint scratch_base = row * head_dim;
    uint scalar_base = row * 4;

    float m = -INFINITY;
    float l = 0.0f;
    float acc = 0.0f;

    for (int key_token = seq_start; key_token < seq_end; ++key_token) {
        int key_pos = key_token - seq_start;
        if (!prefixlm_allowed(is_causal, prefix_len, query_pos, key_pos)) {
            continue;
        }

        int kv_base = (key_token * num_heads + head) * int(head_dim);
        scratch[scratch_base + lane] = q[q_base + int(lane)] * k[kv_base + int(lane)];
        threadgroup_barrier(mem_flags::mem_threadgroup);
        for (uint stride = head_dim >> 1; stride > 0; stride >>= 1) {
            if (lane < stride) {
                scratch[scratch_base + lane] += scratch[scratch_base + lane + stride];
            }
            threadgroup_barrier(mem_flags::mem_threadgroup);
        }

        if (lane == 0) {
            float score = scratch[scratch_base] * scale;
            float m_new = max(m, score);
            float alpha = exp(m - m_new);
            float beta = exp(score - m_new);
            l = l * alpha + beta;
            m = m_new;
            scalar[scalar_base] = alpha;
            scalar[scalar_base + 1] = beta;
            scalar[scalar_base + 2] = m;
            scalar[scalar_base + 3] = l;
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
        acc = acc * scalar[scalar_base] + scalar[scalar_base + 1] * v[kv_base + int(lane)];
        m = scalar[scalar_base + 2];
        l = scalar[scalar_base + 3];
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }

    int out_base = (query_token * num_heads + head) * int(head_dim);
    out[out_base + int(lane)] = acc / l;
    if (lane == 0) {
        lse[query_token * num_heads + head] = m + log(l);
    }
}

kernel void prefixlm_forward_matmulblock_hdim128_q2_k8_l32(
    device const float* q [[buffer(0)]],
    device const float* k [[buffer(1)]],
    device const float* v [[buffer(2)]],
    device float* out [[buffer(3)]],
    device float* lse [[buffer(4)]],
    device const int* prefix_lens [[buffer(5)]],
    device const int* causal_lens [[buffer(6)]],
    device const int* cu_seqlens [[buffer(7)]],
    constant int& total_seqlen [[buffer(8)]],
    constant int& numseqs [[buffer(9)]],
    constant int& num_heads [[buffer(10)]],
    constant int& max_seqlen_all [[buffer(11)]],
    constant int& is_causal [[buffer(12)]],
    constant float& scale [[buffer(13)]],
    uint3 tgid [[threadgroup_position_in_grid]],
    uint3 tid [[thread_position_in_threadgroup]]
) {
    constexpr uint head_dim = 128;
    constexpr uint q_block = 2;
    constexpr uint k_block = 8;
    constexpr uint dot_lanes = 32;
    constexpr uint value_chunks = head_dim / dot_lanes;
    threadgroup float partial[q_block * k_block * dot_lanes];
    threadgroup float scores[q_block * k_block];
    threadgroup float betas[q_block * k_block];
    threadgroup float row_state[q_block * 3];

    uint lane = tid.x;
    uint k_col = tid.y;
    uint q_row = tid.z;
    int query_block = int(tgid.x) / num_heads;
    int head = int(tgid.x) - query_block * num_heads;
    int query_token = query_block * int(q_block) + int(q_row);
    bool active_query = query_token < total_seqlen && head < num_heads;

    int seq_id = active_query ? find_seq_id(cu_seqlens, numseqs, query_token) : 0;
    int seq_start = active_query ? cu_seqlens[seq_id] : 0;
    int seq_end = active_query ? cu_seqlens[seq_id + 1] : 0;
    int seq_len = seq_end - seq_start;
    int query_pos = query_token - seq_start;
    int prefix_len = active_query ? prefix_lens[seq_id] : 0;
    int q_base = (query_token * num_heads + head) * int(head_dim);
    uint partial_base = (q_row * k_block + k_col) * dot_lanes;
    uint score_base = q_row * k_block;
    uint state_base = q_row * 3;

    float m = -INFINITY;
    float l = 0.0f;
    float acc[value_chunks];
    for (uint i = 0; i < value_chunks; ++i) {
        acc[i] = 0.0f;
    }

    for (int tile_start = 0; tile_start < max_seqlen_all; tile_start += int(k_block)) {
        int key_pos = tile_start + int(k_col);
        int key_token = seq_start + key_pos;
        bool allowed = active_query
            && key_pos < seq_len
            && prefixlm_allowed(is_causal, prefix_len, query_pos, key_pos);

        float dot = 0.0f;
        if (allowed) {
            int k_base = (key_token * num_heads + head) * int(head_dim);
            for (uint d = lane; d < head_dim; d += dot_lanes) {
                dot += q[q_base + int(d)] * k[k_base + int(d)];
            }
        }
        partial[partial_base + lane] = dot;
        threadgroup_barrier(mem_flags::mem_threadgroup);
        for (uint stride = dot_lanes >> 1; stride > 0; stride >>= 1) {
            if (lane < stride) {
                partial[partial_base + lane] += partial[partial_base + lane + stride];
            }
            threadgroup_barrier(mem_flags::mem_threadgroup);
        }
        if (lane == 0) {
            scores[score_base + k_col] = allowed ? partial[partial_base] * scale : -INFINITY;
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);

        if (k_col == 0 && lane == 0) {
            float tile_max = -INFINITY;
            for (uint kk = 0; kk < k_block; ++kk) {
                tile_max = max(tile_max, scores[score_base + kk]);
            }
            float m_new = max(m, tile_max);
            float alpha = exp(m - m_new);
            float beta_sum = 0.0f;
            for (uint kk = 0; kk < k_block; ++kk) {
                float beta = exp(scores[score_base + kk] - m_new);
                betas[score_base + kk] = beta;
                beta_sum += beta;
            }
            l = l * alpha + beta_sum;
            m = m_new;
            row_state[state_base] = alpha;
            row_state[state_base + 1] = m;
            row_state[state_base + 2] = l;
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);

        if (k_col == 0) {
            float alpha = row_state[state_base];
            for (uint i = 0; i < 8; ++i) {
                acc[i] *= alpha;
            }
            for (uint kk = 0; kk < k_block; ++kk) {
                float beta = betas[score_base + kk];
                if (beta != 0.0f) {
                    int value_key_pos = tile_start + int(kk);
                    int value_key_token = seq_start + value_key_pos;
                    int v_base = (value_key_token * num_heads + head) * int(head_dim);
                    for (uint i = 0; i < value_chunks; ++i) {
                        uint d = lane + i * dot_lanes;
                        acc[i] += beta * v[v_base + int(d)];
                    }
                }
            }
            m = row_state[state_base + 1];
            l = row_state[state_base + 2];
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }

    if (active_query && k_col == 0) {
        int out_base = (query_token * num_heads + head) * int(head_dim);
        for (uint i = 0; i < value_chunks; ++i) {
            uint d = lane + i * dot_lanes;
            out[out_base + int(d)] = acc[i] / l;
        }
        if (lane == 0) {
            lse[query_token * num_heads + head] = m + log(l);
        }
    }
}

kernel void prefixlm_backward_dq(
    device const float* q [[buffer(0)]],
    device const float* k [[buffer(1)]],
    device const float* v [[buffer(2)]],
    device const float* out [[buffer(3)]],
    device const float* lse [[buffer(4)]],
    device const float* grad_out [[buffer(5)]],
    device float* grad_q [[buffer(6)]],
    device const int* prefix_lens [[buffer(7)]],
    device const int* causal_lens [[buffer(8)]],
    device const int* cu_seqlens [[buffer(9)]],
    constant int& total_seqlen [[buffer(10)]],
    constant int& numseqs [[buffer(11)]],
    constant int& num_heads [[buffer(12)]],
    constant int& head_dim [[buffer(13)]],
    constant int& is_causal [[buffer(14)]],
    constant float& scale [[buffer(15)]],
    uint3 gid [[thread_position_in_grid]],
    uint3 threads_per_threadgroup [[threads_per_threadgroup]],
    uint3 lane_id [[thread_position_in_threadgroup]]
) {
    threadgroup float scratch[256];
    uint group_width = threads_per_threadgroup.x;
    uint lane = lane_id.x;
    int group = int(gid.x / group_width);
    int query_token = group / num_heads;
    int head = group - query_token * num_heads;
    if (query_token >= total_seqlen || head >= num_heads) {
        return;
    }

    int seq_id = find_seq_id(cu_seqlens, numseqs, query_token);
    int seq_start = cu_seqlens[seq_id];
    int seq_end = cu_seqlens[seq_id + 1];
    int query_pos = query_token - seq_start;
    int prefix_len = prefix_lens[seq_id];
    float query_lse = lse[query_token * num_heads + head];

    int qo_base = (query_token * num_heads + head) * head_dim;
    float acc = 0.0f;
    for (int key_token = seq_start; key_token < seq_end; ++key_token) {
        int key_pos = key_token - seq_start;
        if (!prefixlm_allowed(is_causal, prefix_len, query_pos, key_pos)) {
            continue;
        }
        int kv_base = (key_token * num_heads + head) * head_dim;
        scratch[lane] = lane < uint(head_dim) ? q[qo_base + lane] * k[kv_base + lane] : 0.0f;
        reduce_sum(scratch, lane, group_width);
        float prob = exp(scratch[0] * scale - query_lse);
        threadgroup_barrier(mem_flags::mem_threadgroup);

        scratch[lane] = lane < uint(head_dim) ? grad_out[qo_base + lane] * (v[kv_base + lane] - out[qo_base + lane]) : 0.0f;
        reduce_sum(scratch, lane, group_width);
        float dot = scratch[0];
        threadgroup_barrier(mem_flags::mem_threadgroup);

        if (lane < uint(head_dim)) {
            acc += prob * dot * k[kv_base + lane];
        }
    }
    if (lane < uint(head_dim)) {
        grad_q[qo_base + lane] = acc * scale;
    }
}

kernel void prefixlm_backward_dq_hdim128(
    device const float* q [[buffer(0)]],
    device const float* k [[buffer(1)]],
    device const float* v [[buffer(2)]],
    device const float* out [[buffer(3)]],
    device const float* lse [[buffer(4)]],
    device const float* grad_out [[buffer(5)]],
    device float* grad_q [[buffer(6)]],
    device const int* prefix_lens [[buffer(7)]],
    device const int* causal_lens [[buffer(8)]],
    device const int* cu_seqlens [[buffer(9)]],
    constant int& total_seqlen [[buffer(10)]],
    constant int& numseqs [[buffer(11)]],
    constant int& num_heads [[buffer(12)]],
    constant int& is_causal [[buffer(13)]],
    constant float& scale [[buffer(14)]],
    uint3 gid [[thread_position_in_grid]],
    uint3 lane_id [[thread_position_in_threadgroup]]
) {
    constexpr uint head_dim = 128;
    threadgroup float score_scratch[head_dim];
    threadgroup float dot_scratch[head_dim];

    uint lane = lane_id.x;
    int group = int(gid.x / head_dim);
    int query_token = group / num_heads;
    int head = group - query_token * num_heads;
    if (query_token >= total_seqlen || head >= num_heads) {
        return;
    }

    int seq_id = find_seq_id(cu_seqlens, numseqs, query_token);
    int seq_start = cu_seqlens[seq_id];
    int seq_end = cu_seqlens[seq_id + 1];
    int query_pos = query_token - seq_start;
    int prefix_len = prefix_lens[seq_id];
    float query_lse = lse[query_token * num_heads + head];

    int qo_base = (query_token * num_heads + head) * int(head_dim);
    float acc = 0.0f;
    for (int key_token = seq_start; key_token < seq_end; ++key_token) {
        int key_pos = key_token - seq_start;
        if (!prefixlm_allowed(is_causal, prefix_len, query_pos, key_pos)) {
            continue;
        }
        int kv_base = (key_token * num_heads + head) * int(head_dim);
        score_scratch[lane] = q[qo_base + int(lane)] * k[kv_base + int(lane)];
        dot_scratch[lane] = grad_out[qo_base + int(lane)] * (v[kv_base + int(lane)] - out[qo_base + int(lane)]);
        threadgroup_barrier(mem_flags::mem_threadgroup);
        for (uint stride = head_dim >> 1; stride > 0; stride >>= 1) {
            if (lane < stride) {
                score_scratch[lane] += score_scratch[lane + stride];
                dot_scratch[lane] += dot_scratch[lane + stride];
            }
            threadgroup_barrier(mem_flags::mem_threadgroup);
        }

        float prob = exp(score_scratch[0] * scale - query_lse);
        float dot = dot_scratch[0];
        threadgroup_barrier(mem_flags::mem_threadgroup);
        acc += prob * dot * k[kv_base + int(lane)];
    }
    grad_q[qo_base + int(lane)] = acc * scale;
}

kernel void prefixlm_backward_query_dot_hdim128(
    device const float* out [[buffer(0)]],
    device const float* grad_out [[buffer(1)]],
    device float* query_dot [[buffer(2)]],
    constant int& total_seqlen [[buffer(3)]],
    constant int& num_heads [[buffer(4)]],
    uint3 gid [[thread_position_in_grid]],
    uint3 lane_id [[thread_position_in_threadgroup]]
) {
    constexpr uint head_dim = 128;
    threadgroup float scratch[head_dim];

    uint lane = lane_id.x;
    int group = int(gid.x / head_dim);
    int query_token = group / num_heads;
    int head = group - query_token * num_heads;
    if (query_token >= total_seqlen || head >= num_heads) {
        return;
    }

    int base = (query_token * num_heads + head) * int(head_dim);
    scratch[lane] = out[base + int(lane)] * grad_out[base + int(lane)];
    threadgroup_barrier(mem_flags::mem_threadgroup);
    for (uint stride = head_dim >> 1; stride > 0; stride >>= 1) {
        if (lane < stride) {
            scratch[lane] += scratch[lane + stride];
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }
    if (lane == 0) {
        query_dot[query_token * num_heads + head] = scratch[0];
    }
}

kernel void prefixlm_backward_query_dot_hdim128_simd32(
    device const float* out [[buffer(0)]],
    device const float* grad_out [[buffer(1)]],
    device float* query_dot [[buffer(2)]],
    constant int& total_seqlen [[buffer(3)]],
    constant int& num_heads [[buffer(4)]],
    uint3 gid [[thread_position_in_grid]],
    uint simd_lid [[thread_index_in_simdgroup]]
) {
    constexpr uint head_dim = 128;
    constexpr uint lanes = 32;
    constexpr uint elems_per_lane = head_dim / lanes;

    uint lane = simd_lid;
    int group = int(gid.x / lanes);
    int query_token = group / num_heads;
    int head = group - query_token * num_heads;
    if (query_token >= total_seqlen || head >= num_heads) {
        return;
    }

    int base = (query_token * num_heads + head) * int(head_dim);
    float acc = 0.0f;
    for (uint i = 0; i < elems_per_lane; ++i) {
        uint d = lane + i * lanes;
        acc += out[base + int(d)] * grad_out[base + int(d)];
    }
    acc = simd_sum(acc);
    if (lane == 0) {
        query_dot[query_token * num_heads + head] = acc;
    }
}

kernel void prefixlm_backward_dq_hdim128_predot(
    device const float* q [[buffer(0)]],
    device const float* k [[buffer(1)]],
    device const float* v [[buffer(2)]],
    device const float* out [[buffer(3)]],
    device const float* lse [[buffer(4)]],
    device const float* grad_out [[buffer(5)]],
    device float* grad_q [[buffer(6)]],
    device const float* query_dot [[buffer(7)]],
    device const int* prefix_lens [[buffer(8)]],
    device const int* causal_lens [[buffer(9)]],
    device const int* cu_seqlens [[buffer(10)]],
    constant int& total_seqlen [[buffer(11)]],
    constant int& numseqs [[buffer(12)]],
    constant int& num_heads [[buffer(13)]],
    constant int& is_causal [[buffer(14)]],
    constant float& scale [[buffer(15)]],
    uint3 gid [[thread_position_in_grid]],
    uint3 lane_id [[thread_position_in_threadgroup]]
) {
    constexpr uint head_dim = 128;
    threadgroup float score_scratch[head_dim];
    threadgroup float dot_scratch[head_dim];

    uint lane = lane_id.x;
    int group = int(gid.x / head_dim);
    int query_token = group / num_heads;
    int head = group - query_token * num_heads;
    if (query_token >= total_seqlen || head >= num_heads) {
        return;
    }

    int seq_id = find_seq_id(cu_seqlens, numseqs, query_token);
    int seq_start = cu_seqlens[seq_id];
    int seq_end = cu_seqlens[seq_id + 1];
    int query_pos = query_token - seq_start;
    int prefix_len = prefix_lens[seq_id];
    float query_lse = lse[query_token * num_heads + head];
    float d_out_dot_out = query_dot[query_token * num_heads + head];
    int key_start = seq_start;
    int key_end = is_causal != 0
        ? seq_start + query_pos + 1
        : (query_pos < prefix_len ? seq_start + prefix_len : seq_start + query_pos + 1);

    int qo_base = (query_token * num_heads + head) * int(head_dim);
    float acc = 0.0f;
    for (int key_token = key_start; key_token < key_end; ++key_token) {
        int kv_base = (key_token * num_heads + head) * int(head_dim);
        score_scratch[lane] = q[qo_base + int(lane)] * k[kv_base + int(lane)];
        dot_scratch[lane] = grad_out[qo_base + int(lane)] * v[kv_base + int(lane)];
        threadgroup_barrier(mem_flags::mem_threadgroup);
        for (uint stride = head_dim >> 1; stride > 0; stride >>= 1) {
            if (lane < stride) {
                score_scratch[lane] += score_scratch[lane + stride];
                dot_scratch[lane] += dot_scratch[lane + stride];
            }
            threadgroup_barrier(mem_flags::mem_threadgroup);
        }

        float prob = exp(score_scratch[0] * scale - query_lse);
        float dot = dot_scratch[0] - d_out_dot_out;
        threadgroup_barrier(mem_flags::mem_threadgroup);
        acc += prob * dot * k[kv_base + int(lane)];
    }
    grad_q[qo_base + int(lane)] = acc * scale;
}

kernel void prefixlm_backward_dq_hdim128_predot_simd32(
    device const float* q [[buffer(0)]],
    device const float* k [[buffer(1)]],
    device const float* v [[buffer(2)]],
    device const float* out [[buffer(3)]],
    device const float* lse [[buffer(4)]],
    device const float* grad_out [[buffer(5)]],
    device float* grad_q [[buffer(6)]],
    device const float* query_dot [[buffer(7)]],
    device const int* prefix_lens [[buffer(8)]],
    device const int* causal_lens [[buffer(9)]],
    device const int* cu_seqlens [[buffer(10)]],
    constant int& total_seqlen [[buffer(11)]],
    constant int& numseqs [[buffer(12)]],
    constant int& num_heads [[buffer(13)]],
    constant int& is_causal [[buffer(14)]],
    constant float& scale [[buffer(15)]],
    uint3 gid [[thread_position_in_grid]],
    uint simd_lid [[thread_index_in_simdgroup]]
) {
    constexpr uint head_dim = 128;
    constexpr uint lanes = 32;
    constexpr uint elems_per_lane = head_dim / lanes;

    uint lane = simd_lid;
    int group = int(gid.x / lanes);
    int query_token = group / num_heads;
    int head = group - query_token * num_heads;
    if (query_token >= total_seqlen || head >= num_heads) {
        return;
    }

    int seq_id = find_seq_id(cu_seqlens, numseqs, query_token);
    int seq_start = cu_seqlens[seq_id];
    int query_pos = query_token - seq_start;
    int prefix_len = prefix_lens[seq_id];
    float query_lse = lse[query_token * num_heads + head];
    float d_out_dot_out = query_dot[query_token * num_heads + head];
    int key_start = seq_start;
    int key_end = is_causal != 0
        ? seq_start + query_pos + 1
        : (query_pos < prefix_len ? seq_start + prefix_len : seq_start + query_pos + 1);

    int qo_base = (query_token * num_heads + head) * int(head_dim);
    float acc[elems_per_lane];
    for (uint i = 0; i < elems_per_lane; ++i) {
        acc[i] = 0.0f;
    }

    for (int key_token = key_start; key_token < key_end; ++key_token) {
        int kv_base = (key_token * num_heads + head) * int(head_dim);
        float score = 0.0f;
        float dot = 0.0f;
        for (uint i = 0; i < elems_per_lane; ++i) {
            uint d = lane + i * lanes;
            score += q[qo_base + int(d)] * k[kv_base + int(d)];
            dot += grad_out[qo_base + int(d)] * v[kv_base + int(d)];
        }
        score = simd_sum(score);
        dot = simd_sum(dot) - d_out_dot_out;

        float coeff = metal::fast::exp(score * scale - query_lse) * dot;
        for (uint i = 0; i < elems_per_lane; ++i) {
            uint d = lane + i * lanes;
            acc[i] += coeff * k[kv_base + int(d)];
        }
    }

    for (uint i = 0; i < elems_per_lane; ++i) {
        uint d = lane + i * lanes;
        grad_q[qo_base + int(d)] = acc[i] * scale;
    }
}

kernel void prefixlm_backward_dk_dv(
    device const float* q [[buffer(0)]],
    device const float* k [[buffer(1)]],
    device const float* v [[buffer(2)]],
    device const float* out [[buffer(3)]],
    device const float* lse [[buffer(4)]],
    device const float* grad_out [[buffer(5)]],
    device float* grad_k [[buffer(6)]],
    device float* grad_v [[buffer(7)]],
    device const int* prefix_lens [[buffer(8)]],
    device const int* causal_lens [[buffer(9)]],
    device const int* cu_seqlens [[buffer(10)]],
    constant int& total_seqlen [[buffer(11)]],
    constant int& numseqs [[buffer(12)]],
    constant int& num_heads [[buffer(13)]],
    constant int& head_dim [[buffer(14)]],
    constant int& is_causal [[buffer(15)]],
    constant float& scale [[buffer(16)]],
    uint3 gid [[thread_position_in_grid]],
    uint3 threads_per_threadgroup [[threads_per_threadgroup]],
    uint3 lane_id [[thread_position_in_threadgroup]]
) {
    threadgroup float scratch[256];
    uint group_width = threads_per_threadgroup.x;
    uint lane = lane_id.x;
    int group = int(gid.x / group_width);
    int key_token = group / num_heads;
    int head = group - key_token * num_heads;
    if (key_token >= total_seqlen || head >= num_heads) {
        return;
    }

    int seq_id = find_seq_id(cu_seqlens, numseqs, key_token);
    int seq_start = cu_seqlens[seq_id];
    int seq_end = cu_seqlens[seq_id + 1];
    int key_pos = key_token - seq_start;
    int prefix_len = prefix_lens[seq_id];
    int kv_base = (key_token * num_heads + head) * head_dim;

    float acc_k = 0.0f;
    float acc_v = 0.0f;
    for (int query_token = seq_start; query_token < seq_end; ++query_token) {
        int query_pos = query_token - seq_start;
        if (!prefixlm_allowed(is_causal, prefix_len, query_pos, key_pos)) {
            continue;
        }
        int qo_base = (query_token * num_heads + head) * head_dim;
        scratch[lane] = lane < uint(head_dim) ? q[qo_base + lane] * k[kv_base + lane] : 0.0f;
        reduce_sum(scratch, lane, group_width);
        float prob = exp(scratch[0] * scale - lse[query_token * num_heads + head]);
        threadgroup_barrier(mem_flags::mem_threadgroup);

        scratch[lane] = lane < uint(head_dim) ? grad_out[qo_base + lane] * (v[kv_base + lane] - out[qo_base + lane]) : 0.0f;
        reduce_sum(scratch, lane, group_width);
        float dot = scratch[0];
        threadgroup_barrier(mem_flags::mem_threadgroup);

        if (lane < uint(head_dim)) {
            acc_k += prob * dot * q[qo_base + lane];
            acc_v += prob * grad_out[qo_base + lane];
        }
    }
    if (lane < uint(head_dim)) {
        grad_k[kv_base + lane] = acc_k * scale;
        grad_v[kv_base + lane] = acc_v;
    }
}

kernel void prefixlm_backward_dk_dv_hdim128(
    device const float* q [[buffer(0)]],
    device const float* k [[buffer(1)]],
    device const float* v [[buffer(2)]],
    device const float* out [[buffer(3)]],
    device const float* lse [[buffer(4)]],
    device const float* grad_out [[buffer(5)]],
    device float* grad_k [[buffer(6)]],
    device float* grad_v [[buffer(7)]],
    device const int* prefix_lens [[buffer(8)]],
    device const int* causal_lens [[buffer(9)]],
    device const int* cu_seqlens [[buffer(10)]],
    constant int& total_seqlen [[buffer(11)]],
    constant int& numseqs [[buffer(12)]],
    constant int& num_heads [[buffer(13)]],
    constant int& is_causal [[buffer(14)]],
    constant float& scale [[buffer(15)]],
    uint3 gid [[thread_position_in_grid]],
    uint3 lane_id [[thread_position_in_threadgroup]]
) {
    constexpr uint head_dim = 128;
    threadgroup float score_scratch[head_dim];
    threadgroup float dot_scratch[head_dim];

    uint lane = lane_id.x;
    int group = int(gid.x / head_dim);
    int key_token = group / num_heads;
    int head = group - key_token * num_heads;
    if (key_token >= total_seqlen || head >= num_heads) {
        return;
    }

    int seq_id = find_seq_id(cu_seqlens, numseqs, key_token);
    int seq_start = cu_seqlens[seq_id];
    int seq_end = cu_seqlens[seq_id + 1];
    int key_pos = key_token - seq_start;
    int prefix_len = prefix_lens[seq_id];
    int kv_base = (key_token * num_heads + head) * int(head_dim);
    int query_start = is_causal != 0
        ? key_token
        : (key_pos < prefix_len ? seq_start : key_token);

    float acc_k = 0.0f;
    float acc_v = 0.0f;
    for (int query_token = query_start; query_token < seq_end; ++query_token) {
        int qo_base = (query_token * num_heads + head) * int(head_dim);
        score_scratch[lane] = q[qo_base + int(lane)] * k[kv_base + int(lane)];
        dot_scratch[lane] = grad_out[qo_base + int(lane)] * (v[kv_base + int(lane)] - out[qo_base + int(lane)]);
        threadgroup_barrier(mem_flags::mem_threadgroup);
        for (uint stride = head_dim >> 1; stride > 0; stride >>= 1) {
            if (lane < stride) {
                score_scratch[lane] += score_scratch[lane + stride];
                dot_scratch[lane] += dot_scratch[lane + stride];
            }
            threadgroup_barrier(mem_flags::mem_threadgroup);
        }

        float prob = exp(score_scratch[0] * scale - lse[query_token * num_heads + head]);
        float dot = dot_scratch[0];
        threadgroup_barrier(mem_flags::mem_threadgroup);
        acc_k += prob * dot * q[qo_base + int(lane)];
        acc_v += prob * grad_out[qo_base + int(lane)];
    }
    grad_k[kv_base + int(lane)] = acc_k * scale;
    grad_v[kv_base + int(lane)] = acc_v;
}

kernel void prefixlm_backward_dk_dv_hdim128_predot(
    device const float* q [[buffer(0)]],
    device const float* k [[buffer(1)]],
    device const float* v [[buffer(2)]],
    device const float* out [[buffer(3)]],
    device const float* lse [[buffer(4)]],
    device const float* grad_out [[buffer(5)]],
    device float* grad_k [[buffer(6)]],
    device float* grad_v [[buffer(7)]],
    device const float* query_dot [[buffer(8)]],
    device const int* prefix_lens [[buffer(9)]],
    device const int* causal_lens [[buffer(10)]],
    device const int* cu_seqlens [[buffer(11)]],
    constant int& total_seqlen [[buffer(12)]],
    constant int& numseqs [[buffer(13)]],
    constant int& num_heads [[buffer(14)]],
    constant int& is_causal [[buffer(15)]],
    constant float& scale [[buffer(16)]],
    uint3 gid [[thread_position_in_grid]],
    uint3 lane_id [[thread_position_in_threadgroup]]
) {
    constexpr uint head_dim = 128;
    threadgroup float score_scratch[head_dim];
    threadgroup float dot_scratch[head_dim];

    uint lane = lane_id.x;
    int group = int(gid.x / head_dim);
    int key_token = group / num_heads;
    int head = group - key_token * num_heads;
    if (key_token >= total_seqlen || head >= num_heads) {
        return;
    }

    int seq_id = find_seq_id(cu_seqlens, numseqs, key_token);
    int seq_start = cu_seqlens[seq_id];
    int seq_end = cu_seqlens[seq_id + 1];
    int key_pos = key_token - seq_start;
    int prefix_len = prefix_lens[seq_id];
    int kv_base = (key_token * num_heads + head) * int(head_dim);

    float acc_k = 0.0f;
    float acc_v = 0.0f;
    for (int query_token = seq_start; query_token < seq_end; ++query_token) {
        int query_pos = query_token - seq_start;
        if (!prefixlm_allowed(is_causal, prefix_len, query_pos, key_pos)) {
            continue;
        }
        int qo_base = (query_token * num_heads + head) * int(head_dim);
        score_scratch[lane] = q[qo_base + int(lane)] * k[kv_base + int(lane)];
        dot_scratch[lane] = grad_out[qo_base + int(lane)] * v[kv_base + int(lane)];
        threadgroup_barrier(mem_flags::mem_threadgroup);
        for (uint stride = head_dim >> 1; stride > 0; stride >>= 1) {
            if (lane < stride) {
                score_scratch[lane] += score_scratch[lane + stride];
                dot_scratch[lane] += dot_scratch[lane + stride];
            }
            threadgroup_barrier(mem_flags::mem_threadgroup);
        }

        float prob = exp(score_scratch[0] * scale - lse[query_token * num_heads + head]);
        float dot = dot_scratch[0] - query_dot[query_token * num_heads + head];
        threadgroup_barrier(mem_flags::mem_threadgroup);
        acc_k += prob * dot * q[qo_base + int(lane)];
        acc_v += prob * grad_out[qo_base + int(lane)];
    }
    grad_k[kv_base + int(lane)] = acc_k * scale;
    grad_v[kv_base + int(lane)] = acc_v;
}

kernel void prefixlm_backward_dk_dv_hdim128_predot_simd32(
    device const float* q [[buffer(0)]],
    device const float* k [[buffer(1)]],
    device const float* v [[buffer(2)]],
    device const float* out [[buffer(3)]],
    device const float* lse [[buffer(4)]],
    device const float* grad_out [[buffer(5)]],
    device float* grad_k [[buffer(6)]],
    device float* grad_v [[buffer(7)]],
    device const float* query_dot [[buffer(8)]],
    device const int* prefix_lens [[buffer(9)]],
    device const int* causal_lens [[buffer(10)]],
    device const int* cu_seqlens [[buffer(11)]],
    constant int& total_seqlen [[buffer(12)]],
    constant int& numseqs [[buffer(13)]],
    constant int& num_heads [[buffer(14)]],
    constant int& is_causal [[buffer(15)]],
    constant float& scale [[buffer(16)]],
    uint3 gid [[thread_position_in_grid]],
    uint simd_lid [[thread_index_in_simdgroup]]
) {
    constexpr uint head_dim = 128;
    constexpr uint lanes = 32;
    constexpr uint elems_per_lane = head_dim / lanes;

    uint lane = simd_lid;
    int group = int(gid.x / lanes);
    int key_token = group / num_heads;
    int head = group - key_token * num_heads;
    if (key_token >= total_seqlen || head >= num_heads) {
        return;
    }

    int seq_id = find_seq_id(cu_seqlens, numseqs, key_token);
    int seq_start = cu_seqlens[seq_id];
    int seq_end = cu_seqlens[seq_id + 1];
    int key_pos = key_token - seq_start;
    int prefix_len = prefix_lens[seq_id];
    int kv_base = (key_token * num_heads + head) * int(head_dim);

    float acc_k[elems_per_lane];
    float acc_v[elems_per_lane];
    for (uint i = 0; i < elems_per_lane; ++i) {
        acc_k[i] = 0.0f;
        acc_v[i] = 0.0f;
    }

    for (int query_token = seq_start; query_token < seq_end; ++query_token) {
        int query_pos = query_token - seq_start;
        if (!prefixlm_allowed(is_causal, prefix_len, query_pos, key_pos)) {
            continue;
        }
        int qo_base = (query_token * num_heads + head) * int(head_dim);
        float score = 0.0f;
        float dot = 0.0f;
        for (uint i = 0; i < elems_per_lane; ++i) {
            uint d = lane + i * lanes;
            score += q[qo_base + int(d)] * k[kv_base + int(d)];
            dot += grad_out[qo_base + int(d)] * v[kv_base + int(d)];
        }
        score = simd_sum(score);
        dot = simd_sum(dot) - query_dot[query_token * num_heads + head];

        float prob = metal::fast::exp(score * scale - lse[query_token * num_heads + head]);
        float grad_score = prob * dot;
        for (uint i = 0; i < elems_per_lane; ++i) {
            uint d = lane + i * lanes;
            acc_k[i] += grad_score * q[qo_base + int(d)];
            acc_v[i] += prob * grad_out[qo_base + int(d)];
        }
    }

    for (uint i = 0; i < elems_per_lane; ++i) {
        uint d = lane + i * lanes;
        grad_k[kv_base + int(d)] = acc_k[i] * scale;
        grad_v[kv_base + int(d)] = acc_v[i];
    }
}
"""


@lru_cache(maxsize=1)
def _shader_library() -> Any:
    return torch.mps.compile_shader(_MPS_PREFIXLM_SHADER)


def _thread_geometry(total_seqlen: int, num_heads: int, head_dim: int) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    if head_dim > 256:
        raise ValueError(f"MPS PrefixLM attention supports head_dim <= 256, got {head_dim}.")
    group_width = 1 << (head_dim - 1).bit_length()
    groups = max(1, total_seqlen * num_heads)
    return (groups * group_width, 1, 1), (group_width, 1, 1)


def _tiled_forward_hdim128_q4_geometry(total_seqlen: int, num_heads: int) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    q_block = 4
    head_dim = 128
    query_blocks = (total_seqlen + q_block - 1) // q_block
    groups = max(1, query_blocks * num_heads)
    return (groups * head_dim, q_block, 1), (head_dim, q_block, 1)


def _online_forward_hdim128_geometry(total_seqlen: int, num_heads: int) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    head_dim = 128
    groups = max(1, total_seqlen * num_heads)
    return (groups * head_dim, 1, 1), (head_dim, 1, 1)


def _online_forward_hdim128_simd32_geometry(total_seqlen: int, num_heads: int) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    lanes = 32
    groups = max(1, total_seqlen * num_heads)
    return (groups * lanes, 1, 1), (lanes, 1, 1)


def _online_forward_hdim128_headblock4_geometry(total_seqlen: int, num_heads: int) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    head_dim = 128
    head_block = 4
    head_blocks = (num_heads + head_block - 1) // head_block
    groups = max(1, total_seqlen * head_blocks)
    return (groups * head_dim, head_block, 1), (head_dim, head_block, 1)


def _matmulblock_forward_hdim128_q2_k8_l32_geometry(total_seqlen: int, num_heads: int) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    q_block = 2
    dot_lanes = 32
    k_block = 8
    query_blocks = (total_seqlen + q_block - 1) // q_block
    groups = max(1, query_blocks * num_heads)
    return (groups * dot_lanes, k_block, q_block), (dot_lanes, k_block, q_block)


class _MPSPrefixLMAttention(torch.autograd.Function):
    @staticmethod
    def forward(
        ctx: Any,
        q: Tensor,
        k: Tensor,
        v: Tensor,
        is_causal: bool,
        prefix_lens: Tensor,
        causal_lens: Tensor,
        cu_seqlens: Tensor,
        total_seqlen: int,
        numseqs: int,
    ) -> Tensor:
        if q.dtype != torch.float32 or k.dtype != torch.float32 or v.dtype != torch.float32:
            raise TypeError("MPS PrefixLM attention currently supports float32 tensors only.")
        if q.shape != k.shape or q.shape != v.shape:
            raise ValueError("MPS PrefixLM attention currently requires q, k, and v to have identical shapes.")

        q = q.contiguous()
        k = k.contiguous()
        v = v.contiguous()
        prefix_lens = prefix_lens.contiguous()
        causal_lens = causal_lens.contiguous()
        cu_seqlens = cu_seqlens.contiguous()

        out = torch.zeros_like(q)
        lse = torch.empty(q.shape[:2], dtype=q.dtype, device=q.device)

        num_heads = q.shape[1]
        head_dim = q.shape[2]
        scale = 1.0 / math.sqrt(head_dim)
        if head_dim == 128:
            threads, group_size = _online_forward_hdim128_simd32_geometry(total_seqlen, num_heads)
            _shader_library().prefixlm_forward_online_hdim128_simd32(
                q,
                k,
                v,
                out,
                lse,
                prefix_lens,
                causal_lens,
                cu_seqlens,
                int(total_seqlen),
                int(numseqs),
                int(num_heads),
                int(is_causal),
                float(scale),
                threads=threads,
                group_size=group_size,
            )
        else:
            threads, group_size = _thread_geometry(total_seqlen, num_heads, head_dim)
            _shader_library().prefixlm_forward(
                q,
                k,
                v,
                out,
                lse,
                prefix_lens,
                causal_lens,
                cu_seqlens,
                int(total_seqlen),
                int(numseqs),
                int(num_heads),
                int(head_dim),
                int(is_causal),
                float(scale),
                threads=threads,
                group_size=group_size,
            )
        ctx.save_for_backward(q, k, v, out, lse, prefix_lens, causal_lens, cu_seqlens)
        ctx.total_seqlen = int(total_seqlen)
        ctx.numseqs = int(numseqs)
        ctx.num_heads = int(num_heads)
        ctx.head_dim = int(head_dim)
        ctx.is_causal = bool(is_causal)
        ctx.scale = float(scale)
        return out

    @staticmethod
    def backward(ctx: Any, grad_out: Tensor) -> tuple[Tensor | None, ...]:
        q, k, v, out, lse, prefix_lens, causal_lens, cu_seqlens = ctx.saved_tensors
        grad_out = grad_out.contiguous()
        grad_q = torch.zeros_like(q)
        grad_k = torch.zeros_like(k)
        grad_v = torch.zeros_like(v)

        lib = _shader_library()
        if ctx.head_dim == 128:
            simd_threads, simd_group_size = _online_forward_hdim128_simd32_geometry(ctx.total_seqlen, ctx.num_heads)
            query_dot = torch.empty(q.shape[:2], dtype=q.dtype, device=q.device)
            lib.prefixlm_backward_query_dot_hdim128_simd32(
                out,
                grad_out,
                query_dot,
                ctx.total_seqlen,
                ctx.num_heads,
                threads=simd_threads,
                group_size=simd_group_size,
            )
            lib.prefixlm_backward_dq_hdim128_predot_simd32(
                q,
                k,
                v,
                out,
                lse,
                grad_out,
                grad_q,
                query_dot,
                prefix_lens,
                causal_lens,
                cu_seqlens,
                ctx.total_seqlen,
                ctx.numseqs,
                ctx.num_heads,
                int(ctx.is_causal),
                ctx.scale,
                threads=simd_threads,
                group_size=simd_group_size,
            )
            lib.prefixlm_backward_dk_dv_hdim128_predot_simd32(
                q,
                k,
                v,
                out,
                lse,
                grad_out,
                grad_k,
                grad_v,
                query_dot,
                prefix_lens,
                causal_lens,
                cu_seqlens,
                ctx.total_seqlen,
                ctx.numseqs,
                ctx.num_heads,
                int(ctx.is_causal),
                ctx.scale,
                threads=simd_threads,
                group_size=simd_group_size,
            )
        else:
            threads, group_size = _thread_geometry(ctx.total_seqlen, ctx.num_heads, ctx.head_dim)
            lib.prefixlm_backward_dq(
                q,
                k,
                v,
                out,
                lse,
                grad_out,
                grad_q,
                prefix_lens,
                causal_lens,
                cu_seqlens,
                ctx.total_seqlen,
                ctx.numseqs,
                ctx.num_heads,
                ctx.head_dim,
                int(ctx.is_causal),
                ctx.scale,
                threads=threads,
                group_size=group_size,
            )
            lib.prefixlm_backward_dk_dv(
                q,
                k,
                v,
                out,
                lse,
                grad_out,
                grad_k,
                grad_v,
                prefix_lens,
                causal_lens,
                cu_seqlens,
                ctx.total_seqlen,
                ctx.numseqs,
                ctx.num_heads,
                ctx.head_dim,
                int(ctx.is_causal),
                ctx.scale,
                threads=threads,
                group_size=group_size,
            )
        return grad_q, grad_k, grad_v, None, None, None, None, None, None


def flash_attn_varlen_prefixlm_mps(
    q: Tensor,
    k: Tensor,
    v: Tensor,
    is_causal: bool,
    prefix_lens: Tensor,
    causal_lens: Tensor,
    cu_seqlens: Tensor,
    total_seqlen: Tensor,
    numseqs: Tensor,
    max_seqlen_prefix: Tensor,
    max_seqlen_causal: Tensor,
    max_seqlen_all: Tensor,
) -> Tensor:
    info = prefixlm_seq_info_from_tensors(
        prefix_lens,
        causal_lens,
        cu_seqlens,
        total_seqlen,
        numseqs,
        max_seqlen_prefix,
        max_seqlen_causal,
        max_seqlen_all,
    )
    return _MPSPrefixLMAttention.apply(
        q,
        k,
        v,
        is_causal,
        info.prefix_lens,
        info.causal_lens,
        info.cu_seqlens,
        info.total_seqlen,
        info.numseqs,
    )


def flash_attn_varlen_prefixlm_mps_backward_dense_math(
    q: Tensor,
    k: Tensor,
    v: Tensor,
    out: Tensor,
    grad_out: Tensor,
    is_causal: bool,
    prefix_lens: Tensor,
    causal_lens: Tensor,
    cu_seqlens: Tensor,
    total_seqlen: Tensor,
    numseqs: Tensor,
    max_seqlen_prefix: Tensor,
    max_seqlen_causal: Tensor,
    max_seqlen_all: Tensor,
) -> tuple[Tensor, Tensor, Tensor]:
    info = prefixlm_seq_info_from_tensors(
        prefix_lens,
        causal_lens,
        cu_seqlens,
        total_seqlen,
        numseqs,
        max_seqlen_prefix,
        max_seqlen_causal,
        max_seqlen_all,
    )
    scale = 1.0 / math.sqrt(q.shape[-1])
    grad_q = torch.zeros_like(q)
    grad_k = torch.zeros_like(k)
    grad_v = torch.zeros_like(v)

    for seq_id in range(info.numseqs):
        start = int(info.cu_seqlens[seq_id].item())
        end = int(info.cu_seqlens[seq_id + 1].item())
        seq_len = end - start
        if seq_len == 0:
            continue

        prefix_len = int(info.prefix_lens[seq_id].item())
        causal_len = int(info.causal_lens[seq_id].item())
        if prefix_len + causal_len != seq_len:
            raise ValueError(f"Bad PrefixLM lengths for sequence {seq_id}: {prefix_len} + {causal_len} != {seq_len}")

        q_seq = q[start:end].transpose(0, 1)
        k_seq = k[start:end].transpose(0, 1)
        v_seq = v[start:end].transpose(0, 1)
        out_seq = out[start:end].transpose(0, 1)
        grad_out_seq = grad_out[start:end].transpose(0, 1)

        scores = torch.matmul(q_seq, k_seq.transpose(-1, -2)) * scale
        positions = torch.arange(seq_len, device=q.device)
        if is_causal:
            mask = positions[None, :] <= positions[:, None]
        else:
            prefix_queries = positions < prefix_len
            prefix_keys = positions < prefix_len
            causal_queries = ~prefix_queries
            mask = (prefix_queries[:, None] & prefix_keys[None, :]) | (
                causal_queries[:, None] & (positions[None, :] <= positions[:, None])
            )
        scores = scores.masked_fill(~mask.unsqueeze(0), float("-inf"))
        prob = torch.softmax(scores, dim=-1)

        grad_v_seq = torch.matmul(prob.transpose(-1, -2), grad_out_seq)
        grad_prob = torch.matmul(grad_out_seq, v_seq.transpose(-1, -2))
        delta = (grad_out_seq * out_seq).sum(dim=-1, keepdim=True)
        grad_scores = prob * (grad_prob - delta) * scale
        grad_q_seq = torch.matmul(grad_scores, k_seq)
        grad_k_seq = torch.matmul(grad_scores.transpose(-1, -2), q_seq)

        grad_q[start:end] = grad_q_seq.transpose(0, 1)
        grad_k[start:end] = grad_k_seq.transpose(0, 1)
        grad_v[start:end] = grad_v_seq.transpose(0, 1)

    return grad_q, grad_k, grad_v


def flash_attn_varlen_prefixlm_mps_backward_parts(
    q: Tensor,
    k: Tensor,
    v: Tensor,
    out: Tensor,
    grad_out: Tensor,
    is_causal: bool,
    prefix_lens: Tensor,
    causal_lens: Tensor,
    cu_seqlens: Tensor,
    total_seqlen: Tensor,
    numseqs: Tensor,
    max_seqlen_prefix: Tensor,
    max_seqlen_causal: Tensor,
    max_seqlen_all: Tensor,
) -> tuple[Tensor, Tensor, Tensor, Tensor]:
    info = prefixlm_seq_info_from_tensors(
        prefix_lens,
        causal_lens,
        cu_seqlens,
        total_seqlen,
        numseqs,
        max_seqlen_prefix,
        max_seqlen_causal,
        max_seqlen_all,
    )
    if q.dtype != torch.float32 or k.dtype != torch.float32 or v.dtype != torch.float32:
        raise TypeError("MPS PrefixLM benchmark backward currently supports float32 tensors only.")
    if q.shape != k.shape or q.shape != v.shape or q.shape != out.shape or q.shape != grad_out.shape:
        raise ValueError("MPS PrefixLM benchmark backward requires q, k, v, out, and grad_out to have identical shapes.")
    if q.shape[2] != 128:
        raise ValueError(f"MPS PrefixLM benchmark backward is specialized for head_dim=128, got {q.shape[2]}.")
    _validate_test_shape(info.total_seqlen, info.numseqs, q.shape[1], q.shape[2])

    q = q.contiguous()
    k = k.contiguous()
    v = v.contiguous()
    out = out.contiguous()
    grad_out = grad_out.contiguous()
    prefix_lens = info.prefix_lens.contiguous()
    causal_lens = info.causal_lens.contiguous()
    cu_seqlens = info.cu_seqlens.contiguous()

    grad_q = torch.zeros_like(q)
    grad_k = torch.zeros_like(k)
    grad_v = torch.zeros_like(v)
    lse_out = torch.empty(q.shape[:2], dtype=q.dtype, device=q.device)
    query_dot = torch.empty(q.shape[:2], dtype=q.dtype, device=q.device)
    threads, group_size = _online_forward_hdim128_geometry(info.total_seqlen, q.shape[1])
    simd_threads, simd_group_size = _online_forward_hdim128_simd32_geometry(info.total_seqlen, q.shape[1])
    lib = _shader_library()

    # Recompute lse with the online forward kernel; callers benchmark this helper, not training correctness.
    tmp_out = torch.empty_like(q)
    lib.prefixlm_forward_online_hdim128(
        q,
        k,
        v,
        tmp_out,
        lse_out,
        prefix_lens,
        causal_lens,
        cu_seqlens,
        info.total_seqlen,
        info.numseqs,
        int(q.shape[1]),
        int(is_causal),
        float(1.0 / math.sqrt(128)),
        threads=threads,
        group_size=group_size,
    )
    lib.prefixlm_backward_query_dot_hdim128_simd32(
        out,
        grad_out,
        query_dot,
        info.total_seqlen,
        int(q.shape[1]),
        threads=simd_threads,
        group_size=simd_group_size,
    )
    lib.prefixlm_backward_dq_hdim128_predot_simd32(
        q,
        k,
        v,
        out,
        lse_out,
        grad_out,
        grad_q,
        query_dot,
        prefix_lens,
        causal_lens,
        cu_seqlens,
        info.total_seqlen,
        info.numseqs,
        int(q.shape[1]),
        int(is_causal),
        float(1.0 / math.sqrt(128)),
        threads=simd_threads,
        group_size=simd_group_size,
    )
    lib.prefixlm_backward_dk_dv_hdim128_predot_simd32(
        q,
        k,
        v,
        out,
        lse_out,
        grad_out,
        grad_k,
        grad_v,
        query_dot,
        prefix_lens,
        causal_lens,
        cu_seqlens,
        info.total_seqlen,
        info.numseqs,
        int(q.shape[1]),
        int(is_causal),
        float(1.0 / math.sqrt(128)),
        threads=simd_threads,
        group_size=simd_group_size,
    )
    return query_dot, grad_q, grad_k, grad_v


def flash_attn_varlen_prefixlm_mps_backward_context(
    q: Tensor,
    k: Tensor,
    v: Tensor,
    out: Tensor,
    grad_out: Tensor,
    is_causal: bool,
    prefix_lens: Tensor,
    causal_lens: Tensor,
    cu_seqlens: Tensor,
    total_seqlen: Tensor,
    numseqs: Tensor,
    max_seqlen_prefix: Tensor,
    max_seqlen_causal: Tensor,
    max_seqlen_all: Tensor,
) -> tuple[Tensor, Tensor]:
    info = prefixlm_seq_info_from_tensors(
        prefix_lens,
        causal_lens,
        cu_seqlens,
        total_seqlen,
        numseqs,
        max_seqlen_prefix,
        max_seqlen_causal,
        max_seqlen_all,
    )
    if q.shape[2] != 128:
        raise ValueError(f"MPS PrefixLM benchmark backward is specialized for head_dim=128, got {q.shape[2]}.")
    _validate_test_shape(info.total_seqlen, info.numseqs, q.shape[1], q.shape[2])

    q = q.contiguous()
    k = k.contiguous()
    v = v.contiguous()
    out = out.contiguous()
    grad_out = grad_out.contiguous()
    prefix_lens = info.prefix_lens.contiguous()
    causal_lens = info.causal_lens.contiguous()
    cu_seqlens = info.cu_seqlens.contiguous()

    lse = torch.empty(q.shape[:2], dtype=q.dtype, device=q.device)
    query_dot = torch.empty(q.shape[:2], dtype=q.dtype, device=q.device)
    tmp_out = torch.empty_like(q)
    threads, group_size = _online_forward_hdim128_geometry(info.total_seqlen, q.shape[1])
    simd_threads, simd_group_size = _online_forward_hdim128_simd32_geometry(info.total_seqlen, q.shape[1])
    lib = _shader_library()
    lib.prefixlm_forward_online_hdim128(
        q,
        k,
        v,
        tmp_out,
        lse,
        prefix_lens,
        causal_lens,
        cu_seqlens,
        info.total_seqlen,
        info.numseqs,
        int(q.shape[1]),
        int(is_causal),
        float(1.0 / math.sqrt(128)),
        threads=threads,
        group_size=group_size,
    )
    lib.prefixlm_backward_query_dot_hdim128_simd32(
        out,
        grad_out,
        query_dot,
        info.total_seqlen,
        int(q.shape[1]),
        threads=simd_threads,
        group_size=simd_group_size,
    )
    return lse, query_dot


def flash_attn_varlen_prefixlm_mps_backward_dq_part(
    q: Tensor,
    k: Tensor,
    v: Tensor,
    out: Tensor,
    grad_out: Tensor,
    lse: Tensor,
    query_dot: Tensor,
    is_causal: bool,
    prefix_lens: Tensor,
    causal_lens: Tensor,
    cu_seqlens: Tensor,
    total_seqlen: Tensor,
    numseqs: Tensor,
) -> Tensor:
    total_seqlen_int = int(total_seqlen.item())
    numseqs_int = int(numseqs.item())
    grad_q = torch.zeros_like(q)
    threads, group_size = _online_forward_hdim128_simd32_geometry(total_seqlen_int, q.shape[1])
    _shader_library().prefixlm_backward_dq_hdim128_predot_simd32(
        q.contiguous(),
        k.contiguous(),
        v.contiguous(),
        out.contiguous(),
        lse.contiguous(),
        grad_out.contiguous(),
        grad_q,
        query_dot.contiguous(),
        prefix_lens.contiguous(),
        causal_lens.contiguous(),
        cu_seqlens.contiguous(),
        total_seqlen_int,
        numseqs_int,
        int(q.shape[1]),
        int(is_causal),
        float(1.0 / math.sqrt(128)),
        threads=threads,
        group_size=group_size,
    )
    return grad_q


def flash_attn_varlen_prefixlm_mps_backward_dk_dv_part(
    q: Tensor,
    k: Tensor,
    v: Tensor,
    out: Tensor,
    grad_out: Tensor,
    lse: Tensor,
    query_dot: Tensor,
    is_causal: bool,
    prefix_lens: Tensor,
    causal_lens: Tensor,
    cu_seqlens: Tensor,
    total_seqlen: Tensor,
    numseqs: Tensor,
) -> tuple[Tensor, Tensor]:
    total_seqlen_int = int(total_seqlen.item())
    numseqs_int = int(numseqs.item())
    grad_k = torch.zeros_like(k)
    grad_v = torch.zeros_like(v)
    threads, group_size = _online_forward_hdim128_simd32_geometry(total_seqlen_int, q.shape[1])
    _shader_library().prefixlm_backward_dk_dv_hdim128_predot_simd32(
        q.contiguous(),
        k.contiguous(),
        v.contiguous(),
        out.contiguous(),
        lse.contiguous(),
        grad_out.contiguous(),
        grad_k,
        grad_v,
        query_dot.contiguous(),
        prefix_lens.contiguous(),
        causal_lens.contiguous(),
        cu_seqlens.contiguous(),
        total_seqlen_int,
        numseqs_int,
        int(q.shape[1]),
        int(is_causal),
        float(1.0 / math.sqrt(128)),
        threads=threads,
        group_size=group_size,
    )
    return grad_k, grad_v


def flash_attn_varlen_prefixlm_mps_tiled_forward(
    q: Tensor,
    k: Tensor,
    v: Tensor,
    is_causal: bool,
    prefix_lens: Tensor,
    causal_lens: Tensor,
    cu_seqlens: Tensor,
    total_seqlen: Tensor,
    numseqs: Tensor,
    max_seqlen_prefix: Tensor,
    max_seqlen_causal: Tensor,
    max_seqlen_all: Tensor,
) -> Tensor:
    info = prefixlm_seq_info_from_tensors(
        prefix_lens,
        causal_lens,
        cu_seqlens,
        total_seqlen,
        numseqs,
        max_seqlen_prefix,
        max_seqlen_causal,
        max_seqlen_all,
    )
    if q.dtype != torch.float32 or k.dtype != torch.float32 or v.dtype != torch.float32:
        raise TypeError("Tiled MPS PrefixLM attention currently supports float32 tensors only.")
    if q.shape != k.shape or q.shape != v.shape:
        raise ValueError("Tiled MPS PrefixLM attention currently requires q, k, and v to have identical shapes.")
    if q.shape[2] != 128:
        raise ValueError(f"Tiled MPS PrefixLM attention is specialized for head_dim=128, got {q.shape[2]}.")
    _validate_test_shape(info.total_seqlen, info.numseqs, q.shape[1], q.shape[2])

    q = q.contiguous()
    k = k.contiguous()
    v = v.contiguous()
    prefix_lens = info.prefix_lens.contiguous()
    cu_seqlens = info.cu_seqlens.contiguous()
    out = torch.zeros_like(q)
    lse = torch.empty(q.shape[:2], dtype=q.dtype, device=q.device)

    threads, group_size = _tiled_forward_hdim128_q4_geometry(info.total_seqlen, q.shape[1])
    _shader_library().prefixlm_forward_tiled_hdim128_q4(
        q,
        k,
        v,
        out,
        lse,
        prefix_lens,
        torch.empty(0, dtype=torch.int32, device=q.device),
        cu_seqlens,
        info.total_seqlen,
        info.numseqs,
        int(q.shape[1]),
        int(is_causal),
        float(1.0 / math.sqrt(128)),
        threads=threads,
        group_size=group_size,
    )
    return out


def flash_attn_varlen_prefixlm_mps_online_forward(
    q: Tensor,
    k: Tensor,
    v: Tensor,
    is_causal: bool,
    prefix_lens: Tensor,
    causal_lens: Tensor,
    cu_seqlens: Tensor,
    total_seqlen: Tensor,
    numseqs: Tensor,
    max_seqlen_prefix: Tensor,
    max_seqlen_causal: Tensor,
    max_seqlen_all: Tensor,
) -> Tensor:
    info = prefixlm_seq_info_from_tensors(
        prefix_lens,
        causal_lens,
        cu_seqlens,
        total_seqlen,
        numseqs,
        max_seqlen_prefix,
        max_seqlen_causal,
        max_seqlen_all,
    )
    if q.dtype != torch.float32 or k.dtype != torch.float32 or v.dtype != torch.float32:
        raise TypeError("Online MPS PrefixLM attention currently supports float32 tensors only.")
    if q.shape != k.shape or q.shape != v.shape:
        raise ValueError("Online MPS PrefixLM attention currently requires q, k, and v to have identical shapes.")
    if q.shape[2] != 128:
        raise ValueError(f"Online MPS PrefixLM attention is specialized for head_dim=128, got {q.shape[2]}.")
    _validate_test_shape(info.total_seqlen, info.numseqs, q.shape[1], q.shape[2])

    q = q.contiguous()
    k = k.contiguous()
    v = v.contiguous()
    prefix_lens = info.prefix_lens.contiguous()
    cu_seqlens = info.cu_seqlens.contiguous()
    out = torch.zeros_like(q)
    lse = torch.empty(q.shape[:2], dtype=q.dtype, device=q.device)

    threads, group_size = _online_forward_hdim128_geometry(info.total_seqlen, q.shape[1])
    _shader_library().prefixlm_forward_online_hdim128(
        q,
        k,
        v,
        out,
        lse,
        prefix_lens,
        torch.empty(0, dtype=torch.int32, device=q.device),
        cu_seqlens,
        info.total_seqlen,
        info.numseqs,
        int(q.shape[1]),
        int(is_causal),
        float(1.0 / math.sqrt(128)),
        threads=threads,
        group_size=group_size,
    )
    return out


def flash_attn_varlen_prefixlm_mps_simd32_forward(
    q: Tensor,
    k: Tensor,
    v: Tensor,
    is_causal: bool,
    prefix_lens: Tensor,
    causal_lens: Tensor,
    cu_seqlens: Tensor,
    total_seqlen: Tensor,
    numseqs: Tensor,
    max_seqlen_prefix: Tensor,
    max_seqlen_causal: Tensor,
    max_seqlen_all: Tensor,
) -> Tensor:
    info = prefixlm_seq_info_from_tensors(
        prefix_lens,
        causal_lens,
        cu_seqlens,
        total_seqlen,
        numseqs,
        max_seqlen_prefix,
        max_seqlen_causal,
        max_seqlen_all,
    )
    if q.dtype != torch.float32 or k.dtype != torch.float32 or v.dtype != torch.float32:
        raise TypeError("SIMD32 MPS PrefixLM attention currently supports float32 tensors only.")
    if q.shape != k.shape or q.shape != v.shape:
        raise ValueError("SIMD32 MPS PrefixLM attention currently requires q, k, and v to have identical shapes.")
    if q.shape[2] != 128:
        raise ValueError(f"SIMD32 MPS PrefixLM attention is specialized for head_dim=128, got {q.shape[2]}.")
    _validate_test_shape(info.total_seqlen, info.numseqs, q.shape[1], q.shape[2])

    q = q.contiguous()
    k = k.contiguous()
    v = v.contiguous()
    prefix_lens = info.prefix_lens.contiguous()
    cu_seqlens = info.cu_seqlens.contiguous()
    out = torch.zeros_like(q)
    lse = torch.empty(q.shape[:2], dtype=q.dtype, device=q.device)

    threads, group_size = _online_forward_hdim128_simd32_geometry(info.total_seqlen, q.shape[1])
    _shader_library().prefixlm_forward_online_hdim128_simd32(
        q,
        k,
        v,
        out,
        lse,
        prefix_lens,
        torch.empty(0, dtype=torch.int32, device=q.device),
        cu_seqlens,
        info.total_seqlen,
        info.numseqs,
        int(q.shape[1]),
        int(is_causal),
        float(1.0 / math.sqrt(128)),
        threads=threads,
        group_size=group_size,
    )
    return out


def flash_attn_varlen_prefixlm_mps_headblock_forward(
    q: Tensor,
    k: Tensor,
    v: Tensor,
    is_causal: bool,
    prefix_lens: Tensor,
    causal_lens: Tensor,
    cu_seqlens: Tensor,
    total_seqlen: Tensor,
    numseqs: Tensor,
    max_seqlen_prefix: Tensor,
    max_seqlen_causal: Tensor,
    max_seqlen_all: Tensor,
) -> Tensor:
    info = prefixlm_seq_info_from_tensors(
        prefix_lens,
        causal_lens,
        cu_seqlens,
        total_seqlen,
        numseqs,
        max_seqlen_prefix,
        max_seqlen_causal,
        max_seqlen_all,
    )
    if q.dtype != torch.float32 or k.dtype != torch.float32 or v.dtype != torch.float32:
        raise TypeError("Head-block MPS PrefixLM attention currently supports float32 tensors only.")
    if q.shape != k.shape or q.shape != v.shape:
        raise ValueError("Head-block MPS PrefixLM attention currently requires q, k, and v to have identical shapes.")
    if q.shape[2] != 128:
        raise ValueError(f"Head-block MPS PrefixLM attention is specialized for head_dim=128, got {q.shape[2]}.")
    _validate_test_shape(info.total_seqlen, info.numseqs, q.shape[1], q.shape[2])

    q = q.contiguous()
    k = k.contiguous()
    v = v.contiguous()
    prefix_lens = info.prefix_lens.contiguous()
    cu_seqlens = info.cu_seqlens.contiguous()
    out = torch.zeros_like(q)
    lse = torch.empty(q.shape[:2], dtype=q.dtype, device=q.device)

    threads, group_size = _online_forward_hdim128_headblock4_geometry(info.total_seqlen, q.shape[1])
    _shader_library().prefixlm_forward_online_hdim128_headblock4(
        q,
        k,
        v,
        out,
        lse,
        prefix_lens,
        torch.empty(0, dtype=torch.int32, device=q.device),
        cu_seqlens,
        info.total_seqlen,
        info.numseqs,
        int(q.shape[1]),
        int(is_causal),
        float(1.0 / math.sqrt(128)),
        threads=threads,
        group_size=group_size,
    )
    return out


def flash_attn_varlen_prefixlm_mps_matmulblock_forward(
    q: Tensor,
    k: Tensor,
    v: Tensor,
    is_causal: bool,
    prefix_lens: Tensor,
    causal_lens: Tensor,
    cu_seqlens: Tensor,
    total_seqlen: Tensor,
    numseqs: Tensor,
    max_seqlen_prefix: Tensor,
    max_seqlen_causal: Tensor,
    max_seqlen_all: Tensor,
) -> Tensor:
    info = prefixlm_seq_info_from_tensors(
        prefix_lens,
        causal_lens,
        cu_seqlens,
        total_seqlen,
        numseqs,
        max_seqlen_prefix,
        max_seqlen_causal,
        max_seqlen_all,
    )
    if q.dtype != torch.float32 or k.dtype != torch.float32 or v.dtype != torch.float32:
        raise TypeError("Matmul-block MPS PrefixLM attention currently supports float32 tensors only.")
    if q.shape != k.shape or q.shape != v.shape:
        raise ValueError("Matmul-block MPS PrefixLM attention currently requires q, k, and v to have identical shapes.")
    if q.shape[2] != 128:
        raise ValueError(f"Matmul-block MPS PrefixLM attention is specialized for head_dim=128, got {q.shape[2]}.")
    _validate_test_shape(info.total_seqlen, info.numseqs, q.shape[1], q.shape[2])

    q = q.contiguous()
    k = k.contiguous()
    v = v.contiguous()
    prefix_lens = info.prefix_lens.contiguous()
    cu_seqlens = info.cu_seqlens.contiguous()
    out = torch.zeros_like(q)
    lse = torch.empty(q.shape[:2], dtype=q.dtype, device=q.device)

    threads, group_size = _matmulblock_forward_hdim128_q2_k8_l32_geometry(info.total_seqlen, q.shape[1])
    _shader_library().prefixlm_forward_matmulblock_hdim128_q2_k8_l32(
        q,
        k,
        v,
        out,
        lse,
        prefix_lens,
        torch.empty(0, dtype=torch.int32, device=q.device),
        cu_seqlens,
        info.total_seqlen,
        info.numseqs,
        int(q.shape[1]),
        info.max_seqlen_all,
        int(is_causal),
        float(1.0 / math.sqrt(128)),
        threads=threads,
        group_size=group_size,
    )
    return out
