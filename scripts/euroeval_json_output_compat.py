"""Preserve valid non-object JSON answers in EuroEval's LiteLLM adapter."""
import ast
import inspect
import textwrap


def install_json_output_guard(model_class):
    original = model_class._create_model_output
    if getattr(original, '_hrm_json_guard', False):
        return False
    tree = ast.parse(textwrap.dedent(inspect.getsource(original)))
    function = tree.body[0]
    function.decorator_list = []

    class Guard(ast.NodeTransformer):
        count = 0

        def visit_Assert(self, node):
            if ast.unparse(node.test) != 'isinstance(generation_dct, dict)':
                return node
            self.count += 1
            # The surrounding handler already preserves non-JSON text. Send
            # non-object JSON down that same path, without altering the answer.
            replacement = ast.parse('''if not isinstance(generation_dct, dict):
    raise json.JSONDecodeError("Not a classification object", generation_output, 0)
''').body[0]
            return ast.copy_location(replacement, node)

    guard = Guard()
    tree = guard.visit(tree)
    if not guard.count:
        return False
    if guard.count != 1:
        raise RuntimeError('Unexpected EuroEval JSON parser; refusing ambiguous patch')
    namespace = original.__globals__.copy()
    exec(compile(ast.fix_missing_locations(tree), inspect.getfile(original), 'exec'), namespace)
    patched = namespace[original.__name__]
    patched._hrm_json_guard = True
    model_class._create_model_output = staticmethod(patched)
    return True
