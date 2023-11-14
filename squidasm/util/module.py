import importlib.util

def import_module_from_file_path(
    module_name: str,
    module_path: str
):
    spec = importlib.util.spec_from_file_location(module_name, module_path)

    assert spec is not None, f'`spec` is None, unable to import `{module_name}` from `{module_path}`'
    module = importlib.util.module_from_spec(spec)

    assert spec.loader is not None, f'`spec.loader` is None, unable to import `{module_name}` from `{module_path}`'
    spec.loader.exec_module(module)

    return module
