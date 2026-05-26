
#include "combined_include.hpp"
#include "Context.hpp"

class Frontend {
public:
    llvm::LLVMContext llvm_context;
    llvm::SMDiagnostic err;

    Frontend(Context& ctx) : context(ctx) {};
    unique_ptr<llvm::Module> parse(filesystem::path& program_file);
    
    void extract_globals(std::unique_ptr<llvm::Module>& module);
    void fill_block_attrs(structures::Block& block);
    structures::Block* get_block(llvm::BasicBlock* llvm_block, structures::Func& parent_func) ;
private:
    Context& context;
};

