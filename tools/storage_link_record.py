#!/usr/bin/env python3
"""Record an actually executed compiler/link command, before kernel postprocessing.

This transparent CMake link launcher changes no compiler arguments. Its expanded
response view is evidence only; GCC/ld receive the original argument vector.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

try:
    from .storage_build_evidence import digest, file_record, resolved_inputs, verify_source
except ImportError:
    from storage_build_evidence import digest, file_record, resolved_inputs, verify_source


def verify_files(records):
    for record in records:
        file_record(record, 'executed link input')


def response_words(content):
    """GNU response grammar: backslash quotes the next byte in either quote mode."""
    words, word, quote, started = [], [], None, False
    index = 0
    while index < len(content):
        char = content[index]
        if char == '\\':
            index += 1
            if index >= len(content):
                raise ValueError('response ends with an escape')
            word.append(content[index])
            started = True
        elif quote:
            if char == quote:
                quote = None
            else:
                word.append(char)
        elif char in ('"', "'"):
            quote = char
            started = True
        elif char in ' \t\r\n\v\f':
            if started:
                words.append(''.join(word))
                word, started = [], False
        else:
            word.append(char)
            started = True
        index += 1
    if quote:
        raise ValueError('unclosed response quote')
    if started:
        words.append(''.join(word))
    return words


def expand_arguments(arguments, directory):
    directory = Path(directory).resolve()
    files = {}

    def response(token, active, linker):
        if not token.startswith('@'):
            return [token] if linker else compiler([token], active)
        path = (directory / token[1:]).resolve()
        if path in active or len(active) >= 32:
            raise ValueError('recursive/deep linker response input')
        files[str(path)] = {'path': str(path), 'sha256': digest(path)}
        content = response_words(path.read_text(encoding='utf-8'))
        if linker:
            return [item for arg in content for item in response(arg, active | {path}, True)]
        return compiler(content, active | {path})

    def compiler(args, active):
        expanded = []
        index = 0
        while index < len(args):
            arg = args[index]
            if arg.startswith('@'):
                expanded += response(arg, active, False)
            elif arg.startswith('-Wl,'):
                for operand in arg[4:].split(','):
                    for item in response(operand, active, True):
                        expanded += ['-Xlinker', item]
            elif arg == '-Xlinker':
                index += 1
                if index >= len(args):
                    raise ValueError('missing -Xlinker operand')
                for item in response(args[index], active, True):
                    expanded += ['-Xlinker', item]
            else:
                expanded.append(arg)
            index += 1
        return expanded

    expanded = compiler(list(arguments), set())
    return expanded, list(files.values())


def link_paths(arguments, directory):
    output, maps, linker = [], [], []
    index = 1
    while index < len(arguments):
        arg = arguments[index]
        if arg == '-o':
            index += 1
            if index >= len(arguments):
                raise ValueError('missing output argument')
            output.append(arguments[index])
        elif arg.startswith('-o') and len(arg) > 2:
            output.append(arg[2:])
        elif arg.startswith('-Wl,'):
            linker += arg[4:].split(',')
        elif arg == '-Xlinker':
            index += 1
            if index >= len(arguments):
                raise ValueError('missing linker operand')
            linker.append(arguments[index])
        index += 1
    index = 0
    while index < len(linker):
        arg = linker[index]
        if arg == '-Map':
            index += 1
            if index >= len(linker):
                raise ValueError('missing map argument')
            maps.append(linker[index])
        elif arg.startswith('-Map='):
            maps.append(arg[5:])
        elif arg.startswith('-Map') and len(arg) > 4:
            maps.append(arg[4:])
        index += 1
    if len(output) != 1 or len(maps) != 1 or not output[0] or not maps[0]:
        raise ValueError('executed link requires exactly one output and map')
    directory = Path(directory).resolve()
    return (directory / output[0]).resolve(), (directory / maps[0]).resolve()


def run_link(arguments, record, directory=None, source=None, source_tree=None):
    directory = Path(directory or Path.cwd()).resolve()
    record = Path(record).resolve()
    record.parent.mkdir(parents=True, exist_ok=True)
    record.unlink(missing_ok=True)
    if source is not None:
        source_identity = verify_source(source, source_tree)
    expanded, responses = expand_arguments(arguments, directory)
    output, map_path = link_paths(expanded, directory)
    if not output.is_relative_to(directory) or not map_path.is_relative_to(directory):
        raise ValueError('kernel output/map must stay inside the build directory')
    # Hash explicit object/archive inputs before execution. The resolved map
    # adds system libraries afterwards, including linker-script dependencies.
    direct = []
    for arg in expanded[1:]:
        if not arg.startswith('-') and Path(arg).suffix in ('.o', '.obj', '.a', '.lib', '.ld', '.lds', '.def'):
            path = (directory / arg).resolve()
            direct.append({'path': str(path), 'sha256': digest(path)})
    executable = shutil.which(arguments[0])
    if not executable:
        raise ValueError('executed compiler is unavailable')
    compiler = Path(executable).resolve()
    result = {'schema': 1, 'cwd': str(directory), 'argv': list(arguments),
              'expanded_argv': expanded, 'response_files': responses,
              'compiler': {'path': str(compiler), 'sha256': digest(compiler)},
              'direct_inputs': direct, 'output_path': str(output)}
    if source is not None:
        result.update(source_directory=str(Path(source).resolve()), source_tree=source_tree,
                      source_worktree_sha256=source_identity['worktree_sha256'])
    process = subprocess.run(arguments, cwd=directory)
    result['exit_code'] = process.returncode
    if process.returncode == 0:
        if source is not None:
            verify_source(source, source_tree, source_identity['worktree_sha256'])
        verify_files(responses + direct)
        inputs, transient, synthetic = resolved_inputs(map_path, directory)
        snapshot = record.with_suffix('.linked.exe')
        shutil.copyfile(output, snapshot)
        result.update(linked_output={'path': str(snapshot), 'sha256': digest(snapshot)},
                      linker_map={'path': str(map_path), 'sha256': digest(map_path)},
                      resolved_inputs=inputs, transient_lto_inputs=transient,
                      synthetic_inputs=synthetic)
    temporary = record.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    temporary.replace(record)
    return process.returncode


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', required=True, type=Path)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--source-tree', required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        parser.error('missing actual compiler command')
    try:
        return run_link(command, args.record, source=args.source, source_tree=args.source_tree)
    except (OSError, ValueError) as error:
        print('storage link evidence failed: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
