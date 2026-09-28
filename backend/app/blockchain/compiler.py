"""Compile the Solidity contract with py-solc-x (fallback / inmemory build path).

Prefers a pre-built artifact at ``deployments/local.json`` (produced by Hardhat) so
that inmemory mode needs no Node. Falls back to compiling from source with solc-x,
resolving OpenZeppelin imports from ``node_modules``.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.config import PROJECT_ROOT, settings
from app.logging_config import get_logger

log = get_logger("compiler")

SOLC_VERSION = "0.8.24"
CONTRACT_NAME = "TokenisedFundServicing"
SOURCE_KEY = "contracts/TokenisedFundServicing.sol"


def _ensure_solc() -> None:
    from solcx import get_installed_solc_versions, install_solc

    installed = {str(v) for v in get_installed_solc_versions()}
    if SOLC_VERSION not in installed:
        log.info("installing solc", extra={"ctx_version": SOLC_VERSION})
        install_solc(SOLC_VERSION)


def compile_contract() -> dict:
    """Compile from source; returns {abi, bytecode}."""
    from solcx import compile_standard

    _ensure_solc()
    source = Path(settings.contract_source).read_text(encoding="utf-8")
    oz_path = Path(settings.oz_contracts_path)
    if not oz_path.exists():
        raise RuntimeError(
            f"OpenZeppelin sources not found at {oz_path}. Run `npm install` or provide "
            "a pre-built deployments/local.json."
        )

    std_input = {
        "language": "Solidity",
        "sources": {SOURCE_KEY: {"content": source}},
        "settings": {
            "remappings": [f"@openzeppelin/contracts/={oz_path.as_posix()}/"],
            "optimizer": {"enabled": True, "runs": 200},
            "viaIR": True,
            "outputSelection": {"*": {"*": ["abi", "evm.bytecode.object"]}},
        },
    }
    out = compile_standard(
        std_input,
        base_path=str(PROJECT_ROOT),
        allow_paths=[str(PROJECT_ROOT), str(oz_path)],
        solc_version=SOLC_VERSION,
    )
    contract = out["contracts"][SOURCE_KEY][CONTRACT_NAME]
    bytecode = contract["evm"]["bytecode"]["object"]
    if not bytecode.startswith("0x"):
        bytecode = "0x" + bytecode
    return {"abi": contract["abi"], "bytecode": bytecode}


def load_or_build_artifact() -> dict:
    """Return {abi, bytecode, address?} preferring the committed/prebuilt artifact."""
    path = Path(settings.deployments_path)
    if path.exists():
        art = json.loads(path.read_text(encoding="utf-8"))
        if art.get("abi") and art.get("bytecode"):
            log.info("using prebuilt artifact", extra={"ctx_path": str(path)})
            return art
    log.info("compiling contract from source with solc-x")
    return compile_contract()


def write_artifact(art: dict) -> None:
    path = Path(settings.deployments_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(art, indent=2), encoding="utf-8")
