import json
import unittest

from agentic_sim.execution import SelfHostedExecutionBackend, check_self_hosted_connection
from agentic_sim.models import (
    Activation,
    AgentId,
    AgentProfile,
    AgentState,
    EnvironmentState,
    Event,
    EventType,
    ExecutionRequest,
    PlatformManifest,
)
from agentic_sim.utils.time import utc_now


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


def _valid_transport(calls=None):
    def transport(url, headers, payload, timeout):
        if calls is not None:
            calls.append({"url": url, "headers": headers, "payload": payload})
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
                                "environment_actions": [],
                                "metadata": {"policy": "self-hosted-test"},
                            }
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }

    return transport


class SelfHostedBackendConstructionTests(unittest.TestCase):
    def test_constructs_without_an_api_key(self):
        backend = SelfHostedExecutionBackend(
            base_url="http://localhost:8000/v1", model_name="demo/model"
        )

        self.assertEqual(backend.api_key, "")
        self.assertEqual(backend.name, "self_hosted")

    def test_requires_base_url_and_model_name(self):
        with self.assertRaises(ValueError):
            SelfHostedExecutionBackend(model_name="demo/model")
        with self.assertRaises(ValueError):
            SelfHostedExecutionBackend(base_url="http://localhost:8000/v1")

    def test_capabilities_reflect_configured_prefix_caching_and_context_tokens(self):
        backend = SelfHostedExecutionBackend(
            base_url="http://localhost:8000/v1",
            model_name="demo/model",
            enable_prefix_caching=True,
            max_context_tokens=8192,
        )

        self.assertTrue(backend.capabilities.supports_prefix_caching)
        self.assertEqual(backend.capabilities.max_context_tokens, 8192)

    def test_no_auth_header_sent_when_api_key_is_empty(self):
        calls = []
        backend = SelfHostedExecutionBackend(
            base_url="http://localhost:8000/v1",
            model_name="demo/model",
            transport=_valid_transport(calls),
        )

        backend.run_batch([_request()])

        self.assertNotIn("Authorization", calls[0]["headers"])

    def test_auth_header_sent_when_api_key_is_configured(self):
        calls = []
        backend = SelfHostedExecutionBackend(
            base_url="http://localhost:8000/v1",
            model_name="demo/model",
            api_key="secret",
            transport=_valid_transport(calls),
        )

        backend.run_batch([_request()])

        self.assertEqual(calls[0]["headers"]["Authorization"], "Bearer secret")


class SelfHostedBackendPlatformManifestTests(unittest.TestCase):
    def test_no_manifest_configured_leaves_receipt_fields_none(self):
        backend = SelfHostedExecutionBackend(
            base_url="http://localhost:8000/v1",
            model_name="demo/model",
            transport=_valid_transport(),
        )

        result = backend.run_batch([_request()])[0]

        receipt = result.metadata["execution_receipt"]
        self.assertIsNone(receipt["accelerator"])
        self.assertIsNone(receipt["host_architecture"])
        self.assertIsNone(receipt["serving_runtime"])
        self.assertIsNone(receipt["manifest_mode"])
        self.assertNotIn("platform_manifest", result.metadata)

    def test_configured_manifest_flows_onto_receipt_and_metadata(self):
        manifest = PlatformManifest.for_lumi(
            "self_hosted",
            driver_version="ROCm 6.2",
            serving_runtime_version="0.6.3",
            placement_level="single_device",
            manifest_mode="common_denominator",
        )
        backend = SelfHostedExecutionBackend(
            base_url="http://localhost:8000/v1",
            model_name="demo/model",
            transport=_valid_transport(),
            platform_manifest=manifest,
        )

        result = backend.run_batch([_request()])[0]

        receipt = result.metadata["execution_receipt"]
        self.assertEqual(receipt["accelerator"], manifest.accelerator)
        self.assertEqual(receipt["host_architecture"], manifest.host_architecture)
        self.assertEqual(receipt["serving_runtime"], manifest.serving_runtime)
        self.assertEqual(receipt["manifest_mode"], "common_denominator")
        self.assertEqual(result.metadata["platform_manifest"]["manifest_mode"], "common_denominator")


class SelfHostedBackendEndToEndTests(unittest.TestCase):
    def test_full_request_response_pipeline_via_fake_transport(self):
        backend = SelfHostedExecutionBackend(
            base_url="http://localhost:8000/v1",
            model_name="demo/model",
            transport=_valid_transport(),
        )

        result = backend.run_batch([_request()])[0]

        self.assertEqual(result.updated_state.current_goal, "coordinate status")
        self.assertEqual(result.outgoing_messages[0].recipient_id, AgentId("agent_hospital"))
        self.assertEqual(result.metadata["backend"], "self_hosted")


class CheckSelfHostedConnectionTests(unittest.TestCase):
    def test_posts_minimal_json_probe(self):
        calls = []

        def transport(url, headers, payload, timeout):
            calls.append({"url": url, "payload": payload})
            return {
                "choices": [{"message": {"content": json.dumps({"ok": True})}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
            }

        result = check_self_hosted_connection(
            base_url="http://localhost:8000/v1",
            model_name="demo/model",
            timeout_seconds=30,
            transport=transport,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["model"], "demo/model")
        self.assertEqual(calls[0]["url"], "http://localhost:8000/v1/chat/completions")


if __name__ == "__main__":
    unittest.main()
