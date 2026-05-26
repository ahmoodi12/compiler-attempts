/*
# windows
cd cpp_files\llvm_compiler\builds\windows
ninja 

# linux
cd cpp_files\llvm_compiler\builds\linux
ninja 

*/

#include "includes/combined_include.hpp"
#include "includes/cxxopts.hpp"
#include "includes/utils.hpp"
#include "includes/compiler.hpp"

using namespace std;
namespace argparse = cxxopts;

filesystem::path get_file_path(string filename){
    filesystem::path file_path(filename);

    file_path.is_relative() ? file_path = filesystem::current_path() / file_path : file_path; 
    
    if (!filesystem::exists(file_path)){
        utils::error("the file '" + filename + "' doesn't exist.");
    } 
    return file_path;
}

int main(int argc, char **argv)
{
    argparse::Options argparser("main", "llvm compiler");
    
    argparser.add_options()
    ("program", "program file", argparse::value<std::string>())
    ("isa", "isa file", argparse::value<std::string>())
    ("o,output", "output file", argparse::value<std::string>())
    ("w,warn", "show warnings", argparse::value<bool>()->default_value("false"))
    ("t,trace", "trace execution", argparse::value<bool>()->default_value("false"))
    ("h,help", "Show help");

    argparser.parse_positional({ "program", "isa" });
    
    auto args = argparser.parse(argc, argv);
    
    if (!args.count("program")){
        utils::error("missing program file.");
    } 

    if (!args.count("isa")){
        utils::error("missing isa file.");
    } 

    if (args.count("help")){
        cout << argparser.help() << endl;
        return 0;
    }

    filesystem::path program_file = get_file_path(args["program"].as<string>());
    filesystem::path isa_file = get_file_path(args["isa"].as<string>());
    filesystem::path output_file;
    if (args.count("o")){
        output_file = get_file_path(args["o"].as<string>());
    } else {
        output_file = program_file;
        output_file.replace_extension(".asm");
    }
    

    Compiler compiler(program_file.filename().string(), args["warn"].as<bool>(), args["trace"].as<bool>());

    compiler.run(program_file, isa_file, output_file);

    return 0;
}