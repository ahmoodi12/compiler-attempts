
#include "includes/frontend.hpp"
#include "includes/utils.hpp"
#include "includes/data_structures.hpp"

unique_ptr<llvm::Module> Frontend::parse(std::filesystem::path& program_file){
    llvm::SMDiagnostic err;

    auto module = llvm::parseIRFile(
        program_file.string(),
        err,
        llvm_context
    );

    if (!module) {
        utils::error(
            "failed to parse LLVM IR file.",
            program_file.filename().string(),
            true
        );
        err.print("Frontend", llvm::errs());
    }

    return module;
}


void Frontend::extract_globals(std::unique_ptr<llvm::Module> &module){
    for (auto &global : module->globals())
    {
        string name = global.getName().str();
        llvm::Type *type = global.getValueType();

        uint64_t total_bits = this->context.data_layout->getTypeAllocSizeInBits(type);

        // same as ceil(total_bits / data_width)
        uint64_t words = (total_bits + context.parsed_isa.data_width - 1) / context.parsed_isa.data_width;

        vector<I64> words_vec(words, 0); // initialize with zeros

        if (global.hasInitializer())
        {
            llvm::Constant *init = global.getInitializer();
            if (auto *CI = llvm::dyn_cast<llvm::ConstantInt>(init))
            {
                llvm::APInt values = CI->getValue();

                for (size_t i = 0; i < words; i++)
                {
                    size_t word_index = i;
                    if (context.parsed_isa.endianness == "big")
                        word_index = words - 1 - i;

                    llvm::APInt chunk = values.extractBits(context.parsed_isa.data_width, i * context.parsed_isa.data_width);
                    words_vec[word_index] = chunk.getZExtValue();
                }
            }
        }

        this->context.globals.emplace_back(global, context);
    }
}


structures::Block* Frontend::get_block(llvm::BasicBlock* llvm_block, structures::Func& parent_func) {
    for (auto& block : parent_func.blocks) {
        if (&block.llvm_obj == llvm_block) {
            return &block;
        }
    }
    throw std::runtime_error("Block not found in function '" + parent_func.name + "'.");
}

void Frontend::fill_block_attrs(structures::Block& block) {
    for (auto *pred : llvm::predecessors(&block.llvm_obj)) {
        block.entering_blocks.push_back(this->get_block(pred, block.parent_func));
    }
    for (auto *succ : llvm::successors(&block.llvm_obj)) {
        block.exits.push_back(this->get_block(succ, block.parent_func));
    }
    
    // TODO: add filling of entry_temps, resulted_temps, exit_temps
    

}

