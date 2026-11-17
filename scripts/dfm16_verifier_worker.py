"""One verification request in PID/network namespaces with Landlock file isolation."""
import ast
import contextlib
import ctypes
import io
import json
import os
import platform
import re
import resource
import sys


def confine():
    """Fail closed; allow library reads and writes only in the private scratch dir."""
    libc = ctypes.CDLL(None, use_errno=True)
    if platform.machine() not in ('x86_64', 'aarch64'):
        raise RuntimeError('Unsupported syscall ABI')
    abi = libc.syscall(444, 0, 0, 1)
    if abi < 3:
        raise RuntimeError('Landlock ABI >= 3 required')
    mask = (1 << 15)-1  # Through TRUNCATE; supported by ABI 3 and later.
    class Ruleset(ctypes.Structure):
        _fields_ = [('handled_access_fs', ctypes.c_uint64)]
    class PathRule(ctypes.Structure):
        _pack_ = 1
        _fields_ = [('allowed_access', ctypes.c_uint64), ('parent_fd', ctypes.c_int32)]
    ruleset = Ruleset(mask)
    fd = libc.syscall(444, ctypes.byref(ruleset), ctypes.sizeof(ruleset), 0)
    if fd < 0:
        raise OSError(ctypes.get_errno(), 'landlock_create_ruleset')
    try:
        readonly = (1 << 0) | (1 << 2) | (1 << 3)
        for path in json.loads(os.environ['DFM_VERIFIER_READ_PATHS']) + [os.getcwd()]:
            if not os.path.exists(path):
                continue
            access = mask if path == os.getcwd() else readonly
            if not os.path.isdir(path):
                access &= ~(1 << 3)
            pfd = os.open(path, os.O_PATH | os.O_CLOEXEC)
            try:
                rule = PathRule(access, pfd)
                if libc.syscall(445, fd, 1, ctypes.byref(rule), 0):
                    raise OSError(ctypes.get_errno(), 'landlock_add_rule')
            finally:
                os.close(pfd)
        if libc.prctl(38, 1, 0, 0, 0) or libc.syscall(446, fd, 0):
            raise OSError(ctypes.get_errno(), 'landlock_restrict_self')
    finally:
        os.close(fd)


def verify(payload):
    kind, text, spec = payload['kind'], payload['text'], payload['spec']
    if kind == 'synlogic':
        sys.path.insert(0, os.environ['DFM_VERIFIER_ROOT']+'/SynLogic')
        from base.data import Data
        from task2verifier import verifier_classes
        result = verifier_classes[spec['task']]().verify(Data.from_json_dict(spec['game']), text)
        return bool(result == 1)
    if kind == 'math':
        from math_verify import parse, verify as math_verify
        expected = parse('\\boxed{'+str(spec['answer'])+'}')
        return bool(expected and math_verify(expected, parse(text)))
    if kind == 'ifeval':
        sys.path.insert(0, os.environ['DFM_VERIFIER_ROOT']+'/open-instruct')
        from open_instruct.IFEvalG.instructions_registry import INSTRUCTION_DICT
        for group in spec['constraints']:
            if len(group['instruction_id']) != len(group['kwargs']) or not group['instruction_id']:
                raise ValueError('invalid_constraint_group')
            for name, kwargs in zip(group['instruction_id'], group['kwargs']):
                check = INSTRUCTION_DICT[name](name)
                check.build_description(**{k:v for k,v in (kwargs or {}).items() if v is not None})
                if not check.check_following(text):
                    return False
        return bool(spec['constraints'] and text.strip())
    if kind == 'code':
        blocks = re.findall(r'```(?:python|py)\s*\n(.*?)```', text, re.S)
        code = '\n\n'.join(blocks) if blocks else text
        ast.parse(code)
        tests = spec['tests']
        if not tests or not all(isinstance(t, str) and t.lstrip().startswith('assert ') for t in tests):
            raise ValueError('invalid_tests')
        namespace = {'__name__': '__main__'}
        exec(compile(code, '<candidate>', 'exec'), namespace)
        for test in tests:
            tree = ast.parse(test)
            if not tree.body or not all(isinstance(node, ast.Assert) for node in tree.body):
                raise ValueError('non_assert_test')
            exec(compile(tree, '<test>', 'exec'), namespace)
        return True
    raise ValueError('unknown_verifier')


if __name__ == '__main__':
    confine()
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    resource.setrlimit(resource.RLIMIT_AS, (4*1024**3, 4*1024**3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (8*1024**2, 8*1024**2))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
    payload = json.load(sys.stdin)
    try:
        # Imported upstream registries print diagnostics; keep the protocol separate.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            passed = verify(payload)
        result = dict(passed=passed)
    except AssertionError:
        result = dict(passed=False)
    except Exception as exc:
        result = dict(passed=False, error=type(exc).__name__+': '+str(exc)[:300])
    print(json.dumps(result))
