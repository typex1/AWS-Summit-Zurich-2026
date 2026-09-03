"""Step 2 — Create the payment instrument (embedded crypto wallet).

Creates a wallet for the demo user and prints the redirect URL where the
end user funds the wallet (testnet USDC) and grants the agent delegation
to sign transactions. Then polls until the instrument becomes ACTIVE.

Run: python 02_create_wallet.py [--wait]
"""

import sys
import time
import uuid

import config

EMAIL = "your-email@example.com"  # shown in the Coinbase wallet hub; override below
if len(sys.argv) > 2 and sys.argv[1] == "--email":
    EMAIL = sys.argv[2]


def main():
    state = config.load_state()
    manager_arn = state.get("payment_manager_arn")
    connector_id = state.get("payment_connector_id")
    if not (manager_arn and connector_id):
        sys.exit("Run 01_setup_infrastructure.py first.")

    dp = config.data_client()

    if state.get("payment_instrument_id"):
        instrument_id = state["payment_instrument_id"]
        print(f"Instrument already created: {instrument_id}")
        if state.get("redirect_url"):
            print(f"Wallet hub (fund + delegate): {state['redirect_url']}")
    else:
        resp = dp.create_payment_instrument(
            userId=config.USER_ID,
            paymentManagerArn=manager_arn,
            paymentConnectorId=connector_id,
            paymentInstrumentType="EMBEDDED_CRYPTO_WALLET",
            paymentInstrumentDetails={
                "embeddedCryptoWallet": {
                    "network": "ETHEREUM",
                    "linkedAccounts": [{"email": {"emailAddress": EMAIL}}],
                }
            },
            clientToken=str(uuid.uuid4()),
        )["paymentInstrument"]
        instrument_id = resp["paymentInstrumentId"]
        wallet = resp["paymentInstrumentDetails"]["embeddedCryptoWallet"]
        redirect_url = wallet.get("redirectUrl", "")
        config.save_state(
            payment_instrument_id=instrument_id,
            redirect_url=redirect_url,
            wallet_address=wallet.get("walletAddress", ""),
        )
        print(f"Instrument created: {instrument_id}")
        print("\n=== ACTION REQUIRED (end-user step) ===")
        print(f"Open in a browser: {redirect_url}")
        print("1. Grant the agent permission to sign transactions (delegation)")
        print("2. Fund the wallet — for the demo, use testnet USDC (Circle faucet)")
        print("=======================================\n")

    # Poll status
    wait = "--wait" in sys.argv
    while True:
        inst = dp.get_payment_instrument(
            paymentManagerArn=manager_arn,
            paymentInstrumentId=instrument_id,
            userId=config.USER_ID,
        )["paymentInstrument"]
        status = inst["status"]
        wallet = inst.get("paymentInstrumentDetails", {}).get("embeddedCryptoWallet", {})
        if wallet.get("redirectUrl") and not config.load_state().get("redirect_url"):
            config.save_state(redirect_url=wallet["redirectUrl"])
            print(f"Wallet hub (fund + delegate): {wallet['redirectUrl']}")
        print(f"Instrument status: {status}")
        if status == "ACTIVE":
            print("Wallet is active — next: python 03_create_session.py")
            break
        if status in ("FAILED", "DELETED"):
            sys.exit(f"Instrument is {status}.")
        if not wait:
            print("Re-run with --wait to poll until ACTIVE, after funding/delegating.")
            break
        time.sleep(10)


if __name__ == "__main__":
    main()
