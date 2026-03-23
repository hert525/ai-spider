"""Data pipeline — clean, validate, transform crawled data before storage.

Pipeline: Raw Data → Clean → Validate → Transform → Sink
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from loguru import logger


# ── Cleaning ──

def clean_text(text: str) -> str:
    """Strip HTML entities, normalize whitespace, trim."""
    if not isinstance(text, str):
        return str(text) if text is not None else ""
    text = re.sub(r"&\w+;", " ", text)       # HTML entities
    text = re.sub(r"<[^>]+>", "", text)       # stray HTML tags
    text = re.sub(r"\s+", " ", text)          # collapse whitespace
    return text.strip()


def clean_record(record: dict) -> dict:
    """Clean all string fields in a record."""
    cleaned = {}
    for key, value in record.items():
        if isinstance(value, str):
            cleaned[key] = clean_text(value)
        elif isinstance(value, list):
            cleaned[key] = [clean_text(v) if isinstance(v, str) else v for v in value]
        else:
            cleaned[key] = value
    return cleaned


def deduplicate_records(records: list[dict], key_fields: list[str] | None = None) -> list[dict]:
    """Remove duplicate records based on key fields or full content."""
    seen: set[str] = set()
    unique: list[dict] = []
    for rec in records:
        if key_fields:
            fingerprint = "|".join(str(rec.get(k, "")) for k in key_fields)
        else:
            fingerprint = str(sorted(rec.items()))
        if fingerprint not in seen:
            seen.add(fingerprint)
            unique.append(rec)
    return unique


# ── Schema Validation ──

class SchemaField:
    """Field definition for validation."""
    def __init__(self, name: str, field_type: str = "string", required: bool = False,
                 pattern: str = "", min_length: int = 0, max_length: int = 0):
        self.name = name
        self.field_type = field_type  # string, number, url, email, date, list
        self.required = required
        self.pattern = re.compile(pattern) if pattern else None
        self.min_length = min_length
        self.max_length = max_length


class SchemaValidator:
    """Validate records against a schema."""

    def __init__(self, fields: list[SchemaField]):
        self.fields = {f.name: f for f in fields}

    def validate(self, record: dict) -> tuple[bool, list[str]]:
        """Validate a record. Returns (is_valid, list_of_errors)."""
        errors: list[str] = []
        for name, field in self.fields.items():
            value = record.get(name)

            # Required check
            if field.required and (value is None or value == "" or value == []):
                errors.append(f"Missing required field: {name}")
                continue

            if value is None or value == "":
                continue

            # Type check
            if field.field_type == "number":
                if not isinstance(value, (int, float)):
                    try:
                        float(value)
                    except (ValueError, TypeError):
                        errors.append(f"{name}: expected number, got {type(value).__name__}")

            elif field.field_type == "url":
                if isinstance(value, str) and not re.match(r"https?://", value):
                    errors.append(f"{name}: invalid URL '{value[:50]}'")

            elif field.field_type == "email":
                if isinstance(value, str) and not re.match(r"[^@]+@[^@]+\.[^@]+", value):
                    errors.append(f"{name}: invalid email")

            elif field.field_type == "list":
                if not isinstance(value, list):
                    errors.append(f"{name}: expected list")

            # Length check
            if isinstance(value, str):
                if field.min_length and len(value) < field.min_length:
                    errors.append(f"{name}: too short ({len(value)} < {field.min_length})")
                if field.max_length and len(value) > field.max_length:
                    errors.append(f"{name}: too long ({len(value)} > {field.max_length})")

            # Pattern check
            if field.pattern and isinstance(value, str):
                if not field.pattern.search(value):
                    errors.append(f"{name}: doesn't match pattern")

        return len(errors) == 0, errors

    def validate_batch(self, records: list[dict]) -> dict:
        """Validate a batch of records. Returns quality report."""
        total = len(records)
        valid_count = 0
        all_errors: list[dict] = []
        field_null_counts: dict[str, int] = {f: 0 for f in self.fields}

        for i, rec in enumerate(records):
            is_valid, errors = self.validate(rec)
            if is_valid:
                valid_count += 1
            else:
                all_errors.append({"index": i, "errors": errors})

            # Count nulls
            for fname in self.fields:
                val = rec.get(fname)
                if val is None or val == "" or val == []:
                    field_null_counts[fname] += 1

        return {
            "total": total,
            "valid": valid_count,
            "invalid": total - valid_count,
            "valid_rate": round(valid_count / total * 100, 1) if total > 0 else 0,
            "field_null_rates": {
                k: round(v / total * 100, 1) if total > 0 else 0
                for k, v in field_null_counts.items()
            },
            "errors": all_errors[:20],  # Max 20 error samples
        }


# ── Data Pipeline ──

class DataPipeline:
    """Composable data processing pipeline.

    Usage:
        pipeline = DataPipeline()
        pipeline.add_step("clean", clean_record)
        pipeline.add_step("validate", validator.validate)
        result = await pipeline.process(records, metadata)
    """

    def __init__(self):
        self.steps: list[tuple[str, Any]] = []

    def add_cleaner(self) -> "DataPipeline":
        self.steps.append(("clean", None))
        return self

    def add_dedup(self, key_fields: list[str] | None = None) -> "DataPipeline":
        self.steps.append(("dedup", key_fields))
        return self

    def add_validator(self, validator: SchemaValidator) -> "DataPipeline":
        self.steps.append(("validate", validator))
        return self

    def add_transform(self, fn) -> "DataPipeline":
        """Add custom transform function: fn(record) -> record"""
        self.steps.append(("transform", fn))
        return self

    async def process(self, records: list[dict], metadata: dict | None = None) -> dict:
        """Process records through the pipeline.

        Returns:
            {
                "records": [...],          # Processed records
                "input_count": N,
                "output_count": N,
                "dropped": N,
                "quality_report": {...},   # If validator was added
                "steps": [...]             # Step-by-step log
            }
        """
        result = {
            "input_count": len(records),
            "output_count": 0,
            "dropped": 0,
            "quality_report": None,
            "steps": [],
        }
        current = list(records)

        for step_name, step_config in self.steps:
            before = len(current)

            if step_name == "clean":
                current = [clean_record(r) for r in current]
                result["steps"].append({"step": "clean", "records": len(current)})

            elif step_name == "dedup":
                current = deduplicate_records(current, step_config)
                deduped = before - len(current)
                result["steps"].append({"step": "dedup", "records": len(current), "removed": deduped})

            elif step_name == "validate":
                validator: SchemaValidator = step_config
                report = validator.validate_batch(current)
                result["quality_report"] = report
                # Keep only valid records
                valid_records = []
                invalid_indices = {e["index"] for e in report.get("errors", [])}
                for i, rec in enumerate(current):
                    if i not in invalid_indices:
                        valid_records.append(rec)
                current = valid_records
                result["steps"].append({
                    "step": "validate",
                    "records": len(current),
                    "dropped": before - len(current),
                    "valid_rate": report["valid_rate"],
                })

            elif step_name == "transform":
                transformed = []
                for rec in current:
                    try:
                        r = step_config(rec)
                        if r is not None:
                            transformed.append(r)
                    except Exception as e:
                        logger.debug(f"Transform error: {e}")
                current = transformed
                result["steps"].append({"step": "transform", "records": len(current)})

        result["records"] = current
        result["output_count"] = len(current)
        result["dropped"] = result["input_count"] - result["output_count"]

        return result
