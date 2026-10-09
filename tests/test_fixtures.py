import ast
import unittest
from pathlib import Path


class FixtureTests(unittest.TestCase):
    def test_fixture_exports_interfaces_before_announcing_names(self):
        tree = ast.parse((Path(__file__).parent / "tray-fixture.py").read_text())
        main = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "main")
        exports, names = [], []
        for index, node in enumerate(main.body):
            if not isinstance(node, ast.Expr):
                continue
            call = node.value.value if isinstance(node.value, ast.Await) else node.value
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute):
                if call.func.attr == "export":
                    exports.append(index)
                if call.func.attr == "request_name":
                    names.append(index)
        self.assertEqual(len(exports), 3)
        self.assertEqual(len(names), 2)
        self.assertLess(max(exports), min(names))
