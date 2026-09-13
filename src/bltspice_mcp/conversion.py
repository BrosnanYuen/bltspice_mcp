"""LTspice schematic conversion APIs exposed by the MCP dispatcher."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from electronics_design import (
    is_valid_ltspice_netlist_file,
    kicad_sch_to_ltspice_netlist,
    ltspice_netlist_to_asc,
    ltspice_netlist_to_kicad_sch,
)


# The dispatcher supplies configured convert_settings to
# ltspice_netlist_to_asc, kicad_sch_to_ltspice_netlist, and
# ltspice_netlist_to_kicad_sch when a request does not provide them.
CONVERSION_CALLABLES: dict[str, Callable[..., Any]] = {
    "is_valid_ltspice_netlist_file": is_valid_ltspice_netlist_file,
    "ltspice_netlist_to_asc": ltspice_netlist_to_asc,
    "kicad_sch_to_ltspice_netlist": kicad_sch_to_ltspice_netlist,
    "ltspice_netlist_to_kicad_sch": ltspice_netlist_to_kicad_sch,
}

CONVERSION_APIS = frozenset(
    {
        "ltspice_netlist_to_asc",
        "kicad_sch_to_ltspice_netlist",
        "ltspice_netlist_to_kicad_sch",
    }
)
