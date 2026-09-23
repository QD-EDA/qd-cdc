import json
import tempfile
import unittest
from pathlib import Path
from qd_cdc import check, main


def net(cells, ports=None):
    if ports is None:
        ports = {}
        inputs = set()
        outputs = set()
        for c in cells.values():
            for port, bits in c.get("connections", {}).items():
                (outputs if c.get("port_directions", {}).get(port) == "output" else inputs).update(bits)
        for i, bit in enumerate(sorted(inputs - outputs)):
            ports[f"in{i}"] = {"direction": "input", "bits": [bit]}
    return {"modules": {"top": {"ports": ports, "cells": cells}}}


def ff(d, q, clk, async_reg=False):
    return {"type": "$_DFF_P_", "attributes": {"async_reg": "1" if async_reg else "0", "src": "fixture.sv:4"},
            "connections": {"D": [d], "Q": [q], "C": [clk]},
            "port_directions": {"D": "input", "Q": "output", "C": "input"}}


class CDCTest(unittest.TestCase):
    def test_crossing_and_same_clock(self):
        cells = {"src": ff(1, 2, 10), "dst": ff(2, 3, 11), "same": ff(3, 4, 11)}
        self.assertEqual([r["classification"] for r in check(net(cells), "top")], ["CROSSING"])

    def test_two_stage_annotation_is_candidate_only(self):
        cells = {"src": ff(1, 2, 10), "stage1": ff(2, 3, 11, True), "stage2": ff(3, 4, 11, True)}
        r = check(net(cells), "top")
        self.assertEqual([x["classification"] for x in r], ["CANDIDATE_SYNCHRONIZER"])

    def test_unannotated_chain_is_crossing(self):
        cells = {"src": ff(1, 2, 10), "stage1": ff(2, 3, 11), "stage2": ff(3, 4, 11)}
        self.assertEqual(check(net(cells), "top")[0]["classification"], "CROSSING")
        cells["stage1"] = ff(2, 3, 11, True)
        self.assertEqual(check(net(cells), "top")[0]["classification"], "CROSSING")

    def test_combinational_and_unknown_paths(self):
        and_cell = {"type": "$_AND_", "connections": {"A": [2], "B": [8], "Y": [9]},
                    "port_directions": {"A": "input", "B": "input", "Y": "output"}}
        cells = {"src": ff(1, 2, 10), "gate": and_cell, "dst": ff(9, 3, 11)}
        self.assertEqual(check(net(cells), "top")[0]["classification"], "CROSSING")
        cells["gate"] = {"type": "VENDOR_BOX", "connections": {"A": [2], "Y": [9]},
                         "port_directions": {"A": "input", "Y": "output"}}
        self.assertEqual(check(net(cells), "top")[0]["classification"], "UNKNOWN")

    def test_json_is_reproducible_and_bad_top_exit(self):
        cells = {"z": ff(1, 2, 10), "a": ff(2, 3, 11)}
        self.assertEqual(json.dumps(check(net(cells), "top"), sort_keys=True), json.dumps(check(net(cells), "top"), sort_keys=True))
        with tempfile.NamedTemporaryFile("w", suffix=".json") as f:
            json.dump(net(cells), f); f.flush()
            self.assertEqual(main(["check", f.name, "--top", "missing"]), 2)


if __name__ == "__main__":
    unittest.main()
