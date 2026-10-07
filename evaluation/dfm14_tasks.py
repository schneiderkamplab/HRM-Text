"""DFM14 task registrations reuse the existing paired-heldout scorers."""
from inspect_ai import task
from dfm_evals.tasks.dala_dfm13_heldout import make

LANGUAGES=tuple('ga mt mk eu gl cy ru tr zh ar ja id ko hi vi he'.split())


@task(name='dala_dfm14')
def dala_dfm14(language:str,manifest:str,num_shards:int=1,shard_index:int=0,max_gen_toks:int=32):
    return make(language,'acceptability',manifest,num_shards,shard_index,max_gen_toks,LANGUAGES)


@task(name='gec_dala_dfm14')
def gec_dala_dfm14(language:str,manifest:str,num_shards:int=1,shard_index:int=0,max_gen_toks:int=512):
    return make(language,'correction',manifest,num_shards,shard_index,max_gen_toks,LANGUAGES)
