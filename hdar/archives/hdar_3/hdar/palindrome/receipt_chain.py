"""Palindrome receipt chain — the reversible conversation.

The conversation is converted into receipts that return to the machine.

Flow:
  Machine -> mailbox -> GPT -> receipt -> machine -> new mailbox

Each receipt is:
  - Signed by the host (local machine)
  - Linked to the previous receipt (hash chain)
  - Contains the operation, the perception, and the result
  - Can be verified offline

The chain is the palindrome: outward goes the question,
inward returns the answer, and the answer becomes the next question.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PalindromeReceipt:
    """A single receipt in the palindrome chain."""
    receipt_id: str
    sequence: int
    mailbox_id: str
    citizen_id: str
    operation: str
    granted: bool
    lease_state: str
    result_hash: str  # hash of the result data
    result_summary: str = ""
    timestamp: float = 0.0
    previous_receipt_hash: str = ""
    receipt_hash: str = ""
    host_signature: str = ""
    origin_request_hash: str = ""
    completion_rules_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "receipt_id": self.receipt_id,
            "sequence": self.sequence,
            "mailbox_id": self.mailbox_id,
            "citizen_id": self.citizen_id,
            "operation": self.operation,
            "granted": self.granted,
            "lease_state": self.lease_state,
            "result_hash": self.result_hash,
            "result_summary": self.result_summary,
            "timestamp": self.timestamp,
            "previous_receipt_hash": self.previous_receipt_hash,
            "receipt_hash": self.receipt_hash,
            "host_signature": self.host_signature,
            "origin_request_hash": self.origin_request_hash,
            "completion_rules_hash": self.completion_rules_hash,
        }

    def unsigned_canonical(self) -> bytes:
        d = self.to_dict()
        d.pop("host_signature", None)
        d.pop("receipt_hash", None)
        return json.dumps(d, sort_keys=True, separators=(",", ":")).encode()

    def compute_hash(self) -> str:
        return hashlib.sha256(self.unsigned_canonical()).hexdigest()


class ReceiptChain:
    """Hash-linked chain of palindrome receipts.

    Each receipt links to the previous one via its hash, creating
    a tamper-evident sequence. The chain starts from a genesis hash
    and can be verified offline.

    The chain is the palindrome's memory: it records what happened
    in the mailbox, and the machine can continue from the last receipt
    without depending on the chat history surviving.
    """

    GENESIS_HASH = "0" * 64

    def __init__(self, origin_request: Any = None, completion_rules: Any = None):
        self._receipts: List[PalindromeReceipt] = []
        self._last_hash: str = self.GENESIS_HASH
        self.origin_request_hash = self._commit(origin_request)
        self.completion_rules_hash = self._commit(completion_rules)

    @staticmethod
    def _commit(value: Any) -> str:
        if value is None:
            return ""
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
        ).hexdigest()

    def bind_origin(self, origin_request: Any, completion_rules: Any) -> None:
        """Bind the forward request and final-receipt rules before recording work."""
        if self._receipts:
            raise ValueError("cannot bind an origin after receipts exist")
        self.origin_request_hash = self._commit(origin_request)
        self.completion_rules_hash = self._commit(completion_rules)

    def add(
        self,
        mailbox_id: str,
        citizen_id: str,
        operation: str,
        granted: bool,
        lease_state: str,
        result_data: Any,
        result_summary: str = "",
        host_key=None,
    ) -> PalindromeReceipt:
        """Add a receipt to the chain."""
        sequence = len(self._receipts)
        result_hash = hashlib.sha256(
            json.dumps(result_data, sort_keys=True, default=str).encode()
        ).hexdigest()

        receipt = PalindromeReceipt(
            receipt_id=hashlib.sha256(
                f"{mailbox_id}:{citizen_id}:{operation}:{sequence}".encode()
            ).hexdigest()[:32],
            sequence=sequence,
            mailbox_id=mailbox_id,
            citizen_id=citizen_id,
            operation=operation,
            granted=granted,
            lease_state=lease_state,
            result_hash=result_hash,
            result_summary=result_summary,
            timestamp=time.time(),
            previous_receipt_hash=self._last_hash,
            origin_request_hash=self.origin_request_hash,
            completion_rules_hash=self.completion_rules_hash,
        )

        receipt.receipt_hash = receipt.compute_hash()

        if host_key:
            receipt.host_signature = host_key.sign_bytes(receipt.unsigned_canonical())

        self._receipts.append(receipt)
        self._last_hash = receipt.receipt_hash
        return receipt

    def verify_chain(self, host_public_key=None) -> Dict[str, Any]:
        """Verify the entire chain integrity."""
        checks_passed = 0
        checks_failed = 0
        failures: List[str] = []

        prev_hash = self.GENESIS_HASH
        for i, receipt in enumerate(self._receipts):
            # Check sequence
            if receipt.sequence != i:
                checks_failed += 1
                failures.append(f"receipt {i}: sequence mismatch {receipt.sequence}")
            else:
                checks_passed += 1

            # Check hash linkage
            if receipt.previous_receipt_hash != prev_hash:
                checks_failed += 1
                failures.append(f"receipt {i}: hash linkage broken")
            else:
                checks_passed += 1

            # Check receipt hash
            if receipt.compute_hash() != receipt.receipt_hash:
                checks_failed += 1
                failures.append(f"receipt {i}: receipt hash mismatch")
            else:
                checks_passed += 1

            if receipt.origin_request_hash != self.origin_request_hash:
                checks_failed += 1
                failures.append(f"receipt {i}: origin request commitment mismatch")
            else:
                checks_passed += 1

            if receipt.completion_rules_hash != self.completion_rules_hash:
                checks_failed += 1
                failures.append(f"receipt {i}: completion rules commitment mismatch")
            else:
                checks_passed += 1

            # Check signature if key provided
            if host_public_key and receipt.host_signature:
                try:
                    valid = host_public_key.verify(
                        json.loads(receipt.unsigned_canonical().decode()),
                        receipt.host_signature,
                    )
                    if valid:
                        checks_passed += 1
                    else:
                        checks_failed += 1
                        failures.append(f"receipt {i}: signature invalid")
                except Exception:
                    checks_failed += 1
                    failures.append(f"receipt {i}: signature verification error")

            prev_hash = receipt.receipt_hash

        return {
            "total_receipts": len(self._receipts),
            "checks_passed": checks_passed,
            "checks_failed": checks_failed,
            "failures": failures,
            "chain_valid": checks_failed == 0,
            "head_hash": self._last_hash,
        }

    def get_receipts(self) -> List[PalindromeReceipt]:
        return list(self._receipts)

    def get_receipt(self, receipt_id: str) -> Optional[PalindromeReceipt]:
        for r in self._receipts:
            if r.receipt_id == receipt_id:
                return r
        return None

    def head(self) -> Optional[PalindromeReceipt]:
        """Return the most recent receipt."""
        return self._receipts[-1] if self._receipts else None

    def to_dict(self) -> dict:
        return {
            "receipts": [r.to_dict() for r in self._receipts],
            "head_hash": self._last_hash,
            "genesis": self.GENESIS_HASH,
            "origin_request_hash": self.origin_request_hash,
            "completion_rules_hash": self.completion_rules_hash,
        }

    def reverse_trace(self) -> List[dict]:
        """Return the verified completion-to-origin view of the same receipts."""
        verification = self.verify_chain()
        if not verification["chain_valid"]:
            raise ValueError("cannot reverse-trace an invalid receipt chain")
        return [receipt.to_dict() for receipt in reversed(self._receipts)]

    def summary(self) -> dict:
        """Human-readable summary of the chain."""
        return {
            "total_receipts": len(self._receipts),
            "head_hash": self._last_hash[:16] + "...",
            "operations": {
                op: sum(1 for r in self._receipts if r.operation == op)
                for op in set(r.operation for r in self._receipts)
            },
            "granted": sum(1 for r in self._receipts if r.granted),
            "denied": sum(1 for r in self._receipts if not r.granted),
            "mailboxes": list(set(r.mailbox_id for r in self._receipts)),
        }
