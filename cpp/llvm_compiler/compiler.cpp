
#include "includes/combined_include.hpp"

#include "includes/utils.hpp"
#include "includes/compiler.hpp"
#include "includes/frontend.hpp"
#include "includes/Context.hpp"
#include "includes/compiler.hpp"
#include "includes/data_structures.hpp"

vector<string> required_hw_keys = {
    "endianness",
    "data types",
    "regs",
    "address width",
    "data width",
    "reg width",
};

vector<string> required_isa_keys = {
    "hardware",
    "translation table",
    "inst spills"
};

vector<structures::TraceEvent> Compiler::trace_funcs() const {
    vector<structures::TraceEvent> func_events = vector<structures::TraceEvent>();
    for (auto func : ctx.funcs) {
        func_events.emplace_back(func.name, func.trace());
    }
    return func_events;
}

vector<structures::TraceEvent> Compiler::trace_globals() const {
    vector<structures::TraceEvent> global_events = vector<structures::TraceEvent>();
    for (const auto& global : ctx.globals) {
        global_events.emplace_back(global.name, global.trace());
    }
    return global_events;
}


void Compiler::run(filesystem::path& program_file, filesystem::path& isa_file, filesystem::path& output_file){
    ctx.current_file = &isa_file;
    load_isa(isa_file);
    
    ctx.current_file = &program_file;

    auto parser = Frontend(ctx); 
    auto module = parser.parse(program_file);

    ctx.data_layout = &module->getDataLayout();

    // handle globals first
    parser.extract_globals(module);

    ctx.tracer.emit("extracted globals", this->trace_globals());

    // extract llvm IR functions and convert them to our internal representation
    for (auto& func : module->functions()) {
        ctx.funcs.emplace_back(func, ctx.parsed_isa.regs, ctx);
    }

    ctx.tracer.emit("constructed " + to_string(ctx.funcs.size()) + " functions", this->trace_funcs());
    

    if (ctx.tracer.enabled) {
        ofstream f(program_file.parent_path() / (program_file.filename().stem().string() + "_trace.json"));
        f << utils::get_trace_str(ctx.tracer);
    }



    int does_nothing = 0;   // a place for the debugger to break.
    return;
}


unordered_map<string, json> Compiler::generalize_naming(unordered_map<string, vector<string>> aliases, json& map, vector<string> required_keys, filesystem::path& isa_file, string error_context){
    unordered_map<string, json> generalized_dict;

    for (auto& [key, key_aliases] : aliases){
        bool found = false;
        for (const string& alias : key_aliases){
            if (map.contains(alias)){
                found = true;
                generalized_dict[key] = map[alias];
                break;
            }
        }
        if (!found && find(required_keys.begin(), required_keys.end(), key) != required_keys.end()){
            utils::error("missing required key '" + key + "'" + error_context, isa_file.filename().string());
        }
    }
    return generalized_dict;
}

void Compiler::load_isa(filesystem::path& isa_file){
    ifstream f(isa_file);
    json raw_isa = nlohmann::json::parse(f, nullptr, false, true, true);

    unordered_map<string, json> isa_data = generalize_naming(data::ISA_KEYS, raw_isa, required_isa_keys, isa_file);

    json hardware = raw_isa["hardware"];

    unordered_map<string, json> hardware_data = generalize_naming(data::HARDWARE_KEYS, hardware, required_hw_keys, isa_file);

    this->ctx.parsed_isa = Context::Isa();

    // translation table validation
    json translation_table = isa_data["translation table"];

    for (auto& [inst, translation] : translation_table.items()){
        unordered_map<string, vector<string>> inst_translation;
        if (translation.is_array()) {
            vector<string> inst_translation_vec;
            // case 1: direct array
            for (auto& format : translation){
                if (!format.is_string()){
                    utils::error(
                        "translation for instruction '" + inst +
                        "' must be an array of strings.",
                        isa_file.filename().string());
                }
                inst_translation_vec.push_back(format.get<string>());
            }
            inst_translation["default"] = inst_translation_vec;
        }
        else if (translation.is_object()) {
            // case 2: map of formats → arrays
            for (auto& [type, type_translation] : translation.items()){
                if (!type_translation.is_array()){
                    utils::error(
                        "translation for instruction '" + inst +
                        "' must be an array of strings or an object mapping formats to arrays.",
                        isa_file.filename().string());
                }

                vector<string> inst_translation_vec;
                for (auto& type_inst : type_translation){
                    if (!type_inst.is_string()){
                        utils::error(
                            "translation for instruction '" + inst +
                            "' must be an array of strings or an object mapping formats to arrays.",
                            isa_file.filename().string());
                    }
                    inst_translation_vec.push_back(type_inst.get<string>());
                }
                inst_translation[type] = inst_translation_vec;
            }
        }
        else {
            utils::error(
                "translation for instruction '" + inst +
                "' must be an array or an object.",
                isa_file.filename().string());
        }
        this->ctx.parsed_isa.translation_table.emplace(inst, inst_translation);

    }

    // inst spills validation
    json inst_spills = isa_data["inst spills"];
    
    for (auto& [inst, spills] : inst_spills.items()){
        if (!spills.is_number_unsigned()){
            utils::error(
                "spill count for instruction '" + inst +
                "' must be a non-negative integer.",
                isa_file.filename().string());
        }
        this->ctx.parsed_isa.inst_spills[inst] = spills.get<unsigned int>();
    }

    // hardware properties
    this->ctx.parsed_isa.endianness = hardware_data["endianness"].get<string>();
    if (this->ctx.parsed_isa.endianness != "little" && this->ctx.parsed_isa.endianness != "big"){
        utils::error(
            "endianness must be either 'little' or 'big'.",
            isa_file.filename().string());
    }

    if (!hardware_data["data types"].is_object()){
        utils::error(
            "data types must be an object.",
            isa_file.filename().string());
    }
    for (auto& [data_type_group, sizes] : hardware_data["data types"].items()){
        if (!sizes.is_object()){
            utils::error(
                "data type sizes must be an object.",
                isa_file.filename().string());
        }
    }
    
    auto types = generalize_naming(data::data_type_aliases, hardware_data["data types"], {"mem", "reg", "bitwidth"}, isa_file, " in data types");
    
    for (auto& [data_type_group, type_sizes] : types) {
        for (auto& [type, size_value] : type_sizes.items()){
            if (!size_value.is_number_unsigned()){
                utils::error(
                    "size for data type '" + type + "' in group '" + data_type_group + "' must be a non-negative integer.",
                    isa_file.filename().string());
            }
            this->ctx.parsed_isa.data_types[data_type_group][type] = size_value.get<unsigned int>();
        }
    }

    if (hardware_data["spec regs"].is_array()){
        for (auto& reg : hardware_data["spec regs"]){
            if (!reg.is_string()){
                utils::error(
                    "special registers must be an array of strings.",
                    isa_file.filename().string());
            }
            this->ctx.parsed_isa.spec_regs.push_back(reg.get<string>());
        }
    }

    if (hardware_data["regs"].is_array()){
        for (auto& reg : hardware_data["regs"]){
            if (!reg.is_string()){
                utils::error(
                    "registers must be an array of strings.",
                    isa_file.filename().string());
            }
            string reg_str = reg.get<string>();
            if (this->ctx.parsed_isa.spec_regs.end() == find(this->ctx.parsed_isa.spec_regs.begin(), this->ctx.parsed_isa.spec_regs.end(), reg_str)){
                this->ctx.parsed_isa.regs.push_back(reg_str);
            }
        }
    }
    else if (hardware_data["regs"].is_number_unsigned()){
        // if regs is given as a number, generate reg names as r0, r1, ...
        unsigned int num_regs = hardware_data["regs"].get<unsigned int>();
        string reg;
        for (unsigned int i = 0; i < num_regs; i++){
            reg = "r" + to_string(i);
            if (this->ctx.parsed_isa.spec_regs.end() == find(this->ctx.parsed_isa.spec_regs.begin(), this->ctx.parsed_isa.spec_regs.end(), reg)){
                this->ctx.parsed_isa.regs.push_back(reg);
            }
        }
    }
    else {
        utils::error(
            "registers must be an array or a number.",
            isa_file.filename().string());
    }
    
    if (!hardware_data["address width"].is_number_unsigned()){
        utils::error(
            "address width must be a non-negative integer.",
            isa_file.filename().string());
    }
    this->ctx.parsed_isa.address_width = hardware_data["address width"].get<unsigned int>();

    if (!hardware_data["data width"].is_number_unsigned()){
        utils::error(
            "data width must be a non-negative integer.",
            isa_file.filename().string());
    }
    else {
        this->ctx.parsed_isa.data_width = hardware_data["data width"].get<unsigned int>();
        if (this->ctx.parsed_isa.data_width > 64){
            utils::error(
                "data width must not exceed 64 bits.",
                isa_file.filename().string());
        }
    }


    if (!hardware_data["reg width"].is_number_unsigned()){
        utils::error(
            "register width must be a non-negative integer.",
            isa_file.filename().string());
    } else {
        this->ctx.parsed_isa.reg_width = hardware_data["reg width"].get<unsigned int>();
        if (this->ctx.parsed_isa.reg_width > 64){
            utils::error(
                "register width must not exceed 64 bits.",
                isa_file.filename().string());
        }
    }

    // further validation can be added here (e.g. check that all instructions in the translation table have an entry in the spill table)

}
