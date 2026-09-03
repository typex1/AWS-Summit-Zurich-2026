"""Step 1 — Provision AgentCore Payments infrastructure.

Creates (idempotently):
  1. IAM service role trusted by bedrock-agentcore.amazonaws.com
  2. PaymentCredentialProvider (Coinbase CDP credentials -> AgentCore Identity)
  3. PaymentManager (waits for READY)
  4. PaymentConnector (CoinbaseCDP)

Run: python 01_setup_infrastructure.py
"""

import json
import sys
import time

from botocore.exceptions import ClientError

import config


def ensure_service_role(iam, account_id: str) -> str:
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {"aws:SourceAccount": account_id},
                    "ArnLike": {
                        "aws:SourceArn": (
                            f"arn:aws:bedrock-agentcore:{config.REGION}:{account_id}:"
                            "payment-manager/*"
                        )
                    },
                },
            }
        ],
    }
    permissions_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "WorkloadIdentityManagement",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:CreateWorkloadIdentity",
                    "bedrock-agentcore:DeleteWorkloadIdentity",
                ],
                "Resource": [
                    f"arn:aws:bedrock-agentcore:{config.REGION}:{account_id}:workload-identity-directory/default",
                    f"arn:aws:bedrock-agentcore:{config.REGION}:{account_id}:workload-identity-directory/default/workload-identity/*",
                ],
            },
            {
                "Sid": "WorkloadIdentityAccess",
                "Effect": "Allow",
                "Action": ["bedrock-agentcore:GetWorkloadAccessToken"],
                "Resource": [
                    f"arn:aws:bedrock-agentcore:{config.REGION}:{account_id}:workload-identity-directory/default",
                    f"arn:aws:bedrock-agentcore:{config.REGION}:{account_id}:workload-identity-directory/default/workload-identity/{config.PAYMENT_MANAGER_NAME.lower()}-*",
                ],
            },
            {
                "Sid": "PaymentTokenBaseAccess",
                "Effect": "Allow",
                "Action": ["bedrock-agentcore:GetResourcePaymentToken"],
                "Resource": [
                    f"arn:aws:bedrock-agentcore:{config.REGION}:{account_id}:token-vault/default",
                    f"arn:aws:bedrock-agentcore:{config.REGION}:{account_id}:token-vault/default/paymentcredentialprovider/*",
                    f"arn:aws:bedrock-agentcore:{config.REGION}:{account_id}:workload-identity-directory/default",
                    f"arn:aws:bedrock-agentcore:{config.REGION}:{account_id}:workload-identity-directory/default/workload-identity/{config.PAYMENT_MANAGER_NAME.lower()}-*",
                ],
            },
            {
                "Sid": "PaymentCredentialProviderProvisioning",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:CreatePaymentCredentialProvider",
                    "bedrock-agentcore:GetPaymentCredentialProvider",
                    "bedrock-agentcore:TagResource",
                ],
                "Resource": [
                    f"arn:aws:bedrock-agentcore:{config.REGION}:{account_id}:token-vault/default",
                    f"arn:aws:bedrock-agentcore:{config.REGION}:{account_id}:token-vault/default/paymentcredentialprovider/*",
                ],
            },
        ],
    }

    try:
        role = iam.get_role(RoleName=config.SERVICE_ROLE_NAME)
        print(f"IAM role already exists: {role['Role']['Arn']}")
        iam.update_assume_role_policy(
            RoleName=config.SERVICE_ROLE_NAME,
            PolicyDocument=json.dumps(trust_policy),
        )
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchEntity":
            raise
        role = iam.create_role(
            RoleName=config.SERVICE_ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Service role for AgentCore Payments Summit demo",
        )
        print(f"IAM role created: {role['Role']['Arn']}")

    iam.put_role_policy(
        RoleName=config.SERVICE_ROLE_NAME,
        PolicyName="AgentCorePaymentsBasePermissions",
        PolicyDocument=json.dumps(permissions_policy),
    )
    return role["Role"]["Arn"]


def ensure_credential_provider(control) -> str:
    state = config.load_state()
    if state.get("credential_provider_arn"):
        print(f"Credential provider already created: {state['credential_provider_arn']}")
        return state["credential_provider_arn"]

    creds = config.load_cdp_credentials()
    resp = control.create_payment_credential_provider(
        name=config.CREDENTIAL_PROVIDER_NAME,
        credentialProviderVendor="CoinbaseCDP",
        providerConfigurationInput={"coinbaseCdpConfiguration": creds},
    )
    arn = resp["credentialProviderArn"]
    config.save_state(credential_provider_arn=arn)
    print(f"Credential provider created: {arn}")
    return arn


def attach_connector_permissions(iam, control, account_id: str, credential_provider_arn: str):
    """Per-connector permissions: token access on the credential provider and
    GetSecretValue on its backing secrets (normally appended automatically when
    using the console; required here because we bring our own role)."""
    out = control.get_payment_credential_provider(name=config.CREDENTIAL_PROVIDER_NAME)
    cfg = out["providerConfigurationOutput"]["coinbaseCdpConfiguration"]
    secret_arns = [
        cfg["apiKeySecretArn"]["secretArn"],
        cfg["walletSecretArn"]["secretArn"],
    ]
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "PaymentTokenAccess",
                "Effect": "Allow",
                "Action": ["bedrock-agentcore:GetResourcePaymentToken"],
                "Resource": [credential_provider_arn],
            },
            {
                "Sid": "SecretsManagerAccess",
                "Effect": "Allow",
                "Action": ["secretsmanager:GetSecretValue"],
                "Resource": secret_arns,
                "Condition": {
                    "StringEquals": {"aws:ResourceAccount": account_id}
                },
            },
        ],
    }
    iam.put_role_policy(
        RoleName=config.SERVICE_ROLE_NAME,
        PolicyName="AgentCorePaymentsConnectorPermissions",
        PolicyDocument=json.dumps(policy),
    )
    print("Per-connector permissions attached to service role.")


def ensure_payment_manager(control, role_arn: str) -> dict:
    state = config.load_state()
    if state.get("payment_manager_arn"):
        print(f"Payment manager already created: {state['payment_manager_arn']}")
        return state

    resp = control.create_payment_manager(
        name=config.PAYMENT_MANAGER_NAME,
        description="AgentCore Payments demo for AWS Summit",
        authorizerType="AWS_IAM",
        roleArn=role_arn,
    )
    arn = resp["paymentManagerArn"]
    manager_id = resp["paymentManagerId"]
    state = config.save_state(payment_manager_arn=arn, payment_manager_id=manager_id)
    print(f"Payment manager created: {arn}")

    while True:
        status = control.get_payment_manager(paymentManagerId=manager_id)["status"]
        if status == "READY":
            print("Payment manager is READY.")
            break
        if "FAIL" in status:
            sys.exit(f"Payment manager entered {status} state — check the service role.")
        print(f"  status={status} … waiting")
        time.sleep(5)
    return state


def ensure_connector(control, manager_id: str, credential_provider_arn: str) -> str:
    state = config.load_state()
    if state.get("payment_connector_id"):
        print(f"Connector already created: {state['payment_connector_id']}")
        return state["payment_connector_id"]

    resp = control.create_payment_connector(
        paymentManagerId=manager_id,
        name=config.CONNECTOR_NAME,
        type="CoinbaseCDP",
        credentialProviderConfigurations=[
            {"coinbaseCDP": {"credentialProviderArn": credential_provider_arn}}
        ],
    )
    connector_id = resp["paymentConnectorId"]
    config.save_state(payment_connector_id=connector_id)
    print(f"Payment connector created: {connector_id} (status: {resp.get('status')})")
    if resp.get("authorizationUrl"):
        print(f"Connector authorization URL: {resp['authorizationUrl']}")
    return connector_id


def main():
    session = config.boto_session()
    account_id = session.client("sts").get_caller_identity()["Account"]
    print(f"Using profile '{config.AWS_PROFILE}' — account {account_id}, region {config.REGION}\n")

    iam = config.iam_client()
    control = config.control_client()

    role_arn = ensure_service_role(iam, account_id)
    config.save_state(service_role_arn=role_arn)

    # Give IAM a moment to propagate on first creation
    time.sleep(10)

    credential_provider_arn = ensure_credential_provider(control)
    attach_connector_permissions(iam, control, account_id, credential_provider_arn)
    state = ensure_payment_manager(control, role_arn)
    connector_id = ensure_connector(control, state["payment_manager_id"], credential_provider_arn)

    print("\nInfrastructure ready:")
    print(f"  Payment manager : {state['payment_manager_arn']}")
    print(f"  Connector       : {connector_id}")
    print("Next: python 02_create_wallet.py")


if __name__ == "__main__":
    main()
