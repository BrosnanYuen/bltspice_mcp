from bltspice_mcp import create_mcp_server
from bltspice_mcp.responses import (
    completed,
    file_not_found,
    in_progress,
    internal_error,
    invalid_input,
    parser_failed,
    simulation_failed,
    simulator_not_configured,
    timed_out,
    unsupported_file_type,
)


def test_response_shapes():
    assert in_progress("execute") == {
        "status": "performing LTspice operation in progress",
        "operation": "execute",
    }
    assert completed("execute", output={"a": 1}, output_obj_name="x") == {
        "status": "LTspice operation completed!",
        "operation": "execute",
        "output_obj_name": "x",
        "output": {"a": 1},
    }
    assert invalid_input("execute")["status"] == "invalid input!"
    assert file_not_found("execute")["status"] == "file not found!"
    assert unsupported_file_type("execute")["status"] == "unsupported file type!"
    assert simulator_not_configured("runtime_info")["status"] == "simulator not configured!"
    assert simulation_failed("execute")["status"] == "simulation failed!"
    assert parser_failed("execute")["status"] == "parser failed!"
    assert timed_out("execute")["status"] == "LTspice operation timed out!"
    assert internal_error("execute")["status"] == "internal error"


def test_package_export_is_available():
    assert callable(create_mcp_server)
