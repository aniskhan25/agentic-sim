import ast
import unittest
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "agentic_sim"

DOMAIN_PACKAGES = ["models", "utils"]

FORBIDDEN_PREFIXES = (
    "agentic_sim.execution",
    "agentic_sim.state",
    "agentic_sim.engine",
    "agentic_sim.observability",
    "agentic_sim.scenarios",
    "agentic_sim.scheduling",
    "agentic_sim.environment",
    "agentic_sim.messaging",
    "agentic_sim.cli",
    "agentic_sim.config",
    "agentic_sim.sweep",
)


def _imported_module_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


class DependencyBoundaryTests(unittest.TestCase):
    def test_domain_packages_do_not_import_outer_layers(self):
        """Domain code (models/, utils/) must depend on nothing else
        (target_architecture.md's dependency rule). Scans every .py file on
        disk under each domain package, not a hardcoded list, so a new file
        added later is automatically covered."""
        violations = []
        for package in DOMAIN_PACKAGES:
            package_dir = SRC_ROOT / package
            for path in sorted(package_dir.glob("*.py")):
                for module_name in _imported_module_names(path):
                    if module_name.startswith(FORBIDDEN_PREFIXES):
                        violations.append(f"{path.relative_to(SRC_ROOT)} imports {module_name}")
        self.assertEqual(violations, [], "\n".join(violations))

    def test_forbidden_prefix_matching_actually_catches_a_violation(self):
        """Regression guard on the matching logic itself: prove a genuine
        violation would be caught, not just that nothing violates today."""
        violating_source = "from agentic_sim.execution import AittaExecutionBackend\n"
        tree = ast.parse(violating_source)
        module_name = next(
            node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        )
        self.assertTrue(module_name.startswith(FORBIDDEN_PREFIXES))
