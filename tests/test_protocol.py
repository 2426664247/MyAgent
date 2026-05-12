import unittest

from agent_v2.protocol import AgentStep, ToolCallResult


class ToolCallResultTests(unittest.TestCase):
    def test_creation(self) -> None:
        tcr = ToolCallResult(
            tool_call_id="call_001",
            name="read_file",
            arguments={"file_path": "a.txt"},
            result="hello",
            success=True,
        )
        self.assertEqual(tcr.name, "read_file")
        self.assertTrue(tcr.success)


class AgentStepTests(unittest.TestCase):
    def test_default_state(self) -> None:
        step = AgentStep(step_number=1)
        self.assertFalse(step.has_tool_calls)
        self.assertFalse(step.is_final)
        self.assertIsNone(step.thought)
        self.assertIsNone(step.final_answer)

    def test_with_tool_calls(self) -> None:
        step = AgentStep(
            step_number=2,
            tool_calls=[
                ToolCallResult("c1", "list_files", {}, "tree", True),
            ],
        )
        self.assertTrue(step.has_tool_calls)
        self.assertFalse(step.is_final)

    def test_with_final_answer(self) -> None:
        step = AgentStep(step_number=3, final_answer="Done.")
        self.assertTrue(step.is_final)
        self.assertFalse(step.has_tool_calls)


if __name__ == "__main__":
    unittest.main()
