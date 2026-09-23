// SPDX-License-Identifier: Apache-2.0
// Execute against Yosys simcells.v; use explicit reset edges, not startup ordering.
module reset_cell_oracle; reg c=0; reg [7:0] r=8'h33; reg [7:0] d=8'h55; wire [7:0] q;
\$_DFF_NN0_ ff0 (.D(d[0]), .C(c), .R(r[0]), .Q(q[0]));
\$_DFF_NN1_ ff1 (.D(d[1]), .C(c), .R(r[1]), .Q(q[1]));
\$_DFF_NP0_ ff2 (.D(d[2]), .C(c), .R(r[2]), .Q(q[2]));
\$_DFF_NP1_ ff3 (.D(d[3]), .C(c), .R(r[3]), .Q(q[3]));
\$_DFF_PN0_ ff4 (.D(d[4]), .C(c), .R(r[4]), .Q(q[4]));
\$_DFF_PN1_ ff5 (.D(d[5]), .C(c), .R(r[5]), .Q(q[5]));
\$_DFF_PP0_ ff6 (.D(d[6]), .C(c), .R(r[6]), .Q(q[6]));
\$_DFF_PP1_ ff7 (.D(d[7]), .C(c), .R(r[7]), .Q(q[7]));
initial begin
 #1; r=8'hcc; #1; if(q !== 8'haa) $fatal(1,"initial reset semantics");
 r=8'h33;
 #1; c=1;
 #1; if(q !== 8'h5a) $fatal(1,"positive edge semantics");
 c=0;
 #1; if(q !== 8'h55) $fatal(1,"negative edge semantics");
 r=8'hcc;
 #1; if(q !== 8'haa) $fatal(1,"asynchronous reset semantics");
 $display("PASS: eight Yosys reset cell truth tables and clock edges"); $finish;
end
endmodule
