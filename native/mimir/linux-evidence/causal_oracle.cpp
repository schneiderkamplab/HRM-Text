#include "llama.h"
#include "ggml-backend.h"
#include "nlohmann/json.hpp"
#include <algorithm>
#include <cmath>
#include <fstream>
#include <stdexcept>
#include <vector>
using json=nlohmann::ordered_json;
int main(int argc,char **argv) {
 if(argc!=5)return 2;
 ggml_backend_load_all();llama_backend_init();
 std::ifstream in(argv[1]);auto spec=json::parse(in);
 auto mp=llama_model_default_params();mp.n_gpu_layers=std::atoi(argv[3]);
 auto * model=llama_model_load_from_file(spec.at("model").get<std::string>().c_str(),mp);if(!model)return 3;
 int nv=llama_vocab_n_tokens(llama_model_get_vocab(model));json results=json::array();bool passed=true;
 for(const auto & item:spec.at("cases")) {
  if(!item.value("causal",false))continue;
  auto cp=llama_context_default_params();cp.n_ctx=spec.value("n_ctx",128);cp.n_batch=cp.n_ctx;cp.n_ubatch=spec.value("n_ubatch",64);
  cp.n_seq_max=1;cp.kv_unified=false;cp.n_threads=cp.n_threads_batch=4;cp.type_k=cp.type_v=GGML_TYPE_F32;
  cp.flash_attn_type=std::atoi(argv[4])?LLAMA_FLASH_ATTN_TYPE_ENABLED:LLAMA_FLASH_ATTN_TYPE_DISABLED;cp.attention_type=LLAMA_ATTENTION_TYPE_CAUSAL;
  auto * ctx=llama_init_from_model(model,cp);if(!ctx)return 4;int pos=0;
  for(const auto & step:item.at("steps")) {
   if(step.at("prefix").get<bool>()||step.contains("owners")||step.contains("rewind_to"))throw std::runtime_error("unsupported causal control");
   auto tokens=step.at("tokens").get<std::vector<llama_token>>();auto batch=llama_batch_init(tokens.size(),0,1);batch.n_tokens=tokens.size();
   for(size_t i=0;i<tokens.size();++i){batch.token[i]=tokens[i];batch.pos[i]=pos+i;batch.n_seq_id[i]=1;batch.seq_id[i][0]=0;batch.logits[i]=true;}
   if(llama_decode(ctx,batch))return 5;llama_synchronize(ctx);llama_batch_free(batch);
   std::vector<float> expected(tokens.size()*nv);std::ifstream ref(step.at("reference").get<std::string>(),std::ios::binary);ref.read(reinterpret_cast<char*>(expected.data()),expected.size()*sizeof(float));if(!ref)return 6;
   double maximum=0,squared=0;int top=0;bool finite=true;
   for(size_t i=0;i<tokens.size();++i){auto * got=llama_get_logits_ith(ctx,i);auto * want=expected.data()+i*nv;top+=std::max_element(got,got+nv)-got==std::max_element(want,want+nv)-want;
    for(int j=0;j<nv;++j){finite&=std::isfinite(got[j]);double delta=double(got[j])-want[j];maximum=std::max(maximum,std::abs(delta));squared+=delta*delta;}}
   bool ok=finite&&maximum<=spec.at("max_abs").get<double>();passed&=ok;
   results.push_back({{"case",item.at("name")},{"position",pos},{"rows",tokens.size()},{"finite",finite},{"max_abs",maximum},{"rmse",std::sqrt(squared/expected.size())},{"top1_matches",top},{"pass",ok}});pos+=tokens.size();
  }
  llama_free(ctx);
 }
 std::ofstream out(argv[2]);out<<json({{"pass",passed},{"steps",results}}).dump(2)<<'\n';llama_model_free(model);llama_backend_free();return passed?0:1;
}
