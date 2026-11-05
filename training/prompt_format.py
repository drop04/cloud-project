"""Single source of truth for the training / inference text format."""
import json


def prompt_text(command):
    return f"Command: {command}\nJSON:"


def target_text(teacher_raw):
    # canonical compact-ish form of the teacher's own JSON (same keys/values, fixed spacing)
    return " " + json.dumps(json.loads(teacher_raw), ensure_ascii=False)
