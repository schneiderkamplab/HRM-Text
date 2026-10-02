"""CPU-owned second-pilot references; no I/O, execution, or global randomness.

Each public function takes a nonnegative family-local slot and a caller-owned
random.Random-compatible RNG. Normalize interleaved math/code slots before
calling: slot % len(TYPE_NAMES) selects the type, while rng selects parameters.
All returns are fresh JSON-serializable dictionaries. Only the fixed code
strings here, never teacher-generated code, are intended for reference tests.
"""
from fractions import Fraction
import json


MATH_TYPES = (
    "arithmetic", "percentage", "discount", "rectangle_area", "triangle_area",
    "fraction_add", "linear_equation", "equal_groups", "remaining_count",
    "unit_conversion", "mean", "ratio_share",
)
CODE_TYPES = (
    "sum_divisible", "sorted_unique_above", "affine", "count_negative", "clamp",
    "prefix_sums", "absolute_differences", "weighted_sum", "range_span", "stable_unique",
)
TOOL_DOMAINS = ("library", "appointment", "parcel", "event", "stock")


def _kind(slot, kinds):
    if type(slot) is not int or slot < 0:
        raise ValueError("slot must be a nonnegative integer")
    return kinds[slot % len(kinds)]


def math_reference(slot, rng):
    """Return type, parameters, exact evaluable expression, answer (int/str), requirement.

    Fraction answers use reduced a/b strings (or an integer string); no floats
    or approximations enter the reference. Expressions use arithmetic only.
    """
    kind = _kind(slot, MATH_TYPES)
    a, b, c = rng.randint(2, 24), rng.randint(2, 12), rng.randint(1, 20)
    params = {"a": a, "b": b, "c": c}
    if kind == "arithmetic":
        expression, answer = f"{a} * {b} + {c}", a * b + c
        requirement = f"Compute {a} times {b}, then add {c}."
    elif kind == "percentage":
        total, percent = a * 100, b * 5
        params = {"total": total, "percent": percent}
        expression, answer = f"{total} * {percent} / 100", a * percent
        requirement = f"A fictional survey has {total} responses. Exactly {percent}% choose option A. How many choose A?"
    elif kind == "discount":
        price, percent = a * 100, b * 5
        params = {"price": price, "percent": percent}
        expression, answer = f"{price} * (100 - {percent}) / 100", a * (100 - percent)
        requirement = f"An item costs {price} credits before a {percent}% discount. What is its price after the discount, with no other charges?"
    elif kind == "rectangle_area":
        params = {"length": a, "width": b}
        expression, answer = f"{a} * {b}", a * b
        requirement = f"A rectangle is {a} cm long and {b} cm wide. Find its area in square centimetres."
    elif kind == "triangle_area":
        base = 2 * a
        params = {"base": base, "height": b}
        expression, answer = f"{base} * {b} / 2", a * b
        requirement = f"A triangle has base {base} cm and perpendicular height {b} cm. Find its area in square centimetres."
    elif kind == "fraction_add":
        n, d = rng.randint(1, 9), rng.randint(2, 10)
        params = {"numerator_1": a, "denominator_1": b, "numerator_2": n, "denominator_2": d}
        expression, answer = f"{a} / {b} + {n} / {d}", str(Fraction(a, b) + Fraction(n, d))
        requirement = f"Add the fractions {a}/{b} and {n}/{d}. Give an exact reduced fraction, or an integer if the denominator is 1; do not use decimals."
    elif kind == "linear_equation":
        solution = rng.randint(-15, 15)
        rhs = a * solution + c
        params = {"coefficient": a, "offset": c, "rhs": rhs}
        expression, answer = f"({rhs} - {c}) / {a}", solution
        requirement = f"Solve the equation {a} * x + {c} = {rhs} for x."
    elif kind == "equal_groups":
        params = {"groups": a, "per_group": b, "extra": c}
        expression, answer = f"{a} * {b} + {c}", a * b + c
        requirement = f"There are {a} boxes with {b} counters in each box and {c} loose counters. How many counters are there altogether?"
    elif kind == "remaining_count":
        initial, removed = a * b + c, c
        params = {"initial": initial, "removed": removed, "added": a}
        expression, answer = f"{initial} - {removed} + {a}", a * b + a
        requirement = f"A collection starts with {initial} counters. Remove {removed}, then add {a}. How many counters remain?"
    elif kind == "unit_conversion":
        params = {"hours": a, "minutes": c}
        expression, answer = f"{a} * 60 + {c}", a * 60 + c
        requirement = f"Convert {a} hours and {c} additional minutes to a total number of minutes. Use 60 minutes per hour."
    elif kind == "mean":
        values = [a, a + b, a + 2 * b]
        params = {"values": values}
        expression, answer = f"({values[0]} + {values[1]} + {values[2]}) / 3", a + b
        requirement = f"Find the arithmetic mean of the three numbers {values[0]}, {values[1]}, and {values[2]}."
    else:
        total = (a + b) * c
        params = {"first_parts": a, "second_parts": b, "total": total}
        expression, answer = f"{total} * {a} / ({a} + {b})", a * c
        requirement = f"Share {total} counters between two groups in the ratio {a}:{b}. How many counters does the first group receive?"
    return {"type": kind, "parameters": params, "expression": expression,
            "answer": answer, "requirement": requirement + " Return the exact numerical answer without units."}


def code_reference(slot, rng):
    """Return a fixed solve(values) implementation and [argument, expected] tests.

    Domain: finite lists of integers. No input mutation, imports, I/O, recursion
    or unbounded loops. Allowed builtins: sum, sorted, len, min, max, range,
    enumerate, abs. Requirements describe empty input and ordering explicitly.
    """
    kind = _kind(slot, CODE_TYPES)
    divisor, threshold = rng.randint(2, 9), rng.randint(-5, 5)
    factor, offset = rng.randint(2, 7), rng.randint(-8, 8)
    lower, upper = rng.randint(-10, -1), rng.randint(1, 10)
    params = {}
    if kind == "sum_divisible":
        params = {"divisor": divisor}
        body = f"return sum(x for x in values if x % {divisor} == 0)"
        requirement = f"Return the sum of all entries divisible by {divisor}, including negative multiples; return 0 for an empty list."
        tests = [[[], 0], [[-divisor, 0, divisor, 2 * divisor, 1], 2 * divisor], [[divisor, divisor], 2 * divisor]]
    elif kind == "sorted_unique_above":
        params = {"threshold": threshold}
        body = f"return sorted({{x for x in values if x > {threshold}}})"
        requirement = f"Return the distinct entries strictly greater than {threshold}, sorted in ascending order; return [] for empty input."
        tests = [[[], []], [[threshold, threshold + 2, threshold - 1, threshold + 1, threshold + 2], [threshold + 1, threshold + 2]], [[threshold], []]]
    elif kind == "affine":
        params = {"factor": factor, "offset": offset}
        body = f"return [x * {factor} + ({offset}) for x in values]"
        requirement = f"Return a new list applying x * {factor} + ({offset}) to every entry, preserving order and duplicates; return [] for empty input."
        tests = [[[], []], [[-1, 0, 2], [offset - factor, offset, 2 * factor + offset]], [[1, 1], [factor + offset, factor + offset]]]
    elif kind == "count_negative":
        body = "return sum(1 for x in values if x < 0)"
        requirement = "Return the number of strictly negative entries; zero is not negative, duplicates count separately, and empty input returns 0."
        tests = [[[], 0], [[-2, 0, 3, -2], 2], [[0, 1], 0]]
    elif kind == "clamp":
        params = {"lower": lower, "upper": upper}
        body = f"return [min({upper}, max({lower}, x)) for x in values]"
        requirement = f"Clamp each entry to the inclusive interval [{lower}, {upper}]. Preserve order and duplicates; return a new list, or [] for empty input."
        tests = [[[], []], [[lower - 1, lower, 0, upper, upper + 1], [lower, lower, 0, upper, upper]], [[upper + 2, lower - 2], [upper, lower]]]
    elif kind == "prefix_sums":
        body = "return [sum(values[:i + 1]) for i in range(len(values))]"
        requirement = "Return cumulative sums in input order: output index i is the sum from input index 0 through i inclusive. Return [] for empty input."
        tests = [[[], []], [[3, -5, 0, 4], [3, -2, -2, 2]], [[-2], [-2]]]
    elif kind == "absolute_differences":
        body = "return [abs(values[i] - values[i - 1]) for i in range(1, len(values))]"
        requirement = "Return absolute differences between consecutive entries in input order. For n entries there are max(n - 1, 0) differences; empty and singleton inputs return []."
        tests = [[[], []], [[7], []], [[-3, 2, 2, -4], [5, 0, 6]]]
    elif kind == "weighted_sum":
        body = "return sum((i + 1) * x for i, x in enumerate(values))"
        requirement = "Return the sum of each entry multiplied by its 1-based position in the original list; return 0 for empty input."
        tests = [[[], 0], [[3, -2, 4], 11], [[-5], -5], [[2, 2], 6]]
    elif kind == "range_span":
        body = "return max(values) - min(values) if values else 0"
        requirement = "Return the maximum entry minus the minimum entry. Return 0 for empty or singleton input."
        tests = [[[], 0], [[-5], 0], [[-8, -2, -5], 6], [[3, -4, 3], 7]]
    else:
        body = "return [x for i, x in enumerate(values) if x not in values[:i]]"
        requirement = "Remove duplicate entries, preserving the order of first occurrence rather than sorting. Return a new list, or [] for empty input."
        tests = [[[], []], [[3, -1, 3, 0, -1], [3, -1, 0]], [[2, 2, 2], [2]]]
    return {"type": kind, "parameters": params,
            "requirement": "Write a Python function solve(values) for a list of integers. " + requirement + " Do not modify the input list.",
            "code": "def solve(values):\n    " + body, "tests": tests}


def _tool(name, description, arguments):
    properties = {key: {"type": "integer", "minimum": 1} if type(value) is int
                  else {"type": "string", "minLength": 1} for key, value in arguments.items()}
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties,
                           "required": list(arguments), "additionalProperties": False}}}


def tool_scenario(slot, rng):
    """Return two mock OpenAI tool specs and a fully specified lookup/action path.

    missing_field names a required lookup-only argument. A clarification variant
    must obtain it before lookup; it is never an action parameter. Action IDs
    come from the lookup result. All data and success receipts are fictional.
    """
    domain = _kind(slot, TOOL_DOMAINS)
    tag, location, quantity = rng.randint(100, 999), rng.randint(1, 20), rng.randint(1, 4)
    if domain == "library":
        lookup_name, action_name, missing = "lookup_library_copy", "reserve_library_copy", "branch"
        arguments = {"book_id": f"book-{tag}", "branch": f"branch-{location}"}
        lookup_result = dict(arguments, available=True, copy_id=f"copy-{tag}")
        action_arguments = {"copy_id": lookup_result["copy_id"], "member_id": f"member-{tag}"}
        action_result = dict(action_arguments, reservation_id=f"reservation-{tag}", status="reserved")
        goal = "Find an available library copy and reserve it for the specified member."
    elif domain == "appointment":
        lookup_name, action_name, missing = "lookup_appointment_slot", "book_appointment_slot", "clinic"
        arguments = {"service": "routine_consultation", "date": f"2030-04-{rng.randint(1, 28):02d}", "clinic": f"clinic-{location}"}
        lookup_result = dict(arguments, available=True, slot_id=f"slot-{tag}", local_time="10:30")
        action_arguments = {"slot_id": lookup_result["slot_id"], "patient_id": f"patient-{tag}"}
        action_result = dict(action_arguments, booking_id=f"booking-{tag}", status="booked")
        goal = "Find an available appointment slot and book it for the specified fictional patient; give no medical advice."
    elif domain == "parcel":
        lookup_name, action_name, missing = "lookup_parcel", "redirect_parcel", "postcode"
        arguments = {"tracking_id": f"tracking-{tag}", "postcode": f"{10000 + tag}"}
        lookup_result = dict(arguments, parcel_id=f"parcel-{tag}", redirect_allowed=True, available_locker_id=f"locker-{location}")
        action_arguments = {"parcel_id": lookup_result["parcel_id"], "locker_id": lookup_result["available_locker_id"]}
        action_result = dict(action_arguments, confirmation_id=f"redirect-{tag}", status="redirected")
        goal = "Look up a parcel and redirect it to the available locker returned by the lookup."
    elif domain == "event":
        lookup_name, action_name, missing = "lookup_event_tickets", "reserve_event_tickets", "venue"
        arguments = {"event_id": f"event-{tag}", "venue": f"venue-{location}"}
        lookup_result = dict(arguments, ticket_type_id=f"ticket-type-{tag}", available=quantity + rng.randint(1, 10))
        action_arguments = {"ticket_type_id": lookup_result["ticket_type_id"], "quantity": quantity, "attendee_id": f"attendee-{tag}"}
        action_result = dict(action_arguments, reservation_id=f"tickets-{tag}", status="reserved")
        goal = "Check event ticket availability, then reserve the requested quantity for the specified attendee."
    else:
        lookup_name, action_name, missing = "lookup_stock", "reserve_stock", "warehouse"
        arguments = {"sku": f"item-{tag}", "warehouse": f"warehouse-{location}"}
        lookup_result = dict(arguments, stock_id=f"stock-{tag}", available=quantity + rng.randint(1, 20))
        action_arguments = {"stock_id": lookup_result["stock_id"], "quantity": quantity, "customer_id": f"customer-{tag}"}
        action_result = dict(action_arguments, reservation_id=f"stock-reservation-{tag}", status="reserved")
        goal = "Check stock availability, then reserve the requested quantity for the specified customer."
    requirement = (
        "This is a fictional mock scenario, not a real transaction or a claim about actual availability or policies. "
        + goal + f" First call {lookup_name} with arguments " + json.dumps(arguments, sort_keys=True)
        + "; the mock lookup returns " + json.dumps(lookup_result, sort_keys=True)
        + f". For an action-enabled path, then call {action_name} with arguments "
        + json.dumps(action_arguments, sort_keys=True) + "; the mock action returns "
        + json.dumps(action_result, sort_keys=True)
        + f". In a clarification variant, initially omit {missing} from the user's request, ask for it, "
        + "and use the explicit value " + json.dumps(arguments[missing]) + " from the user's clarification before lookup. "
        + f"The field {missing} is required only by the lookup, never by the action. "
        + "Do not claim action success before receiving its mock result; do not invent additional facts."
    )
    return {"domain": domain, "tools": [
                _tool(lookup_name, "Mock lookup only; does not perform a reservation, booking or redirection.", arguments),
                _tool(action_name, "Mock action using the identifier from a successful lookup; performs no real-world action.", action_arguments)],
            "lookup_name": lookup_name, "action_name": action_name, "arguments": arguments,
            "action_arguments": action_arguments, "lookup_result": lookup_result,
            "action_result": action_result, "missing_field": missing, "requirement": requirement}
