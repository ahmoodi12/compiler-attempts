// data.cpp
#include "includes/data.hpp"

namespace data{
Alias ISA_KEYS = {
    {"opcodes", {"opcodes", "instructions", "insts"}},
    {"syntax", {"syntax", "instruction syntax", "cpu syntax", "instruction_syntax", "cpu_syntax"}},
    {"encoding", {"encoding", "instruction encodings", "encodings", "instruction_encodings"}},
    {"hardware", {"hardware", "cpu config", "arch config", "cpu_config", "arch_config"}},
    {"pseudo", {"pseudo instructions", "pseudo", "pseudo inst", "pseudo insts",
                "pseudo_instructions", "pseudo_inst", "pseudo_insts"}},
    {"syntax temp", {"syntax temp", "syntax templates", "syn templates", "syntax_templates", "syn_templates"}},
    {"encoding temp", {"encoding temp", "encoding templates", "enc templates",
                       "encodings templates", "enc_templates", "encoding_templates",
                       "encodings_templates", "enc temp", "enc_temp"}},
    {"translation table", {"instruction_map", "instruction table",
                           "translation table", "inst translation", "t table"}},
    {"inst spills", {"spills", "instruction spills", "spill table", "spill map", "inst_spills",
                     "inst spills", "spill_instructions", "spill", "instruction spill", "spill table", "spill map",
                     "inst_spill", "spill_insts"}},
    {"op types", {"op types", "operand types", "op_types", "operand_types"}}
};

Alias HARDWARE_KEYS = {
    {"endianness", {"endianness", "byte order", "byte_order", 
                    "memory order", "memory_order", "endian", "endianess"}},
    {"data types", {"data types", "d types", "d type regs"}},
    {"stack start", {"stack start", "stack start address", "stack base",
                     "stack base address", "stack bottom", "stack bottom address",
                     "stack low", "stack low address", "stack min"}},
    {"stack end", {"stack end", "stack end address", "stack limit",
                   "stack limit address", "stack top", "stack top address",
                   "stack high", "stack high address", "stack max"}},
    {"regs", {"reg file size", "register file size",
              "reg_file_size", "register_file_size",
              "reg_file", "register_file",
              "num registers", "num_regs",
              "rf size", "rf_size",
              "regs", "registers", "reg file"}},
    {"spec regs", {"special registers", "spec_regs",
                   "special_registers", "spec regs", "special regs"}},
    {"address width", {"address width", "addr width",
                       "address_bits", "addr_bits",
                       "address size", "addr_size", "mem size", "mem_size"}},
    {"data width", {"data width", "data_width",
                    "data bits", "data_bits",
                    "data size", "data_size", "memory width", "memory_width", "memory unit", "mem unit"}},
    {"reg width", {"reg width", "register width",
                   "reg_width", "register_width",
                   "reg bits", "register bits",
                   "reg_bitwidth", "register_bitwidth",
                   "reg size", "register size",
                   "reg_size", "register_size"}},
    {"opcode size", {"instruction length", "instruction size",
                     "opcode width", "opcode len", "len opcode"}}
};


unordered_map<string, unsigned> str_to_llvm_inst = {
    // Terminators
    {"ret", llvm::Instruction::Ret},
    {"br", llvm::Instruction::Br},
    {"switch", llvm::Instruction::Switch},
    {"indirectbr", llvm::Instruction::IndirectBr},
    {"invoke", llvm::Instruction::Invoke},
    {"resume", llvm::Instruction::Resume},
    {"catchswitch", llvm::Instruction::CatchSwitch},
    {"catchret", llvm::Instruction::CatchRet},
    {"cleanupret", llvm::Instruction::CleanupRet},
    {"unreachable", llvm::Instruction::Unreachable},

    // Binary integer operations
    {"add", llvm::Instruction::Add},
    {"sub", llvm::Instruction::Sub},
    {"mul", llvm::Instruction::Mul},
    {"udiv", llvm::Instruction::UDiv},
    {"sdiv", llvm::Instruction::SDiv},
    {"urem", llvm::Instruction::URem},
    {"srem", llvm::Instruction::SRem},
    {"shl", llvm::Instruction::Shl},
    {"lshr", llvm::Instruction::LShr},
    {"ashr", llvm::Instruction::AShr},
    {"and", llvm::Instruction::And},
    {"or", llvm::Instruction::Or},
    {"xor", llvm::Instruction::Xor},

    // Binary floating-point operations
    {"fadd", llvm::Instruction::FAdd},
    {"fsub", llvm::Instruction::FSub},
    {"fmul", llvm::Instruction::FMul},
    {"fdiv", llvm::Instruction::FDiv},
    {"frem", llvm::Instruction::FRem},

    // Memory
    {"alloca", llvm::Instruction::Alloca},
    {"load", llvm::Instruction::Load},
    {"store", llvm::Instruction::Store},
    {"fence", llvm::Instruction::Fence},
    {"cmpxchg", llvm::Instruction::AtomicCmpXchg},
    {"atomicrmw", llvm::Instruction::AtomicRMW},
    {"getelementptr", llvm::Instruction::GetElementPtr},

    // Casts
    {"trunc", llvm::Instruction::Trunc},
    {"zext", llvm::Instruction::ZExt},
    {"sext", llvm::Instruction::SExt},
    {"fptrunc", llvm::Instruction::FPTrunc},
    {"fpext", llvm::Instruction::FPExt},
    {"fptoui", llvm::Instruction::FPToUI},
    {"fptosi", llvm::Instruction::FPToSI},
    {"uitofp", llvm::Instruction::UIToFP},
    {"sitofp", llvm::Instruction::SIToFP},
    {"ptrtoint", llvm::Instruction::PtrToInt},
    {"inttoptr", llvm::Instruction::IntToPtr},
    {"bitcast", llvm::Instruction::BitCast},
    {"addrspacecast", llvm::Instruction::AddrSpaceCast},

    // Comparison
    {"icmp", llvm::Instruction::ICmp},
    {"fcmp", llvm::Instruction::FCmp},

    // Aggregate / Vector
    {"extractelement", llvm::Instruction::ExtractElement},
    {"insertelement", llvm::Instruction::InsertElement},
    {"shufflevector", llvm::Instruction::ShuffleVector},
    {"extractvalue", llvm::Instruction::ExtractValue},
    {"insertvalue", llvm::Instruction::InsertValue},

    // Other
    {"phi", llvm::Instruction::PHI},
    {"call", llvm::Instruction::Call},
    {"select", llvm::Instruction::Select},
    {"va_arg", llvm::Instruction::VAArg},
    {"landingpad", llvm::Instruction::LandingPad},
    {"catchpad", llvm::Instruction::CatchPad},
    {"cleanuppad", llvm::Instruction::CleanupPad},
    {"catchswitch", llvm::Instruction::CatchSwitch},
    {"catchret", llvm::Instruction::CatchRet},
    {"cleanupret", llvm::Instruction::CleanupRet},

    // Experimental / Misc
    {"freeze", llvm::Instruction::Freeze},
    {"callbr", llvm::Instruction::CallBr}
};

Alias data_type_aliases = {
    {"reg", {
        "register", "registers", "reg",
        "gpr", "gprs", "reg_amt", "reg amt", 
        "register amount", "register_amount"
    }},
    {"mem", {
        "memory_space", "mem_space", "memspace", "mem", "mem amt",
        "mem_amt", "memory amount", "address amount", "addresses",
        "addr amt", "addr_amt"
    }},
    {"bitwidth", {
        "width", "bits", "bit_width", "bitwidth", "bit width", 
        "bw", "size", "word_size", 
    }}
};
}