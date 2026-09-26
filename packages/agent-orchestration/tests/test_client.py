import json

import httpx

from agent_orchestration import SciforiumClient, SciforiumConfig
from contracts_py.agents import AgentOutput


def test_sciforium_client_uses_openai_compatible_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.sciforium.com/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-key"
        body = json.loads(request.content)
        assert body["model"] == "/deployments/test/model"
        assert body["temperature"] == 0.7
        assert body["messages"][0]["role"] == "system"
        assert body["messages"][1] == {"role": "user", "content": "Assess it"}
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "act_now_view": {"summary": "A risk exists."},
                                    "inaction_view": {"summary": "Pressure continues."},
                                    "confidence": 0.8,
                                }
                            )
                        }
                    }
                ]
            },
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = SciforiumClient(
        SciforiumConfig(
            api_key="test-key",
            model="/deployments/test/model",
            max_retries=0,
        ),
        http_client,
    )

    output = client.generate_structured(
        [{"role": "user", "content": "Assess it"}], AgentOutput
    )

    assert output.act_now_view.summary == "A risk exists."
    assert output.confidence == 0.8
