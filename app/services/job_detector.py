"""
Detects hidden application instructions embedded in job descriptions.

Some job boards (RemoteOK, WWR) include phrases like:
  "Please mention the word DANKEN when applying"
  "Tag ROTkuMTQ2LjE2LjE0MQ== in your application"
  "Include the phrase 'coffee lover' to show you read this"

This module extracts those instructions so they can be surfaced in the UI
and automatically included in cover letters / application form fields.
"""
import re
from dataclasses import dataclass


@dataclass
class SecretInstruction:
    raw_sentence: str      # The full sentence containing the instruction
    action: str            # "mention" | "include" | "tag" | "write" | "type" | "say"
    secret: str            # The word/phrase/code to include


# Patterns that capture the instruction verb + the secret value.
# Each pattern has one capture group for the secret.
_PATTERNS: list[tuple[str, str]] = [
    # "mention the word DANKEN"  /  "mention DANKEN"
    ("mention", r"mention(?:\s+the\s+(?:word|phrase|code))?\s+[\"']?(\S+)[\"']?"),
    # "include the word X" / "include X in your application"
    ("include", r"include(?:\s+the\s+(?:word|phrase|code))?\s+[\"']?(\S+)[\"']?"),
    # "tag ROTkuMTQ2..."
    ("tag",     r"tag\s+([A-Za-z0-9+/=_-]{4,})"),
    # "write the word X" / "type X" / "say X"
    ("write",   r"write(?:\s+the\s+(?:word|phrase))?\s+[\"']?(\S+)[\"']?"),
    ("type",    r"type(?:\s+the\s+(?:word|phrase))?\s+[\"']?(\S+)[\"']?"),
    ("say",     r"say(?:\s+the\s+(?:word|phrase))?\s+[\"']?(\S+)[\"']?"),
]

# Compiled as a single regex that also captures which sentence contains the match.
_COMPILED = [
    (action, re.compile(pattern, re.IGNORECASE))
    for action, pattern in _PATTERNS
]

# Words that trip the patterns but are never actually secrets
_FALSE_POSITIVES = {
    "you", "your", "the", "this", "that", "us", "me", "it", "so",
    "hello", "hi", "please", "thanks", "thank", "anything", "something",
    "a", "an", "in", "on", "at", "to", "for", "of", "and", "or",
    "application", "apply", "applying", "cover", "letter", "resume",
    "position", "role", "job", "company", "team",
}


def detect_secrets(description: str) -> list[SecretInstruction]:
    """Return all secret instructions found in a job description."""
    found: list[SecretInstruction] = []
    seen_secrets: set[str] = set()

    # Check sentence by sentence for better context capture
    sentences = re.split(r'(?<=[.!?])\s+|\n', description)
    for sentence in sentences:
        for action, pattern in _COMPILED:
            m = pattern.search(sentence)
            if not m:
                continue
            secret = m.group(1).strip("\"'.,;:").strip()
            if secret.lower() in _FALSE_POSITIVES:
                continue
            if secret in seen_secrets:
                continue
            seen_secrets.add(secret)
            found.append(SecretInstruction(
                raw_sentence=sentence.strip(),
                action=action,
                secret=secret,
            ))

    return found


def format_secret_for_application(instructions: list[SecretInstruction]) -> str:
    """Return a string to append to cover letters / application text fields."""
    if not instructions:
        return ""
    parts = [i.secret for i in instructions]
    return " ".join(parts)
