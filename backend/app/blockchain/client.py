"""Web3 client: connection for both chain modes, signed tx sender, revert mapping."""
from __future__ import annotations

import ast
import asyncio

from web3 import Web3
from web3.contract.contract import ContractFunction
from web3.exceptions import ContractCustomError, ContractLogicError

from app.blockchain.accounts import DevAccounts

# Reverts surface differently across providers: web3 raises Contract*Error for HTTP
# nodes, while the eth-tester (inmemory) provider raises TransactionFailed with raw
# revert bytes. Catch all of them.
_REVERT_EXCEPTIONS: list[type] = [ContractLogicError, ContractCustomError]
try:  # pragma: no cover - only present with the inmemory backend installed
    from eth_tester.exceptions import TransactionFailed

    _REVERT_EXCEPTIONS.append(TransactionFailed)
except Exception:  # pragma: no cover
    pass
REVERT_EXCEPTIONS = tuple(_REVERT_EXCEPTIONS)
from app.blockchain.compiler import CONTRACT_NAME, load_or_build_artifact, write_artifact
from app.config import settings
from app.core.errors import ChainRevertError, map_revert
from app.logging_config import get_logger

log = get_logger("chain.client")


def _raw_tx(signed) -> bytes:
    """Handle the eth-account attribute rename across versions."""
    return getattr(signed, "raw_transaction", None) or signed.rawTransaction


def _hex0x(value) -> str:
    """Normalise HexBytes/bytes to a 0x-prefixed hex string (hexbytes 2.x drops 0x)."""
    if isinstance(value, (bytes, bytearray)):
        return "0x" + bytes(value).hex()
    s = str(value)
    return s if s.startswith("0x") else "0x" + s


def _canonical_type(inp: dict) -> str:
    if inp["type"].startswith("tuple"):
        inner = ",".join(_canonical_type(c) for c in inp.get("components", []))
        return f"({inner}){inp['type'][5:]}"
    return inp["type"]


class ChainClient:
    """Owns the Web3 connection and the deployed contract handle."""

    def __init__(self) -> None:
        self.w3: Web3 | None = None
        self.contract = None
        self.address: str | None = None
        self.abi: list | None = None
        self.accounts = DevAccounts()
        self._error_selectors: dict[str, str] = {}
        self._tx_lock = asyncio.Lock()

    # ---------- lifecycle ----------
    async def connect(self) -> None:
        art = load_or_build_artifact()
        self.abi = art["abi"]
        self._build_error_selectors()
        if settings.chain_mode == "inmemory":
            await asyncio.to_thread(self._connect_inmemory, art)
        else:
            await asyncio.to_thread(self._connect_hardhat, art)
        log.info("chain connected", extra={"ctx_mode": settings.chain_mode,
                                           "ctx_address": self.address})

    def _build_error_selectors(self) -> None:
        for item in self.abi or []:
            if item.get("type") == "error":
                types = ",".join(_canonical_type(i) for i in item.get("inputs", []))
                sig = f"{item['name']}({types})"
                sel = "0x" + Web3.keccak(text=sig).hex()[:8]
                self._error_selectors[sel] = item["name"]

    def _connect_inmemory(self, art: dict) -> None:
        from eth_tester import EthereumTester, PyEVMBackend
        from web3 import EthereumTesterProvider

        w3 = Web3(EthereumTesterProvider(EthereumTester(PyEVMBackend())))
        self.w3 = w3
        funder = w3.eth.accounts[0]
        for acct in self.accounts.all_accounts():
            w3.eth.send_transaction({
                "from": funder,
                "to": acct.address,
                "value": w3.to_wei(1000, "ether"),
            })
        self._deploy(art["bytecode"])

    def _connect_hardhat(self, art: dict) -> None:
        w3 = Web3(Web3.HTTPProvider(settings.rpc_url))
        if not w3.is_connected():
            raise RuntimeError(f"Cannot connect to Hardhat RPC at {settings.rpc_url}")
        self.w3 = w3
        self.address = art.get("address")
        if not self.address:
            raise RuntimeError("deployments/local.json has no address; run `npm run deploy`")
        self.contract = w3.eth.contract(
            address=Web3.to_checksum_address(self.address), abi=self.abi
        )

    def _deploy(self, bytecode: str) -> None:
        w3 = self.w3
        admin = self.accounts.admin
        factory = w3.eth.contract(abi=self.abi, bytecode=bytecode)
        ctor = factory.constructor(settings.fund_name, settings.initial_unit_price, admin.address)
        receipt = self._send_sync(ctor, admin, is_constructor=True)
        self.address = receipt["contract_address"]
        self.contract = w3.eth.contract(address=self.address, abi=self.abi)
        self._grant_roles_sync()
        write_artifact({
            "chainId": w3.eth.chain_id,
            "contractName": CONTRACT_NAME,
            "address": self.address,
            "roles": {
                "admin": admin.address,
                "transfer_agent": self.accounts.transfer_agent.address,
                "custodian": self.accounts.custodian.address,
                "auditor": self.accounts.auditor.address,
            },
            "abi": self.abi,
            "bytecode": bytecode,
        })

    def _grant_roles_sync(self) -> None:
        c = self.contract
        admin = self.accounts.admin
        ta = c.functions.TRANSFER_AGENT_ROLE().call()
        cu = c.functions.CUSTODIAN_ROLE().call()
        au = c.functions.AUDITOR_ROLE().call()
        grants = [
            (ta, self.accounts.transfer_agent.address),
            (cu, self.accounts.custodian.address),
            (au, self.accounts.auditor.address),
            (ta, admin.address),  # admin doubles as agent for single-signer demos
            (cu, admin.address),
        ]
        for role, who in grants:
            self._send_sync(c.functions.grantRole(role, who), admin)

    # ---------- sending ----------
    async def send(self, func: ContractFunction, signer) -> dict:
        """Serialised signed send (avoids nonce races); returns receipt dict."""
        async with self._tx_lock:
            return await asyncio.to_thread(self._send_sync, func, signer)

    def _send_sync(self, func, signer, is_constructor: bool = False) -> dict:
        w3 = self.w3
        try:
            gas = func.estimate_gas({"from": signer.address})
        except REVERT_EXCEPTIONS as exc:
            raise self._to_revert(exc) from exc
        tx = func.build_transaction({
            "from": signer.address,
            "nonce": w3.eth.get_transaction_count(signer.address, "pending"),
            "gas": int(gas * 1.25) + 60_000,
            "gasPrice": w3.eth.gas_price,
            "chainId": w3.eth.chain_id,
        })
        signed = signer.sign_transaction(tx)
        try:
            tx_hash = w3.eth.send_raw_transaction(_raw_tx(signed))
            rcpt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        except REVERT_EXCEPTIONS as exc:
            raise self._to_revert(exc) from exc
        if rcpt.get("status") != 1:
            raise ChainRevertError(None, "Transaction reverted", status_code=400)
        return {
            "tx_hash": _hex0x(rcpt["transactionHash"]),
            "block_number": rcpt["blockNumber"],
            "status": "success",
            "gas_used": rcpt["gasUsed"],
            "contract_address": rcpt.get("contractAddress"),
            "receipt": rcpt,
        }

    def read(self, func: ContractFunction):
        try:
            return func.call()
        except REVERT_EXCEPTIONS as exc:
            raise self._to_revert(exc) from exc

    def _to_revert(self, exc: Exception) -> ChainRevertError:
        selector = self._extract_selector(exc)
        name = self._error_selectors.get(selector) if selector else None
        message = getattr(exc, "message", None) or str(exc)
        if not name:
            for known in self._error_selectors.values():
                if known in message:
                    name = known
                    break
        return map_revert(name, message)

    @staticmethod
    def _extract_selector(exc: Exception) -> str | None:
        # HTTP-node style: exc.data holds the revert hex.
        data = getattr(exc, "data", None)
        if isinstance(data, str) and data.startswith("0x") and len(data) >= 10:
            return data[:10].lower()
        if isinstance(data, (bytes, bytearray)) and len(data) >= 4:
            return "0x" + bytes(data[:4]).hex()
        for arg in getattr(exc, "args", []):
            if isinstance(arg, (bytes, bytearray)) and len(arg) >= 4:
                return "0x" + bytes(arg[:4]).hex()
            if isinstance(arg, str) and arg.startswith("0x") and len(arg) >= 10:
                return arg[:10].lower()
        # eth-tester style: the message embeds a Python bytes repr of the revert data,
        # e.g. "execution reverted: b'\\xa2\\xd8...'". Recover the bytes and take 4 bytes.
        message = str(exc)
        marker = "execution reverted:"
        if marker in message:
            tail = message.split(marker, 1)[1].strip()
            if tail[:2] in ("b'", 'b"'):
                try:
                    raw = ast.literal_eval(tail)
                    if isinstance(raw, (bytes, bytearray)) and len(raw) >= 4:
                        return "0x" + bytes(raw[:4]).hex()
                except (ValueError, SyntaxError):
                    return None
        return None

    # ---------- helpers ----------
    def is_connected(self) -> bool:
        try:
            return bool(self.w3 and self.w3.is_connected())
        except Exception:
            return False

    def latest_block(self) -> int:
        return self.w3.eth.block_number

    def block_timestamp(self, block_number: int) -> int:
        return self.w3.eth.get_block(block_number)["timestamp"]
