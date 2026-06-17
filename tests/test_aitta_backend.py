import json
import unittest

from agentic_sim.execution import AittaExecutionBackend, check_aitta_connection
from agentic_sim.models import (
    Activation,
    AgentId,
    AgentProfile,
    AgentState,
    EnvironmentState,
    Event,
    EventType,
    ExecutionRequest,
    MessageType,
)
from agentic_sim.utils.time import utc_now


class AittaBackendTests(unittest.TestCase):
    def test_check_aitta_connection_posts_minimal_json_probe(self):
        calls = []

        def transport(url, headers, payload, timeout):
            calls.append({"url": url, "payload": payload})
            return {
                "choices": [{"message": {"content": json.dumps({"ok": True})}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
            }

        result = check_aitta_connection(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            timeout_seconds=30,
            transport=transport,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["model"], "demo/model")
        self.assertEqual(result["usage"]["total_tokens"], 7)
        self.assertEqual(calls[0]["url"], "https://aitta.example/openai/v1/chat/completions")
        self.assertEqual(calls[0]["payload"]["response_format"], {"type": "json_object"})

    def test_backend_posts_openai_compatible_chat_completion(self):
        calls = []

        def transport(url, headers, payload, timeout):
            calls.append(
                {
                    "url": url,
                    "headers": headers,
                    "payload": payload,
                    "timeout": timeout,
                }
            )
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "current_goal": "coordinate status",
                                    "working_memory": {"decision": "ask operator"},
                                    "outgoing_messages": [
                                        {
                                            "recipient_id": "agent_hospital",
                                            "message_type": "status_request",
                                            "priority": 3,
                                            "payload": {"severity": 4},
                                        }
                                    ],
                                    "environment_actions": [
                                        {
                                            "action_type": "update_summary",
                                            "payload": {"summary": "model reviewed severity"},
                                        }
                                    ],
                                    "metadata": {"policy": "aitta-test"},
                                }
                            )
                        }
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            }

        backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            timeout_seconds=30,
            transport=transport,
        )

        result = backend.run_batch([_request()])[0]

        self.assertEqual(calls[0]["url"], "https://aitta.example/openai/v1/chat/completions")
        self.assertEqual(calls[0]["headers"]["Authorization"], "Bearer secret")
        self.assertEqual(calls[0]["payload"]["model"], "demo/model")
        self.assertEqual(calls[0]["payload"]["response_format"], {"type": "json_object"})
        prompt = json.loads(calls[0]["payload"]["messages"][1]["content"])
        self.assertEqual(prompt["role_policy"]["role"], "coordinator")
        self.assertEqual(prompt["role_policy"]["requirements"][0]["message_type"], "status_request")
        self.assertEqual(calls[0]["timeout"], 30)
        self.assertEqual(result.updated_state.current_goal, "coordinate status")
        self.assertEqual(result.updated_state.working_memory["decision"], "ask operator")
        self.assertEqual(result.outgoing_messages[0].recipient_id, AgentId("agent_hospital"))
        self.assertEqual(result.outgoing_messages[0].message_type, MessageType.STATUS_REQUEST)
        self.assertEqual(result.environment_actions[0].action_type, "update_summary")
        self.assertEqual(result.metadata["model"], "demo/model")
        self.assertEqual(result.metadata["usage"]["completion_tokens"], 20)

    def test_policy_guard_fills_required_outputs_when_model_is_passive(self):
        def transport(url, headers, payload, timeout):
            return {"choices": [{"message": {"content": "{}"}}]}

        backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            transport=transport,
        )

        result = backend.run_batch([_request()])[0]

        self.assertEqual(len(result.outgoing_messages), 1)
        self.assertEqual(result.outgoing_messages[0].recipient_id, AgentId("agent_hospital"))
        self.assertEqual(result.outgoing_messages[0].message_type, MessageType.STATUS_REQUEST)
        self.assertEqual(result.outgoing_messages[0].payload["severity"], 4)
        self.assertEqual(len(result.environment_actions), 1)
        self.assertEqual(result.environment_actions[0].action_type, "update_summary")
        self.assertEqual(result.metadata["policy_guard_added_messages"], 1)
        self.assertEqual(result.metadata["policy_guard_added_actions"], 1)

    def test_backend_ignores_invalid_model_json_and_uses_policy_guard(self):
        def transport(url, headers, payload, timeout):
            return {"choices": [{"message": {"content": "not json"}}]}

        backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            transport=transport,
        )

        result = backend.run_batch([_request()])[0]

        self.assertTrue(result.metadata["model_output_invalid"])
        self.assertEqual(len(result.outgoing_messages), 1)
        self.assertEqual(result.outgoing_messages[0].message_type, MessageType.STATUS_REQUEST)


def _request() -> ExecutionRequest:
    now = utc_now()
    event = Event.create(
        EventType.ENVIRONMENT_UPDATE,
        source="environment",
        target_scope={"roles": ["coordinator"]},
        payload={"operator_ids": ["agent_hospital"]},
        priority=3,
    )
    return ExecutionRequest(
        activation=Activation.create(
            agent_id=AgentId("agent_coordinator"),
            trigger_event_id=event.event_id,
            activation_reason=event.event_type.value,
            priority=event.priority,
            ready_at=now,
        ),
        agent_profile=AgentProfile(
            agent_id=AgentId("agent_coordinator"),
            role="coordinator",
            name="Coordinator",
            region="national",
        ),
        agent_state=AgentState(agent_id=AgentId("agent_coordinator")),
        inbox_messages=[],
        triggering_event=event,
        environment=EnvironmentState(
            scenario="storm",
            tick=1,
            updated_at=now,
            variables={"severity": 4},
        ),
    )
