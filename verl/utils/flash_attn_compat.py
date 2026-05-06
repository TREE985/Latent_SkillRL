import torch

from verl.utils.device import is_cuda_available, is_npu_available

try:
    if is_cuda_available:
        from flash_attn.bert_padding import index_first_axis, pad_input, rearrange, unpad_input
        FLASH_ATTN_AVAILABLE = True
    elif is_npu_available:
        from transformers.integrations.npu_flash_attention import (
            index_first_axis,
            pad_input,
            rearrange,
            unpad_input,
        )
        FLASH_ATTN_AVAILABLE = True
    else:
        raise ImportError
except ImportError:
    from einops import rearrange

    FLASH_ATTN_AVAILABLE = False

    def index_first_axis(x, indices):
        return x[indices]

    def unpad_input(hidden_states, attention_mask):
        if attention_mask.dtype != torch.bool:
            attention_mask = attention_mask.bool()

        batch, seqlen = attention_mask.shape
        hidden_shape = hidden_states.shape[2:]

        flat_mask = attention_mask.reshape(-1)
        indices = flat_mask.nonzero(as_tuple=False).squeeze(-1)
        unpadded = hidden_states.reshape(batch * seqlen, *hidden_shape)[indices]

        seqlens_in_batch = attention_mask.sum(dim=-1, dtype=torch.int32)
        cu_seqlens = torch.zeros(batch + 1, dtype=torch.int32, device=attention_mask.device)
        cu_seqlens[1:] = torch.cumsum(seqlens_in_batch, dim=0)
        max_seqlen = int(seqlens_in_batch.max().item()) if batch > 0 else 0
        return unpadded, indices, cu_seqlens, max_seqlen, seqlens_in_batch

    def pad_input(hidden_states, indices, batch, seqlen):
        hidden_shape = hidden_states.shape[1:]
        output = hidden_states.new_zeros((batch * seqlen, *hidden_shape))
        output[indices] = hidden_states
        return output.view(batch, seqlen, *hidden_shape)


def get_attn_implementation():
    return "flash_attention_2" if FLASH_ATTN_AVAILABLE else "sdpa"
