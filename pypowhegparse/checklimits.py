import glob
from pathlib import Path

from smpl.io.grep import grep


def _checklimits_files(folder):
    return sorted(glob.glob(folder + "/*checklimits*"))


def _encode_lines(lines, trailing_empty=True):
    encoded = [line.encode("utf-8") for line in lines]
    if trailing_empty:
        encoded.append(b"")
    return encoded


def inspect_warn_loop(folder, level=1):
    raise Exception("Unimplemented")


def error_colour_grep(folder):
    matches = []
    for file in _checklimits_files(folder):
        lines = grep("colour check fails", file).read().splitlines()
        matches.extend(f"{file}:{line}" for line in lines)
    return _encode_lines(matches)


def error_spin_grep(folder):
    matches = []
    for file in _checklimits_files(folder):
        lines = grep("spin correlated amplitude wrong", file).read().splitlines()
        matches.extend(f"{file}:{line}" for line in lines)
    return _encode_lines(matches)


def inspect_warn_grep(folder, level=1, after=10, before=10):
    pattern = "W" * level + "ARN"
    blocks = []

    for file in _checklimits_files(folder):
        matched_lines = grep(pattern, file).read().splitlines()
        if not matched_lines:
            continue

        path = Path(file)
        lines = path.read_text().splitlines()
        search_start = 0

        for matched_line in matched_lines:
            for match_index in range(search_start, len(lines)):
                if pattern in lines[match_index] and lines[match_index] == matched_line:
                    break
            else:
                continue

            start = max(0, match_index - before)
            end = min(len(lines), match_index + after + 1)
            block = [f"{file}:{line}" for line in lines[start:end]]
            blocks.append(_encode_lines(block, trailing_empty=False))
            search_start = match_index + 1

    return blocks


def search_for_warn_loop(folder, level=1):
    raise Exception("Unimplemented")


def search_for_warn_grep(folder, level=1):
    pattern = "W" * level + "ARN"
    matches = []
    for file in _checklimits_files(folder):
        matches.extend(grep(pattern, file).read().splitlines())
    return _encode_lines(matches)


def search_for_warn(folder, level=1, grep=True):
    if grep:
        return search_for_warn_grep(folder, level)
    else:
        return search_for_warn_loop(folder, level)


def count_warn(folder, level=1, grep=True):
    if grep:
        return len([line for line in search_for_warn_grep(folder, level) if line])
    else:
        return len(search_for_warn_loop(folder, level)) - 1


def print_stats(folder, grep=True):
    print("#WARN    = ", count_warn(folder, 1))
    print("#WWARN   = ", count_warn(folder, 2))
    print("#WWWARN  = ", count_warn(folder, 3))
    print("#WWWWARN = ", count_warn(folder, 4))
    print("#WWWWWARN = ", count_warn(folder, 5))


def print_warn_grep(folder, level=5):
    for a in inspect_warn_grep(folder, level):
        print()
        for s in a:
            print(s)
        print()
