"""Machine layer: self-modeling, selectors, mailboxes, auth gate, perception receipts."""

from machine.self_model import SelfModel, MachineState, ModelAvailability
from machine.selectors import MachineRegistry, MachineCandidate
from machine.mailbox import Mailbox, MailboxRouter, ModelRequirement, FidelityLevel
from machine.auth_gate import AuthorizationGate, OperationRequest, AuthorizationRecord, AuthorizationDecision
from machine.perception import PerceptionLedger, PerceptionReceipt, PerceptionEvent
