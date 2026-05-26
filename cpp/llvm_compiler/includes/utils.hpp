#pragma once

#include "data_structures.hpp"

namespace utils {

    void error(
        std::string prompt,
        std::string filename = "",
        bool show_warnings = false,
        bool is_warning = false,
        bool fatal = true
    );

    uint64_t get_type_Bitwidth(llvm::Type* T, const llvm::DataLayout& DL);
    string get_trace_str(structures::Tracer tracer);
    string format_event_data(structures::TraceEvent event, bool dont_return_empty_data = false);

}
