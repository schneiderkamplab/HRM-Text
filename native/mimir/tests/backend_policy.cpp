#include "mimir/backend_policy.h"
#include <iostream>
#include <memory>

static void require(bool value, const char * message) { if (!value) { throw std::runtime_error(message); } }
int main() {
    using namespace mimir;
    try {
        std::vector<BackendCandidate> devices{{"Vulkan0","Vulkan",true},{"CUDA0","CUDA",true},{"CPU","CPU",false}};
        auto candidates = backend_candidates(devices,"auto");
        require(candidates.size()==3 && candidates[0].id=="CUDA0" && candidates.back().id=="CPU", "priority/CPU last");
        std::vector<std::string> failures, attempts;
        int resources=0;
        auto selected=try_backends(candidates,[&](const auto & d) {
            require(resources==0,"failed resources released before retry");
            ++resources;
            auto guard=std::shared_ptr<int>(new int, [&](int * p){--resources;delete p;});
            attempts.push_back(d.id);
            if(d.accelerator) throw BackendFailure("simulated allocation failure");
        },failures);
        require(selected.id=="CPU" && failures.size()==2 && attempts.size()==3 && resources==0,"fallback and diagnostics");
        failures.clear();attempts.clear();
        bool explicit_failed=false;
        try { try_backends(backend_candidates(devices,"cuda"),[&](const auto & d){attempts.push_back(d.id);throw BackendFailure("driver failure");},failures); }
        catch(const BackendFailure &){explicit_failed=true;}
        require(explicit_failed && attempts.size()==1,"explicit selection must not change backend");
        for(bool invalid : {false,true}) {
            int calls=0; failures.clear();bool stopped=false;
            try { try_backends(candidates,[&](const auto &){++calls;if(invalid)throw std::invalid_argument("bad model");throw std::runtime_error("cancelled");},failures); }
            catch(const std::exception &){stopped=true;}
            require(stopped && calls==1 && failures.empty(),"invalid input/cancellation not retried");
        }
        require(backend_candidates({},"auto").front().id=="CPU","no accelerator");
        require(backend_candidates({{"MTL0","MTL",true}},"metal").front().id=="MTL0","Metal alias");
        bool missing=false;try{backend_candidates(devices,"absent");}catch(const std::invalid_argument &){missing=true;}
        require(missing,"missing explicit backend");
        failures.clear();
        auto first=try_backends(candidates,[](const auto &){},failures);
        require(first.id=="CUDA0" && failures.empty(),"successful GPU stops retry");
        std::cout<<"Backend policy checks passed\n";
    } catch(const std::exception & e){std::cerr<<e.what()<<'\n';return 1;}
}
