import pytest

import pypowhegparse as pp

from tests._support import PROCESS_DIRS, PROCESS_IDS, checklimits_files


@pytest.mark.parametrize("process_dir", PROCESS_DIRS, ids=PROCESS_IDS)
def test_process_directory_contains_checklimits_fixtures(process_dir):
    assert checklimits_files(process_dir)


@pytest.mark.parametrize("process_dir", PROCESS_DIRS, ids=PROCESS_IDS)
def test_search_for_warn_returns_warn_lines(process_dir):
    lines = pp.search_for_warn(str(process_dir))
    nonempty_lines = [line for line in lines if line]

    assert nonempty_lines
    assert all(isinstance(line, bytes) for line in nonempty_lines)
    assert all(b"*-WARN-*" in line for line in nonempty_lines)


@pytest.mark.parametrize("process_dir", PROCESS_DIRS, ids=PROCESS_IDS)
def test_count_warn_matches_search_results(process_dir):
    lines = pp.search_for_warn(str(process_dir))
    nonempty_lines = [line for line in lines if line]

    assert pp.count_warn(str(process_dir)) == len(nonempty_lines)
