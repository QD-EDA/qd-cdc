// SPDX-License-Identifier: Apache-2.0
// QD harness only; compile the pinned Caliptra implementation separately.
module caliptra_sync_pilot(input clk_a, clk_b, rst_b, din, output dout);
  reg source_q;
  always @(posedge clk_a) source_q <= din;
  caliptra_2ff_sync #(.WIDTH(1), .RST_VAL(0)) sync (
    .clk(clk_b), .rst_b(rst_b), .din(source_q), .dout(dout)
  );
endmodule
