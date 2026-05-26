#pragma once

// for windows
#ifdef _WIN32
  #ifndef NOMINMAX
    #define NOMINMAX
  #endif
#endif

// custom includes 
#include "termcolor.hpp"
#include "json.hpp"
#include "data.hpp"

// standard library includes
#include <string>
#include <unordered_map>
#include <map>
#include <vector>
#include <filesystem>
#include <iostream>
#include <fstream>
#include <string>
#include <variant>
#include <optional>
#include <sstream>
#include <set>

// llvm includes
#include "llvm/IR/Module.h"       // llvm::Module
#include "llvm/IR/LLVMContext.h"  // llvm::LLVMContext
#include "llvm/Support/SourceMgr.h" // llvm::SMDiagnostic
#include "llvm/IRReader/IRReader.h" // parseIRFile()
#include "llvm/Support/MemoryBuffer.h" // readFile into buffer
#include "llvm/IR/Constants.h"
#include "llvm/IR/Constant.h"
#include "llvm/ADT/APInt.h"
#include "llvm/Support/Casting.h"
#include "llvm/IR/Instructions.h"  // llvm::CallBase, llvm::CallInst, llvm::InvokeInst
#include "llvm/IR/Instruction.h"
#include "llvm/IR/CFG.h"
#include "llvm/IR/Instruction.def"


using namespace std;
using json = nlohmann::json;
using I64 = int64_t;

using TranslationFormats = unordered_map<string, vector<string>>;
using TranslationTable   = unordered_map<string, TranslationFormats>;
using InstSpills         = unordered_map<string, int>;
