"""
Natural Language Understanding (NLU) service for Twi/English MoMo utterances.

Implements regex and rule-based slot-filling and intent extraction tuned for
Ghanaian Mobile Money transaction phrases in Twi with English code-mixing.
"""

import re
from typing import Optional

from ai.schemas import IntentType, NLUSlotExtraction


# Intent keyword maps (lowercased)
_INTENT_KEYWORDS: dict[IntentType, list[str]] = {
    IntentType.WITHDRAW: [
        "miyi sika", "yi sika", "meyi sidi", "yi sidi", "meyi", "yi", "withdraw", "gye", "cash out", "cashout", "sidi"
    ],
    IntentType.TRANSFER: ["mesoma", "soma", "transfer", "send", "fa kɔma", "kɔma"],
    IntentType.DEPOSIT: ["gu me account", "deposit", "hyɛ me account", "fa gu"],
}

# Regex patterns

# Currency words in Ghana: cedis, cedi, sidi, ghs, ghana cedis, $
# Match currency before number ("sidi 100", "ghs 50") or after ("100 cedis", "100 sidi")
_CURRENCY_AMOUNT_PATTERN = re.compile(
    r"(?:(?:ghs|ghana\s*cedis?|cedis?|sidi|\$)\s*(\d[\d,]*\.?\d*)|\b(\d[\d,]*\.?\d*)\s*(?:cedis?|sidi|ghs|ghana\s*cedis?|\$)\b)",
    re.IGNORECASE,
)

# Ghanaian phone number: starts with 0, 10 digits total, may contain spaces
_PHONE_PATTERN = re.compile(
    r"\b(0[\s]?\d[\s]?\d[\s]?\d[\s]?\d[\s]?\d[\s]?\d[\s]?\d[\s]?\d[\s]?\d)\b",
)

# Recipient name: word(s) following "ma " (Twi for "give to")
_RECIPIENT_PATTERN = re.compile(
    r"\bma\s+([A-Za-zÀ-ÿɛɔƐƆ]+)",
    re.IGNORECASE,
)


# Public API

def extract_intent(text: str) -> IntentType:
    """Detect the most specific transactional intent from *text*."""
    lowered = text.lower()
    for intent, keywords in _INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in lowered:
                return intent
    return IntentType.UNKNOWN


def extract_amount(text: str, phone: Optional[str] = None) -> Optional[float]:
    """Extract a monetary amount from *text*, or ``None``."""
    match = _CURRENCY_AMOUNT_PATTERN.search(text)
    if match:
        raw = match.group(1) or match.group(2)
        try:
            return float(raw.replace(",", ""))
        except ValueError:
            pass

    # Fallback to standalone numbers that aren't the phone number
    for num in re.findall(r"\b\d+(?:\.\d+)?\b", text):
        if phone and num in phone:
            continue
        if len(num) == 10 and num.startswith("0"):
            continue
        try:
            return float(num)
        except ValueError:
            continue

    return None



def extract_phone(text: str) -> Optional[str]:
    """Extract a 10-digit Ghanaian phone number from *text*."""
    match = _PHONE_PATTERN.search(text)
    if match:
        digits = match.group(1).replace(" ", "")
        if len(digits) == 10 and digits.startswith("0"):
            return digits
    return None


def extract_recipient_name(text: str) -> Optional[str]:
    """Extract the recipient name appearing after 'ma' in *text*."""
    match = _RECIPIENT_PATTERN.search(text)
    if match:
        name = match.group(1).strip()
        return name if name else None
    return None


def extract_slots(text: str) -> NLUSlotExtraction:
    """Run full NLU slot extraction on *text* and return structured results.

    This is the main entry point called by the router.
    """
    phone = extract_phone(text)
    return NLUSlotExtraction(
        intent=extract_intent(text),
        amount=extract_amount(text, phone=phone),
        currency="GHS",
        recipient=extract_recipient_name(text),
        recipient_phone=phone,
        raw_text=text,
    )

