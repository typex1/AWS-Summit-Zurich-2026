"""Step 4 — The demo: a Strands agent that pays for x402-protected content.

The AgentCorePaymentsPlugin intercepts HTTP 402 Payment Required responses,
signs the payment via AgentCore Payments (within the session budget), and
retries the request with the payment proof — all inside the agent loop.

Run: python 04_payment_agent.py ["custom prompt"]
"""

import os
import sys

import config

# Strands' BedrockModel picks up credentials from the environment —
# make sure it uses the same profile/region as the rest of the demo.
os.environ.setdefault("AWS_PROFILE", config.AWS_PROFILE)
os.environ.setdefault("AWS_REGION", config.REGION)

from strands import Agent  # noqa: E402
from strands.models import BedrockModel  # noqa: E402
from strands_tools import http_request  # noqa: E402
from bedrock_agentcore.payments.integrations.config import (  # noqa: E402
    AgentCorePaymentsPluginConfig,
)
from bedrock_agentcore.payments.integrations.strands.plugin import (  # noqa: E402
    AgentCorePaymentsPlugin,
)

MODEL_ID = os.environ.get("DEMO_MODEL_ID", "global.anthropic.claude-sonnet-4-6")

SYSTEM_PROMPT = (
    "You are a research assistant that can access paid APIs on behalf of the "
    "user. When an endpoint requires payment (HTTP 402), the payment is "
    "handled automatically within your configured budget. Summarize what you "
    "retrieved and always report how much was paid."
)

DEFAULT_PROMPT = (
    f"Fetch the premium content at {config.X402_TEST_ENDPOINT} and summarize it. "
    "If payment is required, proceed — it is within budget."
)


def main():
    state = config.load_state()
    required = ("payment_manager_arn", "payment_instrument_id", "payment_session_id")
    missing = [k for k in required if not state.get(k)]
    if missing:
        sys.exit(f"Missing state {missing} — run scripts 01–03 first.")

    plugin = AgentCorePaymentsPlugin(
        config=AgentCorePaymentsPluginConfig(
            payment_manager_arn=state["payment_manager_arn"],
            user_id=config.USER_ID,
            payment_instrument_id=state["payment_instrument_id"],
            payment_session_id=state["payment_session_id"],
            region=config.REGION,
        )
    )

    agent = Agent(
        model=BedrockModel(model_id=MODEL_ID, streaming=True),
        system_prompt=SYSTEM_PROMPT,
        tools=[http_request],
        plugins=[plugin],
    )

    prompt = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PROMPT
    print(f"Prompt: {prompt}\n{'-' * 60}")
    agent(prompt)

    # Show the guardrail bookkeeping after the run
    dp = config.data_client()
    session = dp.get_payment_session(
        userId=config.USER_ID,
        paymentManagerArn=state["payment_manager_arn"],
        paymentSessionId=state["payment_session_id"],
    )["paymentSession"]
    limits = session.get("limits", {}).get("maxSpendAmount", {})
    available = session.get("availableLimits", {}).get("availableSpendAmount", {})
    print(f"\n{'-' * 60}")
    print(f"Session budget    : {limits.get('value')} {limits.get('currency')}")
    print(f"Remaining budget  : {available.get('value')} {available.get('currency')}")
    try:
        balance = dp.get_payment_instrument_balance(
            userId=config.USER_ID,
            paymentManagerArn=state["payment_manager_arn"],
            paymentConnectorId=state["payment_connector_id"],
            paymentInstrumentId=state["payment_instrument_id"],
            chain="BASE_SEPOLIA",
            token="USDC",
        )["tokenBalance"]
        raw = int(balance["amount"])
        human = raw / (10 ** int(balance.get("decimals", 6)))
        print(f"Wallet balance    : {human} {balance.get('token')} on {balance.get('chain')}")
    except Exception as e:  # balance is nice-to-have; don't fail the demo output
        print(f"Wallet balance    : (lookup failed: {e})")


if __name__ == "__main__":
    main()
