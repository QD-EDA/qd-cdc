// SPDX-License-Identifier: Apache-2.0
// QD integration harness. Application synchronizer is compiled unchanged.
module caliptra_clock_pilot #(parameter CLOCK_MODE=0) (
  input clk_a, clk_b, gate_en, rst_b, din, output dout
);
  reg source_q;
  wire launch_clock = CLOCK_MODE == 1 ? clk_a & gate_en : clk_a;
  wire capture_clock = CLOCK_MODE == 2 ? clk_a : clk_b;
  generate
    if (CLOCK_MODE == 2) begin : opposite
      always @(negedge launch_clock) source_q <= din;
    end else begin : positive
      always @(posedge launch_clock) source_q <= din;
    end
  endgenerate
  caliptra_2ff_sync #(.WIDTH(1), .RST_VAL(0)) sync (
    .clk(capture_clock), .rst_b(rst_b), .din(source_q), .dout(dout)
  );
endmodule
