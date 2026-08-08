#!/usr/bin/env python3
"""Generate src/creem/models.py from the official Creem OpenAPI spec.

Usage:
    python scripts/generate_models.py                 # fetch the live spec
    python scripts/generate_models.py path/to/openapi.json   # use a local spec

The output file is checked in. Regenerate when the upstream spec changes.
"""
# pylint: disable=line-too-long,too-many-return-statements,too-many-branches
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

SPEC_URL = "https://docs.creem.io/api-reference/openapi.json"
OUT = Path(__file__).resolve().parent.parent / "src" / "creem" / "models.py"

# Explicit public names. Everything else is derived by stripping
# Entity/Dto/Request suffixes (see derive_name below).
NAME_OVERRIDES = {
    # responses
    "AccountListResponseDto": "CreditsAccountList",
    "AccountResponseDto": "CreditsAccount",
    "BalanceResponseDto": "CreditsBalance",
    "EntryListResponseDto": "CreditsEntryList",
    "EntryResponseDto": "CreditsEntry",
    "TransactionResponseDto": "CreditsTransaction",
    "CustomerCreditsErrorResponseDto": "CreditsErrorResponse",
    "CustomerCreditsErrorDetailDto": "CreditsErrorDetail",
    "PaginationEntity": "Pagination",
    "RefundResponseEntity": "RefundResult",
    "ScreenPromptResponse": "ModerationResult",
    "ScreenPromptRequest": "ModerationScreenParams",
    "WebhookEventEntity": "WebhookEvent",
    "WebhookSubscriptionEntity": "WebhookSubscription",
    "WebhookCheckoutCompletedEventEntity": "CheckoutCompletedEvent",
    "WebhookSubscriptionActiveEventEntity": "SubscriptionActiveEvent",
    "WebhookSubscriptionCanceledEventEntity": "SubscriptionCanceledEvent",
    "WebhookSubscriptionScheduledCancelEventEntity": "SubscriptionScheduledCancelEvent",
    "WebhookSubscriptionPastDueEventEntity": "SubscriptionPastDueEvent",
    "WebhookSubscriptionUnpaidEventEntity": "SubscriptionUnpaidEvent",
    "WebhookSubscriptionExpiredEventEntity": "SubscriptionExpiredEvent",
    "WebhookSubscriptionTrialingEventEntity": "SubscriptionTrialingEvent",
    "WebhookSubscriptionPausedEventEntity": "SubscriptionPausedEvent",
    "WebhookSubscriptionUpdateEventEntity": "SubscriptionUpdateEvent",
    "WebhookRefundCreatedEventEntity": "RefundCreatedEvent",
    "WebhookDisputeCreatedEventEntity": "DisputeCreatedEvent",
    "StatsSummaryEntity": "StatsSummary",
    "StatsMetricTotalsEntity": "StatsTotals",
    "StatsMetricPeriodEntity": "StatsPeriod",
    "CustomerLinksEntity": "CustomerBillingLinks",
    "CustomerRequestEntity": "CheckoutCustomerParams",
    "CustomFieldRequestEntity": "CustomFieldParams",
    "ProductFeatureEntity": "ProductFeature",
    "Text": "CustomFieldText",
    "Checkbox": "CustomFieldCheckbox",
    "TextFieldConfig": "CustomFieldTextConfig",
    "CheckboxFieldConfig": "CustomFieldCheckboxConfig",
    # requests
    "CreateCheckoutRequest": "CheckoutCreateParams",
    "CreateProductRequestEntity": "ProductCreateParams",
    "UpdateProductRequestEntity": "ProductUpdateParams",
    "CreateCustomerRequestEntity": "CustomerCreateParams",
    "UpdateCustomerRequestEntity": "CustomerUpdateParams",
    "CreateCustomerPortalLinkRequestEntity": "CustomerBillingParams",
    "CreateDiscountRequestEntity": "DiscountCreateParams",
    "CancelSubscriptionRequestEntity": "SubscriptionCancelParams",
    "UpdateSubscriptionRequestEntity": "SubscriptionUpdateParams",
    "UpgradeSubscriptionRequestEntity": "SubscriptionUpgradeParams",
    "UpsertSubscriptionItemEntity": "SubscriptionItemUpsert",
    "ActivateLicenseRequestEntity": "LicenseActivateParams",
    "DeactivateLicenseRequestEntity": "LicenseDeactivateParams",
    "ValidateLicenseRequestEntity": "LicenseValidateParams",
    "CreateRefundRequestEntity": "RefundCreateParams",
    "CreateAccountDto": "CreditsAccountCreateParams",
    "CreditDebitRequestDto": "CreditDebitParams",
    "ReverseTransactionRequestDto": "CreditsReverseParams",
}

# Schemas that are plain enum aliases (typed as Literal[...]).
ENUM_SCHEMAS = {
    "EnvironmentMode", "ProductStatus", "ProductFeatureType", "ProductBillingType",
    "ProductBillingPeriod", "ProductCurrency", "TaxMode", "TaxCategory",
    "CustomFieldType", "CustomFieldRequestType", "OrderStatus", "OrderType",
    "SubscriptionCollectionMethod", "SubscriptionStatus", "TransactionType",
    "TransactionStatus", "LicenseStatus", "DiscountType", "CouponDurationType",
    "RefundStatus", "RefundReason", "CommissionStatus",
    "ProductRequestBillingType", "ProductRequestBillingPeriod",
}

# Fields whose "number" type is genuinely fractional.
NUMBER_IS_FLOAT = ("exchange rate", "percentage")


def derive_name(spec_name: str) -> str:
    """Public name for a schema: override table first, then mechanical rules."""
    if spec_name in NAME_OVERRIDES:
        return NAME_OVERRIDES[spec_name]
    if spec_name in ENUM_SCHEMAS:
        return spec_name
    if spec_name.endswith("RequestEntity"):
        return spec_name[: -len("RequestEntity")] + "Params"
    if spec_name.endswith("Request"):
        return spec_name[: -len("Request")] + "Params"
    if spec_name.endswith("ListResponseDto"):
        return spec_name[: -len("ListResponseDto")] + "List"
    if spec_name.endswith("ResponseDto"):
        return spec_name[: -len("ResponseDto")]
    if spec_name.endswith("ListEntity"):
        return spec_name[: -len("ListEntity")] + "List"
    if spec_name.endswith("Entity"):
        return spec_name[: -len("Entity")]
    if spec_name.endswith("Dto"):
        return spec_name[: -len("Dto")]
    return spec_name


def camel(field: str) -> str:
    return "".join(p[:1].upper() + p[1:] for p in field.split("_"))


class Generator:
    """Renders TypedDict models from the OpenAPI spec components."""
    def __init__(self, spec: dict) -> None:
        self.spec = spec
        self.schemas = spec["components"]["schemas"]
        self.hoisted_typeddicts: list[tuple[str, str, dict]] = []  # (name, doc, schema)
        self.hoisted_enums: list[tuple[str, str, list]] = []  # (name, doc, values)

    # -- schema traversal -------------------------------------------------

    def resolve(self, sch: dict) -> dict:
        """Follow $ref / single-ref allOf chains to the concrete schema."""
        for _ in range(12):
            if "$ref" in sch:
                name = sch["$ref"].split("/")[-1]
                if name not in self.schemas:
                    return sch
                sch = self.schemas[name]
            elif "allOf" in sch and len(sch["allOf"]) == 1:
                sch = sch["allOf"][0]
            else:
                break
        return sch

    def type_of(self, sch: dict, parent: str, field: str) -> str:
        """Map a schema fragment to a Python type expression."""
        if sch is None:
            return "Any"
        if "$ref" in sch:
            return derive_name(sch["$ref"].split("/")[-1])
        if "allOf" in sch:
            parts = [self.type_of(o, parent, field) for o in sch["allOf"]]
            return " | ".join(parts)
        if sch.get("enum"):
            name = f"{parent}{camel(field)}"
            self.hoisted_enums.append((name, sch.get("description", ""), sch["enum"]))
            return name
        t = sch.get("type")
        if t == "array":
            return f"list[{self.type_of(sch.get('items', {}), parent, field)}]"
        if t == "object":
            props = sch.get("properties")
            if props:
                name = f"{parent}{camel(field)}"
                self.hoisted_typeddicts.append((name, sch.get("description", ""), sch))
                return name
            addl = sch.get("additionalProperties")
            if isinstance(addl, dict) and addl:
                return f"dict[str, {self.type_of(addl, parent, field)}]"
            return "dict[str, Any]"
        if t == "number":
            desc = (sch.get("description") or "").lower()
            return "float" if any(k in desc for k in NUMBER_IS_FLOAT) else "int"
        if t == "integer":
            return "int"
        if t == "boolean":
            return "bool"
        if t == "string":
            return "str"
        if "oneOf" in sch:
            parts = [self.type_of(o, parent, field) for o in sch["oneOf"] if o.get("type") != "null"]
            nullable = any(o.get("type") == "null" for o in sch["oneOf"])
            result = " | ".join(parts) or "Any"
            return f"{result} | None" if nullable else result
        if "anyOf" in sch:
            return self.type_of({"oneOf": sch["anyOf"]}, parent, field)
        return "Any"

    def render(self) -> str:
        parts: list[str] = []
        parts.append('"""')
        parts.append("TypedDict models for the Creem REST API.")
        parts.append("")
        parts.append("Generated by scripts/generate_models.py from the official OpenAPI spec")
        parts.append(f"({SPEC_URL}). Do not edit by hand.")
        parts.append('"""')
        parts.append("")
        parts.append("from __future__ import annotations")
        parts.append("")
        parts.append("from typing import Any, Literal, NotRequired, Required, TypedDict")
        parts.append("")
        parts.append("")

        # Top-level enum aliases; hoisted inline enums are emitted alongside
        # their parent schemas below.
        enum_lines: list[str] = []
        for spec_name in sorted(self.schemas):
            if spec_name in ENUM_SCHEMAS:
                sch = self.schemas[spec_name]
                vals = ", ".join(repr(v) for v in sch["enum"])
                if sch.get("description"):
                    enum_lines.append(f'# {sch["description"]}')
                enum_lines.append(f"{derive_name(spec_name)} = Literal[{vals}]")
                enum_lines.append("")
        parts.append("# --- Enums ---")
        parts.append("")
        parts.extend(enum_lines)
        parts.append("")

        # TypedDicts.
        parts.append("# --- Object models ---")
        parts.append("")
        names: list[str] = []
        for spec_name in sorted(self.schemas):
            if spec_name in ENUM_SCHEMAS:
                continue
            names.append(spec_name)
        # process in dependency order: emit top-level schemas, hoisting nested
        # objects/enums as they are encountered
        emitted: set[str] = set()

        def emit_typeddict(spec_name: str, parent_name: str | None = None) -> None:
            if spec_name in emitted or spec_name in ENUM_SCHEMAS:
                return
            emitted.add(spec_name)
            sch = self.schemas[spec_name]
            name = derive_name(spec_name)
            doc = sch.get("description") or ""
            resolved = self.resolve(sch)
            props = resolved.get("properties") or {}
            if not props:
                parts.append(f"class {name}(TypedDict):")
                parts.append("    ...")
                parts.append("")
                return
            request_model = name.endswith("Params") or name.endswith("Upsert")
            parts.append(f"class {name}(TypedDict):")
            if doc:
                parts.append(f'    """{doc}"""')
            required = set(resolved.get("required", []))
            for fname, fsch in props.items():
                ann = self.type_of(fsch, name, fname)
                if request_model:
                    ann = f"Required[{ann}]" if fname in required else f"NotRequired[{ann}]"
                else:
                    ann = f"NotRequired[{ann}]"
                fdoc = (fsch.get("description") or "").strip()
                if fdoc:
                    parts.append(f'    {fname}: {ann}  # {fdoc}')
                else:
                    parts.append(f"    {fname}: {ann}")
            parts.append("")
            # hoisted inline objects
            for hname, hdoc, hsch in self.hoisted_typeddicts:
                if hname.startswith(name) and not any(l.startswith(f"class {hname}") for l in parts):
                    parts.append(f"class {hname}(TypedDict):")
                    if hdoc:
                        parts.append(f'    """{hdoc}"""')
                    hreq = set(hsch.get("required", []))
                    for fname, fsch in (hsch.get("properties") or {}).items():
                        ann = self.type_of(fsch, hname, fname)
                        if request_model:
                            ann = f"Required[{ann}]" if fname in hreq else f"NotRequired[{ann}]"
                        else:
                            ann = f"NotRequired[{ann}]"
                        parts.append(f"    {fname}: {ann}")
                    parts.append("")
            for hname, hdoc, hvals in self.hoisted_enums:
                if hname.startswith(name) and not any(l.startswith(f"{hname} = Literal") for l in parts):
                    vals = ", ".join(repr(v) for v in hvals)
                    if hdoc:
                        parts.append(f'# {hdoc}')
                    parts.append(f"{hname} = Literal[{vals}]")
                    parts.append("")
            self.hoisted_typeddicts = [h for h in self.hoisted_typeddicts if not h[0].startswith(name)]
            self.hoisted_enums = [h for h in self.hoisted_enums if not h[0].startswith(name)]

        for spec_name in names:
            emit_typeddict(spec_name)

        return "\n".join(parts)


def main() -> None:
    if len(sys.argv) > 1:
        spec_path = Path(sys.argv[1])
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    else:
        with urllib.request.urlopen(SPEC_URL, timeout=60) as resp:
            spec = json.loads(resp.read())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(Generator(spec).render() + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
