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
        self.assertNotIn("response_format", calls[0]["payload"])
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

    def test_retry_count_is_zero_when_first_attempt_succeeds(self):
        def transport(url, headers, payload, timeout):
            return {"choices": [{"message": {"content": "{}"}}]}

        backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            max_retries=2,
            transport=transport,
        )

        result = backend.run_batch([_request()])[0]

        self.assertEqual(result.metadata["retry_count"], 0)

    def test_retry_count_reflects_number_of_retries_taken(self):
        calls = []

        def transport(url, headers, payload, timeout):
            calls.append(1)
            if len(calls) < 3:
                raise OSError("transient failure")
            return {"choices": [{"message": {"content": "{}"}}]}

        backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            max_retries=3,
            transport=transport,
        )

        result = backend.run_batch([_request()])[0]

        self.assertEqual(len(calls), 3)
        self.assertEqual(result.metadata["retry_count"], 2)

    def test_extracts_json_from_markdown_fence_with_language_tag(self):
        calls = []

        def transport(url, headers, payload, timeout):
            calls.append(payload)
            return {"choices": [{"message": {"content": '```json\n{"current_goal": "ok"}\n```'}}]}

        backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            transport=transport,
        )

        result = backend.run_batch([_request()])[0]

        self.assertEqual(len(calls), 1)
        self.assertEqual(result.updated_state.current_goal, "ok")
        self.assertNotIn("model_output_invalid", result.metadata)
        self.assertEqual(result.metadata["json_repair_attempts"], 0)

    def test_extracts_json_with_leading_and_trailing_commentary(self):
        calls = []

        def transport(url, headers, payload, timeout):
            calls.append(payload)
            return {
                "choices": [
                    {
                        "message": {
                            "content": 'Sure, here you go:\n{"current_goal": "ok"}\nHope that helps!'
                        }
                    }
                ]
            }

        backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            transport=transport,
        )

        result = backend.run_batch([_request()])[0]

        self.assertEqual(len(calls), 1)
        self.assertEqual(result.updated_state.current_goal, "ok")
        self.assertNotIn("model_output_invalid", result.metadata)
        self.assertEqual(result.metadata["json_repair_attempts"], 0)

    def test_tolerates_trailing_comma(self):
        def transport(url, headers, payload, timeout):
            return {"choices": [{"message": {"content": '{"current_goal": "ok",}'}}]}

        backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            transport=transport,
        )

        result = backend.run_batch([_request()])[0]

        self.assertEqual(result.updated_state.current_goal, "ok")
        self.assertNotIn("model_output_invalid", result.metadata)

    def test_truncated_json_falls_back_to_policy_guard(self):
        def transport(url, headers, payload, timeout):
            return {"choices": [{"message": {"content": '{"outgoing_messages": ['}}]}

        backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            max_json_repair_attempts=0,
            transport=transport,
        )

        result = backend.run_batch([_request()])[0]

        self.assertTrue(result.metadata["model_output_invalid"])
        self.assertEqual(len(result.outgoing_messages), 1)
        self.assertEqual(result.outgoing_messages[0].message_type, MessageType.STATUS_REQUEST)
        self.assertEqual(len(result.environment_actions), 1)

    def test_reprompt_succeeds_on_second_attempt(self):
        calls = []

        def transport(url, headers, payload, timeout):
            calls.append(payload)
            if len(calls) == 1:
                return {"choices": [{"message": {"content": "not json"}}]}
            return {"choices": [{"message": {"content": "{}"}}]}

        backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            max_json_repair_attempts=1,
            transport=transport,
        )

        result = backend.run_batch([_request()])[0]

        self.assertEqual(len(calls), 2)
        second_messages = calls[1]["messages"]
        self.assertEqual(second_messages[-2]["role"], "assistant")
        self.assertEqual(second_messages[-2]["content"], "not json")
        self.assertIn("valid JSON", second_messages[-1]["content"])
        self.assertEqual(result.metadata["json_repair_attempts"], 1)
        self.assertNotIn("model_output_invalid", result.metadata)

    def test_reprompt_exhausted_falls_back_to_policy_guard(self):
        calls = []

        def transport(url, headers, payload, timeout):
            calls.append(payload)
            return {"choices": [{"message": {"content": "not json"}}]}

        backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            max_json_repair_attempts=1,
            transport=transport,
        )

        result = backend.run_batch([_request()])[0]

        self.assertEqual(len(calls), 2)
        self.assertEqual(result.metadata["json_repair_attempts"], 1)
        self.assertTrue(result.metadata["model_output_invalid"])
        self.assertEqual(len(result.outgoing_messages), 1)
        self.assertEqual(len(result.environment_actions), 1)

    def test_json_repair_attempts_zero_disables_reprompt(self):
        calls = []

        def transport(url, headers, payload, timeout):
            calls.append(payload)
            return {"choices": [{"message": {"content": "not json"}}]}

        backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            max_json_repair_attempts=0,
            transport=transport,
        )

        result = backend.run_batch([_request()])[0]

        self.assertEqual(len(calls), 1)
        self.assertTrue(result.metadata["model_output_invalid"])
        self.assertEqual(result.metadata["json_repair_attempts"], 0)

    def test_must_not_self_message_is_stripped_and_counted(self):
        def transport(url, headers, payload, timeout):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "outgoing_messages": [
                                        {
                                            "recipient_id": "agent_coordinator",
                                            "message_type": "status_request",
                                            "payload": {},
                                        }
                                    ]
                                }
                            )
                        }
                    }
                ]
            }

        backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            transport=transport,
        )

        result = backend.run_batch([_request()])[0]

        self.assertEqual(result.metadata["must_not_violations"], 1)
        # self-message stripped; guard fills the real required message instead
        self.assertEqual(len(result.outgoing_messages), 1)
        self.assertEqual(result.outgoing_messages[0].recipient_id, AgentId("agent_hospital"))

    def test_must_not_action_outside_allowed_set_for_supply_chain_supplier(self):
        def transport(url, headers, payload, timeout):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "environment_actions": [
                                        {"action_type": "adjust_transport_capacity", "payload": {}}
                                    ]
                                }
                            )
                        }
                    }
                ]
            }

        backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            transport=transport,
        )

        request = _role_request("supply_chain", "supplier", {"risk_level": "normal"})
        result = backend.run_batch([request])[0]

        self.assertEqual(result.metadata["must_not_violations"], 1)
        self.assertFalse(result.metadata["semantic_valid"])
        self.assertEqual(len(result.environment_actions), 0)

    def test_must_not_action_outside_allowed_set_for_storm_hospital(self):
        def transport(url, headers, payload, timeout):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {"environment_actions": [{"action_type": "adjust_inventory", "payload": {}}]}
                            )
                        }
                    }
                ]
            }

        backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            transport=transport,
        )

        request = _role_request("storm", "hospital", {"severity": 1})
        result = backend.run_batch([request])[0]

        self.assertEqual(result.metadata["must_not_violations"], 1)
        self.assertFalse(result.metadata["semantic_valid"])
        self.assertEqual(len(result.environment_actions), 0)

    def test_autonomy_rate_is_one_when_model_fully_autonomous(self):
        def transport(url, headers, payload, timeout):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "outgoing_messages": [
                                        {
                                            "recipient_id": "agent_hospital",
                                            "message_type": "status_request",
                                            "payload": {"severity": 4},
                                        }
                                    ],
                                    "environment_actions": [
                                        {"action_type": "update_summary", "payload": {"summary": "ok"}}
                                    ],
                                }
                            )
                        }
                    }
                ]
            }

        backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            transport=transport,
        )

        result = backend.run_batch([_request()])[0]

        self.assertEqual(result.metadata["policy_guard_added_messages"], 0)
        self.assertEqual(result.metadata["policy_guard_added_actions"], 0)
        self.assertEqual(result.metadata["autonomy_rate"], 1.0)

    def test_autonomy_rate_is_zero_on_invalid_json(self):
        def transport(url, headers, payload, timeout):
            return {"choices": [{"message": {"content": "not json"}}]}

        backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            max_json_repair_attempts=0,
            transport=transport,
        )

        result = backend.run_batch([_request()])[0]

        self.assertEqual(result.metadata["autonomy_rate"], 0.0)

    def test_autonomy_rate_is_partial_when_model_supplies_some_required_outputs(self):
        def transport(url, headers, payload, timeout):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "outgoing_messages": [
                                        {
                                            "recipient_id": "agent_hospital",
                                            "message_type": "status_request",
                                            "payload": {"severity": 4},
                                        }
                                    ]
                                }
                            )
                        }
                    }
                ]
            }

        backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            transport=transport,
        )

        result = backend.run_batch([_request()])[0]

        # model supplied the message but not the required update_summary action
        self.assertEqual(result.metadata["policy_guard_added_messages"], 0)
        self.assertEqual(result.metadata["policy_guard_added_actions"], 1)
        self.assertEqual(result.metadata["autonomy_rate"], 0.5)

    def test_validation_result_and_receipt_match_flat_metadata_for_autonomous_proposal(self):
        def transport(url, headers, payload, timeout):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "outgoing_messages": [
                                        {
                                            "recipient_id": "agent_hospital",
                                            "message_type": "status_request",
                                            "payload": {"severity": 4},
                                        }
                                    ],
                                    "environment_actions": [
                                        {"action_type": "update_summary", "payload": {"summary": "ok"}}
                                    ],
                                }
                            )
                        }
                    }
                ]
            }

        backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            transport=transport,
        )

        result = backend.run_batch([_request()])[0]

        vr = result.metadata["validation_result"]
        self.assertEqual(vr["semantic_valid"], result.metadata["semantic_valid"])
        self.assertEqual(vr["autonomy_rate"], result.metadata["autonomy_rate"])
        self.assertEqual(vr["useful_step"], result.metadata["useful_step"])
        self.assertEqual(vr["violation_reasons"], [])
        self.assertFalse(vr["model_output_invalid"])

    def test_validation_result_counts_must_not_violation_but_final_reasons_are_clean(self):
        def transport(url, headers, payload, timeout):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "outgoing_messages": [
                                        {
                                            "recipient_id": "agent_coordinator",
                                            "message_type": "status_request",
                                            "payload": {},
                                        }
                                    ]
                                }
                            )
                        }
                    }
                ]
            }

        backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            transport=transport,
        )

        result = backend.run_batch([_request()])[0]

        vr = result.metadata["validation_result"]
        # the violation was caught and stripped by the guard, so the count reflects
        # it but the FINAL reasons list is clean -- that's what "useful_step" reports.
        self.assertEqual(vr["must_not_violations"], 1)
        self.assertEqual(vr["violation_reasons"], [])
        self.assertTrue(vr["useful_step"])

    def test_execution_receipt_fields_and_honest_unknowns(self):
        def transport(url, headers, payload, timeout):
            return {"choices": [{"message": {"content": "{}"}}]}

        backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            transport=transport,
        )
        request = _request()

        result = backend.run_batch([request])[0]

        receipt = result.metadata["execution_receipt"]
        self.assertEqual(receipt["activation_id"], request.activation.activation_id)
        self.assertEqual(receipt["attempt_number"], 0)
        self.assertEqual(receipt["provider"], "aitta")
        self.assertEqual(receipt["model"], "demo/model")
        self.assertEqual(receipt["commit_status"], "proposed")
        # unmeasurable fields must stay None, never a fake placeholder
        self.assertIsNone(receipt["state_version_read"])
        self.assertIsNone(receipt["commit_version_written"])
        self.assertIsNone(receipt["request_hash"])
        self.assertIsNone(receipt["dispatch_seconds"])
        self.assertIsNone(receipt["accelerator"])

    def test_proposal_raw_content_matches_transport_response(self):
        raw = '{"current_goal": "coordinate"}'

        def transport(url, headers, payload, timeout):
            return {"choices": [{"message": {"content": raw}}]}

        backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            transport=transport,
        )

        result = backend.run_batch([_request()])[0]

        self.assertEqual(result.proposal.raw_content, raw)
        self.assertTrue(result.proposal.is_valid)
        self.assertEqual(result.proposal.current_goal, "coordinate")

    def test_bounded_violation_drops_out_of_range_delta(self):
        def transport(url, headers, payload, timeout):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "environment_actions": [
                                        {
                                            "action_type": "adjust_inventory",
                                            "payload": {"region": "helsinki", "delta": 50000},
                                        }
                                    ]
                                }
                            )
                        }
                    }
                ]
            }

        backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            transport=transport,
        )

        request = _role_request("supply_chain", "supplier", {"risk_level": "normal"})
        result = backend.run_batch([request])[0]

        self.assertEqual(result.metadata["bounded_violations"], 1)
        self.assertFalse(any(a.action_type == "adjust_inventory" for a in result.environment_actions))
        # a cleanly-stripped violation leaves the final result clean, same precedent as must_not
        self.assertTrue(result.metadata["useful_step"])

    def test_cardinality_violation_dedupes_duplicate_action(self):
        def transport(url, headers, payload, timeout):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "environment_actions": [
                                        {
                                            "action_type": "adjust_inventory",
                                            "payload": {"region": "helsinki", "delta": 10},
                                        },
                                        {
                                            "action_type": "adjust_inventory",
                                            "payload": {"region": "helsinki", "delta": 10},
                                        },
                                    ]
                                }
                            )
                        }
                    }
                ]
            }

        backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            transport=transport,
        )

        request = _role_request("supply_chain", "supplier", {"risk_level": "normal"})
        result = backend.run_batch([request])[0]

        self.assertEqual(result.metadata["cardinality_violations"], 1)
        self.assertEqual(
            sum(1 for a in result.environment_actions if a.action_type == "adjust_inventory"), 1
        )
        self.assertTrue(result.metadata["useful_step"])

    def test_cardinality_violation_dedupes_duplicate_message(self):
        def transport(url, headers, payload, timeout):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "outgoing_messages": [
                                        {
                                            "recipient_id": "agent_coordinator",
                                            "message_type": "status_update",
                                            "payload": {},
                                        },
                                        {
                                            "recipient_id": "agent_coordinator",
                                            "message_type": "status_update",
                                            "payload": {},
                                        },
                                    ]
                                }
                            )
                        }
                    }
                ]
            }

        backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            transport=transport,
        )

        request = _role_request("storm", "hospital", {"severity": 1})
        result = backend.run_batch([request])[0]

        self.assertEqual(result.metadata["cardinality_violations"], 1)
        self.assertEqual(len(result.outgoing_messages), 1)
        self.assertTrue(result.metadata["useful_step"])

    def test_state_mutation_violation_protects_system_managed_keys(self):
        def transport(url, headers, payload, timeout):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({"working_memory": {"last_event_type": "evil"}})
                        }
                    }
                ]
            }

        backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            transport=transport,
        )
        request = _request()

        result = backend.run_batch([request])[0]

        self.assertEqual(
            result.updated_state.working_memory["last_event_type"],
            request.triggering_event.event_type.value,
        )
        self.assertEqual(result.metadata["state_mutation_violations"], 1)
        self.assertEqual(
            result.metadata["validation_result"]["state_mutation_provenance"]["last_event_type"],
            "system",
        )
        self.assertFalse(result.metadata["useful_step"])

    def test_new_contract_violations_are_zero_for_clean_proposal(self):
        def transport(url, headers, payload, timeout):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "outgoing_messages": [
                                        {
                                            "recipient_id": "agent_hospital",
                                            "message_type": "status_request",
                                            "payload": {"severity": 4},
                                        }
                                    ],
                                    "environment_actions": [
                                        {"action_type": "update_summary", "payload": {"summary": "ok"}}
                                    ],
                                }
                            )
                        }
                    }
                ]
            }

        backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            transport=transport,
        )

        result = backend.run_batch([_request()])[0]

        self.assertEqual(result.metadata["bounded_violations"], 0)
        self.assertEqual(result.metadata["cardinality_violations"], 0)
        self.assertEqual(result.metadata["state_mutation_violations"], 0)
        self.assertTrue(result.metadata["useful_step"])

    def test_request_prompt_contains_agent_and_role_policy(self):
        """Prompt includes agent context and role_policy; response_shape is omitted to save tokens."""
        captured = []

        def transport(url, headers, payload, timeout):
            captured.append(payload)
            return {"choices": [{"message": {"content": "{}"}}]}

        backend = AittaExecutionBackend(
            api_key="secret",
            base_url="https://aitta.example/openai/v1/",
            model_name="demo/model",
            transport=transport,
        )
        backend.run_batch([_request()])

        user_content = json.loads(captured[0]["messages"][1]["content"])
        # response_shape was removed to reduce prompt size for small-context models
        self.assertNotIn("response_shape", user_content)
        # role and environment are present
        self.assertEqual(user_content["agent"]["role"], "coordinator")
        self.assertEqual(user_content["environment"]["scenario"], "storm")
        # operator appears in example_operator_ids
        requirements = user_content["role_policy"]["requirements"]
        self.assertTrue(
            any("agent_hospital" in req.get("example_operator_ids", []) for req in requirements),
            "example_operator_ids should reference agent_hospital",
        )


def _role_request(scenario: str, role: str, variables: dict) -> ExecutionRequest:
    now = utc_now()
    agent_id = AgentId(f"agent_{role}")
    event = Event.create(
        EventType.ENVIRONMENT_UPDATE,
        source="environment",
        target_scope={"roles": [role]},
        payload={"coordinator_id": "agent_coordinator"},
        priority=2,
    )
    return ExecutionRequest(
        activation=Activation.create(
            agent_id=agent_id,
            trigger_event_id=event.event_id,
            activation_reason=event.event_type.value,
            priority=event.priority,
            ready_at=now,
        ),
        agent_profile=AgentProfile(
            agent_id=agent_id,
            role=role,
            name=role.title(),
            region="helsinki",
        ),
        agent_state=AgentState(agent_id=agent_id),
        inbox_messages=[],
        triggering_event=event,
        environment=EnvironmentState(
            scenario=scenario,
            tick=1,
            updated_at=now,
            variables=variables,
        ),
    )


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
