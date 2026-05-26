
#include "includes/data_structures.hpp"
#include "includes/Context.hpp"
#include "includes/combined_include.hpp"
#include "includes/utils.hpp"

namespace structures {
// ===== Helpers =====
string vec_to_string(const vector<int>& v) {
    ostringstream oss;
    oss << "[";
    for (size_t i = 0; i < v.size(); ++i) {
        oss << v[i];
        if (i + 1 < v.size()) oss << ", ";
    }
    oss << "]";
    return oss.str();
}

string stringifyConstExpr(llvm::ConstantExpr* ce) {
    std::string s;
    llvm::raw_string_ostream rso(s);
    ce->print(rso); // prints something like "bitcast i32* %ptr to i64*"
    return rso.str();
}

LogicalTemp* get_temp(llvm::Value& llvm_obj, Context& ctx){
    if (!ctx.made_logical_temps.count(&llvm_obj)) {
        ctx.made_logical_temps[&llvm_obj] = make_unique<LogicalTemp>(llvm_obj, ctx);
    }
    return ctx.made_logical_temps[&llvm_obj].get();
}

void build_machine_temps(llvm::Type* type, LogicalTemp* parent, Context& ctx) {
    // Pointer = single machine temp
    if (type->isPointerTy()) {
        int bw = ctx.parsed_isa.data_types["bitwidth"].count("ptr")
               ? ctx.parsed_isa.data_types["bitwidth"]["ptr"]
               : ctx.parsed_isa.address_width;

        parent->machine_temps.emplace_back(parent, parent->llvm_obj, bw, 0, ctx);
        return;
    }

    // Integer
    if (type->isIntegerTy()) {
        int bw = type->getIntegerBitWidth();
        int reg_width = ctx.parsed_isa.reg_width;

        int parts = (bw + reg_width - 1) / reg_width;
        for (int i = 0; i < parts; i++)
            parent->machine_temps.emplace_back(parent, parent->llvm_obj, reg_width, i, ctx);
        return;
    }

    // Vector
    if (auto* vec = llvm::dyn_cast<llvm::VectorType>(type)) {
        unsigned n = vec->getElementCount().getKnownMinValue();
        for (unsigned i = 0; i < n; i++)
            build_machine_temps(vec->getElementType(), parent, ctx);
        return;
    }

    // Array
    if (auto* arr = llvm::dyn_cast<llvm::ArrayType>(type)) {
        for (unsigned i = 0; i < arr->getNumElements(); i++)
            build_machine_temps(arr->getElementType(), parent, ctx);
        return;
    }

    // Struct
    if (auto* st = llvm::dyn_cast<llvm::StructType>(type)) {
        for (unsigned i = 0; i < st->getNumElements(); i++)
            build_machine_temps(st->getTypeAtIndex(i), parent, ctx);
        return;
    }

    // Fallback
    int bw = ctx.data_layout->getTypeSizeInBits(type);
    int reg_width = ctx.parsed_isa.reg_width;
    int parts = (bw + reg_width - 1) / reg_width;
    for (int i = 0; i < parts; i++){
        parent->machine_temps.emplace_back(parent, parent->llvm_obj, reg_width, i, ctx);
    }
}


// ===== MachineTemp =====
MachineTemp::MachineTemp(LogicalTemp* parent, llvm::Value& llvm_obj, int bitwidth, int part_i, Context& ctx) 
    : parent(parent), bitwidth(bitwidth), part_index(part_i) {}
    


// ===== LogicalTemp =====
LogicalTemp::LogicalTemp(llvm::Value& llvm_obj, Context& ctx) 
    : llvm_obj(llvm_obj), id(ctx.ids++){
    type = llvm_obj.getType();    
    logical_bitwidth = ctx.data_layout->getTypeSizeInBits(type);
    build_machine_temps(type, this, ctx);
}

// ===== IR =====
IR::IR(llvm::Instruction& inst_obj, Context& ctx) : llvm_obj(inst_obj) {
    // Store opcode name
    this->name = inst_obj.getOpcodeName();

    // Extract output Temp if instruction produces a value
    if (!inst_obj.getType()->isVoidTy()) {
        // create a Temp for the output
        this->output = get_temp(inst_obj, ctx);
    }

    // Extract input operands and args
    for (auto &op : inst_obj.operands()) {
        llvm::Value* val = op.get();

        if (llvm::isa<llvm::Instruction>(val) || llvm::isa<llvm::Argument>(val)) {
            // SSA temp
            inputs.push_back(get_temp(*val, ctx));
        } 
        else if (llvm::isa<llvm::BasicBlock>(val)) {
            // Label (jump target)
            llvm::BasicBlock* bb = llvm::cast<llvm::BasicBlock>(val);
            labels.push_back(bb);
        } 
        else if (llvm::isa<llvm::GlobalValue>(val)) {
            // Other globals
            args.push_back(val->getName().str());
        }
        else if (llvm::isa<llvm::Constant>(val)) {
            if (llvm::isa<llvm::UndefValue>(val)) {
                args.push_back("<undef>");
            }
            else if (llvm::isa<llvm::PoisonValue>(val)) {
                args.push_back("<poison>");
            }
            else if (auto *ci = llvm::dyn_cast<llvm::ConstantInt>(val)) {
                args.push_back(std::to_string(ci->getSExtValue()));
            } 
            else if (auto *cf = llvm::dyn_cast<llvm::ConstantFP>(val)) {
                llvm::APInt bits = cf->getValueAPF().bitcastToAPInt();
                llvm::SmallVector<char, 32> buf;
                bits.toString(buf, /*Radix=*/10, /*Signed=*/false);
                args.push_back(string(buf.begin(), buf.end()));
            } 
            else if (auto *ce = llvm::dyn_cast<llvm::ConstantExpr>(val)) {
                args.push_back(stringifyConstExpr(ce));
            }
            else {
                args.push_back("<unknown const>");
            }
        } 
        else {
            // fallback for any unknown types (rare)
            args.push_back("<unknown>");
        }
    }
}

string IR::pretty_ir() const {
    ostringstream oss;
    if (output) oss << "%" << output->id << " = ";
    oss << name;
    oss << " ";
    if (!inputs.empty()) {
        for (size_t i = 0; i < inputs.size(); ++i) {
            oss << "%" << inputs[i]->id;
            if (i + 1 < inputs.size()) oss << ", ";
        }
    }
    if (!inputs.empty() && !labels.empty()) oss << ", ";

    if (!args.empty()) {;
        for (size_t i = 0; i < args.size(); ++i) {
            oss << args[i];
            if (i + 1 < args.size()) oss << ", ";
        }
    }
    if (type) oss << "    # " << *type;
    return oss.str();
}

vector<TraceEvent> get_mahcine_temp_ids(const vector<MachineTemp>& temps) {
    vector<TraceEvent> temp_ids;
    for (const auto& t : temps){
        temp_ids.push_back(TraceEvent(to_string(t.parent->id) + "_part" + to_string(t.part_index), vector<TraceEvent>{}));
    }
    return temp_ids;
}

// ===== MIR =====
vector<TraceEvent> MIR::trace() const {
    vector<TraceEvent> data, defs, args_data, inputs_data, output_data, inouts_data;

    for (const auto& arg : args) {
        args_data.emplace_back(arg, vector<TraceEvent>{});
    }

    inputs_data = get_mahcine_temp_ids(inputs);
    output_data = get_mahcine_temp_ids(output); 
    
    data.emplace_back("args", args_data);
    data.emplace_back("inputs", inputs_data);
    data.emplace_back("output", output_data);
    data.emplace_back("spills", vector<TraceEvent>{TraceEvent(vec_to_string(spills), vector<TraceEvent>{})});
    if (type) data.emplace_back("type", vector<TraceEvent>{TraceEvent(*type, vector<TraceEvent>{})});
    
    for (const auto& def : definition) {
        defs.emplace_back(def, vector<TraceEvent>{});
    }
    data.emplace_back("definition", defs);

    return data;
}

bool has_fallback(llvm::Instruction llvm_obj) {

};

// ===== Block =====
Block::Block(llvm::BasicBlock& block_obj, Func& parent, Context& ctx)
    : llvm_obj(block_obj), parent_func(parent), id(ctx.ids++){

    for (auto& llvm_inst : block_obj){
        IR inst(llvm_inst, ctx);
        if (find(ctx.supported_ir.begin(), ctx.supported_ir.end(), llvm_inst.getOpcode()) != ctx.supported_ir.end()) {
            this->ir.push_back(inst);
        }


        else {
            utils::error("couldn't convert unsupported IR instruction '" + 
                         string(llvm_inst.getOpcodeName()) + 
                         "' to a supported instruction.", *ctx.current_file, ctx.show_warnings);
        }
    }
}

vector<TraceEvent> Block::get_ir() const {
    vector<TraceEvent> events;
    for (auto& i : ir) events.emplace_back(i.pretty_ir(), vector<TraceEvent>{});
    return events;
}

vector<TraceEvent> Block::get_mir() const {
    vector<TraceEvent> events;
    for (auto& m : mir) {
        events.emplace_back(m.name, m.trace());
    }
    return events;
}

vector<TraceEvent> get_block_ids(const vector<Block*>& blocks) {
    vector<TraceEvent> block_ids;
    for (auto& eb : blocks){
        block_ids.push_back(TraceEvent(to_string(eb->id), vector<TraceEvent>{}));
    }
    return block_ids;
}

vector<TraceEvent> get_temp_ids(const vector<LogicalTemp*>& temps) {
    vector<TraceEvent> temp_ids;
    for (auto& t : temps){
        temp_ids.push_back(TraceEvent(to_string(t->id), vector<TraceEvent>{}));
    }
    return temp_ids;
}

vector<TraceEvent> Block::trace() const {
    vector<TraceEvent> events;

    auto incoming_block_ids = get_block_ids(entering_blocks);
    auto exit_block_ids = get_block_ids(exits);

    auto entry_t = get_temp_ids(entry_temps);
    auto resulted_t = get_temp_ids(resulted_temps);
    auto exit_t = get_temp_ids(exit_temps);

    events.emplace_back("incoming blocks", incoming_block_ids);
    events.emplace_back("exit blocks", exit_block_ids);
    events.emplace_back("entry temps", entry_t);
    events.emplace_back("ir", this->get_ir());
    events.emplace_back("mir", this->get_mir());
    events.emplace_back("resulted temps", resulted_t);
    events.emplace_back("exit temps", exit_t);
    // add more block info here as needed
    return events;
}

// ===== Func =====
Func::Func(llvm::Function& func_obj, const vector<string>& free_regs, Context& ctx)
    : llvm_obj(func_obj), free_regs(free_regs) {

    this->name = func_obj.getName().str();

    // assign temps for parameters
    for (auto& arg : func_obj.args()) {
        this->params.push_back(pair(get_temp(arg, ctx), vector<int>{}));  // empty bitwidth vector for now
    }

    for (auto& block : func_obj) {
        // constructs and appends a block to blocks
        this->blocks.emplace_back(block, *this, ctx);
    }
}

vector<TraceEvent> Func::trace() const {
    // traces the funcs info
    vector<TraceEvent> events;
    events.emplace_back("params", vector<TraceEvent>{});
    events.emplace_back("results", vector<TraceEvent>{});
    // add rest of func info here as needed
    for (const auto& block : blocks) {
        events.emplace_back("block_" + to_string(block.id), block.trace());
    }
    return events;
}

// Helper: flatten constant into initial_value vector
void flatten_constant(llvm::Constant *C, const llvm::DataLayout &DL, uint64_t word_bits,
                      std::vector<I64> &out, size_t &offset_words, const std::string &endianness) {
    if (auto *CF = llvm::dyn_cast<llvm::ConstantFP>(C)) {
        llvm::APInt bits = CF->getValueAPF().bitcastToAPInt();
        uint64_t num_words = (bits.getBitWidth() + word_bits - 1) / word_bits;
        for (size_t i = 0; i < num_words; i++) {
            size_t idx = offset_words + i;
            if (endianness == "big")
                idx = offset_words + num_words - 1 - i;
            llvm::APInt chunk = bits.extractBits(word_bits, i * word_bits);
            if (idx >= out.size()) out.resize(idx + 1, 0);
            out[idx] = static_cast<I64>(chunk.getZExtValue());
        }
        offset_words += num_words;
    }
    else if (auto *CI = llvm::dyn_cast<llvm::ConstantInt>(C)) {
        llvm::APInt val = CI->getValue();
        uint64_t num_words = (val.getBitWidth() + word_bits - 1) / word_bits;
        for (size_t i = 0; i < num_words; i++) {
            size_t idx = offset_words + i;
            if (endianness == "big")
                idx = offset_words + num_words - 1 - i;
            llvm::APInt chunk = val.extractBits(word_bits, i * word_bits);
            if (idx >= out.size()) out.resize(idx + 1, 0);
            out[idx] = static_cast<I64>(chunk.getZExtValue());
        }
        offset_words += num_words;
    }
    else if (auto *CA = llvm::dyn_cast<llvm::ConstantArray>(C)) {
        for (unsigned i = 0; i < CA->getNumOperands(); i++)
            flatten_constant(CA->getOperand(i), DL, word_bits, out, offset_words, endianness);
    }
    else if (auto *CS = llvm::dyn_cast<llvm::ConstantStruct>(C)) {
        for (unsigned i = 0; i < CS->getNumOperands(); i++)
            flatten_constant(CS->getOperand(i), DL, word_bits, out, offset_words, endianness);
    }
    else if (auto *CV = llvm::dyn_cast<llvm::ConstantVector>(C)) {
        for (unsigned i = 0; i < CV->getNumOperands(); i++)
            flatten_constant(CV->getOperand(i), DL, word_bits, out, offset_words, endianness);
    }
    else {
        // For zero-init or unknown constant
        uint64_t bits = DL.getTypeAllocSizeInBits(C->getType());
        uint64_t words = (bits + word_bits - 1) / word_bits;
        for (uint64_t i = 0; i < words; i++) {
            if (offset_words >= out.size()) out.push_back(0);
            else out[offset_words] = 0;
            offset_words++;
        }
    }
}

// ===== Global =====
Global::Global(llvm::GlobalVariable &global_obj, Context& ctx) 
    : llvm_obj(global_obj)
{
    name = global_obj.getName().str();

    // Determine type
    llvm::Type *type_ptr = global_obj.getValueType();
    switch (type_ptr->getTypeID()) {
        case llvm::Type::IntegerTyID:           type = "int"; break;
        case llvm::Type::FloatTyID:             type = "float"; break;
        case llvm::Type::DoubleTyID:            type = "float"; break;
        case llvm::Type::ArrayTyID:             type = "array"; break;
        case llvm::Type::StructTyID:            type = "struct"; break;
        case llvm::Type::ScalableVectorTyID:    type = "vector"; break;
        case llvm::Type::FixedVectorTyID:       type = "vector"; break;
        default:                                type = "unknown"; break;
    }

    // Compute number of words
    const llvm::DataLayout* DL = ctx.data_layout; // assuming you store DL in ctx
    uint64_t total_bits = DL->getTypeAllocSizeInBits(type_ptr);
    uint64_t words = (total_bits + ctx.parsed_isa.data_width - 1) / ctx.parsed_isa.data_width;

    // Initialize vector
    initial_value = vector<I64>(words, 0);

    // Fill initializer if present
    if (global_obj.hasInitializer()) {
        size_t offset = 0;
        flatten_constant(global_obj.getInitializer(), *DL, ctx.parsed_isa.data_width, initial_value, offset, ctx.parsed_isa.endianness);
    }
}

vector<TraceEvent> Global::trace() const {
    vector<TraceEvent> events;
    string mem_str;
    for (size_t i = 0; i < initial_value.size(); ++i) {
        mem_str += to_string(initial_value[i]);
        if (i + 1 < initial_value.size()) {
            mem_str += ", ";
        }
    }
    events.emplace_back(type, vector<TraceEvent>{TraceEvent(mem_str, {})});
    return events;
}

// ===== Tracer =====

Tracer::Tracer(string module_name, bool en) : events(TraceEvent("working on " + module_name, vector<TraceEvent>{})), enabled(en) {}

void Tracer::emit(const string& event, vector<structures::TraceEvent> data) {
    if (enabled)
        this->events.data.emplace_back(event, data);
}


};