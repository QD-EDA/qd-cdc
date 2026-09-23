module crossing(input wire clk_a, clk_b, input wire d, output reg q);
  reg source;
  always @(posedge clk_a) source <= d;
  always @(posedge clk_b) q <= source;
endmodule
