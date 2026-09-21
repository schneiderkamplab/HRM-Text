#include <dlfcn.h>
#include <chrono>
#include <cstdio>
#include <cstdlib>
extern "C" void mask(const void *,void *,const void *,bool) asm("_ZNK14llama_kv_cache17set_input_kq_maskEP11ggml_tensorPK12llama_ubatchb");
extern "C" void mask(const void *self,void *tensor,const void *batch,bool causal) {
    using Fn=void(*)(const void *,void *,const void *,bool);
    static auto fn=reinterpret_cast<Fn>(dlsym(RTLD_NEXT,"_ZNK14llama_kv_cache17set_input_kq_maskEP11ggml_tensorPK12llama_ubatchb"));
    static FILE * out=fopen(std::getenv("MASK_PROFILE"),"w");
    if(!fn||!out)std::abort();
    auto start=std::chrono::steady_clock::now();fn(self,tensor,batch,causal);
    auto ns=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-start).count();
    fprintf(out,"%d,%lld\n",causal,static_cast<long long>(ns));fflush(out);
}
