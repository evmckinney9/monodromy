"""
monodromy/xx_decompose/paths.py

Routines for producing right-angled paths through the Weyl alcove.  Consider a
set of native interactions with an associated minimal covering set of minimum-
cost circuit polytopes, as well as a target coordinate.  The coverage set
associates to the target coordinate a circuit type C = (O1 ... On) consisting of
a sequence of native interactions Oj.  A _path_ is a sequence (I P1 ... Pn) of
intermediate Weyl points, where Pj is accessible from P(j-1) by Oj.  A path is
said to be _right-angled_ when at each step one coordinate is fixed (up to
possible Weyl reflection) when expressed in canonical coordinates.

Conjecturally, a right-angled path can be realized by local gates whose tensor
components are of the form

    (quarter rotations) * (a IZ + b ZI) * (quarter rotations),

which we assume in `circuits.py`.

NOTE: The routines in this file can fail for numerical reasons, and so they are
      lightly randomized and meant to be repeatedly called.
"""

from collections import Counter
from operator import itemgetter
from typing import List

from ..backend.backend_abc import NoFeasibleSolutions
from .circuits import NoBacksolution
from ..io.base import ConvexPolytopeData, PolytopeData, CircuitPolytopeData
from .scipy import polyhedron_has_element, manual_get_random_vertex


def single_unordered_decomposition_hop(
        target, working_operations, scipy_coverage_set
):
    """
    Produces a single inverse step in a right-angled path.  The target of the
    step is `target`, expressed in monodromy coordinates, and which belongs to
    to the circuit type consisting of XX-type operations enumerated in
    `working_operations`.  The step is taken along one such operation in
    `working_operations`, and the source of the step belongs

    Returns a dictionary keyed on "hop", "ancestor", and "operations_remaining",
    which respectively are: a triple (source, operation, target) describing the
    single step; the source coordinate of the step; and the remaining set of
    operations yet to be stripped off.
    """
    backsolution_polytope = PolytopeData(convex_subpolytopes=[])
    for ancestor in scipy_coverage_set:
        # check that this is actually an ancestor
        if Counter(ancestor.operations) != Counter(working_operations):
            continue

        # impose the target constraints, which sit on "b"
        # (really on "c", but "b" has already been projected off)
        backsolution_polytope.convex_subpolytopes += [
            ConvexPolytopeData(
                inequalities=[
                    [ineq[0] + sum(x * y for x, y in zip(ineq[4:], target)),
                     ineq[1], ineq[2], ineq[3]]
                    for ineq in cp.inequalities
                ],
                equalities=[
                    [eq[0] + sum(x * y for x, y in zip(eq[4:], target)),
                     eq[1], eq[2], eq[3]]
                    for eq in cp.equalities
                ],
            )
            for cp in ancestor.convex_subpolytopes
        ]

        # walk over the convex backsolution subpolytopes, try to find one
        # that's solvable
        try:
            solution = manual_get_random_vertex(backsolution_polytope)

            return {
                "hop": (solution, ancestor.operations[-1], target),
                "ancestor": solution,
                "operations_remaining": ancestor.operations[:-1]
            }
        except NoFeasibleSolutions:
            pass

    raise NoBacksolution()


def scipy_unordered_decomposition_hops(
        coverage_set: List[CircuitPolytopeData],
        scipy_coverage_set: List[CircuitPolytopeData],
        target: List  # raw target tuple
):
    """
    Fixing a `coverage_set` and a `scipy_coverage_set`, finds a minimal
    decomposition for a canonical interaction in `target_polytope` into a
    sequence of operations linking the polytopes in the coverage sets, together
    with specific intermediate canonical points linked by them.

    Returns a list of tuples of shape (source vertex, operation, target vertex),
    so that each target vertex is accessible from its source vertex by
    application of the operation, each target vertex matches its next source
    vertex, the original source vertex corresponds to the identity, and the
    last target lies in `target_polytope`.

    NOTE: `scipy_coverage_set` is extracted from `coverage_set` using
          `calculate_scipy_coverage_set` above.

    NOTE: Operates with the assumption that gates within the circuit
          decomposition may be freely permuted.
    """
    decomposition = []  # retval
    working_polytope = None

    # NOTE: In practice, this computation has already been done.
    best_cost = float("inf")
    for polytope in coverage_set:
        if polytope.cost < best_cost and polyhedron_has_element(polytope, target):
            working_polytope = polytope
            best_cost = polytope.cost

    if working_polytope is None:
        raise ValueError(f"{target} not contained in coverage set.")

    operations_remaining = working_polytope.operations

    # if this polytope corresponds to the empty operation, we're done.
    while 0 < len(operations_remaining):
        target, operations_remaining, hop = \
            itemgetter("ancestor", "operations_remaining", "hop")(
                single_unordered_decomposition_hop(
                    target, operations_remaining, scipy_coverage_set
                )
            )
        # a/k/a decomposition.push
        decomposition.insert(0, hop)

    return decomposition
