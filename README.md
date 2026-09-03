# AgentCore Payments Demo — AWS Summit, September 2

An AI agent that **pays for content autonomously** using [Amazon Bedrock AgentCore Payments](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments.html) (GA since Aug 18, 2026), a Coinbase CDP embedded wallet, and the open **x402** payment protocol.

## The story (30 seconds)

Agents can reason, pick tools, and complete tasks — but they hit a wall when
content or APIs cost money. AgentCore Payments removes that wall: when the
agent gets an HTTP **402 Payment Required**, AgentCore signs a stablecoin
micropayment from a user-delegated wallet — **within a deterministic,
infrastructure-enforced budget** — and the agent retries with payment proof.
No credentials in the agent, no unbounded spending.

## Architecture

```
┌─────────────┐  402 Payment Required   ┌──────────────┐
│ Strands     │ ──────────────────────▶ │ x402 merchant │
│ Agent       │ ◀────────────────────── │ (paid API)    │
│ + Payments  │  retry + X-PAYMENT hdr  └──────────────┘
│   Plugin    │
└──────┬──────┘
       │ sign payment (within session budget)
       ▼
┌────────────────────────── AWS ──────────────────────────┐
│ PaymentManager ─ PaymentConnector (CoinbaseCDP)          │
│      │                  │                                │
│ PaymentSession      PaymentCredentialProvider            │
│ (max spend, TTL)    (secrets in AgentCore Identity)      │
│ PaymentInstrument (embedded crypto wallet, user-funded)  │
└──────────────────────────────────────────────────────────┘
```

## Prerequisites (already done)

- An AWS account with AgentCore Payments available, region `us-east-1`
  (set your profile/region in `demo/config.py` — `AWS_PROFILE`, `REGION` —
  or via `DEMO_AWS_PROFILE` / `DEMO_AWS_REGION`)
- AWS Marketplace subscription: *Coinbase Wallets for AgentCore Payments*
- Coinbase CDP credentials in `~/Downloads/cdp_api_key.json` and
  `~/Downloads/cdp_wallet_secret.txt` (with **Delegated signing** enabled
  in the CDP dashboard)
- A Bedrock model enabled in the account (default: Claude Sonnet 4.6;
  override with `DEMO_MODEL_ID`)

## Setup (once, before the Summit)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cd demo
python 01_setup_infrastructure.py   # IAM role, credentials, manager, connector
python 02_create_wallet.py --email you@example.com
#   → open the printed redirect URL: grant delegation + fund with testnet USDC
python 02_create_wallet.py --wait   # poll until ACTIVE
```

State (ARNs/IDs, no secrets) is stored in `demo/demo_state.json`.

## Current status (as of Aug 21)

Everything below is **provisioned and verified** in the demo account / us-east-1:

| Resource | Value | Status |
|----------|-------|--------|
| IAM service role | `AgentCorePaymentsSummitDemoRole` | ✅ |
| Credential provider | `summit-demo-coinbase-credentials` | ✅ |
| Payment manager | `summitdemopayments-vn3fq6o8xk` | ✅ READY |
| Payment connector | `summitdemocoinbaseconnector-x8bhgjblsx` | ✅ READY |
| Wallet (instrument) | `payment-instrument-XXXXXXXXXXXX` (linked to <your-email>) | ✅ ACTIVE |
| Wallet address | `0xE5eA49eae5Ce81235763Eb1FaB306C8F6580B2ab` | — |
| Payment session | $1.00 / 120 min | ✅ created |
| Agent dry-run | 402 intercepted → ProcessPayment invoked | ✅ verified |

**Remaining manual steps (browser + email OTP — only you can do these):**

1. Open the wallet hub: **https://hub.cdp.coinbase.com/<your-hub-id>**
   (sign in with <your-email> — an OTP is emailed to you)
2. **Grant delegated signing** for the wallet (the dry-run currently fails with
   *"Delegated signing grant is not active for the end user wallet"* — this
   grant is per-wallet, done in the hub).
3. **Fund with testnet USDC** on Base Sepolia: use the
   [Circle faucet](https://faucet.circle.com) → network *Base Sepolia* →
   address `0xE5eA49eae5Ce81235763Eb1FaB306C8F6580B2ab` (a few USDC is plenty;
   payments are ~$0.01–0.10).
4. Re-run `python 04_payment_agent.py` — the payment should now settle and
   the content should arrive.

## Run-of-show (live, ~5 minutes)

| # | Action | Talking point |
|---|--------|---------------|
| 1 | Show the AgentCore console → Build → Payments | "Payments is now a first-class AgentCore primitive — GA since Aug 18." |
| 2 | `python 03_create_session.py 1.00 120` | "Budget guardrail: $1 max, 2h expiry — enforced **deterministically at the infrastructure layer**, not by the LLM." |
| 3 | `python 04_payment_agent.py` | Agent hits the paid endpoint, gets **402**, the plugin signs the payment via the Coinbase wallet, retries — content arrives. "Zero payment code in the agent logic." |
| 4 | Point at the printed session status + wallet balance | "Full audit trail: session spend, remaining budget, wallet balance." |
| 5 | (Optional) Re-run 04 until the $1 session budget is exceeded | "The agent *cannot* overspend — the session rejects it. That's the trust story for autonomous agents." |
| 6 | (Optional) CloudWatch → AgentCore Observability dashboards | "Vended logs and spans for every payment, out of the box." |

### Demo commands cheat sheet

```bash
source .venv/bin/activate && cd demo
python 03_create_session.py 1.00 120     # fresh $1 session
python 04_payment_agent.py               # the money shot
python 04_payment_agent.py "Buy me the premium data at https://sandbox.node4all.com/v1/x402-test"
```

## Fallback plan

- If Wi-Fi/model issues: pre-record the terminal run (e.g. `asciinema`).
- If the sandbox merchant is down: any x402-enabled endpoint works — see the
  Coinbase **x402 Bazaar** MCP server via AgentCore Gateway (10,000+ endpoints).
- Session expired mid-demo: just re-run `03_create_session.py`.

## Cleanup (after the Summit)

```bash
python demo/99_cleanup.py
```
