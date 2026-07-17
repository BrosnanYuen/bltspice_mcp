from pathlib import Path

import pytest

from bltspice_mcp.config import ServerConfig, load_config
from bltspice_mcp.conversion import CONVERSION_CALLABLES
from bltspice_mcp.dispatcher import ApiDispatcher


class DummyObject:
    def __init__(self):
        self.value = 0

    def set_tolerance(self, ref: str, new_tolerance: float, distribution: str = "uniform"):
        self.value = new_tolerance
        return {"ref": ref, "distribution": distribution, "value": self.value}


class DummyTrace:
    def __init__(self, waves):
        self._waves = waves

    def get_wave(self, wave: int):
        return self._waves[wave]


class DummyRaw:
    def __init__(self):
        self._steps = [0, 1]
        self._axis = [[0.0, 1.0, 2.0], [0.0, 1.0]]
        self._traces = {
            "V(opamp_input)": DummyTrace([[10.0, 11.0, 12.0], [20.0, 21.0]]),
            "V(opamp_output)": DummyTrace([[100.0, 101.0, 102.0], [200.0, 201.0]]),
        }

    def get_steps(self):
        return self._steps

    def get_axis(self, wave: int):
        return self._axis[wave]

    def get_trace(self, trace_ref: str):
        return self._traces[trace_ref]


def _config(tmp_path: Path) -> ServerConfig:
    return ServerConfig(
        mcp_server_name="x",
        mcp_server_url="stdio://",
        wine_path=str(tmp_path / "wine"),
        ltspice_path=str(tmp_path / "ltspice.exe"),
        enable_extra_tools=True,
        timeout=10,
    )


def test_execute_known_function(tmp_path: Path):
    d = ApiDispatcher(config=_config(tmp_path), project_root=tmp_path)
    out_name, out = d.execute_api("all_loggers", {})
    assert out_name is None
    assert isinstance(out["result"], list)
    assert "spicelib.SimRunner" in out["result"]


def test_execute_stores_object_with_new_name(tmp_path: Path):
    d = ApiDispatcher(config=_config(tmp_path), project_root=tmp_path)
    out_name, out = d.execute_api("RawWrite", {"new_object_name": "raw_writer"})
    assert out_name == "raw_writer"
    assert "raw_writer" in d.registry
    assert out["result"]["type"].endswith("RawWrite")


def test_execute_object_method_without_dotted_name(tmp_path: Path):
    d = ApiDispatcher(config=_config(tmp_path), project_root=tmp_path)
    d.registry["mc"] = DummyObject()
    out_name, out = d.execute_api(
        "set_tolerance",
        {
            "object_name": "mc",
            "ref": "C",
            "new_tolerance": 0.1,
            "distribution": "uniform",
        },
    )
    assert out_name is None
    assert out["result"]["value"] == 0.1


def test_execute_unknown_api_raises(tmp_path: Path):
    d = ApiDispatcher(config=_config(tmp_path), project_root=tmp_path)
    with pytest.raises(ValueError):
        d.execute_api("does_not_exist", {})


def test_only_requested_electronics_design_apis_are_exposed():
    assert set(CONVERSION_CALLABLES) == {
        "is_valid_ltspice_netlist_file",
        "ltspice_netlist_to_asc",
    }


def test_traces_to_csv_writes_all_waves(tmp_path: Path):
    d = ApiDispatcher(config=_config(tmp_path), project_root=tmp_path)
    d.registry["raw"] = DummyRaw()

    out_name, out = d.execute_api(
        "traces_to_csv",
        {
            "object_name": "raw",
            "trace_refs": ["V(opamp_input)", "V(opamp_output)"],
            "output_files": "./sim_wave_",
        },
    )
    assert out_name is None
    result = out["result"]
    assert result["wave_count"] == 2
    assert len(result["written_files"]) == 2

    csv0 = Path(result["written_files"][0]).read_text(encoding="utf-8")
    csv1 = Path(result["written_files"][1]).read_text(encoding="utf-8")

    assert "xaxis,V(opamp_input),V(opamp_output)" in csv0
    assert "0.0,10.0,100.0" in csv0
    assert "2.0,12.0,102.0" in csv0
    assert "xaxis,V(opamp_input),V(opamp_output)" in csv1
    assert "1.0,21.0,201.0" in csv1


def test_conversion_api_receives_configured_convert_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    captured = {}

    def fake_converter(**kwargs):
        captured.update(kwargs)
        return True, "OK", 0

    monkeypatch.setitem(CONVERSION_CALLABLES, "ltspice_netlist_to_asc", fake_converter)
    d = ApiDispatcher(config=_config(tmp_path), project_root=tmp_path)

    out_name, out = d.execute_api(
        "ltspice_netlist_to_asc",
        {"netlist_filepath": "input.net", "asc_filepath_out": "output.asc"},
    )

    assert out_name is None
    assert out["result"] == [True, "OK", 0]
    assert captured["convert_settings"]["minimum_dist"] == 32
    assert captured["convert_settings"]["wire_pin_out_dist"] == 16
    assert captured["convert_settings"]["grid_size"] == 16
    assert captured["convert_settings"]["autoplace_iter"] == 12
    assert captured["convert_settings"]["ltspice_version"] == 4.1
    assert captured["convert_settings"]["custom_search_paths"] == [str(tmp_path / "valid_asy")]
    assert captured["convert_settings"]["ltspice_windows_path"] == "C:\\users\\brosnan\\AppData\\Local\\LTspice\\"


def test_netlist_to_asc_uses_checked_in_config_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    captured = {}

    def fake_converter(**kwargs):
        captured.update(kwargs)
        return True, "OK", 0

    monkeypatch.setitem(CONVERSION_CALLABLES, "ltspice_netlist_to_asc", fake_converter)
    config_path = Path(__file__).parents[2] / "config.json"
    d = ApiDispatcher(config=load_config(config_path), project_root=tmp_path)

    d.execute_api(
        "ltspice_netlist_to_asc",
        {"netlist_filepath": "input.net", "asc_filepath_out": "output.asc"},
    )

    assert captured["convert_settings"]["ltspice_windows_path"] == "C:\\users\\brosnan\\AppData\\Local\\LTspice\\"
    assert captured["convert_settings"]["minimum_dist"] == 32
    assert captured["convert_settings"]["wire_pin_out_dist"] == 16
    assert captured["convert_settings"]["grid_size"] == 16
    assert captured["convert_settings"]["autoplace_iter"] == 12
    assert captured["convert_settings"]["ltspice_version"] == 4.1


def test_netlist_validator_does_not_receive_convert_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    captured = {}

    def fake_validator(**kwargs):
        captured.update(kwargs)
        return True, "OK", 0

    monkeypatch.setitem(CONVERSION_CALLABLES, "is_valid_ltspice_netlist_file", fake_validator)
    d = ApiDispatcher(config=_config(tmp_path), project_root=tmp_path)

    out_name, out = d.execute_api("is_valid_ltspice_netlist_file", {"filepath": "input.net"})

    assert out_name is None
    assert out["result"] == [True, "OK", 0]
    assert captured == {"filepath": str(tmp_path / "input.net")}


def test_conversion_request_settings_override_configured_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    captured = {}

    def fake_converter(**kwargs):
        captured.update(kwargs)
        return True, "OK", 0

    monkeypatch.setitem(CONVERSION_CALLABLES, "ltspice_netlist_to_asc", fake_converter)
    d = ApiDispatcher(config=_config(tmp_path), project_root=tmp_path)

    d.execute_api(
        "ltspice_netlist_to_asc",
        {
            "netlist_filepath": "input.net",
            "asc_filepath_out": "output.asc",
            "convert_settings": {"minimum_dist": 8, "autoplace_iter": 3},
        },
    )

    assert captured["convert_settings"]["minimum_dist"] == 8
    assert captured["convert_settings"]["autoplace_iter"] == 3
    assert captured["convert_settings"]["wire_pin_out_dist"] == 16
