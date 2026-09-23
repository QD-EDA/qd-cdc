// SPDX-License-Identifier: Apache-2.0
// QD negative fixture: two unrelated flops illegally drive the same data net.
module multiple_drivers(input clk_a, clk_b, clk_c, a, c, output result);
  reg qa, qc;
  wire shared_data;
  (* async_reg = 1 *) reg first, second;
  always @(posedge clk_a) qa <= a;
  always @(posedge clk_c) qc <= c;
  assign shared_data = qa;
  assign shared_data = qc;
  always @(posedge clk_b) begin first <= shared_data; second <= first; end
  assign result = second;
endmodule
