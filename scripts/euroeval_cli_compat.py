"""Normalize redundant selectors for API-only EuroEval launchers."""


def dataset_only_selectors(argv):
    if not any(arg == '--dataset' or arg.startswith('--dataset=') for arg in argv):
        return list(argv)
    result = []
    skip = False
    for arg in argv:
        if skip:
            skip = False
            continue
        if arg == '--language':
            skip = True
        elif not arg.startswith('--language='):
            result.append(arg)
    return result
