import ast
import builtins
from fractions import Fraction
import json
import operator
import random

import pytest
from jsonschema import Draft202012Validator, ValidationError

from dfm12.multilingual_references import (
    CODE_TYPES, MATH_TYPES, TOOL_DOMAINS, code_reference, math_reference, tool_scenario,
)


SAFE_BUILTINS = {name: getattr(builtins, name) for name in
                 ("sum", "sorted", "len", "min", "max", "range", "enumerate", "abs")}


def exact_expression(node):
    if isinstance(node, ast.Expression):
        return exact_expression(node.body)
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return Fraction(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -exact_expression(node.operand)
    if isinstance(node, ast.BinOp):
        operation = {ast.Add: operator.add, ast.Sub: operator.sub,
                     ast.Mult: operator.mul, ast.Div: operator.truediv}[type(node.op)]
        return operation(exact_expression(node.left), exact_expression(node.right))
    raise AssertionError("Unexpected math expression")


@pytest.mark.parametrize("slot", range(len(MATH_TYPES)))
def test_math_exact_arithmetic_and_semantic_parameters(slot):
    for seed in range(50):
        row = math_reference(slot, random.Random(seed))
        p, kind = row["parameters"], row["type"]
        assert kind == MATH_TYPES[slot]
        assert type(row["answer"]) in (str, int)
        expected = exact_expression(ast.parse(row["expression"], mode="eval"))
        assert Fraction(row["answer"]) == expected
        if isinstance(row["answer"], str):
            assert row["answer"] == str(expected)
        if kind == "linear_equation":
            assert p["coefficient"] * expected + p["offset"] == p["rhs"]
        elif kind == "ratio_share":
            assert expected * (p["first_parts"] + p["second_parts"]) == p["total"] * p["first_parts"]
        elif kind == "mean":
            assert expected * len(p["values"]) == sum(p["values"])
        elif kind == "fraction_add":
            assert expected == Fraction(p["numerator_1"], p["denominator_1"]) + Fraction(p["numerator_2"], p["denominator_2"])
        for value in p.values():
            for scalar in value if isinstance(value, list) else [value]:
                assert str(scalar) in row["requirement"]
        assert "exact" in row["requirement"] and row["requirement"].isascii()


def code_oracle(kind, p, values):
    if kind == "sum_divisible":
        return sum(x for x in values if x % p["divisor"] == 0)
    if kind == "sorted_unique_above":
        return sorted(set(filter(lambda x: x > p["threshold"], values)))
    if kind == "affine":
        return [p["factor"] * x + p["offset"] for x in values]
    if kind == "count_negative":
        return len([x for x in values if x < 0])
    if kind == "clamp":
        return [p["lower"] if x < p["lower"] else p["upper"] if x > p["upper"] else x for x in values]
    if kind == "prefix_sums":
        result, total = [], 0
        for x in values:
            total += x
            result.append(total)
        return result
    if kind == "absolute_differences":
        return [abs(right - left) for left, right in zip(values, values[1:])]
    if kind == "weighted_sum":
        return sum(x * position for position, x in zip(range(1, len(values) + 1), values))
    if kind == "range_span":
        ordered = sorted(values)
        return ordered[-1] - ordered[0] if ordered else 0
    return list(dict.fromkeys(values))


@pytest.mark.parametrize("slot", range(len(CODE_TYPES)))
def test_fixed_code_is_safe_and_matches_oracle(slot):
    for seed in range(20):
        reference = code_reference(slot, random.Random(seed))
        tree = ast.parse(reference["code"])
        assert len(tree.body) == 1 and isinstance(tree.body[0], ast.FunctionDef)
        assert tree.body[0].name == "solve"
        assert [arg.arg for arg in tree.body[0].args.args] == ["values"]
        assert not any(isinstance(node, (ast.Import, ast.ImportFrom, ast.Attribute, ast.While,
                                         ast.Global, ast.Nonlocal)) for node in ast.walk(tree))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                assert isinstance(node.func, ast.Name) and node.func.id in SAFE_BUILTINS
        namespace = {"__builtins__": SAFE_BUILTINS}
        exec(compile(tree, "<fixed-reference>", "exec"), namespace)
        tests = reference["tests"]
        assert all(type(pair) is list and len(pair) == 2 for pair in tests)
        assert any(argument == [] for argument, _ in tests)
        rng = random.Random(seed + 1000)
        arguments = [argument for argument, _ in tests] + [[rng.randint(-20, 20) for _ in range(n)] for n in range(25)]
        for argument in arguments:
            before = argument[:]
            assert namespace["solve"](argument) == code_oracle(reference["type"], reference["parameters"], argument)
            assert argument == before
        for argument, expected in tests:
            assert namespace["solve"](argument) == expected
        assert reference["requirement"].isascii() and "solve(values)" in reference["requirement"]
        for value in reference["parameters"].values():
            assert str(value) in reference["requirement"]


@pytest.mark.parametrize("slot", range(len(TOOL_DOMAINS)))
def test_tool_specs_clarification_and_action_consistency(slot):
    for seed in range(25):
        scenario = tool_scenario(slot, random.Random(seed))
        assert scenario["domain"] == TOOL_DOMAINS[slot]
        tools = scenario["tools"]
        assert len(tools) == 2 and all(t["type"] == "function" for t in tools)
        assert [t["function"]["name"] for t in tools] == [scenario["lookup_name"], scenario["action_name"]]
        assert scenario["lookup_name"] != scenario["action_name"]
        lookup, action = [t["function"]["parameters"] for t in tools]
        for schema, argument in ((lookup, scenario["arguments"]), (action, scenario["action_arguments"])):
            Draft202012Validator.check_schema(schema)
            Draft202012Validator(schema).validate(argument)
            assert set(schema["required"]) == set(argument)
            assert schema["additionalProperties"] is False
            with pytest.raises(ValidationError):
                Draft202012Validator(schema).validate(dict(argument, unexpected="value"))
        missing = scenario["missing_field"]
        assert missing in lookup["required"] and missing not in action["properties"]
        incomplete = {k: v for k, v in scenario["arguments"].items() if k != missing}
        with pytest.raises(ValidationError):
            Draft202012Validator(lookup).validate(incomplete)
        for key, value in scenario["arguments"].items():
            assert scenario["lookup_result"][key] == value
        for key, value in scenario["action_arguments"].items():
            assert scenario["action_result"][key] == value
        identifier = {"library": "copy_id", "appointment": "slot_id", "parcel": "parcel_id",
                      "event": "ticket_type_id", "stock": "stock_id"}[scenario["domain"]]
        assert scenario["lookup_result"][identifier] == scenario["action_arguments"][identifier]
        if scenario["domain"] in ("stock", "event"):
            assert 0 < scenario["action_arguments"]["quantity"] <= scenario["lookup_result"]["available"]
        if scenario["domain"] == "parcel":
            assert scenario["lookup_result"]["redirect_allowed"] is True
            assert scenario["action_arguments"]["locker_id"] == scenario["lookup_result"]["available_locker_id"]
        assert "fictional mock" in scenario["requirement"] and scenario["requirement"].isascii()
        for field in ("arguments", "action_arguments", "lookup_result", "action_result"):
            assert json.dumps(scenario[field], sort_keys=True) in scenario["requirement"]


@pytest.mark.parametrize("factory,kinds", [(math_reference, MATH_TYPES), (code_reference, CODE_TYPES), (tool_scenario, TOOL_DOMAINS)])
def test_reproducible_fresh_json_outputs_and_no_global_rng(factory, kinds):
    before = random.getstate()
    for slot in range(len(kinds) * 2):
        first = factory(slot, random.Random(44))
        second = factory(slot, random.Random(44))
        assert first == second == json.loads(json.dumps(first))
        first["requirement"] = "mutated"
        assert factory(slot, random.Random(44)) == second
    assert random.getstate() == before


@pytest.mark.parametrize("factory", [math_reference, code_reference, tool_scenario])
@pytest.mark.parametrize("slot", [-1, True, 1.5, "1", None])
def test_invalid_slots_fail_before_rng_use(factory, slot):
    with pytest.raises(ValueError, match="nonnegative integer"):
        factory(slot, None)


def test_diversity_minimums():
    assert len(MATH_TYPES) == len(set(MATH_TYPES)) >= 10
    assert len(CODE_TYPES) == len(set(CODE_TYPES)) >= 8
    assert set(TOOL_DOMAINS) == {"library", "appointment", "parcel", "event", "stock"}
    assert len({code_reference(i, random.Random(0))["code"] for i in range(len(CODE_TYPES))}) == len(CODE_TYPES)
    assert len({tool_scenario(i, random.Random(0))["lookup_name"] for i in range(len(TOOL_DOMAINS))}) == 5
