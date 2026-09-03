"""Shared configuration and state handling for the AgentCore Payments demo.

All AWS calls use the '<aws-profile>' profile in us-east-1.
Resource ARNs/IDs (never secrets) are persisted to demo_state.json so the
scripts can be run independently and in sequence.
"""

import json
import os
from pathlib import Path

import boto3

AWS_PROFILE = os.environ.get("DEMO_AWS_PROFILE", "<aws-profile>")
REGION = os.environ.get("DEMO_AWS_REGION", "us-east-1")

# Resource names (payment manager/connector names must match [a-zA-Z][a-zA-Z0-9]{0,47})
PAYMENT_MANAGER_NAME = "summitDemoPayments"
CONNECTOR_NAME = "summitDemoCoinbaseConnector"
CREDENTIAL_PROVIDER_NAME = "summit-demo-coinbase-credentials"
SERVICE_ROLE_NAME = "AgentCorePaymentsSummitDemoRole"

# Demo end user
USER_ID = "summit-demo-user"

# x402 test endpoint (sandbox merchant that returns HTTP 402)
X402_TEST_ENDPOINT = "https://sandbox.node4all.com/v1/x402-test"

# Coinbase CDP credential files (downloaded by the developer; read-only, never logged)
CDP_API_KEY_FILE = Path.home() / "Downloads" / "cdp_api_key.json"
CDP_WALLET_SECRET_FILE = Path.home() / "Downloads" / "cdp_wallet_secret.txt"

STATE_FILE = Path(__file__).parent / "demo_state.json"


def boto_session() -> boto3.Session:
    return boto3.Session(profile_name=AWS_PROFILE, region_name=REGION)


def control_client():
    """Control plane: payment manager / connector / credential provider."""
    return boto_session().client("bedrock-agentcore-control")


def data_client():
    """Data plane: payment instruments, sessions, payments."""
    return boto_session().client("bedrock-agentcore")


def iam_client():
    return boto_session().client("iam")


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(**updates) -> dict:
    state = load_state()
    state.update(updates)
    STATE_FILE.write_text(json.dumps(state, indent=2))
    return state


def load_cdp_credentials() -> dict:
    """Read Coinbase CDP credentials from the downloaded files.

    Returns a dict with apiKeyId, apiKeySecret, walletSecret.
    Values are passed straight to the AWS API and never printed.
    """
    if not CDP_API_KEY_FILE.exists() or not CDP_WALLET_SECRET_FILE.exists():
        raise FileNotFoundError(
            f"Expected {CDP_API_KEY_FILE} and {CDP_WALLET_SECRET_FILE}. "
            "Download them from the Coinbase Developer Platform."
        )
    api_key = json.loads(CDP_API_KEY_FILE.read_text())
    wallet_secret = CDP_WALLET_SECRET_FILE.read_text().strip()
    return {
        "apiKeyId": api_key["id"],
        "apiKeySecret": api_key["privateKey"],
        "walletSecret": wallet_secret,
    }
