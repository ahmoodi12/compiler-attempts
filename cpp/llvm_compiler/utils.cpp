
#include "includes/combined_include.hpp"
#include "includes/utils.hpp"
#include "includes/data_structures.hpp"

namespace utils{

void error(string prompt, string filename, bool show_warnings, bool is_warning, bool fatal){
    if (!show_warnings && is_warning) return;
    if (is_warning){ 
        cerr << termcolor::yellow << "Warning";
    } 
    else {
        string color = "\033[0;33m";   // orange color for enon fatal errors
        if (fatal) color = "\033[1;31m";   // red color for fatal errors

        cerr << color << "Error";
    }
    if (!filename.empty()){
    cerr << termcolor::reset << " in the file '" << termcolor::yellow << filename << "'";
    }
    cerr << ":\n";
    cerr << termcolor::bright_blue << ">>" << prompt << "<<\n\n" << termcolor::reset;
    if (!is_warning && fatal) {
        exit(1);
    }
}

uint64_t get_type_Bitwidth(llvm::Type* T, const llvm::DataLayout& DL) {
    return DL.getTypeAllocSizeInBits(T);
}

string format_event_data(structures::TraceEvent event, bool dont_return_empty_data) {
    string data_str = "\"" + event.event + "\"";
    bool nested = false;
    if (!event.data.empty()) {
        for (const auto& sub_event : event.data) {
            if (!sub_event.data.empty()) {
                nested = true;
                break;
            }
        }
    } else if (dont_return_empty_data) {
        return data_str;
    } else {
        data_str += ": []";
        return data_str;
    }

    data_str += nested ? ": {" : ": [";

    for (const auto& sub_event : event.data) {
        data_str += format_event_data(sub_event, !nested);
        if (&sub_event != &event.data.back()) 
            data_str += ",";
    }
    data_str += nested ? "}" : "]";
    return data_str;
}

string get_trace_str(structures::Tracer tracer){
    return "{\n" + format_event_data(tracer.events) + "\n}";

}


}