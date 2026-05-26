#pragma once

#include "combined_include.hpp"


using Alias = std::unordered_map<std::string, std::vector<std::string>>;

namespace data{

extern Alias ISA_KEYS;
extern Alias HARDWARE_KEYS;
extern Alias data_type_aliases;

extern unordered_map<string, unsigned> str_to_llvm_inst;
}