"""Protect the stream boundaries and local import graph without importing the app."""
import ast
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'backend'


def modules():
    return {
        '.'.join(path.relative_to(ROOT).with_suffix('').parts).removesuffix('.__init__'):path
        for path in BACKEND.rglob('*.py')
        if not path.name.startswith('test_') and 'tests' not in path.parts
    }


def dependencies(name, path):
    package = name if path.name == '__init__.py' else name.rpartition('.')[0]
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            target = ('.'*node.level) + (node.module or '')
            target = importlib.util.resolve_name(target, package) if node.level else target
            yield target
            yield from (target + '.' + alias.name for alias in node.names)


def test_streams_do_not_depend_on_http_and_storage_stays_independent():
    for name,path in modules().items():
        imports = list(dependencies(name,path))
        if name.startswith('backend.streams.'):
            assert not any(dep.startswith('backend.api') for dep in imports), name
        if name.startswith('backend.db'):
            assert not any(dep.startswith(('backend.api','backend.streams','backend.integrations')) for dep in imports), name


def test_every_stream_has_one_explicit_current_entrypoint():
    streams = ['A_calendar','B_memory','C_discovery','D_connectors',
               'E_orchestrator','F_booking','G_proactive','H_conversation']
    for stream in streams:
        assert (BACKEND / 'streams' / stream / 'service.py').is_file(), stream
    assert not list((BACKEND / 'domain').glob('*.py')), 'Do not recreate a parallel business layer.'


def test_local_python_dependency_graph_has_no_cycles():
    known = modules()
    graph = {name:{dep for dep in dependencies(name,path) if dep in known and dep != name}
             for name,path in known.items()}
    finished = set()

    def visit(name, stack):
        assert name not in stack, 'Circular dependency: ' + ' → '.join([*stack, name])
        if name in finished:
            return
        for dependency in sorted(graph[name]):
            visit(dependency, [*stack, name])
        finished.add(name)

    for name in sorted(graph):
        visit(name, [])
