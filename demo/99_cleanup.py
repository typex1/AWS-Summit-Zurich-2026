"""Cleanup — tear down all demo resources.

Deletes: payment instrument, connector, payment manager, credential
provider, and the IAM service role. Asks for confirmation first.

Run: python 99_cleanup.py
"""

import sys

from botocore.exceptions import ClientError

import config


def main():
    state = config.load_state()
    if not state:
        sys.exit("No demo_state.json — nothing to clean up.")

    print("This will DELETE the following AgentCore Payments resources:")
    for k, v in state.items():
        print(f"  {k}: {v}")
    if input("Type 'delete' to confirm: ").strip() != "delete":
        sys.exit("Aborted.")

    dp = config.data_client()
    control = config.control_client()
    iam = config.iam_client()

    manager_arn = state.get("payment_manager_arn")
    manager_id = state.get("payment_manager_id")

    if manager_arn and state.get("payment_instrument_id"):
        try:
            dp.delete_payment_instrument(
                paymentManagerArn=manager_arn,
                paymentInstrumentId=state["payment_instrument_id"],
            )
            print("Deleted payment instrument.")
        except ClientError as e:
            print(f"Instrument delete: {e.response['Error']['Code']}")

    if manager_id and state.get("payment_connector_id"):
        try:
            control.delete_payment_connector(
                paymentManagerId=manager_id,
                paymentConnectorId=state["payment_connector_id"],
            )
            print("Deleted payment connector.")
        except ClientError as e:
            print(f"Connector delete: {e.response['Error']['Code']}")

    if manager_id:
        try:
            control.delete_payment_manager(paymentManagerId=manager_id)
            print("Deleted payment manager.")
        except ClientError as e:
            print(f"Manager delete: {e.response['Error']['Code']}")

    if state.get("credential_provider_arn"):
        try:
            control.delete_payment_credential_provider(
                name=config.CREDENTIAL_PROVIDER_NAME
            )
            print("Deleted credential provider.")
        except ClientError as e:
            print(f"Credential provider delete: {e.response['Error']['Code']}")

    try:
        for policy_name in (
            "AgentCorePaymentsBasePermissions",
            "AgentCorePaymentsConnectorPermissions",
        ):
            try:
                iam.delete_role_policy(
                    RoleName=config.SERVICE_ROLE_NAME, PolicyName=policy_name
                )
            except ClientError:
                pass
        iam.delete_role(RoleName=config.SERVICE_ROLE_NAME)
        print("Deleted IAM service role.")
    except ClientError as e:
        print(f"IAM role delete: {e.response['Error']['Code']}")

    config.STATE_FILE.unlink(missing_ok=True)
    print("State file removed. Cleanup complete.")


if __name__ == "__main__":
    main()
