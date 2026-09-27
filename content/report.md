# Technical report

This report is assembled, not written. Each section opens with a few sentences of connecting prose and then carries the solver's own documents, copied verbatim at build time from the pinned commit named above. Every measured figure below sits inside one of those included passages, next to the file that produced it.

## 1 Architecture

SANKHYA is one library with one entry point. A model is read, presolved and scaled, dispatched by its problem class to an engine, postsolved, and then checked by a program that shares no code with the solver.

The passages below describe the shape of the code, the boundaries between its modules, how a solve flows from file to answer, and what every engine is promised by the layer that calls it.

{{include docs/ARCHITECTURE.md section "1. The shape in one paragraph"}}

{{include docs/ARCHITECTURE.md section "2. Modules and their boundaries"}}

{{include docs/ARCHITECTURE.md section "4. How a solve flows"}}

{{include docs/ARCHITECTURE.md section "13. The engine layer"}}

## 2 LP engines

Linear programs have four engines: the dual simplex, the primal simplex, an interior point method and a restarted first-order method. The simplex engines produce a basis, which is what warm starts and branch and bound need; the other two reach large models the simplex cannot.

The coverage table names each algorithm the problem statement asks for with the code that implements it, and the first-order section gives that engine's own record.

{{include docs/PS26119_COVERAGE.md section "Algorithms the PS names"}}

{{include docs/BENCHMARKS.md section "1e. The first-order engine"}}

## 3 MILP engine

Mixed-integer models are solved by branch and cut over the warm-started dual simplex. The passages below cover how the search learns from infeasible nodes and how the tree is spread over several workers.

{{include docs/ARCHITECTURE.md section "11. Conflict analysis"}}

{{include docs/ARCHITECTURE.md section "12. Parallel tree search"}}

## 4 QP engines

Convex quadratic programs have two engines, a first-order splitting method and a proximal interior point. Convexity is decided before any arithmetic, and a Hessian that cannot be proved convex is refused rather than solved to a local point.

The two standard convex QP sets follow, each with the engine that ran it and what the independent verifier said.

{{include docs/BENCHMARKS.md section "2b. Maros-Meszaros"}}

{{include docs/BENCHMARKS.md section "2d. QPLIB"}}

## 5 GPU acceleration

The first-order engine has a CUDA port. The CPU build needs no CUDA at all, and a GPU request on a machine without a usable device falls back to the CPU with a warning.

Where the GPU wins and where it loses is a measurement, not a claim, and the plan written before any card existed says what the hardware may and may not be used to claim.

{{include docs/BENCHMARKS.md section "1g. GPU PDHG crossover"}}

{{include docs/GPU_PLAN.md section "5. What the hardware lets us claim"}}

## 6 Numerical stability

A wrong answer from numerical code looks exactly like a right one. The solver rests on two invariants, stated below, and the robustness sweep pushes each numerical hazard until the answer or the certificate moves.

{{include docs/ARCHITECTURE.md section "3. The two invariants"}}

{{include docs/BENCHMARKS.md section "5. Robustness"}}

## 7 Independent verification

Every answer is re-derived by a separate program that reads only the model file and the solution file. An infeasible verdict carries a certificate the same program checks, and the provenance claim is checked by what the binary actually links against.

{{include docs/BENCHMARKS.md section "3. Correctness beyond the objective value"}}

{{include docs/PROVENANCE.md section "4. Machine-checkable evidence"}}

## 8 Benchmark method

Every benchmark run writes a file with the instance, its hash, the published value, the gap, the status, the time, the commit and the machine. The benchmarks document is generated from those files, so it cannot drift from them.

The passages below give that method, what reproducibility is and is not promised, and what the numbers do not say.

{{include docs/BENCHMARKS.md lead}}

{{include docs/ARCHITECTURE.md section "7. Reproducibility"}}

{{include docs/BENCHMARKS.md section "6. What these numbers do not say"}}

## 9 Results

The headline results follow as the benchmarks document states them: the full Netlib set and the next rung up, the large LPs, scale, the mixed-integer set, nonlinear programs, and the comparison with HiGHS.

The complete tables, every instance named, are on the benchmarks page.

{{include docs/BENCHMARKS.md section "1c. The full set"}}

{{include docs/BENCHMARKS.md section "1c.1 The Kennington set"}}

{{include docs/BENCHMARKS.md section "1d. Beyond Netlib"}}

{{include docs/BENCHMARKS.md section "1f. Scale"}}

{{include docs/BENCHMARKS.md section "2. MIPLIB"}}

{{include docs/BENCHMARKS.md section "2e. Nonlinear programs"}}

{{include docs/BENCHMARKS.md section "4. Comparison against an established solver"}}

## 10 Limitations

What the solver does not do, and what was built and then demoted or withdrawn, is carried here in full.

{{include docs/NEGATIVE-RESULTS.md}}

{{include README.md section "What this does NOT do"}}

## 11 Future work

Only work that exists as an open issue in the tracker is listed. No dates are given and no result is promised.

- Numerical hardening
  - [#590](https://github.com/thegoodengineers/SANKHYA/issues/590) QP answers labelled optimal that the independent verifier rejects
  - [#559](https://github.com/thegoodengineers/SANKHYA/issues/559) exporting the Farkas ray where infeasibility is found today without one
  - [#518](https://github.com/thegoodengineers/SANKHYA/issues/518) a checkable proof of optimality for every MILP answer
  - [#519](https://github.com/thegoodengineers/SANKHYA/issues/519) a rigorous LP bound from any approximate dual
  - [#484](https://github.com/thegoodengineers/SANKHYA/issues/484) detecting infeasible and unbounded LPs from the PDHG iterates
- A faster MILP tree and QP engines
  - [#498](https://github.com/thegoodengineers/SANKHYA/issues/498) c-MIR cuts with variable-bound substitution
  - [#511](https://github.com/thegoodengineers/SANKHYA/issues/511) coefficient tightening on integer rows
  - [#512](https://github.com/thegoodengineers/SANKHYA/issues/512) binary probing with a clique table
  - [#503](https://github.com/thegoodengineers/SANKHYA/issues/503) conflict analysis from LPs that exceed the cutoff
  - [#501](https://github.com/thegoodengineers/SANKHYA/issues/501) no model copy and no refactorization from scratch at every node
  - [#490](https://github.com/thegoodengineers/SANKHYA/issues/490) the proximal interior point for QP
  - [#494](https://github.com/thegoodengineers/SANKHYA/issues/494) the QP interior point as the MIQP node solver
- GPU runs at scale, with a full benchmark report
  - [#478](https://github.com/thegoodengineers/SANKHYA/issues/478) keeping the PDHG iteration loop on the device
  - [#520](https://github.com/thegoodengineers/SANKHYA/issues/520) bounding many branch-and-bound nodes in one batched PDHG
  - [#504](https://github.com/thegoodengineers/SANKHYA/issues/504) MIPLIB with permutation seeds and shifted geometric means
- An industrial pilot on refinery models
  - [#516](https://github.com/thegoodengineers/SANKHYA/issues/516) the standard pooling instances with published global optima
  - [#524](https://github.com/thegoodengineers/SANKHYA/issues/524) warm-started re-solve after model edits, for rolling-horizon planning
  - [#525](https://github.com/thegoodengineers/SANKHYA/issues/525) decomposition by Benders or Dantzig-Wolfe
  - [#527](https://github.com/thegoodengineers/SANKHYA/issues/527) a solution report in the planner's terms
  - [#528](https://github.com/thegoodengineers/SANKHYA/issues/528) convex MINLP by outer approximation
