import copy
import unittest

from qd_cdc import check
from test_qd_cdc import ff, net


def reset_ff(d, q, clk, kind="PN0"):
    cell = ff(d, q, clk)
    cell["type"] = "$_DFF_" + kind + "_"
    cell["connections"]["R"] = [20]
    cell["port_directions"]["R"] = "input"
    return cell


class AsyncResetTest(unittest.TestCase):
    def test_all_eight_mappings_trace_data_but_leave_reset_unknown(self):
        for clock in "PN":
            for polarity in "PN":
                for value in "01":
                    with self.subTest(clock=clock, polarity=polarity, value=value):
                        cells = {"src": ff(1, 2, 10),
                                 "dst": reset_ff(2, 3, 11, clock+polarity+value)}
                        rows = check(net(cells), "top")
                        crossing = next(r for r in rows if r["classification"] == "CROSSING")
                        self.assertEqual(crossing["path"], ["src.Q"])
                        self.assertEqual(crossing["destination_reset"], {
                            "bit": "20", "active_level": int(polarity == "P"),
                            "value": int(value), "clock_edge": "posedge" if clock == "P" else "negedge"})
                        unknown = [r for r in rows if r["classification"] == "UNKNOWN"]
                        self.assertEqual(len(unknown), 1)
                        self.assertIn("reset assertion/deassertion relationship unverified", unknown[0]["path"])

    def test_same_clock_and_primary_input_still_expose_reset(self):
        cells = {"first": reset_ff(1, 2, 10), "second": reset_ff(2, 3, 10)}
        rows = check(net(cells), "top")
        self.assertEqual([r["classification"] for r in rows], ["UNKNOWN", "UNKNOWN"])
        self.assertEqual({r["destination_cell"] for r in rows}, set(cells))

    def test_source_reset_and_candidate_are_not_waivers(self):
        cells = {"src": reset_ff(1, 2, 10), "first": reset_ff(2, 3, 11),
                 "second": reset_ff(3, 4, 11)}
        for name in ("first", "second"):
            cells[name]["attributes"]["async_reg"] = "1"
        rows = check(net(cells), "top")
        candidate = next(r for r in rows if r["classification"] == "CANDIDATE_SYNCHRONIZER")
        self.assertEqual(candidate["source_reset"]["bit"], "20")
        self.assertEqual(sum(r["classification"] == "UNKNOWN" for r in rows), 3)

    def test_malformed_reset_ports_never_get_semantics(self):
        for mutation in ("missing", "wide", "direction", "extra", "bit", "container", "null_d", "null_q", "null_r"):
            cells = {"src": ff(1, 2, 10), "dst": reset_ff(2, 3, 11)}
            design = net(cells)
            cell = cells["dst"]
            if mutation == "missing": del cell["connections"]["R"]
            if mutation == "wide": cell["connections"]["R"] = [20, 21]
            if mutation == "direction": cell["port_directions"]["R"] = "output"
            if mutation == "extra": cell["connections"]["E"] = [22]
            if mutation == "bit": cell["connections"]["R"] = [None]
            if mutation == "container": cell["connections"]["R"] = "0"
            if mutation.startswith("null_"): cell["connections"][mutation[-1].upper()] = None
            rows = check(design, "top")
            self.assertTrue(rows)
            self.assertTrue(all(r["classification"] == "UNKNOWN" for r in rows))
            self.assertTrue(all("destination_reset" not in r for r in rows))

    def test_candidate_requires_matching_edge_and_reset(self):
        for kind in ("NN0", "PP0", "PN1"):
            cells = {"src": ff(1, 2, 10), "first": reset_ff(2, 3, 11),
                     "second": reset_ff(3, 4, 11, kind)}
            for name in ("first", "second"):
                cells[name]["attributes"]["async_reg"] = "1"
            rows = check(net(cells), "top")
            self.assertNotIn("CANDIDATE_SYNCHRONIZER", [r["classification"] for r in rows])
            self.assertIn("CROSSING", [r["classification"] for r in rows])

    def test_constant_reset_and_generated_clock_stay_unknown(self):
        cells = {"dst": reset_ff(1, 2, 11),
                 "gate": {"type": "$_BUF_", "connections": {"A": [10], "Y": [11]},
                          "port_directions": {"A": "input", "Y": "output"}}}
        design = net(cells)
        cells["dst"]["connections"]["R"] = ["0"]
        rows = check(design, "top")
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r["classification"] == "UNKNOWN" for r in rows))
        self.assertTrue(all(r["destination_reset"]["bit"] == "0" for r in rows))

    def test_order_and_unrecognized_reset_family(self):
        cells = {"z": reset_ff(1, 2, 10), "a": reset_ff(2, 3, 11)}
        self.assertEqual(check(net(cells), "top"), check(net(dict(reversed(list(cells.items())))), "top"))
        other = copy.deepcopy(cells)
        other["a"]["type"] = "$_DFFE_PN0P_"
        self.assertTrue(any(r["classification"] == "UNKNOWN" and
                            "unsupported cell $_DFFE_PN0P_" in r["path"]
                            for r in check(net(other), "top")))
