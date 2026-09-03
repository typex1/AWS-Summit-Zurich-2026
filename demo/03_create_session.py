"""Step 3 — Create a budget-limited payment session.

A payment session is the guardrail: a scoped spending context with a max
spend amount and expiry. This is the key talking point of the demo —
the limit is enforced deterministically at the infrastructure layer,
not by the (non-deterministic) LLM.

Run: python 03_create_session.py [max_usd] [expiry_minutes]
"""

import sys
import uuid

import config

MAX_SPEND_USD = sys.argv[1] if len(sys.argv) > 1 else "1.00"
EXPIRY_MINUTES = int(sys.argv[2]) if len(sys.argv) > 2 else 120


def main():
    state = config.load_state()
    manager_arn = state.get("payment_manager_arn")
    if not manager_arn:
        sys.exit("Run 01_setup_infrastructure.py first.")

    dp = config.data_client()
    session = dp.create_payment_session(
        userId=config.USER_ID,
        paymentManagerArn=manager_arn,
        expiryTimeInMinutes=EXPIRY_MINUTES,
        limits={"maxSpendAmount": {"value": MAX_SPEND_USD, "currency": "USD"}},
        clientToken=str(uuid.uuid4()),
    )["paymentSession"]
    session_id = session["paymentSessionId"]
    config.save_state(payment_session_id=session_id)
    print(f"Payment session created: {session_id}")
    print(f"  Budget : ${MAX_SPEND_USD} USD")
    print(f"  Expiry : {EXPIRY_MINUTES} minutes")
    print("Next: python 04_payment_agent.py")


if __name__ == "__main__":
    main()
