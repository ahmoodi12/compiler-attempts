
#include "data_structures.hpp"
#include "combined_include.hpp"


class Allocator {
public:
    Allocator(Context& ctx) : context(ctx) {}

    void define_func_params_results();

private:
    Context& context;   
};