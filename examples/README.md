# Five worked examples: idea → components → repo layout

Each example below was produced by running the real Forge pipeline against this index on 2026-10-03 (`indexer/compose.py plan` and then `fetch`). Capabilities, selected components, licence verdicts and the copied import closures are exactly what the tool returned. The `*.plan.json` files next to this README are the raw plans. Plans point at the fork head commit. The two built repos then pin with `"pins"`: OpenZeppelin v5.7.0, plus eth-infinitism v0.9.0 for #2. `fetch` mirrors those upstream tags into the Blockchains forks.

| # | Idea | Status |
|---|---|---|
| 1 | USD savings vault | Built and deployed: [Blockchains/forge-example-usd-savings-vault](https://github.com/Blockchains/forge-example-usd-savings-vault) · [live app](https://blockchains.github.io/forge-example-usd-savings-vault/) |
| 2 | Gasless membership club | Built and deployed: [Blockchains/forge-example-gasless-membership](https://github.com/Blockchains/forge-example-gasless-membership) · [live app](https://blockchains.github.io/forge-example-gasless-membership/) |
| 3 | Hedera loyalty points | Plan + fetch only. Copied sources compile (`forge build`); glue not yet generated |
| 4 | ZK age-gated DAO voting | Plan + fetch only. Copied sources compile (`forge build`); glue not yet generated |
| 5 | Uniswap v4 dynamic-fee hook | Plan + fetch only. Copied sources compile (`forge build`); glue not yet generated |

## 1. USD savings vault

> A USD-valued savings vault (ERC-4626) where users deposit WETH and receive shares; deposits and total assets are priced in USD with a Chainlink price feed oracle; an admin role manages a USD deposit cap and a management fee (access control).

**Capabilities parsed:** `price-oracle` (price; oracle; price feed; semantic z=1.90), `vault` (vault; savings; semantic z=3.37), `access-control` (admin)

| Capability | Role | Component | Fork @ commit | Licence |
|---|---|---|---|---|
| price-oracle | primary | [`AggregatorV3Interface`](https://github.com/Blockchains/chainlink-evm/blob/d1ee27b0b5875adb8eca1e0da05926f7eb1f6e1f/contracts/src/v0.8/shared/interfaces/AggregatorV3Interface.sol) `contracts/src/v0.8/shared/interfaces/AggregatorV3Interface.sol` | Blockchains/chainlink-evm @ d1ee27b0 | MIT |
| vault | primary | [`ERC4626`](https://github.com/Blockchains/openzeppelin-contracts/blob/40a51f7e78852e48d0b128d4ee3d620cbc7d35d8/contracts/token/ERC20/extensions/ERC4626.sol) `contracts/token/ERC20/extensions/ERC4626.sol` | Blockchains/openzeppelin-contracts @ 40a51f7e | MIT |
| access-control | primary | [`AccessControl`](https://github.com/Blockchains/openzeppelin-contracts/blob/40a51f7e78852e48d0b128d4ee3d620cbc7d35d8/contracts/access/AccessControl.sol) `contracts/access/AccessControl.sol` | Blockchains/openzeppelin-contracts @ 40a51f7e | MIT |
| access-control | companion | [`Ownable`](https://github.com/Blockchains/openzeppelin-contracts/blob/40a51f7e78852e48d0b128d4ee3d620cbc7d35d8/contracts/access/Ownable.sol) `contracts/access/Ownable.sol` | Blockchains/openzeppelin-contracts @ 40a51f7e | MIT |

**Licence verdict:** MIT

**Import closure copied by `fetch`:** 21 files (openzeppelin-contracts: 20, chainlink-evm: 1). Remappings: `@chainlink/contracts/src/=lib/chainlink-evm/contracts/src/`, `@openzeppelin/contracts/=lib/openzeppelin-contracts/contracts/`

**Repo layout:**
```
forge-example-usd-savings-vault/
  .github/workflows/ci.yml
  .github/workflows/pages.yml
  .gitignore
  .gitmodules
  LICENSE
  NOTICE
  README.md
  component-map.json
  foundry.toml
  plan.json
  script/Deploy.s.sol
  src/UsdSavingsVault.sol
  test/SepoliaDeploy.t.sol
  test/UsdSavingsVault.t.sol
  web/.gitignore
  web/index.html
  web/package-lock.json
  web/package.json
  web/scripts/artifacts.mjs
  web/src/chain.test.ts
  web/src/chain.ts
  web/src/main.ts
  web/tsconfig.json
  web/vite.config.ts
  lib/chainlink-evm  (submodule)
  lib/forge-std  (submodule)
  lib/openzeppelin-contracts/  (20 files)
```

## 2. Gasless membership club

> A gasless membership club: members get ERC-4337 smart accounts, a paymaster sponsors gas only for holders of a membership NFT (ERC-721), and admins manage membership with roles.

**Capabilities parsed:** `account-abstraction` (gasless; paymaster; 4337; semantic z=4.00), `nft` (nft), `access-control` (roles), `token-permit` (semantic z=2.41)

| Capability | Role | Component | Fork @ commit | Licence |
|---|---|---|---|---|
| account-abstraction | primary | [`BasePaymaster`](https://github.com/Blockchains/account-abstraction/blob/1c6b669d0eea734e09a87e095ba15e076151718a/contracts/core/BasePaymaster.sol) `contracts/core/BasePaymaster.sol` | Blockchains/account-abstraction @ 1c6b669d | MIT |
| account-abstraction | companion | [`SimpleAccount`](https://github.com/Blockchains/account-abstraction/blob/1c6b669d0eea734e09a87e095ba15e076151718a/contracts/accounts/SimpleAccount.sol) `contracts/accounts/SimpleAccount.sol` | Blockchains/account-abstraction @ 1c6b669d | MIT |
| account-abstraction | companion | [`SimpleAccountFactory`](https://github.com/Blockchains/account-abstraction/blob/1c6b669d0eea734e09a87e095ba15e076151718a/contracts/accounts/SimpleAccountFactory.sol) `contracts/accounts/SimpleAccountFactory.sol` | Blockchains/account-abstraction @ 1c6b669d | MIT |
| account-abstraction | companion | [`EntryPoint`](https://github.com/Blockchains/account-abstraction/blob/1c6b669d0eea734e09a87e095ba15e076151718a/contracts/core/EntryPoint.sol) `contracts/core/EntryPoint.sol` | Blockchains/account-abstraction @ 1c6b669d | GPL-3.0 |
| nft | primary | [`ERC721`](https://github.com/Blockchains/openzeppelin-contracts/blob/40a51f7e78852e48d0b128d4ee3d620cbc7d35d8/contracts/token/ERC721/ERC721.sol) `contracts/token/ERC721/ERC721.sol` | Blockchains/openzeppelin-contracts @ 40a51f7e | MIT |
| nft | companion | [`ERC721URIStorage`](https://github.com/Blockchains/openzeppelin-contracts/blob/40a51f7e78852e48d0b128d4ee3d620cbc7d35d8/contracts/token/ERC721/extensions/ERC721URIStorage.sol) `contracts/token/ERC721/extensions/ERC721URIStorage.sol` | Blockchains/openzeppelin-contracts @ 40a51f7e | MIT |
| access-control | primary | [`AccessControl`](https://github.com/Blockchains/openzeppelin-contracts/blob/40a51f7e78852e48d0b128d4ee3d620cbc7d35d8/contracts/access/AccessControl.sol) `contracts/access/AccessControl.sol` | Blockchains/openzeppelin-contracts @ 40a51f7e | MIT |
| access-control | companion | [`Ownable`](https://github.com/Blockchains/openzeppelin-contracts/blob/40a51f7e78852e48d0b128d4ee3d620cbc7d35d8/contracts/access/Ownable.sol) `contracts/access/Ownable.sol` | Blockchains/openzeppelin-contracts @ 40a51f7e | MIT |
| token-permit | primary | [`ERC20Permit`](https://github.com/Blockchains/openzeppelin-contracts/blob/40a51f7e78852e48d0b128d4ee3d620cbc7d35d8/contracts/token/ERC20/extensions/ERC20Permit.sol) `contracts/token/ERC20/extensions/ERC20Permit.sol` | Blockchains/openzeppelin-contracts @ 40a51f7e | MIT |

**Licence verdict:** GPL-3.0-or-later. Includes strong-copyleft files (GPL-3.0); the composed project is distributed under GPL terms.

**Import closure copied by `fetch`:** 71 files (openzeppelin-contracts: 48, account-abstraction: 23). Remappings: `@account-abstraction/contracts/=lib/account-abstraction/contracts/`, `@openzeppelin/contracts/=lib/openzeppelin-contracts/contracts/`, `account-abstraction/=lib/account-abstraction/contracts/`

**Repo layout:**
```
forge-example-gasless-membership/
  .github/workflows/ci.yml
  .github/workflows/pages.yml
  .gitignore
  .gitmodules
  LICENSE
  NOTICE
  README.md
  component-map.json
  foundry.toml
  plan.json
  script/Deploy.s.sol
  src/ClubPaymaster.sol
  src/MembershipNFT.sol
  test/GaslessMembership.t.sol
  web/.gitignore
  web/index.html
  web/package-lock.json
  web/package.json
  web/scripts/artifacts.mjs
  web/src/chain.test.ts
  web/src/chain.ts
  web/src/main.ts
  web/tsconfig.json
  web/vite.config.ts
  lib/account-abstraction/  (23 files)
  lib/forge-std  (submodule)
  lib/openzeppelin-contracts/  (42 files)
```

## 3. Hedera loyalty points

> A retail loyalty points programme on Hedera: create a fungible loyalty token with the Hedera Token Service, mint points to customers on purchase, and let them redeem points for rewards, with a simple web dashboard.

**Capabilities parsed:** `fungible-token` (token; points; loyalty points; semantic z=2.06), `hedera-hts` (hedera; hedera token service; semantic z=3.21)

| Capability | Role | Component | Fork @ commit | Licence |
|---|---|---|---|---|
| fungible-token | primary | [`ERC20`](https://github.com/Blockchains/openzeppelin-contracts/blob/40a51f7e78852e48d0b128d4ee3d620cbc7d35d8/contracts/token/ERC20/ERC20.sol) `contracts/token/ERC20/ERC20.sol` | Blockchains/openzeppelin-contracts @ 40a51f7e | MIT |
| fungible-token | companion | [`ERC20`](https://github.com/Blockchains/solady/blob/2afba69bf67b78dd4abeadcc696052b3a6f71499/src/tokens/ERC20.sol) `src/tokens/ERC20.sol` | Blockchains/solady @ 2afba69b | MIT |
| hedera-hts | primary | [`HederaTokenService`](https://github.com/Blockchains/hedera-smart-contracts/blob/43854b5c927e467b53f36316a5097f2b0815c75b/lib/layer-zero/hts/HederaTokenService.sol) `lib/layer-zero/hts/HederaTokenService.sol` | Blockchains/hedera-smart-contracts @ 43854b5c | Apache-2.0 |
| hedera-hts | companion | [`IHederaTokenService`](https://github.com/Blockchains/hedera-smart-contracts/blob/43854b5c927e467b53f36316a5097f2b0815c75b/lib/layer-zero/hts/IHederaTokenService.sol) `lib/layer-zero/hts/IHederaTokenService.sol` | Blockchains/hedera-smart-contracts @ 43854b5c | Apache-2.0 |

**Licence verdict:** MIT

**Import closure copied by `fetch`:** 8 files (hedera-smart-contracts: 2, solady: 1, openzeppelin-contracts: 5). Remappings: `@openzeppelin/contracts/=lib/openzeppelin-contracts/contracts/`, `solady/=lib/solady/src/`

**Repo layout:**
```
<project>/
  NOTICE, component-map.json, plan.json, README.md, LICENSE, foundry.toml, .github/workflows/{ci,pages}.yml
  lib/hedera-smart-contracts/  (2 files copied unmodified)
  lib/solady/  (1 files copied unmodified)
  lib/openzeppelin-contracts/  (5 files copied unmodified)
  lib/forge-std  (submodule: Blockchains/forge-std)
  src/LoyaltyPoints.sol  (HTS fungible token created via HederaTokenService.createFungibleToken; mint on purchase, burn on redeem)
  script/create-token.ts  (@hashgraph/sdk TokenCreateTransaction alternative, testnet)
  test/LoyaltyPoints.t.sol  (Hedera testnet fork via hashio.io JSON-RPC relay)
  web/  (dashboard: balances from the Mirror Node REST API)
```

## 4. ZK age-gated DAO voting

> DAO governance where only members who prove they are over 18 with a zero-knowledge proof (circom Groth16 verifier, no identity revealed) can vote on proposals; votes use ERC20Votes with a governor and timelock.

**Capabilities parsed:** `zk-proof` (circom; groth16; zero-knowledge proof; zero-knowledge proof; semantic z=2.68), `governance` (dao; governance; dao governance; semantic z=3.81), `identity` (identity)

| Capability | Role | Component | Fork @ commit | Licence |
|---|---|---|---|---|
| zk-proof | primary | [`IsZero`](https://github.com/Blockchains/circomlib/blob/35e54ea21da3e8762557234298dbb553c175ea8d/circuits/comparators.circom) `circuits/comparators.circom` | Blockchains/circomlib @ 35e54ea2 | GPL-3.0 |
| zk-proof | companion | [`Sigma`](https://github.com/Blockchains/circomlib/blob/35e54ea21da3e8762557234298dbb553c175ea8d/circuits/poseidon.circom) `circuits/poseidon.circom` | Blockchains/circomlib @ 35e54ea2 | GPL-3.0 |
| governance | primary | [`Governor`](https://github.com/Blockchains/openzeppelin-contracts/blob/40a51f7e78852e48d0b128d4ee3d620cbc7d35d8/contracts/governance/Governor.sol) `contracts/governance/Governor.sol` | Blockchains/openzeppelin-contracts @ 40a51f7e | MIT |
| governance | companion | [`TimelockController`](https://github.com/Blockchains/openzeppelin-contracts/blob/40a51f7e78852e48d0b128d4ee3d620cbc7d35d8/contracts/governance/TimelockController.sol) `contracts/governance/TimelockController.sol` | Blockchains/openzeppelin-contracts @ 40a51f7e | MIT |
| governance | companion | [`ERC20Votes`](https://github.com/Blockchains/openzeppelin-contracts/blob/40a51f7e78852e48d0b128d4ee3d620cbc7d35d8/contracts/token/ERC20/extensions/ERC20Votes.sol) `contracts/token/ERC20/extensions/ERC20Votes.sol` | Blockchains/openzeppelin-contracts @ 40a51f7e | MIT |

**Licence verdict:** GPL-3.0-or-later. Includes strong-copyleft files (GPL-3.0); the composed project is distributed under GPL terms.

**Import closure copied by `fetch`:** 52 files (openzeppelin-contracts: 45, circomlib: 7). Remappings: `@openzeppelin/contracts/=lib/openzeppelin-contracts/contracts/`

**Repo layout:**
```
<project>/
  NOTICE, component-map.json, plan.json, README.md, LICENSE, foundry.toml, .github/workflows/{ci,pages}.yml
  lib/openzeppelin-contracts/  (45 files copied unmodified)
  lib/circomlib/  (7 files copied unmodified)
  lib/forge-std  (submodule: Blockchains/forge-std)
  circuits/age.circom  (GreaterEqThan(16) on currentYear-birthYear >= 18 + Poseidon commitment; compiled with circom 2.2.3: 796 labels)
  src/AgeVerifier.sol  (snarkjs-exported Groth16 verifier)
  src/AgeGatedGovernor.sol  (Governor + GovernorVotes + GovernorTimelockControl; _castVote requires a verified proof)
  src/MemberToken.sol  (ERC20Votes)
  test/AgeGatedGovernor.t.sol, test/circuits.test.ts
```

## 5. Uniswap v4 dynamic-fee hook

> A Uniswap v4 hook that sets a dynamic swap fee based on volatility measured from a Chainlink price feed oracle, raising fees when the market is volatile.

**Capabilities parsed:** `dex-hook` (hook; uniswap v4 hook; v4 hook; semantic z=3.27), `price-oracle` (price; oracle; price feed; semantic z=1.63)

| Capability | Role | Component | Fork @ commit | Licence |
|---|---|---|---|---|
| dex-hook | primary | [`IHooks`](https://github.com/Blockchains/v4-core/blob/46c6834698c48bc4a463a86d8420f4eb1d7f3b75/src/interfaces/IHooks.sol) `src/interfaces/IHooks.sol` | Blockchains/v4-core @ 46c68346 | MIT |
| dex-hook | companion | [`LPFeeLibrary`](https://github.com/Blockchains/v4-core/blob/46c6834698c48bc4a463a86d8420f4eb1d7f3b75/src/libraries/LPFeeLibrary.sol) `src/libraries/LPFeeLibrary.sol` | Blockchains/v4-core @ 46c68346 | MIT |
| dex-hook | companion | [`IPoolManager`](https://github.com/Blockchains/v4-core/blob/46c6834698c48bc4a463a86d8420f4eb1d7f3b75/src/interfaces/IPoolManager.sol) `src/interfaces/IPoolManager.sol` | Blockchains/v4-core @ 46c68346 | MIT |
| price-oracle | primary | [`AggregatorV3Interface`](https://github.com/Blockchains/chainlink-evm/blob/d1ee27b0b5875adb8eca1e0da05926f7eb1f6e1f/contracts/src/v0.8/shared/interfaces/AggregatorV3Interface.sol) `contracts/src/v0.8/shared/interfaces/AggregatorV3Interface.sol` | Blockchains/chainlink-evm @ d1ee27b0 | MIT |

**Licence verdict:** MIT

**Import closure copied by `fetch`:** 17 files (chainlink-evm: 1, v4-core: 16). Remappings: `@chainlink/contracts/src/=lib/chainlink-evm/contracts/src/`, `@uniswap/v4-core/=lib/v4-core/`, `v4-core/=lib/v4-core/`

**Repo layout:**
```
<project>/
  NOTICE, component-map.json, plan.json, README.md, LICENSE, foundry.toml, .github/workflows/{ci,pages}.yml
  lib/chainlink-evm/  (1 files copied unmodified)
  lib/v4-core/  (16 files copied unmodified)
  lib/forge-std  (submodule: Blockchains/forge-std)
  src/VolatilityFeeHook.sol  (beforeSwap returns LPFeeLibrary.OVERRIDE_FEE_FLAG | fee computed from Chainlink round-to-round deviation)
  test/VolatilityFeeHook.t.sol  (v4-core Deployers + mainnet ETH/USD fork)
  script/DeployHook.s.sol  (HookMiner salt for the BEFORE_SWAP flag)
  Note: PoolManager is BUSL-1.1 and is NOT copied. It is used only as an unmodified test dependency (submodule), as in the uniswap-v4-hook starter.
```

## Reproduce
```bash
pip install -r requirements.txt
python3 indexer/compose.py plan "<idea>" --json plan.json   # parse + retrieve + licence check
python3 indexer/compose.py fetch plan.json out/                # copy the import closure from the Blockchains forks, write NOTICE + component map
```
Set `BL_INDEX` to a checkout of this repo. The website `/forge` composer runs the same pipeline, with Grok parsing the idea and generating the glue.
