import datetime
import subprocess
from types import SimpleNamespace

import pytest

from replication import config, schedules
from replication.logging_utils import SafeStream, _fmt_cmd, _truncate
from replication.planner import (
    EXTRA_RECV_ARGS_ENV,
    EXTRA_RECV_FLAGS,
    EXTRA_SEND_ARGS_ENV,
    EXTRA_SEND_FLAGS,
    ExtraArgsError,
    build_zfs_recv_args,
    build_zfs_send_args,
    check_extra_args_against_task,
    parse_extra_zfs_args,
    zfs_recv_shell,
)


@pytest.mark.parametrize(
    "value,default,expected",
    [(None, True, True), (None, False, False), ("YES", False, True), (" on ", False, True), ("0", True, False), ("garbage", True, False)],
)
def test_as_bool(value, default, expected):
    assert config.as_bool(value, default=default) is expected


@pytest.mark.parametrize(
    "size,unit,expected",
    [("8", "m", ("8", "M")), (0, "K", ("1", "K")), ("bad", "T", ("1", "G")), (None, None, ("1", "G"))],
)
def test_clamp_mbuffer(size, unit, expected):
    assert config.clamp_mbuffer(size, unit) == expected


@pytest.mark.parametrize(
    "size,unit,expected",
    [("256", "k", ("256", "k")), (0, "K", ("256", "k")), ("bad", "M", ("256", "M")), (None, None, ("256", "k"))],
)
def test_clamp_mbuffer_block(size, unit, expected):
    assert config.clamp_mbuffer_block(size, unit) == expected


@pytest.mark.parametrize(
    "pool,dataset,expected",
    [("tank", "data", "tank/data"), ("tank", "tank/data", "tank/data"), ("tank", "tank", "tank"), ("", "tank/data", "tank/data"), ("tank", "", "tank")],
)
def test_join_zfs_path(pool, dataset, expected):
    assert config.join_zfs_path(pool, dataset) == expected


def test_destination_ports_distinguish_ssh_and_netcat(monkeypatch):
    monkeypatch.setenv("zfsRepConfig_destDataset_port", "31337")
    monkeypatch.setenv("zfsRepConfig_destDataset_sshPort", "2222")
    assert config.get_dest_ports("ssh") == ("2222", "31337")
    assert config.get_dest_ports("netcat") == ("2222", "31337")
    assert config.get_dest_ports("mbuffer") == ("2222", "31337")
    monkeypatch.delenv("zfsRepConfig_destDataset_sshPort")
    assert config.get_dest_ports("ssh") == ("31337", "31337")
    assert config.get_dest_ports("netcat") == ("22", "31337")
    assert config.get_dest_ports("mbuffer") == ("22", "31337")


@pytest.mark.parametrize(
    "recursive,include,expected_flag",
    [(True, None, "-I"), (False, None, "-i"), (True, False, "-i"), (False, True, "-I")],
)
def test_incremental_send_flag_matrix(recursive, include, expected_flag):
    args = build_zfs_send_args("tank/data@new", "tank/data@old", recursive=recursive, compressed=False, raw=False, include_intermediates=include)
    assert expected_flag in args
    assert args[-3:] == [expected_flag, "tank/data@old", "tank/data@new"]


def test_send_flags_are_composed_without_incremental_base():
    assert build_zfs_send_args("tank/data@snap", "", recursive=True, compressed=True, raw=True) == [
        "zfs", "send", "-R", "-Lc", "-w", "tank/data@snap"
    ]


def test_compressed_send_omits_embedded_data_flag():
    args = build_zfs_send_args("tank/data@new", "tank/data@old", recursive=False, compressed=True, raw=False)
    assert "-Lc" in args
    assert not any(a.startswith("-") and not a.startswith("--") and "e" in a for a in args)


@pytest.mark.parametrize("text, expected", [
    ("", []),
    ("-p", ["-p"]),
    ("-pb --holds", ["-p", "-b", "--holds"]),
])
def test_extra_send_args_accepts_allowlisted_flags(text, expected):
    assert parse_extra_zfs_args(text, EXTRA_SEND_FLAGS) == expected


@pytest.mark.parametrize("text, expected", [
    ("-o compression=zstd", ["-o", "compression=zstd"]),
    ("-ocompression=zstd -x mountpoint -u", ["-o", "compression=zstd", "-x", "mountpoint", "-u"]),
    ("-uo readonly=on", ["-u", "-o", "readonly=on"]),
    ("-o 'org.example:note=a b'", ["-o", "org.example:note=a b"]),
])
def test_extra_recv_args_accepts_allowlisted_flags(text, expected):
    assert parse_extra_zfs_args(text, EXTRA_RECV_FLAGS) == expected


@pytest.mark.parametrize("text, allowed", [
    ("-R", EXTRA_SEND_FLAGS),
    ("-w", EXTRA_SEND_FLAGS),
    ("-pw", EXTRA_SEND_FLAGS),
    ("--props=yes", EXTRA_SEND_FLAGS),
    ("tank/other@snap", EXTRA_SEND_FLAGS),
    ("-F", EXTRA_RECV_FLAGS),
    ("-d", EXTRA_RECV_FLAGS),
    ("-o", EXTRA_RECV_FLAGS),
    ("-o compression", EXTRA_RECV_FLAGS),
    ("-x mountpoint=/mnt", EXTRA_RECV_FLAGS),
    ("-o origin=tank/x@s", EXTRA_RECV_FLAGS),
    ("-o -u", EXTRA_RECV_FLAGS),
    ("-u; rm -rf /", EXTRA_RECV_FLAGS),
    ("-o 'unterminated", EXTRA_RECV_FLAGS),
    ("-p --props", EXTRA_SEND_FLAGS),
    ("-hh", EXTRA_SEND_FLAGS),
    ("-u -u", EXTRA_RECV_FLAGS),
    ("-o compression=lz4 -o compression=zstd", EXTRA_RECV_FLAGS),
    ("-o mountpoint=/mnt -x mountpoint", EXTRA_RECV_FLAGS),
    ("-x atime -x atime", EXTRA_RECV_FLAGS),
    ("-o encryption=on", EXTRA_RECV_FLAGS),
    ("-x keylocation", EXTRA_RECV_FLAGS),
    ("-x com.45drives_scheduler:task_name", EXTRA_RECV_FLAGS),
    ("-o =value", EXTRA_RECV_FLAGS),
])
def test_extra_args_rejects_unsafe_or_managed_input(text, allowed):
    with pytest.raises(ExtraArgsError):
        parse_extra_zfs_args(text, allowed)


def test_distinct_properties_and_flags_are_not_duplicates():
    assert parse_extra_zfs_args("-o compression=zstd -x mountpoint -o atime=off -u -h", EXTRA_RECV_FLAGS) == [
        "-o", "compression=zstd", "-x", "mountpoint", "-o", "atime=off", "-u", "-h",
    ]


@pytest.mark.parametrize("send", [["-p"], ["--props"]])
def test_props_flag_conflicts_with_recursive_send(send):
    with pytest.raises(ExtraArgsError, match="Send Recursive"):
        check_extra_args_against_task(send, recursive=True)
    check_extra_args_against_task(send, recursive=False)


def test_send_args_include_extra_flags_before_snapshots(monkeypatch):
    monkeypatch.setenv(EXTRA_SEND_ARGS_ENV, "-p")
    args = build_zfs_send_args("tank/data@new", "tank/data@old", recursive=False, compressed=True, raw=False)
    assert args == ["zfs", "send", "-Lc", "-p", "-i", "tank/data@old", "tank/data@new"]


def test_recv_args_place_extra_flags_before_target(monkeypatch):
    monkeypatch.setenv(EXTRA_RECV_ARGS_ENV, "-o compression=zstd -u")
    assert build_zfs_recv_args("backup/data", True) == [
        "zfs", "recv", "-s", "-F", "-o", "compression=zstd", "-u", "backup/data",
    ]


def test_recv_shell_quotes_values_for_remote_shells(monkeypatch):
    monkeypatch.setenv(EXTRA_RECV_ARGS_ENV, "-o 'org.example:note=a b'")
    assert zfs_recv_shell("backup/data", False) == "zfs recv -s -o 'org.example:note=a b' backup/data"


def test_recv_args_without_extras_are_unchanged(monkeypatch):
    monkeypatch.delenv(EXTRA_RECV_ARGS_ENV, raising=False)
    assert build_zfs_recv_args("backup/data", False) == ["zfs", "recv", "-s", "backup/data"]


@pytest.mark.parametrize(
    "pattern,current,expected",
    [("*", 9, True), ("2..5", 4, True), ("2..5", 7, False), ("1/3", 7, True), ("1/0", 1, False), ("1,4,9", 4, True), ("8", 8, True), ("bad", 8, False)],
)
def test_schedule_field_matching(pattern, current, expected):
    assert schedules._field_matches_value(pattern, current) is expected


def test_schedule_matches_day_of_week_and_chooses_most_specific():
    now = datetime.datetime(2026, 8, 4, 14, 30)  # Tuesday
    intervals = [
        {"minute": {"value": "30"}},
        {"minute": {"value": "30"}, "hour": {"value": "14"}, "dayOfWeek": ["Tuesday"]},
        {"minute": {"value": "30"}, "hour": {"value": "14"}, "dayOfWeek": ["Mon"]},
    ]
    assert schedules.match_current_tier(intervals, now) == 1


def test_schedule_tie_prefers_lower_index_and_no_match_falls_back_to_zero():
    now = datetime.datetime(2026, 8, 4, 14, 30)
    tied = [{"minute": {"value": "30"}}, {"hour": {"value": "14"}}]
    assert schedules.match_current_tier(tied, now) == 0
    assert schedules.match_current_tier([{"hour": {"value": "2"}}], now) == 0


def test_load_schedule_json_success_and_failure(tmp_path, capsys):
    path = tmp_path / "schedule.json"
    path.write_text('{"intervals": []}')
    assert schedules.load_schedule_json(str(path)) == {"intervals": []}
    assert schedules.load_schedule_json(str(tmp_path / "missing.json")) is None
    assert "could not read schedule JSON" in capsys.readouterr().out


def test_logging_helpers_bound_output_and_quote_commands():
    assert _truncate("abcdef", 4) == "abcd\n...[truncated 2 chars]"
    assert _fmt_cmd(["zfs", "get", "name with spaces"]) == "zfs get 'name with spaces'"


def test_safe_stream_absorbs_broken_writer():
    class Broken:
        def write(self, data):
            raise BrokenPipeError()

        def flush(self):
            raise BrokenPipeError()

    stream = SafeStream(Broken())
    assert stream.write("x") == 0
    assert stream.flush() is None
    assert stream.isatty() is False

