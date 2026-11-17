"""Portable HF interface for native Embla experiment checkpoints.

Generation supports unpadded incremental physical-layer KV caches.
The prefix length is fixed at the initial generation call, never inferred from labels.
"""
import torch
from transformers import PreTrainedModel, GenerationMixin
from transformers.modeling_outputs import CausalLMOutputWithPast
from .upstream.configuration_embla import EmblaConfig
from .model import EmblaTrainingModel
from .upstream.modeling_embla import EmblaCache


class EmblaExperimentForCausalLM(PreTrainedModel, GenerationMixin):
    config_class = EmblaConfig
    base_model_prefix = 'model'
    _supports_sdpa = False

    def __init__(self, config):
        super().__init__(config)
        self.model = EmblaTrainingModel(config,decoder_loops=getattr(config,'decoder_loops',1),
                prefix_lm=getattr(config,'prefix_lm',False),attention_backend='tiled')
        self.post_init()

    def get_input_embeddings(self):
        return self.model.transformer.wte

    def get_output_embeddings(self):
        return self.model.lm_head

    @classmethod
    def _supports_default_dynamic_cache(cls):
        return False

    def forward(self,input_ids,attention_mask=None,position_ids=None,labels=None,
                prompt_mask=None,prefix_lengths=None,logits_to_keep=0,use_cache=False,
                past_key_values=None,**kwargs):
        cache = past_key_values
        if cache is None and use_cache:
            cache = EmblaCache()
        if attention_mask is not None and not bool(attention_mask.all()):
            raise ValueError('Use unpadded rows or explicit packed position_ids')
        if self.model.prefix_lm and prompt_mask is None:
            if prefix_lengths is None:
                raise ValueError('PrefixLM needs explicit prefix_lengths or prompt_mask')
            lengths=torch.as_tensor(prefix_lengths,device=input_ids.device).reshape(-1,1)
            prompt_mask=(torch.arange(input_ids.shape[1],device=input_ids.device)[None] + (cache.seen if cache is not None else 0)) < lengths
        logits=self.model(input_ids,position_ids=position_ids,prompt_mask=prompt_mask,cache=cache,
                          last_token_only=labels is None and logits_to_keep == 1)
        loss=None
        if labels is not None:
            loss=torch.nn.functional.cross_entropy(logits[:,:-1].float().reshape(-1,self.config.vocab_size),
                                                   labels[:,1:].reshape(-1),ignore_index=-100)
        if isinstance(logits_to_keep,int) and logits_to_keep:
            logits=logits[:,-logits_to_keep:]
        return CausalLMOutputWithPast(logits=logits,loss=loss,past_key_values=cache)

    def prepare_inputs_for_generation(self,input_ids,attention_mask=None,prefix_lengths=None,past_key_values=None,use_cache=True,**kwargs):
        if past_key_values is not None:
            input_ids=input_ids[:,past_key_values.seen:]
            if attention_mask is not None: attention_mask=attention_mask[:,-input_ids.shape[1]:]
        return dict(input_ids=input_ids,attention_mask=attention_mask,prefix_lengths=prefix_lengths,
                    past_key_values=past_key_values,logits_to_keep=1,use_cache=use_cache)

    def generate(self,inputs=None,**kwargs):
        ids=inputs if inputs is not None else kwargs.get('input_ids')
        if self.model.prefix_lm and 'prefix_lengths' not in kwargs:
            if ids is None:
                raise ValueError('PrefixLM generation requires input_ids')
            kwargs['prefix_lengths']=torch.full((ids.shape[0],),ids.shape[1],device=ids.device)
        kwargs.setdefault('use_cache',True)
        return super().generate(inputs,**kwargs)
