import unittest

from agent_v2.registry import ToolEntry, _build_json_schema, _parse_param_docs, tool, clear_registry, get_registry, get_tools_payload


class SchemaTests(unittest.TestCase):
    def test_basic_schema(self) -> None:
        def greet(name: str, count: int = 1) -> str:
            """打招呼。

            :param name: 用户名字
            :param count: 次数
            """
            return ""

        schema = _build_json_schema(greet)
        self.assertEqual(schema["type"], "object")
        self.assertIn("name", schema["properties"])
        self.assertIn("count", schema["properties"])
        self.assertEqual(schema["properties"]["name"]["type"], "string")
        self.assertEqual(schema["properties"]["count"]["type"], "integer")
        self.assertEqual(schema["properties"]["count"]["default"], 1)
        self.assertIn("name", schema["required"])
        self.assertNotIn("count", schema["required"])

    def test_skip_sandbox_param(self) -> None:
        def do_thing(sandbox: object, path: str) -> str:
            return ""

        schema = _build_json_schema(do_thing)
        self.assertNotIn("sandbox", schema["properties"])
        self.assertIn("path", schema["properties"])

    def test_parse_param_docs(self) -> None:
        def fn(a: str, b: int) -> str:
            """Doc.

            :param a: first arg
            :param b: second arg
            """
            return ""

        docs = _parse_param_docs(fn)
        self.assertEqual(docs["a"], "first arg")
        self.assertEqual(docs["b"], "second arg")


class RegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_registry()

    def tearDown(self) -> None:
        clear_registry()

    def test_decorator_registers(self) -> None:
        @tool(name="my_tool", confirm=False)
        def my_tool(x: str) -> str:
            """A test tool."""
            return x

        registry = get_registry()
        self.assertIn("my_tool", registry)
        self.assertEqual(registry["my_tool"].description, "A test tool.")

    def test_tools_payload_format(self) -> None:
        @tool()
        def hello(name: str) -> str:
            """Say hello."""
            return f"hi {name}"

        payload = get_tools_payload()
        self.assertEqual(len(payload), 1)
        item = payload[0]
        self.assertEqual(item["type"], "function")
        self.assertEqual(item["function"]["name"], "hello")
        self.assertIn("parameters", item["function"])

    def test_confirm_flag(self) -> None:
        @tool(confirm=True)
        def danger(cmd: str) -> str:
            """Run something dangerous."""
            return "done"

        registry = get_registry()
        self.assertTrue(registry["danger"].confirm)


if __name__ == "__main__":
    unittest.main()
