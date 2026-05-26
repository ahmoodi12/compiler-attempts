#pragma once

#include "combined_include.hpp"

class Context;  // Forward declaration

namespace structures
{
Context* context = nullptr;  // Global context pointer, to be set by the compiler before any other code runs

// ===== Helpers =====
inline string vec_to_string(const vector<int>& v);

// ===== Tracer =====
struct TraceEvent {
    string event;
    vector<TraceEvent> data;
    TraceEvent(const string& event, vector<TraceEvent> data) : event(event), data(data) {}
};

struct Tracer {
    bool enabled;
    TraceEvent events;

    Tracer(string module_name, bool en);
    void emit(const string& event, vector<TraceEvent> data);
    //string repr() const;
};

// ===== Temp =====
struct LogicalTemp;

struct MachineTemp {
    LogicalTemp* parent;
    int part_index = 0;  // for temps that are split into multiple machine temps
    int bitwidth = 0;  // not really used, just for debugging

    MachineTemp(LogicalTemp* parent, llvm::Value& llvm_obj, int bitwidth, int part_i, Context& ctx);
};

struct LogicalTemp {
    llvm::Value& llvm_obj;
    llvm::Type*  type;
    int id;
    int logical_bitwidth;
    vector<MachineTemp> machine_temps;

    LogicalTemp(llvm::Value& llvm_obj, Context& ctx);
};

LogicalTemp* get_temp(llvm::Value& llvm_obj, Context& ctx);
void build_machine_temps(llvm::Type* type, LogicalTemp* parent, Context& ctx);

// ===== IR =====
struct IR {
    llvm::Instruction& llvm_obj;
    string name;
    vector<LogicalTemp*> inputs;
    LogicalTemp* output = nullptr;
    vector<string> args;
    vector<llvm::BasicBlock*> labels;
    optional<string> type;

    IR(llvm::Instruction& inst_obj, Context& ctx);
    string pretty_ir() const;
};

// ===== MIR =====
struct MIR {
    string name;
    vector<string> args;
    vector<string> definition;
    vector<MachineTemp> inputs;
    vector<MachineTemp> output;
    vector<int> spills;
    optional<string> type;

    vector<TraceEvent> trace() const;
};

struct Func;

// ===== Block =====
struct Block {
    llvm::BasicBlock& llvm_obj;
    int id;
    vector<Block*> entering_blocks;
    vector<Block*> exits;
    vector<LogicalTemp*> entry_temps;
    vector<LogicalTemp*> resulted_temps;
    vector<LogicalTemp*> exit_temps;
    vector<IR> ir;
    vector<MIR> mir;
    Func& parent_func;

    Block(llvm::BasicBlock& block_obj, Func& parent, Context& ctx);
    vector<TraceEvent> trace() const;
    vector<TraceEvent> get_ir() const;
    vector<TraceEvent> get_mir() const;
};

// ===== Func =====
struct Func {
    string name;
    llvm::Function& llvm_obj;
    vector<Block> blocks;
    vector<pair<LogicalTemp*, vector<int>>> params;
    optional<pair<LogicalTemp*, vector<int>>> result;
    int stack_offset = 0;
    vector<string> free_regs;
    vector<LogicalTemp*> local_temps;
    Func(llvm::Function& func_obj, const vector<string>& free_regs, Context& ctx);
    vector<TraceEvent> trace() const;
};

void flatten_constant(llvm::Constant *C, const llvm::DataLayout &DL, uint64_t word_bits,
                    std::vector<I64> &out, size_t &offset_words, const std::string &endianness);

struct Global {
    string name;
    llvm::GlobalVariable& llvm_obj;
    vector<I64> initial_value;  
    string type;   // repr array, struct, vector, int, float, etc
    Global(llvm::GlobalVariable &global_obj, Context& ctx_ref);
    vector<TraceEvent> trace() const;

};
}