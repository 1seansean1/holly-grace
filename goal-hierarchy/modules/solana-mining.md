# Solana Mining — Terrestrial Goal Module

**Module ID**: `solana-mining`
**Level**: 5 (Profit class)
**Block**: K (Solana Mining)
**Agent**: a10 (Solana Mining Agent, rank=3, capacity=4, sigma_max=8000)
**Status**: Test case (not yet seeded to production DB)

## Predicates (f38–f42)

| Index | Name | Pass Condition | Variance | eps_dmg |
|-------|------|----------------|----------|---------|
| f38 | Hash-rate efficiency | Mining output per kWh >= industry median | 0.10 | 0.12 |
| f39 | Wallet security | Hardware signing; no hot-wallet private keys | 0.05 | 0.10 |
| f40 | Staking yield | Annualized APY >= network avg minus 1 sigma | 0.08 | 0.15 |
| f41 | Validator uptime | >= 99.5% over trailing 7 days | 0.03 | 0.10 |
| f42 | Energy ROI | Net SOL revenue > electricity + depreciation | 0.12 | 0.15 |

## Coupling Axes

### Intra-block (Block K internal)
| Source | Target | rho | Interpretation |
|--------|--------|-----|----------------|
| f38 | f42 | 0.70 | Hash-rate directly drives energy ROI |
| f40 | f42 | 0.60 | Staking yield contributes to ROI |
| f38 | f40 | 0.40 | Hash-rate correlates with staking capability |
| f39 | f41 | 0.30 | Wallet security correlates with uptime discipline |
| f38 | f41 | 0.50 | Hash-rate depends on validator uptime |

### Cross-block
| Source | Target | rho | Type | Channel | Interpretation |
|--------|--------|-----|------|---------|----------------|
| f42 | f24 | 0.50 | terrestrial-internal | TC-2 | Energy ROI feeds revenue growth |
| f19 | f38 | 0.40 | downward | DC-2 | System health constrains hash-rate |

### No upward coupling
Solana mining has zero upward channels to Celestial. The upward coupling budget
(2 channels: UC-1, UC-2) is fully consumed by the Personality module. This means
Solana mining cannot influence moral/ethical predicates — it is a pure Terrestrial
optimization target.

## Eigenvalue

| lambda | Value | Dominant Predicates | Interpretation |
|--------|-------|---------------------|----------------|
| lambda_20 | 0.45 | f38, f40, f42 | Solana mining profitability mode |

Adding this eigenvalue increases cod(G) from 19 to 20.

## Feasibility Impact

- **Rank**: Agent a10 (rank=3) adds to total. New total: 38 >= cod(G)=20. Margin=18.
- **Coupling**: All new cross-block axes are governed by orchestrators (O3 governs a10 via value chain).
- **Epsilon**: All predicates pass eps_eff < eps_dmg check (variance/sigma_max < eps_dmg for all f38-f42).

## Gate Behavior

The lexicographic gate enforces:
- **L5 gate open** iff all L0-L4 (Celestial) predicates pass
- If Conscience (L1) or Nonmaleficence (L2) fails → L5 gate closes → mining halted
- If a Solana predicate (L5) fails, it does NOT close its own gate, but it DOES close L6 (Personality)
- Recovery: restoring the Celestial predicate reopens the gate immediately

## Environment Variables (.env)

```
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
SOLANA_WALLET_ADDRESS=          # Your Solana wallet pubkey
SOLANA_VALIDATOR_IDENTITY=       # Validator identity keypair pubkey
SOLANA_VALIDATOR_VOTE_ACCOUNT=   # Vote account pubkey
SOL_STAKING_POOL=               # Stake pool address (if using)
SOL_ELECTRICITY_RATE_KWH=0.12   # $/kWh for electricity cost
SOL_HARDWARE_DEPRECIATION_MONTHLY=150.00  # Monthly hardware depreciation
```

## Test Suite

43 tests in `tests/test_solana_mining_module.py`:
- **TestSolanaModuleDefinition** (11 tests): Structure validation
- **TestSolanaEigenspectrum** (8 tests): Coupling matrix and eigenvalue integration
- **TestSolanaFeasibility** (3 tests): Statement 55 verification
- **TestSolanaGateBehavior** (7 tests): Lexicographic gate open/close/recovery
- **TestSolanaCouplingIntegration** (4 tests): Cross-block relationships
- **TestSolanaModuleLifecycle** (6 tests): CRUD operations
- **TestSolanaEndToEnd** (4 tests): Full pipeline scenarios

## Activation

To activate Solana mining in production:
1. Fill in the wallet/validator env vars in `.env`
2. Add Solana predicates (f38-f42) to `src/hierarchy/seed.py`
3. Add agent a10 to `_AGENTS` and O3's `governed_agents`
4. Add eigenvalue lambda_20 to `_EIGENVALUES`
5. Restart server — hierarchy will re-seed with new data
6. Observation pipeline will need a `_assess_solana()` function in `observer.py`
