#pragma once

#include "combined_include.hpp"
#include "data_structures.hpp"

class Context {
public:
    struct Isa {
        TranslationTable translation_table;
        InstSpills inst_spills;
        string endianness;
        unordered_map<string, unordered_map<string, unsigned int>> data_types;
        vector<string> regs;
        vector<string> spec_regs;
        int address_width;
        int data_width;
        int reg_width;
    };

    Isa parsed_isa;
    filesystem::path* current_file = nullptr;
    set<unsigned> supported_ir;
    bool show_warnings;
    bool trace;
    vector<string> compiled_code;
    vector<structures::Global> globals;
    structures::Tracer tracer;
    vector<structures::Func> funcs;
    long long int ids = 0;  // 64 bits to avoid any overflow if even possible lol
    const llvm::DataLayout* data_layout = nullptr;
    unordered_map<llvm::Value*, unique_ptr<structures::LogicalTemp>> made_logical_temps;

    explicit Context(string module_name, bool trace, bool show_warnings) : trace(trace), show_warnings(show_warnings), tracer(module_name, trace) {}

    void reset() {
        compiled_code.clear();
        globals.clear();
        funcs.clear();
    }

    bool is_big_endian() const {
        return parsed_isa.endianness == "big";
    }

    bool is_little_endian() const {
        return parsed_isa.endianness == "little";
    }
};
