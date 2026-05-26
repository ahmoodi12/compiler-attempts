#pragma once

#include "combined_include.hpp"
#include "Context.hpp"
#include "data_structures.hpp"

class Compiler {
private:
    Context ctx;

    void load_isa(filesystem::path& isa_file);

    unordered_map<string, json> generalize_naming(
        unordered_map<string, vector<string>> aliases,
        json& raw_isa,
        vector<string> required_keys,
        filesystem::path& isa_file,
        string error_context = "."
    );

    vector<structures::TraceEvent> trace_funcs() const;
    vector<structures::TraceEvent> trace_globals() const;

public:
    explicit Compiler(string module_name, bool warn, bool trace) : ctx(module_name, trace, warn) {
        structures::context = &ctx;  // set the global context pointer to this instance's context
    }

    void run(filesystem::path& program_file,
             filesystem::path& isa_file,
             filesystem::path& output_file);

};
