# Creem API Reference

Complete reference for the Creem REST API (v1), built for Python backend integrations. Compiled 2026-08-07 from the official OpenAPI spec (https://docs.creem.io/api-reference/openapi.json), the Creem documentation dump (https://docs.creem.io/llms-full.txt), and the agent skill file (https://creem.io/SKILL.md).

## Contents

- [Platform Overview](#platform-overview)
- [Authentication & Environments](#authentication--environments)
- [Quickstart: Selling a Product](#quickstart-selling-a-product)
- [Error Handling](#error-handling)
- [Endpoints](#endpoints)
- [Webhooks](#webhooks)
- [Test Mode](#test-mode)
- [Schema Appendix](#schema-appendix)

---

## Platform Overview

Creem is a **Merchant of Record (MoR)** for SaaS and digital businesses. It handles payments (cards, PayPal, Apple Pay, Google Pay), global tax compliance (VAT/GST/sales tax in 190+ countries), chargebacks, currency conversion, and payouts (fiat and USDC).

### Object IDs

Resources use prefixed IDs: `prod_` (product), `ch_` (checkout), `cust_` (customer), `sub_` (subscription), `sitem_` (subscription item), `pprice_` (product price), `tran_`/`txn_` (transaction), `ord_` (order), `disc_` (discount), `ref_` (refund), `evt_` (webhook event), `disp_` (dispute), `cca_` (customer credits account), `inst_` (license instance). License keys are `XXXXXX-XXXXXX-XXXXXX-XXXXXX` strings (not `lic_`-prefixed). Do not assume formats — always use IDs returned by the API.

### Pricing

All monetary amounts are integers in **cents** (1000 = $10.00). Supported currencies: `USD`, `EUR`. Tax amounts are returned separately (`tax_amount`); `amount`/`amount_due` are pre-tax totals unless the product uses inclusive tax mode.

---

## Authentication & Environments

All API requests require the API key in the **`x-api-key` header**. Keys are managed in the dashboard (https://creem.io/dashboard/developers). Never expose keys in client-side code.

| Environment | Key prefix | Base URL |
|---|---|---|
| Test (sandbox) | `creem_test_` | `https://test-api.creem.io` |
| Production | `creem_` | `https://api.creem.io` |

API paths are prefixed with `/v1`. Test and production are completely isolated: keys are not interchangeable between environments, and data does not cross over.

```bash
curl https://api.creem.io/v1/products/search \
  -H "x-api-key: creem_YOUR_API_KEY"
```

Missing or invalid keys return `401` (missing) or `403` (invalid/insufficient permissions).

## Quickstart: Selling a Product

The canonical payment flow has three steps:

**1. Create a checkout session** (server-side, with your secret API key):

```bash
curl -X POST https://api.creem.io/v1/checkouts \
  -H "x-api-key: creem_YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"product_id": "prod_abc123", "success_url": "https://yoursite.com/success", "customer": {"email": "user@example.com"}, "metadata": {"userId": "user_123"}, "discount_code": "LAUNCH20"}'
```

The response is a `CheckoutEntity` whose `checkout_url` you redirect the customer to. Creem hosts the payment page (cards, PayPal, Apple Pay, Google Pay); test mode accepts the [test cards](#test-mode) without real charges.

**2. Handle the payment result.** Production integrations use webhooks (see [Webhooks](#webhooks)): grant access on `checkout.completed` / `subscription.paid`, revoke on `subscription.canceled` / `subscription.expired`. Simpler scripts can poll `GET /v1/checkouts?checkout_id=...` and watch for `status: completed`.

**3. Map payments to your users.** Pass an internal user reference in `metadata` (e.g. `userId`); it is echoed back on checkout responses and webhook payloads.

```python
# Minimal Python client sketch (the SDK will wrap this):
import httpx

client = httpx.Client(
    base_url="https://api.creem.io/v1",
    headers={"x-api-key": "creem_YOUR_API_KEY"},
)
resp = client.post("/checkouts", json={
    "product_id": "prod_abc123",
    "success_url": "https://yoursite.com/success",
    "metadata": {"userId": "user_123"},
})
resp.raise_for_status()
checkout_url = resp.json()["checkout_url"]
```

---


## API Conventions

- **Content type:** request bodies are `application/json`; responses are JSON.
- **Timestamps:** ISO-8601 strings (`2024-10-12T11:58:33.097Z`) for resource timestamps; epoch **milliseconds** for webhook envelope `created_at` and error `timestamp`.
- **Pagination:** list endpoints use `page_number` (default 1) and `page_size` (default 10) query parameters. The customer-credits list endpoints use cursor-style pagination with `has_more` in the response.
- **Nulls:** nullable fields are returned as `null`, not omitted.
- **Environment marker:** every object carries a `mode` field (`test`, `prod`, `sandbox`) identifying the environment it was created in.
- **Idempotency:** checkouts accept a `request_id` to identify and track each checkout request.

---

## Error Handling

Errors return a JSON body with this shape:

```json
{
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": 400,
  "error": "Bad Request",
  "message": ["The 'product_id' field is required."],
  "timestamp": 1706889600000
}
```

| Field | Type | Description |
|---|---|---|
| `trace_id` | string | Unique request identifier — include it in support requests |
| `status` | number | HTTP status code |
| `error` | string | Error category |
| `message` | string[] | Human-readable error messages (may be empty) |
| `timestamp` | number | Unix timestamp in milliseconds |

| Status | Error | When it occurs |
|---|---|---|
| `200` | OK | Successful request |
| `400` | Bad Request | Invalid parameters, malformed JSON, validation errors, duplicate resource |
| `401` | Unauthorized | Missing API key |
| `403` | Forbidden | Invalid API key or insufficient permissions |
| `404` | Not Found | Resource does not exist (or wrong environment) |
| `429` | Rate limit exceeded | Too many requests |
| `500` | Internal Server Error | Server-side failure |

Validation failures list the offending fields in `message` (e.g. `["product_id must be a string", "success_url must be a valid URL"]`).

---

## Endpoints

Operations are grouped by resource. All paths are relative to the base URL (see [Authentication & Environments](#authentication--environments)).

### Products

### `GET /v1/products/search` — List all products

Search and retrieve a paginated list of products. Filter by status, billing type, and other criteria.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `searchProducts`.


**Query parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `page_number` | number | no (default: `1`) | The page number for pagination. |
| `page_size` | number | no (default: `10`) | The number of items per page. |
| `status` | ProductStatus | no | Lifecycle status of the product: `active` or `archived`. |


**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully retrieved products | ProductListEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `ProductListEntity`:**

- `items` *(array<ProductEntity>, required)* — List of product items
  *(fields of `ProductEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value.
  - `name` *(string, required)* — The name of the product
  - `description` *(string, required)* — A brief description of the product — e.g. `This is a sample product description.`
  - `image_url` *(string, optional)* — URL of the product image. Only png as jpg are supported — e.g. `https://example.com/image.jpg`
  - `image_urls` *(array<string>, optional)* — Ordered list of product image URLs. The first entry is the cover image (mirrored in image_url). — e.g. `['https://example.com/image.jpg']`
  - `features` *(array<FeatureEntity>, optional)* — Features of the product.
    *(fields of `FeatureEntity`)*
    - `id` *(string, required)* — Unique identifier for the feature. — e.g. `feat_abc123`
    - `type` *(ProductFeatureType, required)* — e.g. `licenseKey`
    - `description` *(string, required)* — A brief description of the feature. — e.g. `Access to premium course materials.`
  - `price` *(number, required)* — The price of the product in cents. 1000 = $10.00 — e.g. `400`
  - `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
  - `billing_type` *(ProductBillingType, required)* — e.g. `recurring`
  - `billing_period` *(ProductBillingPeriod, required)* — e.g. `every-month`
  - `status` *(ProductStatus, required)* — e.g. `active`
  - `tax_mode` *(TaxMode, required)* — e.g. `inclusive`
  - `tax_category` *(TaxCategory, required)* — e.g. `saas`
  - `product_url` *(string, optional)* — The product page you can redirect your customers to for express checkout. — e.g. `https://creem.io/product/prod_123123123123`
  - `default_success_url` *(string, optional)* — The URL to which the user will be redirected after successfull payment. — e.g. `https://example.com/?status=successful`
  - `custom_fields` *(array<CustomField>, optional)* — Custom fields configured for the product. Collect additional information from your customer during checkout.
    *(fields of `CustomField`)*
    - `type` *(CustomFieldType, required)*
    - `key` *(string, required)* — Unique key for custom field. Must be unique to this field, alphanumeric, and up to 200 characters.
    - `label` *(string, required)* — The label for the field, displayed to the customer, up to 50 characters
    - `optional` *(boolean, optional)* — Whether the customer is required to complete the field. Defaults to `false`.
    - `text` *(Text, optional)* — Configuration for text field type.
      - `max_length` *(number, optional)* — Maximum character length constraint for the input.
      - `minimum_length` *(number, optional)* — Minimum character length requirement for the input.
      - `value` *(string, optional)* — The value of the input.
    - `checkbox` *(Checkbox, optional)* — Configuration for checkbox field type.
      - `label` *(string, optional)* — The markdown text to display for the checkbox.
      - `value` *(boolean, optional)* — The value of the checkbox (checked or not).
  - `created_at` *(string, required)* — Creation date of the product — e.g. `2023-01-01T00:00:00Z`
  - `updated_at` *(string, required)* — Last updated date of the product — e.g. `2023-01-01T00:00:00Z`
- `pagination` *(PaginationEntity, required)* — Pagination details for the list
  - `total_records` *(number, required)* — Total number of records in the list — e.g. `0`
  - `total_pages` *(number, required)* — Total number of pages available — e.g. `0`
  - `current_page` *(number, required)* — The current page number — e.g. `1`
  - `next_page` *(number, required)* — The next page number, or null if there is no next page — e.g. `2`
  - `prev_page` *(number, required)* — The previous page number, or null if there is no previous page

---

### `POST /v1/products` — Creates a new product.

Create a new product for one-time payments, including free products with a 0 price, or subscriptions. Configure pricing, billing cycles, and features.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `createProduct`.


**Query parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `Idempotency-Key` | string | no | Optional key that makes retries return the originally created product instead of creating a duplicate. |

**Request body** (application/json, required):

Schema: `CreateProductRequestEntity`

- `name` *(string, required)* — Name of the product
- `description` *(string, required)* — Description of the product
- `image_url` *(string, optional)* — URL of the product image — e.g. `https://picsum.photos/200/300`
- `image_urls` *(array<string>, optional)* — Ordered list of product image URLs (max 8). The first entry is the cover image; when provided it takes precedence over image_url. — e.g. `['https://picsum.photos/200/300', 'https://picsum.photos/200/301']`
- `price` *(integer, required)* — The price of the product in cents. Must be 0 (free product) or at least 100 (one whole unit of the currency). — e.g. `400`
- `currency` *(ProductCurrency, required)* — e.g. `USD`
- `billing_type` *(ProductRequestBillingType, required)* — e.g. `recurring`
- `billing_period` *(ProductRequestBillingPeriod, optional)* — e.g. `every-month`
- `tax_mode` *(TaxMode, optional)* — e.g. `inclusive`
- `tax_category` *(TaxCategory, optional)* — e.g. `saas`
- `pay_what_you_want` *(boolean, optional)* — Enable pay-what-you-want pricing: the customer chooses the amount at checkout. The `price` field acts as the minimum the customer must pay. Only supported for one-time payment products. — e.g. `False`
- `suggested_price` *(integer, optional)* — Suggested amount in cents, pre-filled at checkout when pay_what_you_want is enabled. Must be greater than or equal to `price` (the minimum). Ignored when pay_what_you_want is disabled. — e.g. `1500`
- `default_success_url` *(string, optional)* — The URL to which the user will be redirected after successfull payment. — e.g. `https://example.com/?status=successful`
- `custom_fields` *(array<CustomFieldRequestEntity>, optional)* — Collect additional information from your customer using custom fields during checkout. Up to 3 fields are supported.
  *(fields of `CustomFieldRequestEntity`)*
  - `type` *(CustomFieldRequestType, required)* — e.g. `text`
  - `key` *(string, required)* — Unique key for custom field. Must be unique to this field, alphanumeric, and up to 200 characters. — e.g. `companyName`
  - `label` *(string, required)* — The label for the field, displayed to the customer, up to 50 characters. — e.g. `Company Name`
  - `optional` *(boolean, optional)* — Whether the customer is required to complete the field. Defaults to `false`
  - `text` *(TextFieldConfig, optional)* — Configuration for text field type.
    - `max_length` *(number, optional)* — Maximum character length constraint for the input. — e.g. `200`
    - `min_length` *(number, optional)* — Minimum character length requirement for the input. — e.g. `1`
  - `checkbox` *(CheckboxFieldConfig, optional)* — Configuration for checkbox field type.
    - `label` *(string, optional)* — The markdown text to display for the checkbox. — e.g. `I agree to the [terms and conditions](https://example.com/terms)`
- `custom_field` *(array<CustomFieldRequestEntity>, optional)* — DEPRECATED: Use `custom_fields` instead. Collect additional information from your customer using custom fields during checkout. Up to 3 fields are supported.
  *(fields of `CustomFieldRequestEntity`)*
  - `type` *(CustomFieldRequestType, required)* — e.g. `text`
  - `key` *(string, required)* — Unique key for custom field. Must be unique to this field, alphanumeric, and up to 200 characters. — e.g. `companyName`
  - `label` *(string, required)* — The label for the field, displayed to the customer, up to 50 characters. — e.g. `Company Name`
  - `optional` *(boolean, optional)* — Whether the customer is required to complete the field. Defaults to `false`
  - `text` *(TextFieldConfig, optional)* — Configuration for text field type.
    - `max_length` *(number, optional)* — Maximum character length constraint for the input. — e.g. `200`
    - `min_length` *(number, optional)* — Minimum character length requirement for the input. — e.g. `1`
  - `checkbox` *(CheckboxFieldConfig, optional)* — Configuration for checkbox field type.
    - `label` *(string, optional)* — The markdown text to display for the checkbox. — e.g. `I agree to the [terms and conditions](https://example.com/terms)`
- `abandoned_cart_recovery_enabled` *(boolean, optional)* — Enable abandoned cart recovery for this product

**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully created a product | ProductEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `ProductEntity`:**

- `id` *(string, required)* — Unique identifier for the object.
- `mode` *(EnvironmentMode, required)*
- `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value.
- `name` *(string, required)* — The name of the product
- `description` *(string, required)* — A brief description of the product — e.g. `This is a sample product description.`
- `image_url` *(string, optional)* — URL of the product image. Only png as jpg are supported — e.g. `https://example.com/image.jpg`
- `image_urls` *(array<string>, optional)* — Ordered list of product image URLs. The first entry is the cover image (mirrored in image_url). — e.g. `['https://example.com/image.jpg']`
- `features` *(array<FeatureEntity>, optional)* — Features of the product.
  *(fields of `FeatureEntity`)*
  - `id` *(string, required)* — Unique identifier for the feature. — e.g. `feat_abc123`
  - `type` *(ProductFeatureType, required)* — e.g. `licenseKey`
  - `description` *(string, required)* — A brief description of the feature. — e.g. `Access to premium course materials.`
- `price` *(number, required)* — The price of the product in cents. 1000 = $10.00 — e.g. `400`
- `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
- `billing_type` *(ProductBillingType, required)* — e.g. `recurring`
- `billing_period` *(ProductBillingPeriod, required)* — e.g. `every-month`
- `status` *(ProductStatus, required)* — e.g. `active`
- `tax_mode` *(TaxMode, required)* — e.g. `inclusive`
- `tax_category` *(TaxCategory, required)* — e.g. `saas`
- `product_url` *(string, optional)* — The product page you can redirect your customers to for express checkout. — e.g. `https://creem.io/product/prod_123123123123`
- `default_success_url` *(string, optional)* — The URL to which the user will be redirected after successfull payment. — e.g. `https://example.com/?status=successful`
- `custom_fields` *(array<CustomField>, optional)* — Custom fields configured for the product. Collect additional information from your customer during checkout.
  *(fields of `CustomField`)*
  - `type` *(CustomFieldType, required)*
  - `key` *(string, required)* — Unique key for custom field. Must be unique to this field, alphanumeric, and up to 200 characters.
  - `label` *(string, required)* — The label for the field, displayed to the customer, up to 50 characters
  - `optional` *(boolean, optional)* — Whether the customer is required to complete the field. Defaults to `false`.
  - `text` *(Text, optional)* — Configuration for text field type.
    - `max_length` *(number, optional)* — Maximum character length constraint for the input.
    - `minimum_length` *(number, optional)* — Minimum character length requirement for the input.
    - `value` *(string, optional)* — The value of the input.
  - `checkbox` *(Checkbox, optional)* — Configuration for checkbox field type.
    - `label` *(string, optional)* — The markdown text to display for the checkbox.
    - `value` *(boolean, optional)* — The value of the checkbox (checked or not).
- `created_at` *(string, required)* — Creation date of the product — e.g. `2023-01-01T00:00:00Z`
- `updated_at` *(string, required)* — Last updated date of the product — e.g. `2023-01-01T00:00:00Z`

---

### `GET /v1/products/{id}` — Get a product by ID

Retrieve a single product by its unique identifier.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `getProduct`.


**Path parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | The product ID |


**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully retrieved the product | ProductEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `ProductEntity`:**

- `id` *(string, required)* — Unique identifier for the object.
- `mode` *(EnvironmentMode, required)*
- `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value.
- `name` *(string, required)* — The name of the product
- `description` *(string, required)* — A brief description of the product — e.g. `This is a sample product description.`
- `image_url` *(string, optional)* — URL of the product image. Only png as jpg are supported — e.g. `https://example.com/image.jpg`
- `image_urls` *(array<string>, optional)* — Ordered list of product image URLs. The first entry is the cover image (mirrored in image_url). — e.g. `['https://example.com/image.jpg']`
- `features` *(array<FeatureEntity>, optional)* — Features of the product.
  *(fields of `FeatureEntity`)*
  - `id` *(string, required)* — Unique identifier for the feature. — e.g. `feat_abc123`
  - `type` *(ProductFeatureType, required)* — e.g. `licenseKey`
  - `description` *(string, required)* — A brief description of the feature. — e.g. `Access to premium course materials.`
- `price` *(number, required)* — The price of the product in cents. 1000 = $10.00 — e.g. `400`
- `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
- `billing_type` *(ProductBillingType, required)* — e.g. `recurring`
- `billing_period` *(ProductBillingPeriod, required)* — e.g. `every-month`
- `status` *(ProductStatus, required)* — e.g. `active`
- `tax_mode` *(TaxMode, required)* — e.g. `inclusive`
- `tax_category` *(TaxCategory, required)* — e.g. `saas`
- `product_url` *(string, optional)* — The product page you can redirect your customers to for express checkout. — e.g. `https://creem.io/product/prod_123123123123`
- `default_success_url` *(string, optional)* — The URL to which the user will be redirected after successfull payment. — e.g. `https://example.com/?status=successful`
- `custom_fields` *(array<CustomField>, optional)* — Custom fields configured for the product. Collect additional information from your customer during checkout.
  *(fields of `CustomField`)*
  - `type` *(CustomFieldType, required)*
  - `key` *(string, required)* — Unique key for custom field. Must be unique to this field, alphanumeric, and up to 200 characters.
  - `label` *(string, required)* — The label for the field, displayed to the customer, up to 50 characters
  - `optional` *(boolean, optional)* — Whether the customer is required to complete the field. Defaults to `false`.
  - `text` *(Text, optional)* — Configuration for text field type.
    - `max_length` *(number, optional)* — Maximum character length constraint for the input.
    - `minimum_length` *(number, optional)* — Minimum character length requirement for the input.
    - `value` *(string, optional)* — The value of the input.
  - `checkbox` *(Checkbox, optional)* — Configuration for checkbox field type.
    - `label` *(string, optional)* — The markdown text to display for the checkbox.
    - `value` *(boolean, optional)* — The value of the checkbox (checked or not).
- `created_at` *(string, required)* — Creation date of the product — e.g. `2023-01-01T00:00:00Z`
- `updated_at` *(string, required)* — Last updated date of the product — e.g. `2023-01-01T00:00:00Z`

---

### `PATCH /v1/products/{id}` — Update a product

Update a product. Only supplied fields change; a price change mints a new default price.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `updateProduct`.


**Path parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | The product ID |

**Request body** (application/json, required):

Schema: `UpdateProductRequestEntity`

- `name` *(string, optional)* — Name of the product
- `description` *(string, optional)* — Description of the product
- `image_url` *(string, optional)* — URL of the product image
- `image_urls` *(array<string>, optional)* — Ordered list of product image URLs (max 8). The first entry is the cover image; when provided it takes precedence over image_url. An empty list removes all images.
- `default_success_url` *(string, optional)* — Redirect URL after successful payment.
- `price` *(integer, optional)* — The price of the product in cents. Must be 0 (free product) or at least 100 (one whole unit of the currency).
- `currency` *(ProductCurrency, optional)* — e.g. `USD`
- `billing_type` *(ProductRequestBillingType, optional)* — e.g. `recurring`
- `billing_period` *(ProductRequestBillingPeriod, optional)* — e.g. `every-month`
- `tax_mode` *(TaxMode, optional)* — e.g. `inclusive`
- `pay_what_you_want` *(boolean, optional)* — Enable pay-what-you-want pricing (one-time only).
- `suggested_price` *(integer, optional)* — Suggested amount in cents when pay_what_you_want is enabled.

**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully updated the product | ProductEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `ProductEntity`:**

- `id` *(string, required)* — Unique identifier for the object.
- `mode` *(EnvironmentMode, required)*
- `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value.
- `name` *(string, required)* — The name of the product
- `description` *(string, required)* — A brief description of the product — e.g. `This is a sample product description.`
- `image_url` *(string, optional)* — URL of the product image. Only png as jpg are supported — e.g. `https://example.com/image.jpg`
- `image_urls` *(array<string>, optional)* — Ordered list of product image URLs. The first entry is the cover image (mirrored in image_url). — e.g. `['https://example.com/image.jpg']`
- `features` *(array<FeatureEntity>, optional)* — Features of the product.
  *(fields of `FeatureEntity`)*
  - `id` *(string, required)* — Unique identifier for the feature. — e.g. `feat_abc123`
  - `type` *(ProductFeatureType, required)* — e.g. `licenseKey`
  - `description` *(string, required)* — A brief description of the feature. — e.g. `Access to premium course materials.`
- `price` *(number, required)* — The price of the product in cents. 1000 = $10.00 — e.g. `400`
- `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
- `billing_type` *(ProductBillingType, required)* — e.g. `recurring`
- `billing_period` *(ProductBillingPeriod, required)* — e.g. `every-month`
- `status` *(ProductStatus, required)* — e.g. `active`
- `tax_mode` *(TaxMode, required)* — e.g. `inclusive`
- `tax_category` *(TaxCategory, required)* — e.g. `saas`
- `product_url` *(string, optional)* — The product page you can redirect your customers to for express checkout. — e.g. `https://creem.io/product/prod_123123123123`
- `default_success_url` *(string, optional)* — The URL to which the user will be redirected after successfull payment. — e.g. `https://example.com/?status=successful`
- `custom_fields` *(array<CustomField>, optional)* — Custom fields configured for the product. Collect additional information from your customer during checkout.
  *(fields of `CustomField`)*
  - `type` *(CustomFieldType, required)*
  - `key` *(string, required)* — Unique key for custom field. Must be unique to this field, alphanumeric, and up to 200 characters.
  - `label` *(string, required)* — The label for the field, displayed to the customer, up to 50 characters
  - `optional` *(boolean, optional)* — Whether the customer is required to complete the field. Defaults to `false`.
  - `text` *(Text, optional)* — Configuration for text field type.
    - `max_length` *(number, optional)* — Maximum character length constraint for the input.
    - `minimum_length` *(number, optional)* — Minimum character length requirement for the input.
    - `value` *(string, optional)* — The value of the input.
  - `checkbox` *(Checkbox, optional)* — Configuration for checkbox field type.
    - `label` *(string, optional)* — The markdown text to display for the checkbox.
    - `value` *(boolean, optional)* — The value of the checkbox (checked or not).
- `created_at` *(string, required)* — Creation date of the product — e.g. `2023-01-01T00:00:00Z`
- `updated_at` *(string, required)* — Last updated date of the product — e.g. `2023-01-01T00:00:00Z`

---

### `DELETE /v1/products/{id}` — Archive a product

Archive a product (soft-delete). The product is retained for historical orders and subscriptions but can no longer be purchased.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `archiveProduct`.


**Path parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | The product ID |


**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully archived the product | ProductEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `ProductEntity`:**

- `id` *(string, required)* — Unique identifier for the object.
- `mode` *(EnvironmentMode, required)*
- `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value.
- `name` *(string, required)* — The name of the product
- `description` *(string, required)* — A brief description of the product — e.g. `This is a sample product description.`
- `image_url` *(string, optional)* — URL of the product image. Only png as jpg are supported — e.g. `https://example.com/image.jpg`
- `image_urls` *(array<string>, optional)* — Ordered list of product image URLs. The first entry is the cover image (mirrored in image_url). — e.g. `['https://example.com/image.jpg']`
- `features` *(array<FeatureEntity>, optional)* — Features of the product.
  *(fields of `FeatureEntity`)*
  - `id` *(string, required)* — Unique identifier for the feature. — e.g. `feat_abc123`
  - `type` *(ProductFeatureType, required)* — e.g. `licenseKey`
  - `description` *(string, required)* — A brief description of the feature. — e.g. `Access to premium course materials.`
- `price` *(number, required)* — The price of the product in cents. 1000 = $10.00 — e.g. `400`
- `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
- `billing_type` *(ProductBillingType, required)* — e.g. `recurring`
- `billing_period` *(ProductBillingPeriod, required)* — e.g. `every-month`
- `status` *(ProductStatus, required)* — e.g. `active`
- `tax_mode` *(TaxMode, required)* — e.g. `inclusive`
- `tax_category` *(TaxCategory, required)* — e.g. `saas`
- `product_url` *(string, optional)* — The product page you can redirect your customers to for express checkout. — e.g. `https://creem.io/product/prod_123123123123`
- `default_success_url` *(string, optional)* — The URL to which the user will be redirected after successfull payment. — e.g. `https://example.com/?status=successful`
- `custom_fields` *(array<CustomField>, optional)* — Custom fields configured for the product. Collect additional information from your customer during checkout.
  *(fields of `CustomField`)*
  - `type` *(CustomFieldType, required)*
  - `key` *(string, required)* — Unique key for custom field. Must be unique to this field, alphanumeric, and up to 200 characters.
  - `label` *(string, required)* — The label for the field, displayed to the customer, up to 50 characters
  - `optional` *(boolean, optional)* — Whether the customer is required to complete the field. Defaults to `false`.
  - `text` *(Text, optional)* — Configuration for text field type.
    - `max_length` *(number, optional)* — Maximum character length constraint for the input.
    - `minimum_length` *(number, optional)* — Minimum character length requirement for the input.
    - `value` *(string, optional)* — The value of the input.
  - `checkbox` *(Checkbox, optional)* — Configuration for checkbox field type.
    - `label` *(string, optional)* — The markdown text to display for the checkbox.
    - `value` *(boolean, optional)* — The value of the checkbox (checked or not).
- `created_at` *(string, required)* — Creation date of the product — e.g. `2023-01-01T00:00:00Z`
- `updated_at` *(string, required)* — Last updated date of the product — e.g. `2023-01-01T00:00:00Z`

---

### Checkouts

### `GET /v1/checkouts` — Retrieve a checkout session.

Retrieve details of a checkout session by ID. View status, customer info, and payment details.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `retrieveCheckout`.


**Query parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `checkout_id` | string | yes | The ID of the checkout session to retrieve. |


**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully retrieved the checkout session | CheckoutEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `CheckoutEntity`:**

- `id` *(string, required)* — Unique identifier for the object.
- `mode` *(EnvironmentMode, required)*
- `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value.
- `status` *(enum: pending|processing|completed|expired, required)* — Status of the checkout. — e.g. `completed`
- `request_id` *(string, optional)* — Identify and track each checkout request.
- `product` *(string | ProductEntity, required)* — The product associated with the checkout session.
  *(fields of `ProductEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value.
  - `name` *(string, required)* — The name of the product
  - `description` *(string, required)* — A brief description of the product — e.g. `This is a sample product description.`
  - `image_url` *(string, optional)* — URL of the product image. Only png as jpg are supported — e.g. `https://example.com/image.jpg`
  - `image_urls` *(array<string>, optional)* — Ordered list of product image URLs. The first entry is the cover image (mirrored in image_url). — e.g. `['https://example.com/image.jpg']`
  - `features` *(array<FeatureEntity>, optional)* — Features of the product.
    *(fields of `FeatureEntity`)*
    - `id` *(string, required)* — Unique identifier for the feature. — e.g. `feat_abc123`
    - `type` *(ProductFeatureType, required)* — e.g. `licenseKey`
    - `description` *(string, required)* — A brief description of the feature. — e.g. `Access to premium course materials.`
  - `price` *(number, required)* — The price of the product in cents. 1000 = $10.00 — e.g. `400`
  - `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
  - `billing_type` *(ProductBillingType, required)* — e.g. `recurring`
  - `billing_period` *(ProductBillingPeriod, required)* — e.g. `every-month`
  - `status` *(ProductStatus, required)* — e.g. `active`
  - `tax_mode` *(TaxMode, required)* — e.g. `inclusive`
  - `tax_category` *(TaxCategory, required)* — e.g. `saas`
  - `product_url` *(string, optional)* — The product page you can redirect your customers to for express checkout. — e.g. `https://creem.io/product/prod_123123123123`
  - `default_success_url` *(string, optional)* — The URL to which the user will be redirected after successfull payment. — e.g. `https://example.com/?status=successful`
  - `custom_fields` *(array<CustomField>, optional)* — Custom fields configured for the product. Collect additional information from your customer during checkout.
    *(fields of `CustomField`)*
    - `type` *(CustomFieldType, required)*
    - `key` *(string, required)* — Unique key for custom field. Must be unique to this field, alphanumeric, and up to 200 characters.
    - `label` *(string, required)* — The label for the field, displayed to the customer, up to 50 characters
    - `optional` *(boolean, optional)* — Whether the customer is required to complete the field. Defaults to `false`.
    - `text` *(Text, optional)* — Configuration for text field type.
      - `max_length` *(number, optional)* — Maximum character length constraint for the input.
      - `minimum_length` *(number, optional)* — Minimum character length requirement for the input.
      - `value` *(string, optional)* — The value of the input.
    - `checkbox` *(Checkbox, optional)* — Configuration for checkbox field type.
      - `label` *(string, optional)* — The markdown text to display for the checkbox.
      - `value` *(boolean, optional)* — The value of the checkbox (checked or not).
  - `created_at` *(string, required)* — Creation date of the product — e.g. `2023-01-01T00:00:00Z`
  - `updated_at` *(string, required)* — Last updated date of the product — e.g. `2023-01-01T00:00:00Z`
- `units` *(number, optional)* — The number of units for the of the product.
- `custom_price` *(integer, optional)* — The per-unit price override (in cents, product currency) this checkout was created with. Only present when the checkout was created with a custom_price. One-time payment products only. — e.g. `1500`
- `order` *(OrderEntity, optional)* — The order associated with the checkout session.
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value.
  - `customer` *(string, optional)* — The customer who placed the order.
  - `product` *(string, required)* — The product associated with the order.
  - `transaction` *(string, optional)* — The transaction ID of the order — e.g. `tx_1234567890`
  - `discount` *(string, optional)* — The discount ID of the order — e.g. `dis_1234567890`
  - `amount` *(number, required)* — The total amount of the order in cents. 1000 = $10.00 — e.g. `2000`
  - `sub_total` *(number, optional)* — The subtotal of the order in cents. 1000 = $10.00 — e.g. `1800`
  - `tax_amount` *(number, optional)* — The tax amount of the order in cents. 1000 = $10.00 — e.g. `200`
  - `discount_amount` *(number, optional)* — The discount amount of the order in cents. 1000 = $10.00 — e.g. `100`
  - `amount_due` *(number, optional)* — The amount due for the order in cents. 1000 = $10.00 — e.g. `1900`
  - `amount_paid` *(number, optional)* — The amount paid for the order in cents. 1000 = $10.00 — e.g. `1900`
  - `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
  - `fx_amount` *(number, optional)* — The amount in the foreign currency, if applicable. — e.g. `15`
  - `fx_currency` *(string, optional)* — Three-letter ISO code of the foreign currency, if applicable. — e.g. `EUR`
  - `fx_rate` *(number, optional)* — The exchange rate used for converting between currencies, if applicable. — e.g. `1.2`
  - `status` *(OrderStatus, required)* — e.g. `pending`
  - `type` *(OrderType, required)* — e.g. `recurring`
  - `affiliate` *(string, optional)* — The affiliate associated with the order, if applicable.
  - `created_at` *(string, required)* — Creation date of the order — e.g. `2023-09-13T00:00:00Z`
  - `updated_at` *(string, required)* — Last updated date of the order — e.g. `2023-09-13T00:00:00Z`
- `subscription` *(string | SubscriptionEntity, optional)* — The subscription associated with the checkout session.
  *(fields of `SubscriptionEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value. — e.g. `subscription`
  - `product` *(ProductEntity | string, required)* — The product associated with the subscription.
    *(fields of `ProductEntity`)*
    - `id` *(string, required)* — Unique identifier for the object.
    - `mode` *(EnvironmentMode, required)*
    - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value.
    - `name` *(string, required)* — The name of the product
    - `description` *(string, required)* — A brief description of the product — e.g. `This is a sample product description.`
    - `image_url` *(string, optional)* — URL of the product image. Only png as jpg are supported — e.g. `https://example.com/image.jpg`
    - `image_urls` *(array<string>, optional)* — Ordered list of product image URLs. The first entry is the cover image (mirrored in image_url). — e.g. `['https://example.com/image.jpg']`
    - `features` *(array<FeatureEntity>, optional)* — Features of the product.
      *(fields of `FeatureEntity`)*
      - `id` *(string, required)* — Unique identifier for the feature. — e.g. `feat_abc123`
      - `type` *(ProductFeatureType, required)* — e.g. `licenseKey`
      - `description` *(string, required)* — A brief description of the feature. — e.g. `Access to premium course materials.`
    - `price` *(number, required)* — The price of the product in cents. 1000 = $10.00 — e.g. `400`
    - `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
    - `billing_type` *(ProductBillingType, required)* — e.g. `recurring`
    - `billing_period` *(ProductBillingPeriod, required)* — e.g. `every-month`
    - `status` *(ProductStatus, required)* — e.g. `active`
    - `tax_mode` *(TaxMode, required)* — e.g. `inclusive`
    - `tax_category` *(TaxCategory, required)* — e.g. `saas`
    - `product_url` *(string, optional)* — The product page you can redirect your customers to for express checkout. — e.g. `https://creem.io/product/prod_123123123123`
    - `default_success_url` *(string, optional)* — The URL to which the user will be redirected after successfull payment. — e.g. `https://example.com/?status=successful`
    - `custom_fields` *(array<CustomField>, optional)* — Custom fields configured for the product. Collect additional information from your customer during checkout.
      *(fields of `CustomField`)*
      - `type` *(CustomFieldType, required)*
      - `key` *(string, required)* — Unique key for custom field. Must be unique to this field, alphanumeric, and up to 200 characters.
      - `label` *(string, required)* — The label for the field, displayed to the customer, up to 50 characters
      - `optional` *(boolean, optional)* — Whether the customer is required to complete the field. Defaults to `false`.
      - `text` *(Text, optional)* — Configuration for text field type.
        - `max_length` *(number, optional)* — Maximum character length constraint for the input.
        - `minimum_length` *(number, optional)* — Minimum character length requirement for the input.
        - `value` *(string, optional)* — The value of the input.
      - `checkbox` *(Checkbox, optional)* — Configuration for checkbox field type.
        - `label` *(string, optional)* — The markdown text to display for the checkbox.
        - `value` *(boolean, optional)* — The value of the checkbox (checked or not).
    - `created_at` *(string, required)* — Creation date of the product — e.g. `2023-01-01T00:00:00Z`
    - `updated_at` *(string, required)* — Last updated date of the product — e.g. `2023-01-01T00:00:00Z`
  - `customer` *(CustomerEntity | string, required)* — The customer who owns the subscription.
    *(fields of `CustomerEntity`)*
    - `id` *(string, required)* — Unique identifier for the object.
    - `mode` *(EnvironmentMode, required)*
    - `object` *(string, required)* — String representing the object’s type. Objects of the same type share the same value.
    - `email` *(string, required)* — Customer email address. — e.g. `user@example.com`
    - `name` *(string, optional)* — Customer name. — e.g. `John Doe`
    - `metadata` *(object, optional)* — Additional metadata associated with the customer. — e.g. `{'key': 'value'}`
    - `country` *(string, required)* — The ISO 3166-1 alpha-2 country code for the customer. — e.g. `US`
    - `created_at` *(string, required)* — Creation date of the customer — e.g. `2023-01-01T00:00:00Z`
    - `updated_at` *(string, required)* — Last updated date of the customer — e.g. `2023-01-01T00:00:00Z`
  - `items` *(array<SubscriptionItemEntity>, optional)* — Subscription items.
    *(fields of `SubscriptionItemEntity`)*
    - `id` *(string, required)* — Unique identifier for the object.
    - `mode` *(EnvironmentMode, required)*
    - `object` *(string, required)* — String representing the object’s type. Objects of the same type share the same value.
    - `product_id` *(string, optional)* — The ID of the product associated with the subscription item.
    - `price_id` *(string, optional)* — The ID of the price associated with the subscription item.
    - `units` *(number, optional)* — The number of units for the subscription item.
  - `collection_method` *(SubscriptionCollectionMethod, required)* — e.g. `charge_automatically`
  - `status` *(SubscriptionStatus, required)* — e.g. `active`
  - `last_transaction_id` *(string, optional)* — The ID of the last paid transaction. — e.g. `tran_3e6Z6TzvHKdsjEgXnGDEp0`
  - `last_transaction` *(TransactionEntity, optional)* — The last paid transaction.
    - `id` *(string, required)* — Unique identifier for the object.
    - `mode` *(EnvironmentMode, required)*
    - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value. — e.g. `transaction`
    - `amount` *(number, required)* — The transaction amount in cents. 1000 = $10.00 — e.g. `2000`
    - `amount_paid` *(number, optional)* — The amount the customer paid in cents. 1000 = $10.00 — e.g. `2000`
    - `discount_amount` *(number, optional)* — The discount amount in cents. 1000 = $10.00 — e.g. `2000`
    - `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
    - `type` *(TransactionType, required)*
    - `tax_country` *(string, optional)* — The ISO alpha-2 country code where tax is collected. — e.g. `US`
    - `tax_amount` *(number, optional)* — The sale tax amount in cents. 1000 = $10.00 — e.g. `2000`
    - `status` *(TransactionStatus, required)*
    - `refunded_amount` *(number, optional)* — The amount that has been refunded in cents. 1000 = $10.00 — e.g. `2000`
    - `order` *(string, optional)* — The order associated with the transaction.
    - `subscription` *(string, optional)* — The subscription associated with the transaction.
    - `customer` *(string, optional)* — The customer associated with the transaction.
    - `description` *(string, optional)* — The description of the transaction.
    - `period_start` *(number, optional)* — Start period for the invoice as timestamp
    - `period_end` *(number, optional)* — End period for the invoice as timestamp
    - `created_at` *(number, required)* — Creation date of the order as timestamp
  - `last_transaction_date` *(string, optional)* — The date of the last paid transaction. — e.g. `2024-09-12T12:34:56Z`
  - `next_transaction_date` *(string, optional)* — The date when the next subscription transaction will be charged. — e.g. `2024-09-12T12:34:56Z`
  - `current_period_start_date` *(string, optional)* — The start date of the current subscription period. — e.g. `2024-09-12T12:34:56Z`
  - `current_period_end_date` *(string, optional)* — The end date of the current subscription period. — e.g. `2024-09-12T12:34:56Z`
  - `canceled_at` *(string, optional)* — The date and time when the subscription was canceled, if applicable. — e.g. `2024-09-12T12:34:56Z`
  - `created_at` *(string, required)* — The date and time when the subscription was created. — e.g. `2024-01-01T00:00:00Z`
  - `updated_at` *(string, required)* — The date and time when the subscription was last updated. — e.g. `2024-09-12T12:34:56Z`
  - `discount` *(object{id, discountCode, name, type, amount, duration, durationI...}, optional)* — The discount applied to the subscription, if any.
    - `id` *(string, optional)* — The unique identifier of the discount (e.g. dis_...). — e.g. `dis_3e6Z6TzvHKdsjEgXnGDEp0`
    - `discountCode` *(string, optional)* — The discount code applied to the subscription. — e.g. `HOLIDAY2024`
    - `name` *(string, optional)*
    - `type` *(enum: percentage|fixed, optional)*
    - `amount` *(number, optional)*
    - `duration` *(enum: forever|once|repeating, optional)*
    - `durationInMonths` *(number, optional)*
  - `metadata` *(object, optional)* — Metadata for the subscription in the form of key-value pairs. — e.g. `{'userId': 'user_123', 'plan': 'pro'}`
- `customer` *(string | CustomerEntity, optional)* — The customer associated with the checkout session.
  *(fields of `CustomerEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object’s type. Objects of the same type share the same value.
  - `email` *(string, required)* — Customer email address. — e.g. `user@example.com`
  - `name` *(string, optional)* — Customer name. — e.g. `John Doe`
  - `metadata` *(object, optional)* — Additional metadata associated with the customer. — e.g. `{'key': 'value'}`
  - `country` *(string, required)* — The ISO 3166-1 alpha-2 country code for the customer. — e.g. `US`
  - `created_at` *(string, required)* — Creation date of the customer — e.g. `2023-01-01T00:00:00Z`
  - `updated_at` *(string, required)* — Last updated date of the customer — e.g. `2023-01-01T00:00:00Z`
- `custom_fields` *(array<CustomField>, optional)* — Additional information collected from your customer during the checkout process.
  *(fields of `CustomField`)*
  - `type` *(CustomFieldType, required)*
  - `key` *(string, required)* — Unique key for custom field. Must be unique to this field, alphanumeric, and up to 200 characters.
  - `label` *(string, required)* — The label for the field, displayed to the customer, up to 50 characters
  - `optional` *(boolean, optional)* — Whether the customer is required to complete the field. Defaults to `false`.
  - `text` *(Text, optional)* — Configuration for text field type.
    - `max_length` *(number, optional)* — Maximum character length constraint for the input.
    - `minimum_length` *(number, optional)* — Minimum character length requirement for the input.
    - `value` *(string, optional)* — The value of the input.
  - `checkbox` *(Checkbox, optional)* — Configuration for checkbox field type.
    - `label` *(string, optional)* — The markdown text to display for the checkbox.
    - `value` *(boolean, optional)* — The value of the checkbox (checked or not).
- `checkout_url` *(string, optional)* — The URL to which the customer will be redirected to complete the payment.
- `success_url` *(string, optional)* — The URL to which the user will be redirected after the checkout process is completed. — e.g. `https://example.com/return`
- `license_keys` *(array<LicenseEntity>, optional)* — License keys issued for the order.
  *(fields of `LicenseEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — A string representing the object's type. Objects of the same type share the same value.
  - `product_id` *(string, required)* — The ID of the product this license belongs to. — e.g. `prod_abc123`
  - `status` *(LicenseStatus, required)* — e.g. `active`
  - `key` *(string, required)* — The license key. — e.g. `ABC123-XYZ456-XYZ456-XYZ456`
  - `activation` *(number, required)* — The number of instances that this license key was activated. — e.g. `5`
  - `activation_limit` *(number, optional)* — The activation limit. Null if activations are unlimited. — e.g. `1`
  - `expires_at` *(string, optional)* — The date the license key expires. Null if it does not have an expiration date. — e.g. `2023-09-13T00:00:00Z`
  - `created_at` *(string, required)* — The creation date of the license key. — e.g. `2023-09-13T00:00:00Z`
  - `instance` *(LicenseInstanceEntity, optional)* — Associated license instances.
    - `id` *(string, required)* — Unique identifier for the object.
    - `mode` *(EnvironmentMode, required)*
    - `object` *(string, required)* — A string representing the object’s type. Objects of the same type share the same value. — e.g. `license-instance`
    - `name` *(string, required)* — The name of the license instance. — e.g. `My Customer License Instance`
    - `status` *(enum: active|deactivated, required)* — The status of the license instance. — e.g. `active`
    - `created_at` *(string, required)* — The creation date of the license instance. — e.g. `2023-09-13T00:00:00Z`
- `feature` *(array<ProductFeatureEntity>, optional)* — DEPRECATED: Use `license_keys` instead. Features issued for the order.
  *(fields of `ProductFeatureEntity`)*
  - `id` *(string, optional)* — Unique identifier for the feature. — e.g. `feat_abc123`
  - `description` *(string, optional)* — A brief description of the feature. — e.g. `Get access to the full course materials.`
  - `type` *(ProductFeatureType, optional)* — e.g. `licenseKey`
  - `private_note` *(string, optional)* — Private note from the seller. This is only visible to the customer after purchase. — e.g. `Thank you for your purchase! Here is your access code: XYZ123`
  - `file` *(FileFeatureEntity, optional)* — File feature data containing downloadable files.
    - `files` *(array<FeatureFileEntity>, required)* — List of downloadable files.
      *(fields of `FeatureFileEntity`)*
      - `id` *(string, required)* — Unique identifier for the file. — e.g. `file_abc123`
      - `file_name` *(string, required)* — The name of the file. — e.g. `ebook.pdf`
      - `url` *(string, required)* — The URL to download the file. — e.g. `https://storage.creem.io/files/ebook.pdf`
      - `type` *(string, required)* — The MIME type of the file. — e.g. `application/pdf`
      - `size` *(number, required)* — The size of the file in bytes. — e.g. `1024000`
  - `license_key` *(LicenseEntity, optional)* — License key issued for the order.
    - `id` *(string, required)* — Unique identifier for the object.
    - `mode` *(EnvironmentMode, required)*
    - `object` *(string, required)* — A string representing the object's type. Objects of the same type share the same value.
    - `product_id` *(string, required)* — The ID of the product this license belongs to. — e.g. `prod_abc123`
    - `status` *(LicenseStatus, required)* — e.g. `active`
    - `key` *(string, required)* — The license key. — e.g. `ABC123-XYZ456-XYZ456-XYZ456`
    - `activation` *(number, required)* — The number of instances that this license key was activated. — e.g. `5`
    - `activation_limit` *(number, optional)* — The activation limit. Null if activations are unlimited. — e.g. `1`
    - `expires_at` *(string, optional)* — The date the license key expires. Null if it does not have an expiration date. — e.g. `2023-09-13T00:00:00Z`
    - `created_at` *(string, required)* — The creation date of the license key. — e.g. `2023-09-13T00:00:00Z`
    - `instance` *(LicenseInstanceEntity, optional)* — Associated license instances.
      - `id` *(string, required)* — Unique identifier for the object.
      - `mode` *(EnvironmentMode, required)*
      - `object` *(string, required)* — A string representing the object’s type. Objects of the same type share the same value. — e.g. `license-instance`
      - `name` *(string, required)* — The name of the license instance. — e.g. `My Customer License Instance`
      - `status` *(enum: active|deactivated, required)* — The status of the license instance. — e.g. `active`
      - `created_at` *(string, required)* — The creation date of the license instance. — e.g. `2023-09-13T00:00:00Z`
  - `customer_credits` *(CustomerCreditsFeatureEntity, optional)* — Customer credits feature data.
    - `amount` *(string, required)* — The number of credits to grant. String to preserve BigInt precision. — e.g. `100`
    - `unit_label` *(string, optional)* — Optional label for the credit unit (e.g. "tokens", "credits"). — e.g. `tokens`
  - `license` *(LicenseEntity, optional)* — DEPRECATED: Use `license_key` instead. License key issued for the order.
    - `id` *(string, required)* — Unique identifier for the object.
    - `mode` *(EnvironmentMode, required)*
    - `object` *(string, required)* — A string representing the object's type. Objects of the same type share the same value.
    - `product_id` *(string, required)* — The ID of the product this license belongs to. — e.g. `prod_abc123`
    - `status` *(LicenseStatus, required)* — e.g. `active`
    - `key` *(string, required)* — The license key. — e.g. `ABC123-XYZ456-XYZ456-XYZ456`
    - `activation` *(number, required)* — The number of instances that this license key was activated. — e.g. `5`
    - `activation_limit` *(number, optional)* — The activation limit. Null if activations are unlimited. — e.g. `1`
    - `expires_at` *(string, optional)* — The date the license key expires. Null if it does not have an expiration date. — e.g. `2023-09-13T00:00:00Z`
    - `created_at` *(string, required)* — The creation date of the license key. — e.g. `2023-09-13T00:00:00Z`
    - `instance` *(LicenseInstanceEntity, optional)* — Associated license instances.
      - `id` *(string, required)* — Unique identifier for the object.
      - `mode` *(EnvironmentMode, required)*
      - `object` *(string, required)* — A string representing the object’s type. Objects of the same type share the same value. — e.g. `license-instance`
      - `name` *(string, required)* — The name of the license instance. — e.g. `My Customer License Instance`
      - `status` *(enum: active|deactivated, required)* — The status of the license instance. — e.g. `active`
      - `created_at` *(string, required)* — The creation date of the license instance. — e.g. `2023-09-13T00:00:00Z`
- `metadata` *(object, optional)* — Metadata for the checkout in the form of key-value pairs — e.g. `{'userId': 'user_123', 'visitCount': 42, 'lastVisit': '2023-04-01'}`
- `discount` *(object{id, discountCode, name, type, amount, duration, durationI...}, optional)* — The discount applied to the checkout, if any.
  - `id` *(string, optional)* — The unique identifier of the discount (e.g. dis_...). — e.g. `dis_3e6Z6TzvHKdsjEgXnGDEp0`
  - `discountCode` *(string, optional)* — The discount code applied to the checkout. — e.g. `HOLIDAY2024`
  - `name` *(string, optional)*
  - `type` *(enum: percentage|fixed, optional)*
  - `amount` *(number, optional)*
  - `duration` *(enum: forever|once|repeating, optional)*
  - `durationInMonths` *(number, optional)*

---

### `POST /v1/checkouts` — Creates a new checkout session.

Create a new checkout session to accept one-time payments or start subscriptions. Returns a checkout URL to redirect customers.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `createCheckout`.


**Request body** (application/json, required):

Schema: `CreateCheckoutRequest`

- `request_id` *(string, optional)* — Identify and track each checkout request.
- `product_id` *(string, required)* — The ID of the product associated with the checkout session. — e.g. `prod_1234567890`
- `units` *(number, optional)* — The number of units for the order. — e.g. `1`
- `custom_price` *(integer, optional)* — Override the unit price of the product for this checkout session, in cents (e.g. 1500 = $15.00). The product currency is used, and the amount is per unit: with `units: 3` and `custom_price: 1500` the customer pays 4500. Must be between 100 (one whole unit of the currency) and 99999999. Only supported for one-time payment products. Use this for dynamic pricing models such as pay-what-you-want, donations, or amounts calculated by your application. — e.g. `1500`
- `discount_code` *(string, optional)* — Prefill the checkout session with a discount code. — e.g. `SUMMER2024`
- `customer` *(CustomerRequestEntity, optional)* — Customer data for checkout session. This will prefill the customer info on the checkout page.
  - `id` *(string, optional)* — Unique identifier of the customer. You may specify only one of these parameters: id or email. — e.g. `cust_1234567890`
  - `email` *(string, optional)* — Customer email address. You may only specify one of these parameters: id, email. — e.g. `user@example.com`
- `custom_fields` *(array<CustomFieldRequestEntity>, optional)* — Collect additional information from your customer using custom fields. Up to 3 fields are supported.
  *(fields of `CustomFieldRequestEntity`)*
  - `type` *(CustomFieldRequestType, required)* — e.g. `text`
  - `key` *(string, required)* — Unique key for custom field. Must be unique to this field, alphanumeric, and up to 200 characters. — e.g. `companyName`
  - `label` *(string, required)* — The label for the field, displayed to the customer, up to 50 characters. — e.g. `Company Name`
  - `optional` *(boolean, optional)* — Whether the customer is required to complete the field. Defaults to `false`
  - `text` *(TextFieldConfig, optional)* — Configuration for text field type.
    - `max_length` *(number, optional)* — Maximum character length constraint for the input. — e.g. `200`
    - `min_length` *(number, optional)* — Minimum character length requirement for the input. — e.g. `1`
  - `checkbox` *(CheckboxFieldConfig, optional)* — Configuration for checkbox field type.
    - `label` *(string, optional)* — The markdown text to display for the checkbox. — e.g. `I agree to the [terms and conditions](https://example.com/terms)`
- `custom_field` *(array<CustomFieldRequestEntity>, optional)* — DEPRECATED: Use `custom_fields` instead. Collect additional information from your customer using custom fields. Up to 3 fields are supported.
  *(fields of `CustomFieldRequestEntity`)*
  - `type` *(CustomFieldRequestType, required)* — e.g. `text`
  - `key` *(string, required)* — Unique key for custom field. Must be unique to this field, alphanumeric, and up to 200 characters. — e.g. `companyName`
  - `label` *(string, required)* — The label for the field, displayed to the customer, up to 50 characters. — e.g. `Company Name`
  - `optional` *(boolean, optional)* — Whether the customer is required to complete the field. Defaults to `false`
  - `text` *(TextFieldConfig, optional)* — Configuration for text field type.
    - `max_length` *(number, optional)* — Maximum character length constraint for the input. — e.g. `200`
    - `min_length` *(number, optional)* — Minimum character length requirement for the input. — e.g. `1`
  - `checkbox` *(CheckboxFieldConfig, optional)* — Configuration for checkbox field type.
    - `label` *(string, optional)* — The markdown text to display for the checkbox. — e.g. `I agree to the [terms and conditions](https://example.com/terms)`
- `success_url` *(string, optional)* — The URL to which the user will be redirected after the checkout process is completed.
- `metadata` *(object, optional)* — Metadata for the checkout in the form of key-value pairs — e.g. `{'userId': 'user_123', 'visitCount': 42, 'lastVisit': '2023-04-01'}`

**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully created a checkout session | CheckoutEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `CheckoutEntity`:**

- `id` *(string, required)* — Unique identifier for the object.
- `mode` *(EnvironmentMode, required)*
- `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value.
- `status` *(enum: pending|processing|completed|expired, required)* — Status of the checkout. — e.g. `completed`
- `request_id` *(string, optional)* — Identify and track each checkout request.
- `product` *(string | ProductEntity, required)* — The product associated with the checkout session.
  *(fields of `ProductEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value.
  - `name` *(string, required)* — The name of the product
  - `description` *(string, required)* — A brief description of the product — e.g. `This is a sample product description.`
  - `image_url` *(string, optional)* — URL of the product image. Only png as jpg are supported — e.g. `https://example.com/image.jpg`
  - `image_urls` *(array<string>, optional)* — Ordered list of product image URLs. The first entry is the cover image (mirrored in image_url). — e.g. `['https://example.com/image.jpg']`
  - `features` *(array<FeatureEntity>, optional)* — Features of the product.
    *(fields of `FeatureEntity`)*
    - `id` *(string, required)* — Unique identifier for the feature. — e.g. `feat_abc123`
    - `type` *(ProductFeatureType, required)* — e.g. `licenseKey`
    - `description` *(string, required)* — A brief description of the feature. — e.g. `Access to premium course materials.`
  - `price` *(number, required)* — The price of the product in cents. 1000 = $10.00 — e.g. `400`
  - `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
  - `billing_type` *(ProductBillingType, required)* — e.g. `recurring`
  - `billing_period` *(ProductBillingPeriod, required)* — e.g. `every-month`
  - `status` *(ProductStatus, required)* — e.g. `active`
  - `tax_mode` *(TaxMode, required)* — e.g. `inclusive`
  - `tax_category` *(TaxCategory, required)* — e.g. `saas`
  - `product_url` *(string, optional)* — The product page you can redirect your customers to for express checkout. — e.g. `https://creem.io/product/prod_123123123123`
  - `default_success_url` *(string, optional)* — The URL to which the user will be redirected after successfull payment. — e.g. `https://example.com/?status=successful`
  - `custom_fields` *(array<CustomField>, optional)* — Custom fields configured for the product. Collect additional information from your customer during checkout.
    *(fields of `CustomField`)*
    - `type` *(CustomFieldType, required)*
    - `key` *(string, required)* — Unique key for custom field. Must be unique to this field, alphanumeric, and up to 200 characters.
    - `label` *(string, required)* — The label for the field, displayed to the customer, up to 50 characters
    - `optional` *(boolean, optional)* — Whether the customer is required to complete the field. Defaults to `false`.
    - `text` *(Text, optional)* — Configuration for text field type.
      - `max_length` *(number, optional)* — Maximum character length constraint for the input.
      - `minimum_length` *(number, optional)* — Minimum character length requirement for the input.
      - `value` *(string, optional)* — The value of the input.
    - `checkbox` *(Checkbox, optional)* — Configuration for checkbox field type.
      - `label` *(string, optional)* — The markdown text to display for the checkbox.
      - `value` *(boolean, optional)* — The value of the checkbox (checked or not).
  - `created_at` *(string, required)* — Creation date of the product — e.g. `2023-01-01T00:00:00Z`
  - `updated_at` *(string, required)* — Last updated date of the product — e.g. `2023-01-01T00:00:00Z`
- `units` *(number, optional)* — The number of units for the of the product.
- `custom_price` *(integer, optional)* — The per-unit price override (in cents, product currency) this checkout was created with. Only present when the checkout was created with a custom_price. One-time payment products only. — e.g. `1500`
- `order` *(OrderEntity, optional)* — The order associated with the checkout session.
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value.
  - `customer` *(string, optional)* — The customer who placed the order.
  - `product` *(string, required)* — The product associated with the order.
  - `transaction` *(string, optional)* — The transaction ID of the order — e.g. `tx_1234567890`
  - `discount` *(string, optional)* — The discount ID of the order — e.g. `dis_1234567890`
  - `amount` *(number, required)* — The total amount of the order in cents. 1000 = $10.00 — e.g. `2000`
  - `sub_total` *(number, optional)* — The subtotal of the order in cents. 1000 = $10.00 — e.g. `1800`
  - `tax_amount` *(number, optional)* — The tax amount of the order in cents. 1000 = $10.00 — e.g. `200`
  - `discount_amount` *(number, optional)* — The discount amount of the order in cents. 1000 = $10.00 — e.g. `100`
  - `amount_due` *(number, optional)* — The amount due for the order in cents. 1000 = $10.00 — e.g. `1900`
  - `amount_paid` *(number, optional)* — The amount paid for the order in cents. 1000 = $10.00 — e.g. `1900`
  - `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
  - `fx_amount` *(number, optional)* — The amount in the foreign currency, if applicable. — e.g. `15`
  - `fx_currency` *(string, optional)* — Three-letter ISO code of the foreign currency, if applicable. — e.g. `EUR`
  - `fx_rate` *(number, optional)* — The exchange rate used for converting between currencies, if applicable. — e.g. `1.2`
  - `status` *(OrderStatus, required)* — e.g. `pending`
  - `type` *(OrderType, required)* — e.g. `recurring`
  - `affiliate` *(string, optional)* — The affiliate associated with the order, if applicable.
  - `created_at` *(string, required)* — Creation date of the order — e.g. `2023-09-13T00:00:00Z`
  - `updated_at` *(string, required)* — Last updated date of the order — e.g. `2023-09-13T00:00:00Z`
- `subscription` *(string | SubscriptionEntity, optional)* — The subscription associated with the checkout session.
  *(fields of `SubscriptionEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value. — e.g. `subscription`
  - `product` *(ProductEntity | string, required)* — The product associated with the subscription.
    *(fields of `ProductEntity`)*
    - `id` *(string, required)* — Unique identifier for the object.
    - `mode` *(EnvironmentMode, required)*
    - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value.
    - `name` *(string, required)* — The name of the product
    - `description` *(string, required)* — A brief description of the product — e.g. `This is a sample product description.`
    - `image_url` *(string, optional)* — URL of the product image. Only png as jpg are supported — e.g. `https://example.com/image.jpg`
    - `image_urls` *(array<string>, optional)* — Ordered list of product image URLs. The first entry is the cover image (mirrored in image_url). — e.g. `['https://example.com/image.jpg']`
    - `features` *(array<FeatureEntity>, optional)* — Features of the product.
      *(fields of `FeatureEntity`)*
      - `id` *(string, required)* — Unique identifier for the feature. — e.g. `feat_abc123`
      - `type` *(ProductFeatureType, required)* — e.g. `licenseKey`
      - `description` *(string, required)* — A brief description of the feature. — e.g. `Access to premium course materials.`
    - `price` *(number, required)* — The price of the product in cents. 1000 = $10.00 — e.g. `400`
    - `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
    - `billing_type` *(ProductBillingType, required)* — e.g. `recurring`
    - `billing_period` *(ProductBillingPeriod, required)* — e.g. `every-month`
    - `status` *(ProductStatus, required)* — e.g. `active`
    - `tax_mode` *(TaxMode, required)* — e.g. `inclusive`
    - `tax_category` *(TaxCategory, required)* — e.g. `saas`
    - `product_url` *(string, optional)* — The product page you can redirect your customers to for express checkout. — e.g. `https://creem.io/product/prod_123123123123`
    - `default_success_url` *(string, optional)* — The URL to which the user will be redirected after successfull payment. — e.g. `https://example.com/?status=successful`
    - `custom_fields` *(array<CustomField>, optional)* — Custom fields configured for the product. Collect additional information from your customer during checkout.
      *(fields of `CustomField`)*
      - `type` *(CustomFieldType, required)*
      - `key` *(string, required)* — Unique key for custom field. Must be unique to this field, alphanumeric, and up to 200 characters.
      - `label` *(string, required)* — The label for the field, displayed to the customer, up to 50 characters
      - `optional` *(boolean, optional)* — Whether the customer is required to complete the field. Defaults to `false`.
      - `text` *(Text, optional)* — Configuration for text field type.
        - `max_length` *(number, optional)* — Maximum character length constraint for the input.
        - `minimum_length` *(number, optional)* — Minimum character length requirement for the input.
        - `value` *(string, optional)* — The value of the input.
      - `checkbox` *(Checkbox, optional)* — Configuration for checkbox field type.
        - `label` *(string, optional)* — The markdown text to display for the checkbox.
        - `value` *(boolean, optional)* — The value of the checkbox (checked or not).
    - `created_at` *(string, required)* — Creation date of the product — e.g. `2023-01-01T00:00:00Z`
    - `updated_at` *(string, required)* — Last updated date of the product — e.g. `2023-01-01T00:00:00Z`
  - `customer` *(CustomerEntity | string, required)* — The customer who owns the subscription.
    *(fields of `CustomerEntity`)*
    - `id` *(string, required)* — Unique identifier for the object.
    - `mode` *(EnvironmentMode, required)*
    - `object` *(string, required)* — String representing the object’s type. Objects of the same type share the same value.
    - `email` *(string, required)* — Customer email address. — e.g. `user@example.com`
    - `name` *(string, optional)* — Customer name. — e.g. `John Doe`
    - `metadata` *(object, optional)* — Additional metadata associated with the customer. — e.g. `{'key': 'value'}`
    - `country` *(string, required)* — The ISO 3166-1 alpha-2 country code for the customer. — e.g. `US`
    - `created_at` *(string, required)* — Creation date of the customer — e.g. `2023-01-01T00:00:00Z`
    - `updated_at` *(string, required)* — Last updated date of the customer — e.g. `2023-01-01T00:00:00Z`
  - `items` *(array<SubscriptionItemEntity>, optional)* — Subscription items.
    *(fields of `SubscriptionItemEntity`)*
    - `id` *(string, required)* — Unique identifier for the object.
    - `mode` *(EnvironmentMode, required)*
    - `object` *(string, required)* — String representing the object’s type. Objects of the same type share the same value.
    - `product_id` *(string, optional)* — The ID of the product associated with the subscription item.
    - `price_id` *(string, optional)* — The ID of the price associated with the subscription item.
    - `units` *(number, optional)* — The number of units for the subscription item.
  - `collection_method` *(SubscriptionCollectionMethod, required)* — e.g. `charge_automatically`
  - `status` *(SubscriptionStatus, required)* — e.g. `active`
  - `last_transaction_id` *(string, optional)* — The ID of the last paid transaction. — e.g. `tran_3e6Z6TzvHKdsjEgXnGDEp0`
  - `last_transaction` *(TransactionEntity, optional)* — The last paid transaction.
    - `id` *(string, required)* — Unique identifier for the object.
    - `mode` *(EnvironmentMode, required)*
    - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value. — e.g. `transaction`
    - `amount` *(number, required)* — The transaction amount in cents. 1000 = $10.00 — e.g. `2000`
    - `amount_paid` *(number, optional)* — The amount the customer paid in cents. 1000 = $10.00 — e.g. `2000`
    - `discount_amount` *(number, optional)* — The discount amount in cents. 1000 = $10.00 — e.g. `2000`
    - `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
    - `type` *(TransactionType, required)*
    - `tax_country` *(string, optional)* — The ISO alpha-2 country code where tax is collected. — e.g. `US`
    - `tax_amount` *(number, optional)* — The sale tax amount in cents. 1000 = $10.00 — e.g. `2000`
    - `status` *(TransactionStatus, required)*
    - `refunded_amount` *(number, optional)* — The amount that has been refunded in cents. 1000 = $10.00 — e.g. `2000`
    - `order` *(string, optional)* — The order associated with the transaction.
    - `subscription` *(string, optional)* — The subscription associated with the transaction.
    - `customer` *(string, optional)* — The customer associated with the transaction.
    - `description` *(string, optional)* — The description of the transaction.
    - `period_start` *(number, optional)* — Start period for the invoice as timestamp
    - `period_end` *(number, optional)* — End period for the invoice as timestamp
    - `created_at` *(number, required)* — Creation date of the order as timestamp
  - `last_transaction_date` *(string, optional)* — The date of the last paid transaction. — e.g. `2024-09-12T12:34:56Z`
  - `next_transaction_date` *(string, optional)* — The date when the next subscription transaction will be charged. — e.g. `2024-09-12T12:34:56Z`
  - `current_period_start_date` *(string, optional)* — The start date of the current subscription period. — e.g. `2024-09-12T12:34:56Z`
  - `current_period_end_date` *(string, optional)* — The end date of the current subscription period. — e.g. `2024-09-12T12:34:56Z`
  - `canceled_at` *(string, optional)* — The date and time when the subscription was canceled, if applicable. — e.g. `2024-09-12T12:34:56Z`
  - `created_at` *(string, required)* — The date and time when the subscription was created. — e.g. `2024-01-01T00:00:00Z`
  - `updated_at` *(string, required)* — The date and time when the subscription was last updated. — e.g. `2024-09-12T12:34:56Z`
  - `discount` *(object{id, discountCode, name, type, amount, duration, durationI...}, optional)* — The discount applied to the subscription, if any.
    - `id` *(string, optional)* — The unique identifier of the discount (e.g. dis_...). — e.g. `dis_3e6Z6TzvHKdsjEgXnGDEp0`
    - `discountCode` *(string, optional)* — The discount code applied to the subscription. — e.g. `HOLIDAY2024`
    - `name` *(string, optional)*
    - `type` *(enum: percentage|fixed, optional)*
    - `amount` *(number, optional)*
    - `duration` *(enum: forever|once|repeating, optional)*
    - `durationInMonths` *(number, optional)*
  - `metadata` *(object, optional)* — Metadata for the subscription in the form of key-value pairs. — e.g. `{'userId': 'user_123', 'plan': 'pro'}`
- `customer` *(string | CustomerEntity, optional)* — The customer associated with the checkout session.
  *(fields of `CustomerEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object’s type. Objects of the same type share the same value.
  - `email` *(string, required)* — Customer email address. — e.g. `user@example.com`
  - `name` *(string, optional)* — Customer name. — e.g. `John Doe`
  - `metadata` *(object, optional)* — Additional metadata associated with the customer. — e.g. `{'key': 'value'}`
  - `country` *(string, required)* — The ISO 3166-1 alpha-2 country code for the customer. — e.g. `US`
  - `created_at` *(string, required)* — Creation date of the customer — e.g. `2023-01-01T00:00:00Z`
  - `updated_at` *(string, required)* — Last updated date of the customer — e.g. `2023-01-01T00:00:00Z`
- `custom_fields` *(array<CustomField>, optional)* — Additional information collected from your customer during the checkout process.
  *(fields of `CustomField`)*
  - `type` *(CustomFieldType, required)*
  - `key` *(string, required)* — Unique key for custom field. Must be unique to this field, alphanumeric, and up to 200 characters.
  - `label` *(string, required)* — The label for the field, displayed to the customer, up to 50 characters
  - `optional` *(boolean, optional)* — Whether the customer is required to complete the field. Defaults to `false`.
  - `text` *(Text, optional)* — Configuration for text field type.
    - `max_length` *(number, optional)* — Maximum character length constraint for the input.
    - `minimum_length` *(number, optional)* — Minimum character length requirement for the input.
    - `value` *(string, optional)* — The value of the input.
  - `checkbox` *(Checkbox, optional)* — Configuration for checkbox field type.
    - `label` *(string, optional)* — The markdown text to display for the checkbox.
    - `value` *(boolean, optional)* — The value of the checkbox (checked or not).
- `checkout_url` *(string, optional)* — The URL to which the customer will be redirected to complete the payment.
- `success_url` *(string, optional)* — The URL to which the user will be redirected after the checkout process is completed. — e.g. `https://example.com/return`
- `license_keys` *(array<LicenseEntity>, optional)* — License keys issued for the order.
  *(fields of `LicenseEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — A string representing the object's type. Objects of the same type share the same value.
  - `product_id` *(string, required)* — The ID of the product this license belongs to. — e.g. `prod_abc123`
  - `status` *(LicenseStatus, required)* — e.g. `active`
  - `key` *(string, required)* — The license key. — e.g. `ABC123-XYZ456-XYZ456-XYZ456`
  - `activation` *(number, required)* — The number of instances that this license key was activated. — e.g. `5`
  - `activation_limit` *(number, optional)* — The activation limit. Null if activations are unlimited. — e.g. `1`
  - `expires_at` *(string, optional)* — The date the license key expires. Null if it does not have an expiration date. — e.g. `2023-09-13T00:00:00Z`
  - `created_at` *(string, required)* — The creation date of the license key. — e.g. `2023-09-13T00:00:00Z`
  - `instance` *(LicenseInstanceEntity, optional)* — Associated license instances.
    - `id` *(string, required)* — Unique identifier for the object.
    - `mode` *(EnvironmentMode, required)*
    - `object` *(string, required)* — A string representing the object’s type. Objects of the same type share the same value. — e.g. `license-instance`
    - `name` *(string, required)* — The name of the license instance. — e.g. `My Customer License Instance`
    - `status` *(enum: active|deactivated, required)* — The status of the license instance. — e.g. `active`
    - `created_at` *(string, required)* — The creation date of the license instance. — e.g. `2023-09-13T00:00:00Z`
- `feature` *(array<ProductFeatureEntity>, optional)* — DEPRECATED: Use `license_keys` instead. Features issued for the order.
  *(fields of `ProductFeatureEntity`)*
  - `id` *(string, optional)* — Unique identifier for the feature. — e.g. `feat_abc123`
  - `description` *(string, optional)* — A brief description of the feature. — e.g. `Get access to the full course materials.`
  - `type` *(ProductFeatureType, optional)* — e.g. `licenseKey`
  - `private_note` *(string, optional)* — Private note from the seller. This is only visible to the customer after purchase. — e.g. `Thank you for your purchase! Here is your access code: XYZ123`
  - `file` *(FileFeatureEntity, optional)* — File feature data containing downloadable files.
    - `files` *(array<FeatureFileEntity>, required)* — List of downloadable files.
      *(fields of `FeatureFileEntity`)*
      - `id` *(string, required)* — Unique identifier for the file. — e.g. `file_abc123`
      - `file_name` *(string, required)* — The name of the file. — e.g. `ebook.pdf`
      - `url` *(string, required)* — The URL to download the file. — e.g. `https://storage.creem.io/files/ebook.pdf`
      - `type` *(string, required)* — The MIME type of the file. — e.g. `application/pdf`
      - `size` *(number, required)* — The size of the file in bytes. — e.g. `1024000`
  - `license_key` *(LicenseEntity, optional)* — License key issued for the order.
    - `id` *(string, required)* — Unique identifier for the object.
    - `mode` *(EnvironmentMode, required)*
    - `object` *(string, required)* — A string representing the object's type. Objects of the same type share the same value.
    - `product_id` *(string, required)* — The ID of the product this license belongs to. — e.g. `prod_abc123`
    - `status` *(LicenseStatus, required)* — e.g. `active`
    - `key` *(string, required)* — The license key. — e.g. `ABC123-XYZ456-XYZ456-XYZ456`
    - `activation` *(number, required)* — The number of instances that this license key was activated. — e.g. `5`
    - `activation_limit` *(number, optional)* — The activation limit. Null if activations are unlimited. — e.g. `1`
    - `expires_at` *(string, optional)* — The date the license key expires. Null if it does not have an expiration date. — e.g. `2023-09-13T00:00:00Z`
    - `created_at` *(string, required)* — The creation date of the license key. — e.g. `2023-09-13T00:00:00Z`
    - `instance` *(LicenseInstanceEntity, optional)* — Associated license instances.
      - `id` *(string, required)* — Unique identifier for the object.
      - `mode` *(EnvironmentMode, required)*
      - `object` *(string, required)* — A string representing the object’s type. Objects of the same type share the same value. — e.g. `license-instance`
      - `name` *(string, required)* — The name of the license instance. — e.g. `My Customer License Instance`
      - `status` *(enum: active|deactivated, required)* — The status of the license instance. — e.g. `active`
      - `created_at` *(string, required)* — The creation date of the license instance. — e.g. `2023-09-13T00:00:00Z`
  - `customer_credits` *(CustomerCreditsFeatureEntity, optional)* — Customer credits feature data.
    - `amount` *(string, required)* — The number of credits to grant. String to preserve BigInt precision. — e.g. `100`
    - `unit_label` *(string, optional)* — Optional label for the credit unit (e.g. "tokens", "credits"). — e.g. `tokens`
  - `license` *(LicenseEntity, optional)* — DEPRECATED: Use `license_key` instead. License key issued for the order.
    - `id` *(string, required)* — Unique identifier for the object.
    - `mode` *(EnvironmentMode, required)*
    - `object` *(string, required)* — A string representing the object's type. Objects of the same type share the same value.
    - `product_id` *(string, required)* — The ID of the product this license belongs to. — e.g. `prod_abc123`
    - `status` *(LicenseStatus, required)* — e.g. `active`
    - `key` *(string, required)* — The license key. — e.g. `ABC123-XYZ456-XYZ456-XYZ456`
    - `activation` *(number, required)* — The number of instances that this license key was activated. — e.g. `5`
    - `activation_limit` *(number, optional)* — The activation limit. Null if activations are unlimited. — e.g. `1`
    - `expires_at` *(string, optional)* — The date the license key expires. Null if it does not have an expiration date. — e.g. `2023-09-13T00:00:00Z`
    - `created_at` *(string, required)* — The creation date of the license key. — e.g. `2023-09-13T00:00:00Z`
    - `instance` *(LicenseInstanceEntity, optional)* — Associated license instances.
      - `id` *(string, required)* — Unique identifier for the object.
      - `mode` *(EnvironmentMode, required)*
      - `object` *(string, required)* — A string representing the object’s type. Objects of the same type share the same value. — e.g. `license-instance`
      - `name` *(string, required)* — The name of the license instance. — e.g. `My Customer License Instance`
      - `status` *(enum: active|deactivated, required)* — The status of the license instance. — e.g. `active`
      - `created_at` *(string, required)* — The creation date of the license instance. — e.g. `2023-09-13T00:00:00Z`
- `metadata` *(object, optional)* — Metadata for the checkout in the form of key-value pairs — e.g. `{'userId': 'user_123', 'visitCount': 42, 'lastVisit': '2023-04-01'}`
- `discount` *(object{id, discountCode, name, type, amount, duration, durationI...}, optional)* — The discount applied to the checkout, if any.
  - `id` *(string, optional)* — The unique identifier of the discount (e.g. dis_...). — e.g. `dis_3e6Z6TzvHKdsjEgXnGDEp0`
  - `discountCode` *(string, optional)* — The discount code applied to the checkout. — e.g. `HOLIDAY2024`
  - `name` *(string, optional)*
  - `type` *(enum: percentage|fixed, optional)*
  - `amount` *(number, optional)*
  - `duration` *(enum: forever|once|repeating, optional)*
  - `durationInMonths` *(number, optional)*

---

### Customers

### `GET /v1/customers/list` — List all customers

Retrieve a paginated list of all customers. Filter and search through your customer base.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `listCustomers`.


**Query parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `page_number` | number | no (default: `1`) | The page number for pagination. |
| `page_size` | number | no (default: `50`) | The number of items per page. |


**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully retrieved customers | CustomerListEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `CustomerListEntity`:**

- `items` *(array<CustomerEntity>, required)* — List of customer items
  *(fields of `CustomerEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object’s type. Objects of the same type share the same value.
  - `email` *(string, required)* — Customer email address. — e.g. `user@example.com`
  - `name` *(string, optional)* — Customer name. — e.g. `John Doe`
  - `metadata` *(object, optional)* — Additional metadata associated with the customer. — e.g. `{'key': 'value'}`
  - `country` *(string, required)* — The ISO 3166-1 alpha-2 country code for the customer. — e.g. `US`
  - `created_at` *(string, required)* — Creation date of the customer — e.g. `2023-01-01T00:00:00Z`
  - `updated_at` *(string, required)* — Last updated date of the customer — e.g. `2023-01-01T00:00:00Z`
- `pagination` *(PaginationEntity, required)* — Pagination details for the list
  - `total_records` *(number, required)* — Total number of records in the list — e.g. `0`
  - `total_pages` *(number, required)* — Total number of pages available — e.g. `0`
  - `current_page` *(number, required)* — The current page number — e.g. `1`
  - `next_page` *(number, required)* — The next page number, or null if there is no next page — e.g. `2`
  - `prev_page` *(number, required)* — The previous page number, or null if there is no previous page

---

### `GET /v1/customers/{id}/orders` — List customer orders

Retrieve a paginated list of orders for a specific customer.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `listCustomerOrders`.


**Path parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | The unique identifier of the customer |
| `page_number` | number | no (default: `1`) | The page number for pagination. |
| `page_size` | number | no (default: `10`) | The number of items per page. |


**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully retrieved customer orders | OrderListEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `OrderListEntity`:**

- `items` *(array<OrderEntity>, required)* — List of order items
  *(fields of `OrderEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value.
  - `customer` *(string, optional)* — The customer who placed the order.
  - `product` *(string, required)* — The product associated with the order.
  - `transaction` *(string, optional)* — The transaction ID of the order — e.g. `tx_1234567890`
  - `discount` *(string, optional)* — The discount ID of the order — e.g. `dis_1234567890`
  - `amount` *(number, required)* — The total amount of the order in cents. 1000 = $10.00 — e.g. `2000`
  - `sub_total` *(number, optional)* — The subtotal of the order in cents. 1000 = $10.00 — e.g. `1800`
  - `tax_amount` *(number, optional)* — The tax amount of the order in cents. 1000 = $10.00 — e.g. `200`
  - `discount_amount` *(number, optional)* — The discount amount of the order in cents. 1000 = $10.00 — e.g. `100`
  - `amount_due` *(number, optional)* — The amount due for the order in cents. 1000 = $10.00 — e.g. `1900`
  - `amount_paid` *(number, optional)* — The amount paid for the order in cents. 1000 = $10.00 — e.g. `1900`
  - `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
  - `fx_amount` *(number, optional)* — The amount in the foreign currency, if applicable. — e.g. `15`
  - `fx_currency` *(string, optional)* — Three-letter ISO code of the foreign currency, if applicable. — e.g. `EUR`
  - `fx_rate` *(number, optional)* — The exchange rate used for converting between currencies, if applicable. — e.g. `1.2`
  - `status` *(OrderStatus, required)* — e.g. `pending`
  - `type` *(OrderType, required)* — e.g. `recurring`
  - `affiliate` *(string, optional)* — The affiliate associated with the order, if applicable.
  - `created_at` *(string, required)* — Creation date of the order — e.g. `2023-09-13T00:00:00Z`
  - `updated_at` *(string, required)* — Last updated date of the order — e.g. `2023-09-13T00:00:00Z`
- `pagination` *(PaginationEntity, required)* — Pagination details for the list
  - `total_records` *(number, required)* — Total number of records in the list — e.g. `0`
  - `total_pages` *(number, required)* — Total number of pages available — e.g. `0`
  - `current_page` *(number, required)* — The current page number — e.g. `1`
  - `next_page` *(number, required)* — The next page number, or null if there is no next page — e.g. `2`
  - `prev_page` *(number, required)* — The previous page number, or null if there is no previous page

---

### `GET /v1/customers/{id}/subscriptions` — List customer subscriptions

Retrieve a paginated list of subscriptions for a specific customer.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `listCustomerSubscriptions`.


**Path parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | The unique identifier of the customer |
| `page_number` | number | no (default: `1`) | The page number for pagination. |
| `page_size` | number | no (default: `10`) | The number of items per page. |


**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully retrieved customer subscriptions | SubscriptionListEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `SubscriptionListEntity`:**

- `items` *(array<SubscriptionEntity>, required)* — List of subscription items
  *(fields of `SubscriptionEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value. — e.g. `subscription`
  - `product` *(ProductEntity | string, required)* — The product associated with the subscription.
    *(fields of `ProductEntity`)*
    - `id` *(string, required)* — Unique identifier for the object.
    - `mode` *(EnvironmentMode, required)*
    - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value.
    - `name` *(string, required)* — The name of the product
    - `description` *(string, required)* — A brief description of the product — e.g. `This is a sample product description.`
    - `image_url` *(string, optional)* — URL of the product image. Only png as jpg are supported — e.g. `https://example.com/image.jpg`
    - `image_urls` *(array<string>, optional)* — Ordered list of product image URLs. The first entry is the cover image (mirrored in image_url). — e.g. `['https://example.com/image.jpg']`
    - `features` *(array<FeatureEntity>, optional)* — Features of the product.
      *(fields of `FeatureEntity`)*
      - `id` *(string, required)* — Unique identifier for the feature. — e.g. `feat_abc123`
      - `type` *(ProductFeatureType, required)* — e.g. `licenseKey`
      - `description` *(string, required)* — A brief description of the feature. — e.g. `Access to premium course materials.`
    - `price` *(number, required)* — The price of the product in cents. 1000 = $10.00 — e.g. `400`
    - `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
    - `billing_type` *(ProductBillingType, required)* — e.g. `recurring`
    - `billing_period` *(ProductBillingPeriod, required)* — e.g. `every-month`
    - `status` *(ProductStatus, required)* — e.g. `active`
    - `tax_mode` *(TaxMode, required)* — e.g. `inclusive`
    - `tax_category` *(TaxCategory, required)* — e.g. `saas`
    - `product_url` *(string, optional)* — The product page you can redirect your customers to for express checkout. — e.g. `https://creem.io/product/prod_123123123123`
    - `default_success_url` *(string, optional)* — The URL to which the user will be redirected after successfull payment. — e.g. `https://example.com/?status=successful`
    - `custom_fields` *(array<CustomField>, optional)* — Custom fields configured for the product. Collect additional information from your customer during checkout.
      *(fields of `CustomField`)*
      - `type` *(CustomFieldType, required)*
      - `key` *(string, required)* — Unique key for custom field. Must be unique to this field, alphanumeric, and up to 200 characters.
      - `label` *(string, required)* — The label for the field, displayed to the customer, up to 50 characters
      - `optional` *(boolean, optional)* — Whether the customer is required to complete the field. Defaults to `false`.
      - `text` *(Text, optional)* — Configuration for text field type.
        - `max_length` *(number, optional)* — Maximum character length constraint for the input.
        - `minimum_length` *(number, optional)* — Minimum character length requirement for the input.
        - `value` *(string, optional)* — The value of the input.
      - `checkbox` *(Checkbox, optional)* — Configuration for checkbox field type.
        - `label` *(string, optional)* — The markdown text to display for the checkbox.
        - `value` *(boolean, optional)* — The value of the checkbox (checked or not).
    - `created_at` *(string, required)* — Creation date of the product — e.g. `2023-01-01T00:00:00Z`
    - `updated_at` *(string, required)* — Last updated date of the product — e.g. `2023-01-01T00:00:00Z`
  - `customer` *(CustomerEntity | string, required)* — The customer who owns the subscription.
    *(fields of `CustomerEntity`)*
    - `id` *(string, required)* — Unique identifier for the object.
    - `mode` *(EnvironmentMode, required)*
    - `object` *(string, required)* — String representing the object’s type. Objects of the same type share the same value.
    - `email` *(string, required)* — Customer email address. — e.g. `user@example.com`
    - `name` *(string, optional)* — Customer name. — e.g. `John Doe`
    - `metadata` *(object, optional)* — Additional metadata associated with the customer. — e.g. `{'key': 'value'}`
    - `country` *(string, required)* — The ISO 3166-1 alpha-2 country code for the customer. — e.g. `US`
    - `created_at` *(string, required)* — Creation date of the customer — e.g. `2023-01-01T00:00:00Z`
    - `updated_at` *(string, required)* — Last updated date of the customer — e.g. `2023-01-01T00:00:00Z`
  - `items` *(array<SubscriptionItemEntity>, optional)* — Subscription items.
    *(fields of `SubscriptionItemEntity`)*
    - `id` *(string, required)* — Unique identifier for the object.
    - `mode` *(EnvironmentMode, required)*
    - `object` *(string, required)* — String representing the object’s type. Objects of the same type share the same value.
    - `product_id` *(string, optional)* — The ID of the product associated with the subscription item.
    - `price_id` *(string, optional)* — The ID of the price associated with the subscription item.
    - `units` *(number, optional)* — The number of units for the subscription item.
  - `collection_method` *(SubscriptionCollectionMethod, required)* — e.g. `charge_automatically`
  - `status` *(SubscriptionStatus, required)* — e.g. `active`
  - `last_transaction_id` *(string, optional)* — The ID of the last paid transaction. — e.g. `tran_3e6Z6TzvHKdsjEgXnGDEp0`
  - `last_transaction` *(TransactionEntity, optional)* — The last paid transaction.
    - `id` *(string, required)* — Unique identifier for the object.
    - `mode` *(EnvironmentMode, required)*
    - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value. — e.g. `transaction`
    - `amount` *(number, required)* — The transaction amount in cents. 1000 = $10.00 — e.g. `2000`
    - `amount_paid` *(number, optional)* — The amount the customer paid in cents. 1000 = $10.00 — e.g. `2000`
    - `discount_amount` *(number, optional)* — The discount amount in cents. 1000 = $10.00 — e.g. `2000`
    - `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
    - `type` *(TransactionType, required)*
    - `tax_country` *(string, optional)* — The ISO alpha-2 country code where tax is collected. — e.g. `US`
    - `tax_amount` *(number, optional)* — The sale tax amount in cents. 1000 = $10.00 — e.g. `2000`
    - `status` *(TransactionStatus, required)*
    - `refunded_amount` *(number, optional)* — The amount that has been refunded in cents. 1000 = $10.00 — e.g. `2000`
    - `order` *(string, optional)* — The order associated with the transaction.
    - `subscription` *(string, optional)* — The subscription associated with the transaction.
    - `customer` *(string, optional)* — The customer associated with the transaction.
    - `description` *(string, optional)* — The description of the transaction.
    - `period_start` *(number, optional)* — Start period for the invoice as timestamp
    - `period_end` *(number, optional)* — End period for the invoice as timestamp
    - `created_at` *(number, required)* — Creation date of the order as timestamp
  - `last_transaction_date` *(string, optional)* — The date of the last paid transaction. — e.g. `2024-09-12T12:34:56Z`
  - `next_transaction_date` *(string, optional)* — The date when the next subscription transaction will be charged. — e.g. `2024-09-12T12:34:56Z`
  - `current_period_start_date` *(string, optional)* — The start date of the current subscription period. — e.g. `2024-09-12T12:34:56Z`
  - `current_period_end_date` *(string, optional)* — The end date of the current subscription period. — e.g. `2024-09-12T12:34:56Z`
  - `canceled_at` *(string, optional)* — The date and time when the subscription was canceled, if applicable. — e.g. `2024-09-12T12:34:56Z`
  - `created_at` *(string, required)* — The date and time when the subscription was created. — e.g. `2024-01-01T00:00:00Z`
  - `updated_at` *(string, required)* — The date and time when the subscription was last updated. — e.g. `2024-09-12T12:34:56Z`
  - `discount` *(object{id, discountCode, name, type, amount, duration, durationI...}, optional)* — The discount applied to the subscription, if any.
    - `id` *(string, optional)* — The unique identifier of the discount (e.g. dis_...). — e.g. `dis_3e6Z6TzvHKdsjEgXnGDEp0`
    - `discountCode` *(string, optional)* — The discount code applied to the subscription. — e.g. `HOLIDAY2024`
    - `name` *(string, optional)*
    - `type` *(enum: percentage|fixed, optional)*
    - `amount` *(number, optional)*
    - `duration` *(enum: forever|once|repeating, optional)*
    - `durationInMonths` *(number, optional)*
  - `metadata` *(object, optional)* — Metadata for the subscription in the form of key-value pairs. — e.g. `{'userId': 'user_123', 'plan': 'pro'}`
- `pagination` *(PaginationEntity, required)* — Pagination details for the list
  - `total_records` *(number, required)* — Total number of records in the list — e.g. `0`
  - `total_pages` *(number, required)* — Total number of pages available — e.g. `0`
  - `current_page` *(number, required)* — The current page number — e.g. `1`
  - `next_page` *(number, required)* — The next page number, or null if there is no next page — e.g. `2`
  - `prev_page` *(number, required)* — The previous page number, or null if there is no previous page

---

### `GET /v1/customers/{id}/licenses` — List customer licenses

Retrieve a paginated list of license keys for a specific customer.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `listCustomerLicenses`.


**Path parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | The unique identifier of the customer |
| `page_number` | number | no (default: `1`) | The page number for pagination. |
| `page_size` | number | no (default: `10`) | The number of items per page. |


**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully retrieved customer licenses | LicenseListEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `LicenseListEntity`:**

- `items` *(array<LicenseEntity>, required)* — List of license items
  *(fields of `LicenseEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — A string representing the object's type. Objects of the same type share the same value.
  - `product_id` *(string, required)* — The ID of the product this license belongs to. — e.g. `prod_abc123`
  - `status` *(LicenseStatus, required)* — e.g. `active`
  - `key` *(string, required)* — The license key. — e.g. `ABC123-XYZ456-XYZ456-XYZ456`
  - `activation` *(number, required)* — The number of instances that this license key was activated. — e.g. `5`
  - `activation_limit` *(number, optional)* — The activation limit. Null if activations are unlimited. — e.g. `1`
  - `expires_at` *(string, optional)* — The date the license key expires. Null if it does not have an expiration date. — e.g. `2023-09-13T00:00:00Z`
  - `created_at` *(string, required)* — The creation date of the license key. — e.g. `2023-09-13T00:00:00Z`
  - `instance` *(LicenseInstanceEntity, optional)* — Associated license instances.
    - `id` *(string, required)* — Unique identifier for the object.
    - `mode` *(EnvironmentMode, required)*
    - `object` *(string, required)* — A string representing the object’s type. Objects of the same type share the same value. — e.g. `license-instance`
    - `name` *(string, required)* — The name of the license instance. — e.g. `My Customer License Instance`
    - `status` *(enum: active|deactivated, required)* — The status of the license instance. — e.g. `active`
    - `created_at` *(string, required)* — The creation date of the license instance. — e.g. `2023-09-13T00:00:00Z`
- `pagination` *(PaginationEntity, required)* — Pagination details for the list
  - `total_records` *(number, required)* — Total number of records in the list — e.g. `0`
  - `total_pages` *(number, required)* — Total number of pages available — e.g. `0`
  - `current_page` *(number, required)* — The current page number — e.g. `1`
  - `next_page` *(number, required)* — The next page number, or null if there is no next page — e.g. `2`
  - `prev_page` *(number, required)* — The previous page number, or null if there is no previous page

---

### `GET /v1/customers` — Retrieve a customer

Retrieve customer information by ID or email. View purchase history, subscriptions, and profile details.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `retrieveCustomer`.


**Query parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `customer_id` | string | no | The unique identifier of the customer. |
| `email` | string | no | The email address of the customer. |


**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully retrieved the customer | CustomerEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `CustomerEntity`:**

- `id` *(string, required)* — Unique identifier for the object.
- `mode` *(EnvironmentMode, required)*
- `object` *(string, required)* — String representing the object’s type. Objects of the same type share the same value.
- `email` *(string, required)* — Customer email address. — e.g. `user@example.com`
- `name` *(string, optional)* — Customer name. — e.g. `John Doe`
- `metadata` *(object, optional)* — Additional metadata associated with the customer. — e.g. `{'key': 'value'}`
- `country` *(string, required)* — The ISO 3166-1 alpha-2 country code for the customer. — e.g. `US`
- `created_at` *(string, required)* — Creation date of the customer — e.g. `2023-01-01T00:00:00Z`
- `updated_at` *(string, required)* — Last updated date of the customer — e.g. `2023-01-01T00:00:00Z`

---

### `POST /v1/customers` — Create a customer

Create a new customer record for the authenticated store.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `createCustomer`.


**Request body** (application/json, required):

Schema: `CreateCustomerRequestEntity`

- `email` *(string, required)* — The email address of the customer. — e.g. `john@example.com`
- `name` *(string, required)* — The full name of the customer. — e.g. `John Doe`
- `metadata` *(object, optional)* — Additional metadata for the customer. — e.g. `{'key': 'value'}`

**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully created the customer | CustomerEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `CustomerEntity`:**

- `id` *(string, required)* — Unique identifier for the object.
- `mode` *(EnvironmentMode, required)*
- `object` *(string, required)* — String representing the object’s type. Objects of the same type share the same value.
- `email` *(string, required)* — Customer email address. — e.g. `user@example.com`
- `name` *(string, optional)* — Customer name. — e.g. `John Doe`
- `metadata` *(object, optional)* — Additional metadata associated with the customer. — e.g. `{'key': 'value'}`
- `country` *(string, required)* — The ISO 3166-1 alpha-2 country code for the customer. — e.g. `US`
- `created_at` *(string, required)* — Creation date of the customer — e.g. `2023-01-01T00:00:00Z`
- `updated_at` *(string, required)* — Last updated date of the customer — e.g. `2023-01-01T00:00:00Z`

---

### `PATCH /v1/customers` — Update a customer

Authentication: **`x-api-key` header** (required: yes). Operation ID: `updateCustomer`.


**Request body** (application/json, required):

Schema: `UpdateCustomerRequestEntity`

- `customer_id` *(string, required)* — The ID of the customer to update. — e.g. `cust_abc123`
- `name` *(string, optional)* — The full name of the customer. — e.g. `John Doe`
- `metadata` *(object, optional)* — Additional metadata for the customer. — e.g. `{'key': 'value'}`

**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully updated the customer | CustomerEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `CustomerEntity`:**

- `id` *(string, required)* — Unique identifier for the object.
- `mode` *(EnvironmentMode, required)*
- `object` *(string, required)* — String representing the object’s type. Objects of the same type share the same value.
- `email` *(string, required)* — Customer email address. — e.g. `user@example.com`
- `name` *(string, optional)* — Customer name. — e.g. `John Doe`
- `metadata` *(object, optional)* — Additional metadata associated with the customer. — e.g. `{'key': 'value'}`
- `country` *(string, required)* — The ISO 3166-1 alpha-2 country code for the customer. — e.g. `US`
- `created_at` *(string, required)* — Creation date of the customer — e.g. `2023-01-01T00:00:00Z`
- `updated_at` *(string, required)* — Last updated date of the customer — e.g. `2023-01-01T00:00:00Z`

---

### `POST /v1/customers/billing` — Generate Customer Links

Generate a customer portal link for managing billing, subscriptions, and payment methods.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `generateCustomerLinks`.


**Request body** (application/json, required):

Schema: `CreateCustomerPortalLinkRequestEntity`

- `customer_id` *(string, required)* — Unique identifier of the customer.

**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully generated customer links | CustomerLinksEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `CustomerLinksEntity`:**

- `customer_portal_link` *(string, required)* — Customer portal link.

---

### Subscriptions

### `GET /v1/subscriptions` — Retrieve a subscription

Retrieve subscription details by ID. View status, billing cycle, customer info, and payment history.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `retrieveSubscription`.


**Query parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `subscription_id` | string | yes | The unique identifier of the subscription |


**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully retrieved the subscription | SubscriptionEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `SubscriptionEntity`:**

- `id` *(string, required)* — Unique identifier for the object.
- `mode` *(EnvironmentMode, required)*
- `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value. — e.g. `subscription`
- `product` *(ProductEntity | string, required)* — The product associated with the subscription.
  *(fields of `ProductEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value.
  - `name` *(string, required)* — The name of the product
  - `description` *(string, required)* — A brief description of the product — e.g. `This is a sample product description.`
  - `image_url` *(string, optional)* — URL of the product image. Only png as jpg are supported — e.g. `https://example.com/image.jpg`
  - `image_urls` *(array<string>, optional)* — Ordered list of product image URLs. The first entry is the cover image (mirrored in image_url). — e.g. `['https://example.com/image.jpg']`
  - `features` *(array<FeatureEntity>, optional)* — Features of the product.
    *(fields of `FeatureEntity`)*
    - `id` *(string, required)* — Unique identifier for the feature. — e.g. `feat_abc123`
    - `type` *(ProductFeatureType, required)* — e.g. `licenseKey`
    - `description` *(string, required)* — A brief description of the feature. — e.g. `Access to premium course materials.`
  - `price` *(number, required)* — The price of the product in cents. 1000 = $10.00 — e.g. `400`
  - `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
  - `billing_type` *(ProductBillingType, required)* — e.g. `recurring`
  - `billing_period` *(ProductBillingPeriod, required)* — e.g. `every-month`
  - `status` *(ProductStatus, required)* — e.g. `active`
  - `tax_mode` *(TaxMode, required)* — e.g. `inclusive`
  - `tax_category` *(TaxCategory, required)* — e.g. `saas`
  - `product_url` *(string, optional)* — The product page you can redirect your customers to for express checkout. — e.g. `https://creem.io/product/prod_123123123123`
  - `default_success_url` *(string, optional)* — The URL to which the user will be redirected after successfull payment. — e.g. `https://example.com/?status=successful`
  - `custom_fields` *(array<CustomField>, optional)* — Custom fields configured for the product. Collect additional information from your customer during checkout.
    *(fields of `CustomField`)*
    - `type` *(CustomFieldType, required)*
    - `key` *(string, required)* — Unique key for custom field. Must be unique to this field, alphanumeric, and up to 200 characters.
    - `label` *(string, required)* — The label for the field, displayed to the customer, up to 50 characters
    - `optional` *(boolean, optional)* — Whether the customer is required to complete the field. Defaults to `false`.
    - `text` *(Text, optional)* — Configuration for text field type.
      - `max_length` *(number, optional)* — Maximum character length constraint for the input.
      - `minimum_length` *(number, optional)* — Minimum character length requirement for the input.
      - `value` *(string, optional)* — The value of the input.
    - `checkbox` *(Checkbox, optional)* — Configuration for checkbox field type.
      - `label` *(string, optional)* — The markdown text to display for the checkbox.
      - `value` *(boolean, optional)* — The value of the checkbox (checked or not).
  - `created_at` *(string, required)* — Creation date of the product — e.g. `2023-01-01T00:00:00Z`
  - `updated_at` *(string, required)* — Last updated date of the product — e.g. `2023-01-01T00:00:00Z`
- `customer` *(CustomerEntity | string, required)* — The customer who owns the subscription.
  *(fields of `CustomerEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object’s type. Objects of the same type share the same value.
  - `email` *(string, required)* — Customer email address. — e.g. `user@example.com`
  - `name` *(string, optional)* — Customer name. — e.g. `John Doe`
  - `metadata` *(object, optional)* — Additional metadata associated with the customer. — e.g. `{'key': 'value'}`
  - `country` *(string, required)* — The ISO 3166-1 alpha-2 country code for the customer. — e.g. `US`
  - `created_at` *(string, required)* — Creation date of the customer — e.g. `2023-01-01T00:00:00Z`
  - `updated_at` *(string, required)* — Last updated date of the customer — e.g. `2023-01-01T00:00:00Z`
- `items` *(array<SubscriptionItemEntity>, optional)* — Subscription items.
  *(fields of `SubscriptionItemEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object’s type. Objects of the same type share the same value.
  - `product_id` *(string, optional)* — The ID of the product associated with the subscription item.
  - `price_id` *(string, optional)* — The ID of the price associated with the subscription item.
  - `units` *(number, optional)* — The number of units for the subscription item.
- `collection_method` *(SubscriptionCollectionMethod, required)* — e.g. `charge_automatically`
- `status` *(SubscriptionStatus, required)* — e.g. `active`
- `last_transaction_id` *(string, optional)* — The ID of the last paid transaction. — e.g. `tran_3e6Z6TzvHKdsjEgXnGDEp0`
- `last_transaction` *(TransactionEntity, optional)* — The last paid transaction.
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value. — e.g. `transaction`
  - `amount` *(number, required)* — The transaction amount in cents. 1000 = $10.00 — e.g. `2000`
  - `amount_paid` *(number, optional)* — The amount the customer paid in cents. 1000 = $10.00 — e.g. `2000`
  - `discount_amount` *(number, optional)* — The discount amount in cents. 1000 = $10.00 — e.g. `2000`
  - `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
  - `type` *(TransactionType, required)*
  - `tax_country` *(string, optional)* — The ISO alpha-2 country code where tax is collected. — e.g. `US`
  - `tax_amount` *(number, optional)* — The sale tax amount in cents. 1000 = $10.00 — e.g. `2000`
  - `status` *(TransactionStatus, required)*
  - `refunded_amount` *(number, optional)* — The amount that has been refunded in cents. 1000 = $10.00 — e.g. `2000`
  - `order` *(string, optional)* — The order associated with the transaction.
  - `subscription` *(string, optional)* — The subscription associated with the transaction.
  - `customer` *(string, optional)* — The customer associated with the transaction.
  - `description` *(string, optional)* — The description of the transaction.
  - `period_start` *(number, optional)* — Start period for the invoice as timestamp
  - `period_end` *(number, optional)* — End period for the invoice as timestamp
  - `created_at` *(number, required)* — Creation date of the order as timestamp
- `last_transaction_date` *(string, optional)* — The date of the last paid transaction. — e.g. `2024-09-12T12:34:56Z`
- `next_transaction_date` *(string, optional)* — The date when the next subscription transaction will be charged. — e.g. `2024-09-12T12:34:56Z`
- `current_period_start_date` *(string, optional)* — The start date of the current subscription period. — e.g. `2024-09-12T12:34:56Z`
- `current_period_end_date` *(string, optional)* — The end date of the current subscription period. — e.g. `2024-09-12T12:34:56Z`
- `canceled_at` *(string, optional)* — The date and time when the subscription was canceled, if applicable. — e.g. `2024-09-12T12:34:56Z`
- `created_at` *(string, required)* — The date and time when the subscription was created. — e.g. `2024-01-01T00:00:00Z`
- `updated_at` *(string, required)* — The date and time when the subscription was last updated. — e.g. `2024-09-12T12:34:56Z`
- `discount` *(object{id, discountCode, name, type, amount, duration, durationI...}, optional)* — The discount applied to the subscription, if any.
  - `id` *(string, optional)* — The unique identifier of the discount (e.g. dis_...). — e.g. `dis_3e6Z6TzvHKdsjEgXnGDEp0`
  - `discountCode` *(string, optional)* — The discount code applied to the subscription. — e.g. `HOLIDAY2024`
  - `name` *(string, optional)*
  - `type` *(enum: percentage|fixed, optional)*
  - `amount` *(number, optional)*
  - `duration` *(enum: forever|once|repeating, optional)*
  - `durationInMonths` *(number, optional)*
- `metadata` *(object, optional)* — Metadata for the subscription in the form of key-value pairs. — e.g. `{'userId': 'user_123', 'plan': 'pro'}`

---

### `GET /v1/subscriptions/search` — List all subscriptions

Search and retrieve a paginated list of subscriptions. View status, billing cycle, and customer info.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `searchSubscriptions`.


**Query parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `page_number` | number | no (default: `1`) | The page number for pagination. |
| `page_size` | number | no (default: `10`) | The number of items per page. |


**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully retrieved subscriptions | SubscriptionListEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `SubscriptionListEntity`:**

- `items` *(array<SubscriptionEntity>, required)* — List of subscription items
  *(fields of `SubscriptionEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value. — e.g. `subscription`
  - `product` *(ProductEntity | string, required)* — The product associated with the subscription.
    *(fields of `ProductEntity`)*
    - `id` *(string, required)* — Unique identifier for the object.
    - `mode` *(EnvironmentMode, required)*
    - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value.
    - `name` *(string, required)* — The name of the product
    - `description` *(string, required)* — A brief description of the product — e.g. `This is a sample product description.`
    - `image_url` *(string, optional)* — URL of the product image. Only png as jpg are supported — e.g. `https://example.com/image.jpg`
    - `image_urls` *(array<string>, optional)* — Ordered list of product image URLs. The first entry is the cover image (mirrored in image_url). — e.g. `['https://example.com/image.jpg']`
    - `features` *(array<FeatureEntity>, optional)* — Features of the product.
      *(fields of `FeatureEntity`)*
      - `id` *(string, required)* — Unique identifier for the feature. — e.g. `feat_abc123`
      - `type` *(ProductFeatureType, required)* — e.g. `licenseKey`
      - `description` *(string, required)* — A brief description of the feature. — e.g. `Access to premium course materials.`
    - `price` *(number, required)* — The price of the product in cents. 1000 = $10.00 — e.g. `400`
    - `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
    - `billing_type` *(ProductBillingType, required)* — e.g. `recurring`
    - `billing_period` *(ProductBillingPeriod, required)* — e.g. `every-month`
    - `status` *(ProductStatus, required)* — e.g. `active`
    - `tax_mode` *(TaxMode, required)* — e.g. `inclusive`
    - `tax_category` *(TaxCategory, required)* — e.g. `saas`
    - `product_url` *(string, optional)* — The product page you can redirect your customers to for express checkout. — e.g. `https://creem.io/product/prod_123123123123`
    - `default_success_url` *(string, optional)* — The URL to which the user will be redirected after successfull payment. — e.g. `https://example.com/?status=successful`
    - `custom_fields` *(array<CustomField>, optional)* — Custom fields configured for the product. Collect additional information from your customer during checkout.
      *(fields of `CustomField`)*
      - `type` *(CustomFieldType, required)*
      - `key` *(string, required)* — Unique key for custom field. Must be unique to this field, alphanumeric, and up to 200 characters.
      - `label` *(string, required)* — The label for the field, displayed to the customer, up to 50 characters
      - `optional` *(boolean, optional)* — Whether the customer is required to complete the field. Defaults to `false`.
      - `text` *(Text, optional)* — Configuration for text field type.
        - `max_length` *(number, optional)* — Maximum character length constraint for the input.
        - `minimum_length` *(number, optional)* — Minimum character length requirement for the input.
        - `value` *(string, optional)* — The value of the input.
      - `checkbox` *(Checkbox, optional)* — Configuration for checkbox field type.
        - `label` *(string, optional)* — The markdown text to display for the checkbox.
        - `value` *(boolean, optional)* — The value of the checkbox (checked or not).
    - `created_at` *(string, required)* — Creation date of the product — e.g. `2023-01-01T00:00:00Z`
    - `updated_at` *(string, required)* — Last updated date of the product — e.g. `2023-01-01T00:00:00Z`
  - `customer` *(CustomerEntity | string, required)* — The customer who owns the subscription.
    *(fields of `CustomerEntity`)*
    - `id` *(string, required)* — Unique identifier for the object.
    - `mode` *(EnvironmentMode, required)*
    - `object` *(string, required)* — String representing the object’s type. Objects of the same type share the same value.
    - `email` *(string, required)* — Customer email address. — e.g. `user@example.com`
    - `name` *(string, optional)* — Customer name. — e.g. `John Doe`
    - `metadata` *(object, optional)* — Additional metadata associated with the customer. — e.g. `{'key': 'value'}`
    - `country` *(string, required)* — The ISO 3166-1 alpha-2 country code for the customer. — e.g. `US`
    - `created_at` *(string, required)* — Creation date of the customer — e.g. `2023-01-01T00:00:00Z`
    - `updated_at` *(string, required)* — Last updated date of the customer — e.g. `2023-01-01T00:00:00Z`
  - `items` *(array<SubscriptionItemEntity>, optional)* — Subscription items.
    *(fields of `SubscriptionItemEntity`)*
    - `id` *(string, required)* — Unique identifier for the object.
    - `mode` *(EnvironmentMode, required)*
    - `object` *(string, required)* — String representing the object’s type. Objects of the same type share the same value.
    - `product_id` *(string, optional)* — The ID of the product associated with the subscription item.
    - `price_id` *(string, optional)* — The ID of the price associated with the subscription item.
    - `units` *(number, optional)* — The number of units for the subscription item.
  - `collection_method` *(SubscriptionCollectionMethod, required)* — e.g. `charge_automatically`
  - `status` *(SubscriptionStatus, required)* — e.g. `active`
  - `last_transaction_id` *(string, optional)* — The ID of the last paid transaction. — e.g. `tran_3e6Z6TzvHKdsjEgXnGDEp0`
  - `last_transaction` *(TransactionEntity, optional)* — The last paid transaction.
    - `id` *(string, required)* — Unique identifier for the object.
    - `mode` *(EnvironmentMode, required)*
    - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value. — e.g. `transaction`
    - `amount` *(number, required)* — The transaction amount in cents. 1000 = $10.00 — e.g. `2000`
    - `amount_paid` *(number, optional)* — The amount the customer paid in cents. 1000 = $10.00 — e.g. `2000`
    - `discount_amount` *(number, optional)* — The discount amount in cents. 1000 = $10.00 — e.g. `2000`
    - `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
    - `type` *(TransactionType, required)*
    - `tax_country` *(string, optional)* — The ISO alpha-2 country code where tax is collected. — e.g. `US`
    - `tax_amount` *(number, optional)* — The sale tax amount in cents. 1000 = $10.00 — e.g. `2000`
    - `status` *(TransactionStatus, required)*
    - `refunded_amount` *(number, optional)* — The amount that has been refunded in cents. 1000 = $10.00 — e.g. `2000`
    - `order` *(string, optional)* — The order associated with the transaction.
    - `subscription` *(string, optional)* — The subscription associated with the transaction.
    - `customer` *(string, optional)* — The customer associated with the transaction.
    - `description` *(string, optional)* — The description of the transaction.
    - `period_start` *(number, optional)* — Start period for the invoice as timestamp
    - `period_end` *(number, optional)* — End period for the invoice as timestamp
    - `created_at` *(number, required)* — Creation date of the order as timestamp
  - `last_transaction_date` *(string, optional)* — The date of the last paid transaction. — e.g. `2024-09-12T12:34:56Z`
  - `next_transaction_date` *(string, optional)* — The date when the next subscription transaction will be charged. — e.g. `2024-09-12T12:34:56Z`
  - `current_period_start_date` *(string, optional)* — The start date of the current subscription period. — e.g. `2024-09-12T12:34:56Z`
  - `current_period_end_date` *(string, optional)* — The end date of the current subscription period. — e.g. `2024-09-12T12:34:56Z`
  - `canceled_at` *(string, optional)* — The date and time when the subscription was canceled, if applicable. — e.g. `2024-09-12T12:34:56Z`
  - `created_at` *(string, required)* — The date and time when the subscription was created. — e.g. `2024-01-01T00:00:00Z`
  - `updated_at` *(string, required)* — The date and time when the subscription was last updated. — e.g. `2024-09-12T12:34:56Z`
  - `discount` *(object{id, discountCode, name, type, amount, duration, durationI...}, optional)* — The discount applied to the subscription, if any.
    - `id` *(string, optional)* — The unique identifier of the discount (e.g. dis_...). — e.g. `dis_3e6Z6TzvHKdsjEgXnGDEp0`
    - `discountCode` *(string, optional)* — The discount code applied to the subscription. — e.g. `HOLIDAY2024`
    - `name` *(string, optional)*
    - `type` *(enum: percentage|fixed, optional)*
    - `amount` *(number, optional)*
    - `duration` *(enum: forever|once|repeating, optional)*
    - `durationInMonths` *(number, optional)*
  - `metadata` *(object, optional)* — Metadata for the subscription in the form of key-value pairs. — e.g. `{'userId': 'user_123', 'plan': 'pro'}`
- `pagination` *(PaginationEntity, required)* — Pagination details for the list
  - `total_records` *(number, required)* — Total number of records in the list — e.g. `0`
  - `total_pages` *(number, required)* — Total number of pages available — e.g. `0`
  - `current_page` *(number, required)* — The current page number — e.g. `1`
  - `next_page` *(number, required)* — The next page number, or null if there is no next page — e.g. `2`
  - `prev_page` *(number, required)* — The previous page number, or null if there is no previous page

---

### `POST /v1/subscriptions/{id}/cancel` — Cancel a subscription.

Cancel an active subscription immediately or schedule cancellation at period end.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `cancelSubscription`.


**Path parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | The unique identifier of the subscription |

**Request body** (application/json, required):

Schema: `CancelSubscriptionRequestEntity`

- `mode` *(enum: immediate|scheduled, optional)* — The mode of cancellation (immediate or scheduled), default can be configured in the store billing settings. — e.g. `immediate`
- `onExecute` *(enum: cancel|pause, optional)* — The action to execute when canceling (cancel or pause) when mode is scheduled, ignored when mode is immediate or not provided — e.g. `cancel`

**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully canceled a subscription | SubscriptionEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `SubscriptionEntity`:**

- `id` *(string, required)* — Unique identifier for the object.
- `mode` *(EnvironmentMode, required)*
- `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value. — e.g. `subscription`
- `product` *(ProductEntity | string, required)* — The product associated with the subscription.
  *(fields of `ProductEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value.
  - `name` *(string, required)* — The name of the product
  - `description` *(string, required)* — A brief description of the product — e.g. `This is a sample product description.`
  - `image_url` *(string, optional)* — URL of the product image. Only png as jpg are supported — e.g. `https://example.com/image.jpg`
  - `image_urls` *(array<string>, optional)* — Ordered list of product image URLs. The first entry is the cover image (mirrored in image_url). — e.g. `['https://example.com/image.jpg']`
  - `features` *(array<FeatureEntity>, optional)* — Features of the product.
    *(fields of `FeatureEntity`)*
    - `id` *(string, required)* — Unique identifier for the feature. — e.g. `feat_abc123`
    - `type` *(ProductFeatureType, required)* — e.g. `licenseKey`
    - `description` *(string, required)* — A brief description of the feature. — e.g. `Access to premium course materials.`
  - `price` *(number, required)* — The price of the product in cents. 1000 = $10.00 — e.g. `400`
  - `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
  - `billing_type` *(ProductBillingType, required)* — e.g. `recurring`
  - `billing_period` *(ProductBillingPeriod, required)* — e.g. `every-month`
  - `status` *(ProductStatus, required)* — e.g. `active`
  - `tax_mode` *(TaxMode, required)* — e.g. `inclusive`
  - `tax_category` *(TaxCategory, required)* — e.g. `saas`
  - `product_url` *(string, optional)* — The product page you can redirect your customers to for express checkout. — e.g. `https://creem.io/product/prod_123123123123`
  - `default_success_url` *(string, optional)* — The URL to which the user will be redirected after successfull payment. — e.g. `https://example.com/?status=successful`
  - `custom_fields` *(array<CustomField>, optional)* — Custom fields configured for the product. Collect additional information from your customer during checkout.
    *(fields of `CustomField`)*
    - `type` *(CustomFieldType, required)*
    - `key` *(string, required)* — Unique key for custom field. Must be unique to this field, alphanumeric, and up to 200 characters.
    - `label` *(string, required)* — The label for the field, displayed to the customer, up to 50 characters
    - `optional` *(boolean, optional)* — Whether the customer is required to complete the field. Defaults to `false`.
    - `text` *(Text, optional)* — Configuration for text field type.
      - `max_length` *(number, optional)* — Maximum character length constraint for the input.
      - `minimum_length` *(number, optional)* — Minimum character length requirement for the input.
      - `value` *(string, optional)* — The value of the input.
    - `checkbox` *(Checkbox, optional)* — Configuration for checkbox field type.
      - `label` *(string, optional)* — The markdown text to display for the checkbox.
      - `value` *(boolean, optional)* — The value of the checkbox (checked or not).
  - `created_at` *(string, required)* — Creation date of the product — e.g. `2023-01-01T00:00:00Z`
  - `updated_at` *(string, required)* — Last updated date of the product — e.g. `2023-01-01T00:00:00Z`
- `customer` *(CustomerEntity | string, required)* — The customer who owns the subscription.
  *(fields of `CustomerEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object’s type. Objects of the same type share the same value.
  - `email` *(string, required)* — Customer email address. — e.g. `user@example.com`
  - `name` *(string, optional)* — Customer name. — e.g. `John Doe`
  - `metadata` *(object, optional)* — Additional metadata associated with the customer. — e.g. `{'key': 'value'}`
  - `country` *(string, required)* — The ISO 3166-1 alpha-2 country code for the customer. — e.g. `US`
  - `created_at` *(string, required)* — Creation date of the customer — e.g. `2023-01-01T00:00:00Z`
  - `updated_at` *(string, required)* — Last updated date of the customer — e.g. `2023-01-01T00:00:00Z`
- `items` *(array<SubscriptionItemEntity>, optional)* — Subscription items.
  *(fields of `SubscriptionItemEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object’s type. Objects of the same type share the same value.
  - `product_id` *(string, optional)* — The ID of the product associated with the subscription item.
  - `price_id` *(string, optional)* — The ID of the price associated with the subscription item.
  - `units` *(number, optional)* — The number of units for the subscription item.
- `collection_method` *(SubscriptionCollectionMethod, required)* — e.g. `charge_automatically`
- `status` *(SubscriptionStatus, required)* — e.g. `active`
- `last_transaction_id` *(string, optional)* — The ID of the last paid transaction. — e.g. `tran_3e6Z6TzvHKdsjEgXnGDEp0`
- `last_transaction` *(TransactionEntity, optional)* — The last paid transaction.
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value. — e.g. `transaction`
  - `amount` *(number, required)* — The transaction amount in cents. 1000 = $10.00 — e.g. `2000`
  - `amount_paid` *(number, optional)* — The amount the customer paid in cents. 1000 = $10.00 — e.g. `2000`
  - `discount_amount` *(number, optional)* — The discount amount in cents. 1000 = $10.00 — e.g. `2000`
  - `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
  - `type` *(TransactionType, required)*
  - `tax_country` *(string, optional)* — The ISO alpha-2 country code where tax is collected. — e.g. `US`
  - `tax_amount` *(number, optional)* — The sale tax amount in cents. 1000 = $10.00 — e.g. `2000`
  - `status` *(TransactionStatus, required)*
  - `refunded_amount` *(number, optional)* — The amount that has been refunded in cents. 1000 = $10.00 — e.g. `2000`
  - `order` *(string, optional)* — The order associated with the transaction.
  - `subscription` *(string, optional)* — The subscription associated with the transaction.
  - `customer` *(string, optional)* — The customer associated with the transaction.
  - `description` *(string, optional)* — The description of the transaction.
  - `period_start` *(number, optional)* — Start period for the invoice as timestamp
  - `period_end` *(number, optional)* — End period for the invoice as timestamp
  - `created_at` *(number, required)* — Creation date of the order as timestamp
- `last_transaction_date` *(string, optional)* — The date of the last paid transaction. — e.g. `2024-09-12T12:34:56Z`
- `next_transaction_date` *(string, optional)* — The date when the next subscription transaction will be charged. — e.g. `2024-09-12T12:34:56Z`
- `current_period_start_date` *(string, optional)* — The start date of the current subscription period. — e.g. `2024-09-12T12:34:56Z`
- `current_period_end_date` *(string, optional)* — The end date of the current subscription period. — e.g. `2024-09-12T12:34:56Z`
- `canceled_at` *(string, optional)* — The date and time when the subscription was canceled, if applicable. — e.g. `2024-09-12T12:34:56Z`
- `created_at` *(string, required)* — The date and time when the subscription was created. — e.g. `2024-01-01T00:00:00Z`
- `updated_at` *(string, required)* — The date and time when the subscription was last updated. — e.g. `2024-09-12T12:34:56Z`
- `discount` *(object{id, discountCode, name, type, amount, duration, durationI...}, optional)* — The discount applied to the subscription, if any.
  - `id` *(string, optional)* — The unique identifier of the discount (e.g. dis_...). — e.g. `dis_3e6Z6TzvHKdsjEgXnGDEp0`
  - `discountCode` *(string, optional)* — The discount code applied to the subscription. — e.g. `HOLIDAY2024`
  - `name` *(string, optional)*
  - `type` *(enum: percentage|fixed, optional)*
  - `amount` *(number, optional)*
  - `duration` *(enum: forever|once|repeating, optional)*
  - `durationInMonths` *(number, optional)*
- `metadata` *(object, optional)* — Metadata for the subscription in the form of key-value pairs. — e.g. `{'userId': 'user_123', 'plan': 'pro'}`

---

### `POST /v1/subscriptions/{id}` — Update a subscription.

Modify subscription details like units, seats, or add-ons. Support proration and immediate billing options.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `updateSubscription`.


**Path parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | The unique identifier of the subscription |

**Request body** (application/json, required):

Schema: `UpdateSubscriptionRequestEntity`

- `items` *(array<UpsertSubscriptionItemEntity>, optional)* — List of subscription items to update/create. If no item ID is provided, the item will be created.
  *(fields of `UpsertSubscriptionItemEntity`)*
  - `id` *(string, optional)* — The id of the item to update.
  - `product_id` *(string, optional)* — The ID of the product associated with the subscription item.
  - `price_id` *(string, optional)* — The ID of the price associated with the subscription item.
  - `units` *(number, optional)* — The number of units for the subscription item.
- `update_behavior` *(enum: proration-charge-immediately|proration-charge|proration-none, optional)* — The update behavior for the subscription (defaults to proration)

**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully updated a subscription | SubscriptionEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `SubscriptionEntity`:**

- `id` *(string, required)* — Unique identifier for the object.
- `mode` *(EnvironmentMode, required)*
- `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value. — e.g. `subscription`
- `product` *(ProductEntity | string, required)* — The product associated with the subscription.
  *(fields of `ProductEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value.
  - `name` *(string, required)* — The name of the product
  - `description` *(string, required)* — A brief description of the product — e.g. `This is a sample product description.`
  - `image_url` *(string, optional)* — URL of the product image. Only png as jpg are supported — e.g. `https://example.com/image.jpg`
  - `image_urls` *(array<string>, optional)* — Ordered list of product image URLs. The first entry is the cover image (mirrored in image_url). — e.g. `['https://example.com/image.jpg']`
  - `features` *(array<FeatureEntity>, optional)* — Features of the product.
    *(fields of `FeatureEntity`)*
    - `id` *(string, required)* — Unique identifier for the feature. — e.g. `feat_abc123`
    - `type` *(ProductFeatureType, required)* — e.g. `licenseKey`
    - `description` *(string, required)* — A brief description of the feature. — e.g. `Access to premium course materials.`
  - `price` *(number, required)* — The price of the product in cents. 1000 = $10.00 — e.g. `400`
  - `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
  - `billing_type` *(ProductBillingType, required)* — e.g. `recurring`
  - `billing_period` *(ProductBillingPeriod, required)* — e.g. `every-month`
  - `status` *(ProductStatus, required)* — e.g. `active`
  - `tax_mode` *(TaxMode, required)* — e.g. `inclusive`
  - `tax_category` *(TaxCategory, required)* — e.g. `saas`
  - `product_url` *(string, optional)* — The product page you can redirect your customers to for express checkout. — e.g. `https://creem.io/product/prod_123123123123`
  - `default_success_url` *(string, optional)* — The URL to which the user will be redirected after successfull payment. — e.g. `https://example.com/?status=successful`
  - `custom_fields` *(array<CustomField>, optional)* — Custom fields configured for the product. Collect additional information from your customer during checkout.
    *(fields of `CustomField`)*
    - `type` *(CustomFieldType, required)*
    - `key` *(string, required)* — Unique key for custom field. Must be unique to this field, alphanumeric, and up to 200 characters.
    - `label` *(string, required)* — The label for the field, displayed to the customer, up to 50 characters
    - `optional` *(boolean, optional)* — Whether the customer is required to complete the field. Defaults to `false`.
    - `text` *(Text, optional)* — Configuration for text field type.
      - `max_length` *(number, optional)* — Maximum character length constraint for the input.
      - `minimum_length` *(number, optional)* — Minimum character length requirement for the input.
      - `value` *(string, optional)* — The value of the input.
    - `checkbox` *(Checkbox, optional)* — Configuration for checkbox field type.
      - `label` *(string, optional)* — The markdown text to display for the checkbox.
      - `value` *(boolean, optional)* — The value of the checkbox (checked or not).
  - `created_at` *(string, required)* — Creation date of the product — e.g. `2023-01-01T00:00:00Z`
  - `updated_at` *(string, required)* — Last updated date of the product — e.g. `2023-01-01T00:00:00Z`
- `customer` *(CustomerEntity | string, required)* — The customer who owns the subscription.
  *(fields of `CustomerEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object’s type. Objects of the same type share the same value.
  - `email` *(string, required)* — Customer email address. — e.g. `user@example.com`
  - `name` *(string, optional)* — Customer name. — e.g. `John Doe`
  - `metadata` *(object, optional)* — Additional metadata associated with the customer. — e.g. `{'key': 'value'}`
  - `country` *(string, required)* — The ISO 3166-1 alpha-2 country code for the customer. — e.g. `US`
  - `created_at` *(string, required)* — Creation date of the customer — e.g. `2023-01-01T00:00:00Z`
  - `updated_at` *(string, required)* — Last updated date of the customer — e.g. `2023-01-01T00:00:00Z`
- `items` *(array<SubscriptionItemEntity>, optional)* — Subscription items.
  *(fields of `SubscriptionItemEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object’s type. Objects of the same type share the same value.
  - `product_id` *(string, optional)* — The ID of the product associated with the subscription item.
  - `price_id` *(string, optional)* — The ID of the price associated with the subscription item.
  - `units` *(number, optional)* — The number of units for the subscription item.
- `collection_method` *(SubscriptionCollectionMethod, required)* — e.g. `charge_automatically`
- `status` *(SubscriptionStatus, required)* — e.g. `active`
- `last_transaction_id` *(string, optional)* — The ID of the last paid transaction. — e.g. `tran_3e6Z6TzvHKdsjEgXnGDEp0`
- `last_transaction` *(TransactionEntity, optional)* — The last paid transaction.
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value. — e.g. `transaction`
  - `amount` *(number, required)* — The transaction amount in cents. 1000 = $10.00 — e.g. `2000`
  - `amount_paid` *(number, optional)* — The amount the customer paid in cents. 1000 = $10.00 — e.g. `2000`
  - `discount_amount` *(number, optional)* — The discount amount in cents. 1000 = $10.00 — e.g. `2000`
  - `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
  - `type` *(TransactionType, required)*
  - `tax_country` *(string, optional)* — The ISO alpha-2 country code where tax is collected. — e.g. `US`
  - `tax_amount` *(number, optional)* — The sale tax amount in cents. 1000 = $10.00 — e.g. `2000`
  - `status` *(TransactionStatus, required)*
  - `refunded_amount` *(number, optional)* — The amount that has been refunded in cents. 1000 = $10.00 — e.g. `2000`
  - `order` *(string, optional)* — The order associated with the transaction.
  - `subscription` *(string, optional)* — The subscription associated with the transaction.
  - `customer` *(string, optional)* — The customer associated with the transaction.
  - `description` *(string, optional)* — The description of the transaction.
  - `period_start` *(number, optional)* — Start period for the invoice as timestamp
  - `period_end` *(number, optional)* — End period for the invoice as timestamp
  - `created_at` *(number, required)* — Creation date of the order as timestamp
- `last_transaction_date` *(string, optional)* — The date of the last paid transaction. — e.g. `2024-09-12T12:34:56Z`
- `next_transaction_date` *(string, optional)* — The date when the next subscription transaction will be charged. — e.g. `2024-09-12T12:34:56Z`
- `current_period_start_date` *(string, optional)* — The start date of the current subscription period. — e.g. `2024-09-12T12:34:56Z`
- `current_period_end_date` *(string, optional)* — The end date of the current subscription period. — e.g. `2024-09-12T12:34:56Z`
- `canceled_at` *(string, optional)* — The date and time when the subscription was canceled, if applicable. — e.g. `2024-09-12T12:34:56Z`
- `created_at` *(string, required)* — The date and time when the subscription was created. — e.g. `2024-01-01T00:00:00Z`
- `updated_at` *(string, required)* — The date and time when the subscription was last updated. — e.g. `2024-09-12T12:34:56Z`
- `discount` *(object{id, discountCode, name, type, amount, duration, durationI...}, optional)* — The discount applied to the subscription, if any.
  - `id` *(string, optional)* — The unique identifier of the discount (e.g. dis_...). — e.g. `dis_3e6Z6TzvHKdsjEgXnGDEp0`
  - `discountCode` *(string, optional)* — The discount code applied to the subscription. — e.g. `HOLIDAY2024`
  - `name` *(string, optional)*
  - `type` *(enum: percentage|fixed, optional)*
  - `amount` *(number, optional)*
  - `duration` *(enum: forever|once|repeating, optional)*
  - `durationInMonths` *(number, optional)*
- `metadata` *(object, optional)* — Metadata for the subscription in the form of key-value pairs. — e.g. `{'userId': 'user_123', 'plan': 'pro'}`

---

### `POST /v1/subscriptions/{id}/upgrade` — Upgrade a subscription to a different product

Upgrade a subscription to a different product or plan. Handle proration and plan changes seamlessly.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `upgradeSubscription`.


**Path parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | The unique identifier of the subscription |

**Request body** (application/json, required):

Schema: `UpgradeSubscriptionRequestEntity`

- `product_id` *(string, required)* — The ID of the product to upgrade to — e.g. `prod_123`
- `update_behavior` *(enum: proration-charge-immediately|proration-charge|proration-none, optional)* — The update behavior for the subscription (defaults to proration-charge-immediately)

**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully upgraded the subscription | SubscriptionEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `SubscriptionEntity`:**

- `id` *(string, required)* — Unique identifier for the object.
- `mode` *(EnvironmentMode, required)*
- `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value. — e.g. `subscription`
- `product` *(ProductEntity | string, required)* — The product associated with the subscription.
  *(fields of `ProductEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value.
  - `name` *(string, required)* — The name of the product
  - `description` *(string, required)* — A brief description of the product — e.g. `This is a sample product description.`
  - `image_url` *(string, optional)* — URL of the product image. Only png as jpg are supported — e.g. `https://example.com/image.jpg`
  - `image_urls` *(array<string>, optional)* — Ordered list of product image URLs. The first entry is the cover image (mirrored in image_url). — e.g. `['https://example.com/image.jpg']`
  - `features` *(array<FeatureEntity>, optional)* — Features of the product.
    *(fields of `FeatureEntity`)*
    - `id` *(string, required)* — Unique identifier for the feature. — e.g. `feat_abc123`
    - `type` *(ProductFeatureType, required)* — e.g. `licenseKey`
    - `description` *(string, required)* — A brief description of the feature. — e.g. `Access to premium course materials.`
  - `price` *(number, required)* — The price of the product in cents. 1000 = $10.00 — e.g. `400`
  - `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
  - `billing_type` *(ProductBillingType, required)* — e.g. `recurring`
  - `billing_period` *(ProductBillingPeriod, required)* — e.g. `every-month`
  - `status` *(ProductStatus, required)* — e.g. `active`
  - `tax_mode` *(TaxMode, required)* — e.g. `inclusive`
  - `tax_category` *(TaxCategory, required)* — e.g. `saas`
  - `product_url` *(string, optional)* — The product page you can redirect your customers to for express checkout. — e.g. `https://creem.io/product/prod_123123123123`
  - `default_success_url` *(string, optional)* — The URL to which the user will be redirected after successfull payment. — e.g. `https://example.com/?status=successful`
  - `custom_fields` *(array<CustomField>, optional)* — Custom fields configured for the product. Collect additional information from your customer during checkout.
    *(fields of `CustomField`)*
    - `type` *(CustomFieldType, required)*
    - `key` *(string, required)* — Unique key for custom field. Must be unique to this field, alphanumeric, and up to 200 characters.
    - `label` *(string, required)* — The label for the field, displayed to the customer, up to 50 characters
    - `optional` *(boolean, optional)* — Whether the customer is required to complete the field. Defaults to `false`.
    - `text` *(Text, optional)* — Configuration for text field type.
      - `max_length` *(number, optional)* — Maximum character length constraint for the input.
      - `minimum_length` *(number, optional)* — Minimum character length requirement for the input.
      - `value` *(string, optional)* — The value of the input.
    - `checkbox` *(Checkbox, optional)* — Configuration for checkbox field type.
      - `label` *(string, optional)* — The markdown text to display for the checkbox.
      - `value` *(boolean, optional)* — The value of the checkbox (checked or not).
  - `created_at` *(string, required)* — Creation date of the product — e.g. `2023-01-01T00:00:00Z`
  - `updated_at` *(string, required)* — Last updated date of the product — e.g. `2023-01-01T00:00:00Z`
- `customer` *(CustomerEntity | string, required)* — The customer who owns the subscription.
  *(fields of `CustomerEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object’s type. Objects of the same type share the same value.
  - `email` *(string, required)* — Customer email address. — e.g. `user@example.com`
  - `name` *(string, optional)* — Customer name. — e.g. `John Doe`
  - `metadata` *(object, optional)* — Additional metadata associated with the customer. — e.g. `{'key': 'value'}`
  - `country` *(string, required)* — The ISO 3166-1 alpha-2 country code for the customer. — e.g. `US`
  - `created_at` *(string, required)* — Creation date of the customer — e.g. `2023-01-01T00:00:00Z`
  - `updated_at` *(string, required)* — Last updated date of the customer — e.g. `2023-01-01T00:00:00Z`
- `items` *(array<SubscriptionItemEntity>, optional)* — Subscription items.
  *(fields of `SubscriptionItemEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object’s type. Objects of the same type share the same value.
  - `product_id` *(string, optional)* — The ID of the product associated with the subscription item.
  - `price_id` *(string, optional)* — The ID of the price associated with the subscription item.
  - `units` *(number, optional)* — The number of units for the subscription item.
- `collection_method` *(SubscriptionCollectionMethod, required)* — e.g. `charge_automatically`
- `status` *(SubscriptionStatus, required)* — e.g. `active`
- `last_transaction_id` *(string, optional)* — The ID of the last paid transaction. — e.g. `tran_3e6Z6TzvHKdsjEgXnGDEp0`
- `last_transaction` *(TransactionEntity, optional)* — The last paid transaction.
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value. — e.g. `transaction`
  - `amount` *(number, required)* — The transaction amount in cents. 1000 = $10.00 — e.g. `2000`
  - `amount_paid` *(number, optional)* — The amount the customer paid in cents. 1000 = $10.00 — e.g. `2000`
  - `discount_amount` *(number, optional)* — The discount amount in cents. 1000 = $10.00 — e.g. `2000`
  - `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
  - `type` *(TransactionType, required)*
  - `tax_country` *(string, optional)* — The ISO alpha-2 country code where tax is collected. — e.g. `US`
  - `tax_amount` *(number, optional)* — The sale tax amount in cents. 1000 = $10.00 — e.g. `2000`
  - `status` *(TransactionStatus, required)*
  - `refunded_amount` *(number, optional)* — The amount that has been refunded in cents. 1000 = $10.00 — e.g. `2000`
  - `order` *(string, optional)* — The order associated with the transaction.
  - `subscription` *(string, optional)* — The subscription associated with the transaction.
  - `customer` *(string, optional)* — The customer associated with the transaction.
  - `description` *(string, optional)* — The description of the transaction.
  - `period_start` *(number, optional)* — Start period for the invoice as timestamp
  - `period_end` *(number, optional)* — End period for the invoice as timestamp
  - `created_at` *(number, required)* — Creation date of the order as timestamp
- `last_transaction_date` *(string, optional)* — The date of the last paid transaction. — e.g. `2024-09-12T12:34:56Z`
- `next_transaction_date` *(string, optional)* — The date when the next subscription transaction will be charged. — e.g. `2024-09-12T12:34:56Z`
- `current_period_start_date` *(string, optional)* — The start date of the current subscription period. — e.g. `2024-09-12T12:34:56Z`
- `current_period_end_date` *(string, optional)* — The end date of the current subscription period. — e.g. `2024-09-12T12:34:56Z`
- `canceled_at` *(string, optional)* — The date and time when the subscription was canceled, if applicable. — e.g. `2024-09-12T12:34:56Z`
- `created_at` *(string, required)* — The date and time when the subscription was created. — e.g. `2024-01-01T00:00:00Z`
- `updated_at` *(string, required)* — The date and time when the subscription was last updated. — e.g. `2024-09-12T12:34:56Z`
- `discount` *(object{id, discountCode, name, type, amount, duration, durationI...}, optional)* — The discount applied to the subscription, if any.
  - `id` *(string, optional)* — The unique identifier of the discount (e.g. dis_...). — e.g. `dis_3e6Z6TzvHKdsjEgXnGDEp0`
  - `discountCode` *(string, optional)* — The discount code applied to the subscription. — e.g. `HOLIDAY2024`
  - `name` *(string, optional)*
  - `type` *(enum: percentage|fixed, optional)*
  - `amount` *(number, optional)*
  - `duration` *(enum: forever|once|repeating, optional)*
  - `durationInMonths` *(number, optional)*
- `metadata` *(object, optional)* — Metadata for the subscription in the form of key-value pairs. — e.g. `{'userId': 'user_123', 'plan': 'pro'}`

---

### `POST /v1/subscriptions/{id}/pause` — Pause a subscription.

Temporarily pause a subscription. Stop billing while retaining the subscription for later resumption.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `pauseSubscription`.


**Path parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | The unique identifier of the subscription |


**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully paused a subscription | SubscriptionEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `SubscriptionEntity`:**

- `id` *(string, required)* — Unique identifier for the object.
- `mode` *(EnvironmentMode, required)*
- `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value. — e.g. `subscription`
- `product` *(ProductEntity | string, required)* — The product associated with the subscription.
  *(fields of `ProductEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value.
  - `name` *(string, required)* — The name of the product
  - `description` *(string, required)* — A brief description of the product — e.g. `This is a sample product description.`
  - `image_url` *(string, optional)* — URL of the product image. Only png as jpg are supported — e.g. `https://example.com/image.jpg`
  - `image_urls` *(array<string>, optional)* — Ordered list of product image URLs. The first entry is the cover image (mirrored in image_url). — e.g. `['https://example.com/image.jpg']`
  - `features` *(array<FeatureEntity>, optional)* — Features of the product.
    *(fields of `FeatureEntity`)*
    - `id` *(string, required)* — Unique identifier for the feature. — e.g. `feat_abc123`
    - `type` *(ProductFeatureType, required)* — e.g. `licenseKey`
    - `description` *(string, required)* — A brief description of the feature. — e.g. `Access to premium course materials.`
  - `price` *(number, required)* — The price of the product in cents. 1000 = $10.00 — e.g. `400`
  - `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
  - `billing_type` *(ProductBillingType, required)* — e.g. `recurring`
  - `billing_period` *(ProductBillingPeriod, required)* — e.g. `every-month`
  - `status` *(ProductStatus, required)* — e.g. `active`
  - `tax_mode` *(TaxMode, required)* — e.g. `inclusive`
  - `tax_category` *(TaxCategory, required)* — e.g. `saas`
  - `product_url` *(string, optional)* — The product page you can redirect your customers to for express checkout. — e.g. `https://creem.io/product/prod_123123123123`
  - `default_success_url` *(string, optional)* — The URL to which the user will be redirected after successfull payment. — e.g. `https://example.com/?status=successful`
  - `custom_fields` *(array<CustomField>, optional)* — Custom fields configured for the product. Collect additional information from your customer during checkout.
    *(fields of `CustomField`)*
    - `type` *(CustomFieldType, required)*
    - `key` *(string, required)* — Unique key for custom field. Must be unique to this field, alphanumeric, and up to 200 characters.
    - `label` *(string, required)* — The label for the field, displayed to the customer, up to 50 characters
    - `optional` *(boolean, optional)* — Whether the customer is required to complete the field. Defaults to `false`.
    - `text` *(Text, optional)* — Configuration for text field type.
      - `max_length` *(number, optional)* — Maximum character length constraint for the input.
      - `minimum_length` *(number, optional)* — Minimum character length requirement for the input.
      - `value` *(string, optional)* — The value of the input.
    - `checkbox` *(Checkbox, optional)* — Configuration for checkbox field type.
      - `label` *(string, optional)* — The markdown text to display for the checkbox.
      - `value` *(boolean, optional)* — The value of the checkbox (checked or not).
  - `created_at` *(string, required)* — Creation date of the product — e.g. `2023-01-01T00:00:00Z`
  - `updated_at` *(string, required)* — Last updated date of the product — e.g. `2023-01-01T00:00:00Z`
- `customer` *(CustomerEntity | string, required)* — The customer who owns the subscription.
  *(fields of `CustomerEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object’s type. Objects of the same type share the same value.
  - `email` *(string, required)* — Customer email address. — e.g. `user@example.com`
  - `name` *(string, optional)* — Customer name. — e.g. `John Doe`
  - `metadata` *(object, optional)* — Additional metadata associated with the customer. — e.g. `{'key': 'value'}`
  - `country` *(string, required)* — The ISO 3166-1 alpha-2 country code for the customer. — e.g. `US`
  - `created_at` *(string, required)* — Creation date of the customer — e.g. `2023-01-01T00:00:00Z`
  - `updated_at` *(string, required)* — Last updated date of the customer — e.g. `2023-01-01T00:00:00Z`
- `items` *(array<SubscriptionItemEntity>, optional)* — Subscription items.
  *(fields of `SubscriptionItemEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object’s type. Objects of the same type share the same value.
  - `product_id` *(string, optional)* — The ID of the product associated with the subscription item.
  - `price_id` *(string, optional)* — The ID of the price associated with the subscription item.
  - `units` *(number, optional)* — The number of units for the subscription item.
- `collection_method` *(SubscriptionCollectionMethod, required)* — e.g. `charge_automatically`
- `status` *(SubscriptionStatus, required)* — e.g. `active`
- `last_transaction_id` *(string, optional)* — The ID of the last paid transaction. — e.g. `tran_3e6Z6TzvHKdsjEgXnGDEp0`
- `last_transaction` *(TransactionEntity, optional)* — The last paid transaction.
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value. — e.g. `transaction`
  - `amount` *(number, required)* — The transaction amount in cents. 1000 = $10.00 — e.g. `2000`
  - `amount_paid` *(number, optional)* — The amount the customer paid in cents. 1000 = $10.00 — e.g. `2000`
  - `discount_amount` *(number, optional)* — The discount amount in cents. 1000 = $10.00 — e.g. `2000`
  - `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
  - `type` *(TransactionType, required)*
  - `tax_country` *(string, optional)* — The ISO alpha-2 country code where tax is collected. — e.g. `US`
  - `tax_amount` *(number, optional)* — The sale tax amount in cents. 1000 = $10.00 — e.g. `2000`
  - `status` *(TransactionStatus, required)*
  - `refunded_amount` *(number, optional)* — The amount that has been refunded in cents. 1000 = $10.00 — e.g. `2000`
  - `order` *(string, optional)* — The order associated with the transaction.
  - `subscription` *(string, optional)* — The subscription associated with the transaction.
  - `customer` *(string, optional)* — The customer associated with the transaction.
  - `description` *(string, optional)* — The description of the transaction.
  - `period_start` *(number, optional)* — Start period for the invoice as timestamp
  - `period_end` *(number, optional)* — End period for the invoice as timestamp
  - `created_at` *(number, required)* — Creation date of the order as timestamp
- `last_transaction_date` *(string, optional)* — The date of the last paid transaction. — e.g. `2024-09-12T12:34:56Z`
- `next_transaction_date` *(string, optional)* — The date when the next subscription transaction will be charged. — e.g. `2024-09-12T12:34:56Z`
- `current_period_start_date` *(string, optional)* — The start date of the current subscription period. — e.g. `2024-09-12T12:34:56Z`
- `current_period_end_date` *(string, optional)* — The end date of the current subscription period. — e.g. `2024-09-12T12:34:56Z`
- `canceled_at` *(string, optional)* — The date and time when the subscription was canceled, if applicable. — e.g. `2024-09-12T12:34:56Z`
- `created_at` *(string, required)* — The date and time when the subscription was created. — e.g. `2024-01-01T00:00:00Z`
- `updated_at` *(string, required)* — The date and time when the subscription was last updated. — e.g. `2024-09-12T12:34:56Z`
- `discount` *(object{id, discountCode, name, type, amount, duration, durationI...}, optional)* — The discount applied to the subscription, if any.
  - `id` *(string, optional)* — The unique identifier of the discount (e.g. dis_...). — e.g. `dis_3e6Z6TzvHKdsjEgXnGDEp0`
  - `discountCode` *(string, optional)* — The discount code applied to the subscription. — e.g. `HOLIDAY2024`
  - `name` *(string, optional)*
  - `type` *(enum: percentage|fixed, optional)*
  - `amount` *(number, optional)*
  - `duration` *(enum: forever|once|repeating, optional)*
  - `durationInMonths` *(number, optional)*
- `metadata` *(object, optional)* — Metadata for the subscription in the form of key-value pairs. — e.g. `{'userId': 'user_123', 'plan': 'pro'}`

---

### `POST /v1/subscriptions/{id}/resume` — Resume a subscription.

Resume a subscription. Subscription must be in paused or scheduled_cancel status.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `resumeSubscription`.


**Path parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | The unique identifier of the subscription |


**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully resumed a subscription | SubscriptionEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `SubscriptionEntity`:**

- `id` *(string, required)* — Unique identifier for the object.
- `mode` *(EnvironmentMode, required)*
- `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value. — e.g. `subscription`
- `product` *(ProductEntity | string, required)* — The product associated with the subscription.
  *(fields of `ProductEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value.
  - `name` *(string, required)* — The name of the product
  - `description` *(string, required)* — A brief description of the product — e.g. `This is a sample product description.`
  - `image_url` *(string, optional)* — URL of the product image. Only png as jpg are supported — e.g. `https://example.com/image.jpg`
  - `image_urls` *(array<string>, optional)* — Ordered list of product image URLs. The first entry is the cover image (mirrored in image_url). — e.g. `['https://example.com/image.jpg']`
  - `features` *(array<FeatureEntity>, optional)* — Features of the product.
    *(fields of `FeatureEntity`)*
    - `id` *(string, required)* — Unique identifier for the feature. — e.g. `feat_abc123`
    - `type` *(ProductFeatureType, required)* — e.g. `licenseKey`
    - `description` *(string, required)* — A brief description of the feature. — e.g. `Access to premium course materials.`
  - `price` *(number, required)* — The price of the product in cents. 1000 = $10.00 — e.g. `400`
  - `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
  - `billing_type` *(ProductBillingType, required)* — e.g. `recurring`
  - `billing_period` *(ProductBillingPeriod, required)* — e.g. `every-month`
  - `status` *(ProductStatus, required)* — e.g. `active`
  - `tax_mode` *(TaxMode, required)* — e.g. `inclusive`
  - `tax_category` *(TaxCategory, required)* — e.g. `saas`
  - `product_url` *(string, optional)* — The product page you can redirect your customers to for express checkout. — e.g. `https://creem.io/product/prod_123123123123`
  - `default_success_url` *(string, optional)* — The URL to which the user will be redirected after successfull payment. — e.g. `https://example.com/?status=successful`
  - `custom_fields` *(array<CustomField>, optional)* — Custom fields configured for the product. Collect additional information from your customer during checkout.
    *(fields of `CustomField`)*
    - `type` *(CustomFieldType, required)*
    - `key` *(string, required)* — Unique key for custom field. Must be unique to this field, alphanumeric, and up to 200 characters.
    - `label` *(string, required)* — The label for the field, displayed to the customer, up to 50 characters
    - `optional` *(boolean, optional)* — Whether the customer is required to complete the field. Defaults to `false`.
    - `text` *(Text, optional)* — Configuration for text field type.
      - `max_length` *(number, optional)* — Maximum character length constraint for the input.
      - `minimum_length` *(number, optional)* — Minimum character length requirement for the input.
      - `value` *(string, optional)* — The value of the input.
    - `checkbox` *(Checkbox, optional)* — Configuration for checkbox field type.
      - `label` *(string, optional)* — The markdown text to display for the checkbox.
      - `value` *(boolean, optional)* — The value of the checkbox (checked or not).
  - `created_at` *(string, required)* — Creation date of the product — e.g. `2023-01-01T00:00:00Z`
  - `updated_at` *(string, required)* — Last updated date of the product — e.g. `2023-01-01T00:00:00Z`
- `customer` *(CustomerEntity | string, required)* — The customer who owns the subscription.
  *(fields of `CustomerEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object’s type. Objects of the same type share the same value.
  - `email` *(string, required)* — Customer email address. — e.g. `user@example.com`
  - `name` *(string, optional)* — Customer name. — e.g. `John Doe`
  - `metadata` *(object, optional)* — Additional metadata associated with the customer. — e.g. `{'key': 'value'}`
  - `country` *(string, required)* — The ISO 3166-1 alpha-2 country code for the customer. — e.g. `US`
  - `created_at` *(string, required)* — Creation date of the customer — e.g. `2023-01-01T00:00:00Z`
  - `updated_at` *(string, required)* — Last updated date of the customer — e.g. `2023-01-01T00:00:00Z`
- `items` *(array<SubscriptionItemEntity>, optional)* — Subscription items.
  *(fields of `SubscriptionItemEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object’s type. Objects of the same type share the same value.
  - `product_id` *(string, optional)* — The ID of the product associated with the subscription item.
  - `price_id` *(string, optional)* — The ID of the price associated with the subscription item.
  - `units` *(number, optional)* — The number of units for the subscription item.
- `collection_method` *(SubscriptionCollectionMethod, required)* — e.g. `charge_automatically`
- `status` *(SubscriptionStatus, required)* — e.g. `active`
- `last_transaction_id` *(string, optional)* — The ID of the last paid transaction. — e.g. `tran_3e6Z6TzvHKdsjEgXnGDEp0`
- `last_transaction` *(TransactionEntity, optional)* — The last paid transaction.
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value. — e.g. `transaction`
  - `amount` *(number, required)* — The transaction amount in cents. 1000 = $10.00 — e.g. `2000`
  - `amount_paid` *(number, optional)* — The amount the customer paid in cents. 1000 = $10.00 — e.g. `2000`
  - `discount_amount` *(number, optional)* — The discount amount in cents. 1000 = $10.00 — e.g. `2000`
  - `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
  - `type` *(TransactionType, required)*
  - `tax_country` *(string, optional)* — The ISO alpha-2 country code where tax is collected. — e.g. `US`
  - `tax_amount` *(number, optional)* — The sale tax amount in cents. 1000 = $10.00 — e.g. `2000`
  - `status` *(TransactionStatus, required)*
  - `refunded_amount` *(number, optional)* — The amount that has been refunded in cents. 1000 = $10.00 — e.g. `2000`
  - `order` *(string, optional)* — The order associated with the transaction.
  - `subscription` *(string, optional)* — The subscription associated with the transaction.
  - `customer` *(string, optional)* — The customer associated with the transaction.
  - `description` *(string, optional)* — The description of the transaction.
  - `period_start` *(number, optional)* — Start period for the invoice as timestamp
  - `period_end` *(number, optional)* — End period for the invoice as timestamp
  - `created_at` *(number, required)* — Creation date of the order as timestamp
- `last_transaction_date` *(string, optional)* — The date of the last paid transaction. — e.g. `2024-09-12T12:34:56Z`
- `next_transaction_date` *(string, optional)* — The date when the next subscription transaction will be charged. — e.g. `2024-09-12T12:34:56Z`
- `current_period_start_date` *(string, optional)* — The start date of the current subscription period. — e.g. `2024-09-12T12:34:56Z`
- `current_period_end_date` *(string, optional)* — The end date of the current subscription period. — e.g. `2024-09-12T12:34:56Z`
- `canceled_at` *(string, optional)* — The date and time when the subscription was canceled, if applicable. — e.g. `2024-09-12T12:34:56Z`
- `created_at` *(string, required)* — The date and time when the subscription was created. — e.g. `2024-01-01T00:00:00Z`
- `updated_at` *(string, required)* — The date and time when the subscription was last updated. — e.g. `2024-09-12T12:34:56Z`
- `discount` *(object{id, discountCode, name, type, amount, duration, durationI...}, optional)* — The discount applied to the subscription, if any.
  - `id` *(string, optional)* — The unique identifier of the discount (e.g. dis_...). — e.g. `dis_3e6Z6TzvHKdsjEgXnGDEp0`
  - `discountCode` *(string, optional)* — The discount code applied to the subscription. — e.g. `HOLIDAY2024`
  - `name` *(string, optional)*
  - `type` *(enum: percentage|fixed, optional)*
  - `amount` *(number, optional)*
  - `duration` *(enum: forever|once|repeating, optional)*
  - `durationInMonths` *(number, optional)*
- `metadata` *(object, optional)* — Metadata for the subscription in the form of key-value pairs. — e.g. `{'userId': 'user_123', 'plan': 'pro'}`

---

### Transactions

### `GET /v1/transactions` — Get a transaction by ID

Retrieve a single transaction by ID. View payment details, status, and associated order information.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `getTransactionById`.


**Query parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `transaction_id` | string | yes | The unique identifier of the transaction. |


**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully retrieved transaction | TransactionEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `TransactionEntity`:**

- `id` *(string, required)* — Unique identifier for the object.
- `mode` *(EnvironmentMode, required)*
- `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value. — e.g. `transaction`
- `amount` *(number, required)* — The transaction amount in cents. 1000 = $10.00 — e.g. `2000`
- `amount_paid` *(number, optional)* — The amount the customer paid in cents. 1000 = $10.00 — e.g. `2000`
- `discount_amount` *(number, optional)* — The discount amount in cents. 1000 = $10.00 — e.g. `2000`
- `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
- `type` *(TransactionType, required)*
- `tax_country` *(string, optional)* — The ISO alpha-2 country code where tax is collected. — e.g. `US`
- `tax_amount` *(number, optional)* — The sale tax amount in cents. 1000 = $10.00 — e.g. `2000`
- `status` *(TransactionStatus, required)*
- `refunded_amount` *(number, optional)* — The amount that has been refunded in cents. 1000 = $10.00 — e.g. `2000`
- `order` *(string, optional)* — The order associated with the transaction.
- `subscription` *(string, optional)* — The subscription associated with the transaction.
- `customer` *(string, optional)* — The customer associated with the transaction.
- `description` *(string, optional)* — The description of the transaction.
- `period_start` *(number, optional)* — Start period for the invoice as timestamp
- `period_end` *(number, optional)* — End period for the invoice as timestamp
- `created_at` *(number, required)* — Creation date of the order as timestamp

---

### `GET /v1/transactions/search` — List all transactions

Search and retrieve payment transactions. Filter by customer, product, date range, and status.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `searchTransactions`.


**Query parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `customer_id` | string | no | Filter transactions by customer ID. |
| `order_id` | string | no | Filter transactions by order ID. |
| `product_id` | string | no | Filter transactions by product ID. |
| `page_number` | number | no (default: `1`) | The page number for pagination. |
| `page_size` | number | no (default: `10`) | The number of items per page. |


**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully retrieved transactions | TransactionListEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `TransactionListEntity`:**

- `items` *(array<TransactionEntity>, required)* — List of transactions items
  *(fields of `TransactionEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value. — e.g. `transaction`
  - `amount` *(number, required)* — The transaction amount in cents. 1000 = $10.00 — e.g. `2000`
  - `amount_paid` *(number, optional)* — The amount the customer paid in cents. 1000 = $10.00 — e.g. `2000`
  - `discount_amount` *(number, optional)* — The discount amount in cents. 1000 = $10.00 — e.g. `2000`
  - `currency` *(string, required)* — Three-letter ISO currency code, in uppercase. Must be a supported currency. — e.g. `USD`
  - `type` *(TransactionType, required)*
  - `tax_country` *(string, optional)* — The ISO alpha-2 country code where tax is collected. — e.g. `US`
  - `tax_amount` *(number, optional)* — The sale tax amount in cents. 1000 = $10.00 — e.g. `2000`
  - `status` *(TransactionStatus, required)*
  - `refunded_amount` *(number, optional)* — The amount that has been refunded in cents. 1000 = $10.00 — e.g. `2000`
  - `order` *(string, optional)* — The order associated with the transaction.
  - `subscription` *(string, optional)* — The subscription associated with the transaction.
  - `customer` *(string, optional)* — The customer associated with the transaction.
  - `description` *(string, optional)* — The description of the transaction.
  - `period_start` *(number, optional)* — Start period for the invoice as timestamp
  - `period_end` *(number, optional)* — End period for the invoice as timestamp
  - `created_at` *(number, required)* — Creation date of the order as timestamp
- `pagination` *(PaginationEntity, required)* — Pagination details for the list
  - `total_records` *(number, required)* — Total number of records in the list — e.g. `0`
  - `total_pages` *(number, required)* — Total number of pages available — e.g. `0`
  - `current_page` *(number, required)* — The current page number — e.g. `1`
  - `next_page` *(number, required)* — The next page number, or null if there is no next page — e.g. `2`
  - `prev_page` *(number, required)* — The previous page number, or null if there is no previous page

---

### Discounts

### `GET /v1/discounts/search` — Search discounts

Search and list discount codes for a store with filters and pagination.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `searchDiscounts`.


**Query parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `page_number` | number | no (default: `1`) | The page number for pagination. |
| `page_size` | number | no (default: `10`) | The number of items per page. |
| `product_id` | string | no | Filter discounts that apply to a specific product. |
| `status` | enum: active\|deleted | no | Filter by discount status. |
| `type` | enum: percentage\|fixed | no | Filter by discount type. |
| `created_after` | string | no | Filter discounts created after this date. |
| `created_before` | string | no | Filter discounts created before this date. |


**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully retrieved the list of discounts | DiscountListEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `DiscountListEntity`:**

- `items` *(array<DiscountEntity>, required)* — List of discount items
  *(fields of `DiscountEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — A string representing the object’s type. Objects of the same type share the same value. — e.g. `discount`
  - `status` *(enum: deleted|active|draft|expired|scheduled, required)* — The status of the discount (e.g., active, inactive). — e.g. `active`
  - `name` *(string, required)* — The name of the discount. — e.g. `Holiday Sale`
  - `code` *(string, required)* — The discount code. A unique identifier for the discount. — e.g. `HOLIDAY2024`
  - `type` *(enum: percentage|fixed, required)* — The type of the discount, either "percentage" or "fixed". — e.g. `percentage`
  - `amount` *(number, optional)* — The amount of the discount. Can be a percentage or a fixed amount. — e.g. `20`
  - `currency` *(string, optional)* — The currency of the discount. Only required if type is "fixed". — e.g. `USD`
  - `percentage` *(number, optional)* — The percentage of the discount. Only applicable if type is "percentage". — e.g. `15`
  - `expiry_date` *(string, optional)* — The expiry date of the discount. — e.g. `2024-12-31T23:59:59Z`
  - `max_redemptions` *(number, optional)* — The maximum number of redemptions allowed for the discount. — e.g. `100`
  - `duration` *(enum: forever|once|repeating, optional)* — The duration type for the discount. — e.g. `repeating`
  - `duration_in_months` *(number, optional)* — The number of months the discount is valid for. Only applicable if the duration is "repeating" and the product is a subscription. — e.g. `6`
  - `applies_to_products` *(array<string>, optional)* — The list of product IDs to which this discount applies. — e.g. `['prod_123', 'prod_456']`
  - `redeem_count` *(number, optional)* — The number of times this discount has been redeemed. — e.g. `15`
- `pagination` *(PaginationEntity, required)* — Pagination details for the list
  - `total_records` *(number, required)* — Total number of records in the list — e.g. `0`
  - `total_pages` *(number, required)* — Total number of pages available — e.g. `0`
  - `current_page` *(number, required)* — The current page number — e.g. `1`
  - `next_page` *(number, required)* — The next page number, or null if there is no next page — e.g. `2`
  - `prev_page` *(number, required)* — The previous page number, or null if there is no previous page

---

### `GET /v1/discounts` — Retrieve discount

Retrieve discount code details by ID or code. Check usage limits, expiration, and discount amount.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `retrieveDiscount`.


**Query parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `discount_id` | string | no | The unique identifier of the discount (provide either discount_id OR discount_code). |
| `discount_code` | string | no | The unique discount code (provide either discount_id OR discount_code). |


**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully retrieved the discount | DiscountEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `DiscountEntity`:**

- `id` *(string, required)* — Unique identifier for the object.
- `mode` *(EnvironmentMode, required)*
- `object` *(string, required)* — A string representing the object’s type. Objects of the same type share the same value. — e.g. `discount`
- `status` *(enum: deleted|active|draft|expired|scheduled, required)* — The status of the discount (e.g., active, inactive). — e.g. `active`
- `name` *(string, required)* — The name of the discount. — e.g. `Holiday Sale`
- `code` *(string, required)* — The discount code. A unique identifier for the discount. — e.g. `HOLIDAY2024`
- `type` *(enum: percentage|fixed, required)* — The type of the discount, either "percentage" or "fixed". — e.g. `percentage`
- `amount` *(number, optional)* — The amount of the discount. Can be a percentage or a fixed amount. — e.g. `20`
- `currency` *(string, optional)* — The currency of the discount. Only required if type is "fixed". — e.g. `USD`
- `percentage` *(number, optional)* — The percentage of the discount. Only applicable if type is "percentage". — e.g. `15`
- `expiry_date` *(string, optional)* — The expiry date of the discount. — e.g. `2024-12-31T23:59:59Z`
- `max_redemptions` *(number, optional)* — The maximum number of redemptions allowed for the discount. — e.g. `100`
- `duration` *(enum: forever|once|repeating, optional)* — The duration type for the discount. — e.g. `repeating`
- `duration_in_months` *(number, optional)* — The number of months the discount is valid for. Only applicable if the duration is "repeating" and the product is a subscription. — e.g. `6`
- `applies_to_products` *(array<string>, optional)* — The list of product IDs to which this discount applies. — e.g. `['prod_123', 'prod_456']`
- `redeem_count` *(number, optional)* — The number of times this discount has been redeemed. — e.g. `15`

---

### `POST /v1/discounts` — Create a discount.

Create promotional discount codes for products. Set percentage or fixed amount discounts with expiration dates.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `createDiscount`.


**Request body** (application/json, required):

Schema: `CreateDiscountRequestEntity`

- `name` *(string, required)* — The name of the discount. — e.g. `Holiday Sale`
- `code` *(string, optional)* — Optional discount code. If left empty, a code will be generated. — e.g. `HOLIDAY2024`
- `type` *(DiscountType, required)*
- `amount` *(number, optional)* — The fixed value for the discount. Only applicable if the type is "fixed". — e.g. `20`
- `currency` *(string, optional)* — The currency of the discount. Only required if type is "fixed". — e.g. `USD`
- `percentage` *(number, optional)* — The percentage value for the discount. Only applicable if the type is "percentage". — e.g. `15`
- `expiry_date` *(string, optional)* — The expiry date of the discount. — e.g. `2024-12-31T23:59:59Z`
- `max_redemptions` *(number, optional)* — The maximum number of redemptions for the discount. — e.g. `100`
- `duration` *(CouponDurationType, required)* — e.g. `repeating`
- `duration_in_months` *(number, optional)* — The number of months the discount is valid for. Only applicable if the duration is "repeating" and the product is a subscription. — e.g. `6`
- `applies_to_products` *(array<string>, required)* — The list of product IDs to which this discount applies. — e.g. `['prod_123', 'prod_456']`

**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully created a discount | DiscountEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `DiscountEntity`:**

- `id` *(string, required)* — Unique identifier for the object.
- `mode` *(EnvironmentMode, required)*
- `object` *(string, required)* — A string representing the object’s type. Objects of the same type share the same value. — e.g. `discount`
- `status` *(enum: deleted|active|draft|expired|scheduled, required)* — The status of the discount (e.g., active, inactive). — e.g. `active`
- `name` *(string, required)* — The name of the discount. — e.g. `Holiday Sale`
- `code` *(string, required)* — The discount code. A unique identifier for the discount. — e.g. `HOLIDAY2024`
- `type` *(enum: percentage|fixed, required)* — The type of the discount, either "percentage" or "fixed". — e.g. `percentage`
- `amount` *(number, optional)* — The amount of the discount. Can be a percentage or a fixed amount. — e.g. `20`
- `currency` *(string, optional)* — The currency of the discount. Only required if type is "fixed". — e.g. `USD`
- `percentage` *(number, optional)* — The percentage of the discount. Only applicable if type is "percentage". — e.g. `15`
- `expiry_date` *(string, optional)* — The expiry date of the discount. — e.g. `2024-12-31T23:59:59Z`
- `max_redemptions` *(number, optional)* — The maximum number of redemptions allowed for the discount. — e.g. `100`
- `duration` *(enum: forever|once|repeating, optional)* — The duration type for the discount. — e.g. `repeating`
- `duration_in_months` *(number, optional)* — The number of months the discount is valid for. Only applicable if the duration is "repeating" and the product is a subscription. — e.g. `6`
- `applies_to_products` *(array<string>, optional)* — The list of product IDs to which this discount applies. — e.g. `['prod_123', 'prod_456']`
- `redeem_count` *(number, optional)* — The number of times this discount has been redeemed. — e.g. `15`

---

### `DELETE /v1/discounts/{id}/delete` — Delete a discount.

Permanently delete a discount code. Prevent further usage of the discount.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `deleteDiscount`.


**Path parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | The unique identifier of the discount to delete |


**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully deleted a discount | DiscountEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `DiscountEntity`:**

- `id` *(string, required)* — Unique identifier for the object.
- `mode` *(EnvironmentMode, required)*
- `object` *(string, required)* — A string representing the object’s type. Objects of the same type share the same value. — e.g. `discount`
- `status` *(enum: deleted|active|draft|expired|scheduled, required)* — The status of the discount (e.g., active, inactive). — e.g. `active`
- `name` *(string, required)* — The name of the discount. — e.g. `Holiday Sale`
- `code` *(string, required)* — The discount code. A unique identifier for the discount. — e.g. `HOLIDAY2024`
- `type` *(enum: percentage|fixed, required)* — The type of the discount, either "percentage" or "fixed". — e.g. `percentage`
- `amount` *(number, optional)* — The amount of the discount. Can be a percentage or a fixed amount. — e.g. `20`
- `currency` *(string, optional)* — The currency of the discount. Only required if type is "fixed". — e.g. `USD`
- `percentage` *(number, optional)* — The percentage of the discount. Only applicable if type is "percentage". — e.g. `15`
- `expiry_date` *(string, optional)* — The expiry date of the discount. — e.g. `2024-12-31T23:59:59Z`
- `max_redemptions` *(number, optional)* — The maximum number of redemptions allowed for the discount. — e.g. `100`
- `duration` *(enum: forever|once|repeating, optional)* — The duration type for the discount. — e.g. `repeating`
- `duration_in_months` *(number, optional)* — The number of months the discount is valid for. Only applicable if the duration is "repeating" and the product is a subscription. — e.g. `6`
- `applies_to_products` *(array<string>, optional)* — The list of product IDs to which this discount applies. — e.g. `['prod_123', 'prod_456']`
- `redeem_count` *(number, optional)* — The number of times this discount has been redeemed. — e.g. `15`

---

### Licenses

### `POST /v1/licenses/activate` — Activates a license key.

Activate a license key for a specific device or instance. Register new activations and track usage limits.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `activateLicense`.


**Request body** (application/json, required):

Schema: `ActivateLicenseRequestEntity`

- `key` *(string, required)* — The license key to activate.
- `instance_name` *(string, required)* — A label for the new instance to identify it in Creem.

**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully activated a license key | LicenseEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `LicenseEntity`:**

- `id` *(string, required)* — Unique identifier for the object.
- `mode` *(EnvironmentMode, required)*
- `object` *(string, required)* — A string representing the object's type. Objects of the same type share the same value.
- `product_id` *(string, required)* — The ID of the product this license belongs to. — e.g. `prod_abc123`
- `status` *(LicenseStatus, required)* — e.g. `active`
- `key` *(string, required)* — The license key. — e.g. `ABC123-XYZ456-XYZ456-XYZ456`
- `activation` *(number, required)* — The number of instances that this license key was activated. — e.g. `5`
- `activation_limit` *(number, optional)* — The activation limit. Null if activations are unlimited. — e.g. `1`
- `expires_at` *(string, optional)* — The date the license key expires. Null if it does not have an expiration date. — e.g. `2023-09-13T00:00:00Z`
- `created_at` *(string, required)* — The creation date of the license key. — e.g. `2023-09-13T00:00:00Z`
- `instance` *(LicenseInstanceEntity, optional)* — Associated license instances.
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — A string representing the object’s type. Objects of the same type share the same value. — e.g. `license-instance`
  - `name` *(string, required)* — The name of the license instance. — e.g. `My Customer License Instance`
  - `status` *(enum: active|deactivated, required)* — The status of the license instance. — e.g. `active`
  - `created_at` *(string, required)* — The creation date of the license instance. — e.g. `2023-09-13T00:00:00Z`

---

### `POST /v1/licenses/deactivate` — Deactivate a license key instance.

Remove a device activation from a license key. Free up activation slots for new devices.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `deactivateLicense`.


**Request body** (application/json, required):

Schema: `DeactivateLicenseRequestEntity`

- `key` *(string, required)* — The license key to deactivate.
- `instance_id` *(string, required)* — Id of the instance to deactivate.

**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully deactivated a license key instance | LicenseEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `LicenseEntity`:**

- `id` *(string, required)* — Unique identifier for the object.
- `mode` *(EnvironmentMode, required)*
- `object` *(string, required)* — A string representing the object's type. Objects of the same type share the same value.
- `product_id` *(string, required)* — The ID of the product this license belongs to. — e.g. `prod_abc123`
- `status` *(LicenseStatus, required)* — e.g. `active`
- `key` *(string, required)* — The license key. — e.g. `ABC123-XYZ456-XYZ456-XYZ456`
- `activation` *(number, required)* — The number of instances that this license key was activated. — e.g. `5`
- `activation_limit` *(number, optional)* — The activation limit. Null if activations are unlimited. — e.g. `1`
- `expires_at` *(string, optional)* — The date the license key expires. Null if it does not have an expiration date. — e.g. `2023-09-13T00:00:00Z`
- `created_at` *(string, required)* — The creation date of the license key. — e.g. `2023-09-13T00:00:00Z`
- `instance` *(LicenseInstanceEntity, optional)* — Associated license instances.
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — A string representing the object’s type. Objects of the same type share the same value. — e.g. `license-instance`
  - `name` *(string, required)* — The name of the license instance. — e.g. `My Customer License Instance`
  - `status` *(enum: active|deactivated, required)* — The status of the license instance. — e.g. `active`
  - `created_at` *(string, required)* — The creation date of the license instance. — e.g. `2023-09-13T00:00:00Z`

---

### `POST /v1/licenses/validate` — Validates a license key or instance.

Verify if a license key is valid and active for a specific instance. Check activation status and expiration.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `validateLicense`.


**Request body** (application/json, required):

Schema: `ValidateLicenseRequestEntity`

- `key` *(string, required)* — The license key to validate.
- `instance_id` *(string, required)* — Id of the instance to validate.

**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully validated a license key instance | LicenseEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `LicenseEntity`:**

- `id` *(string, required)* — Unique identifier for the object.
- `mode` *(EnvironmentMode, required)*
- `object` *(string, required)* — A string representing the object's type. Objects of the same type share the same value.
- `product_id` *(string, required)* — The ID of the product this license belongs to. — e.g. `prod_abc123`
- `status` *(LicenseStatus, required)* — e.g. `active`
- `key` *(string, required)* — The license key. — e.g. `ABC123-XYZ456-XYZ456-XYZ456`
- `activation` *(number, required)* — The number of instances that this license key was activated. — e.g. `5`
- `activation_limit` *(number, optional)* — The activation limit. Null if activations are unlimited. — e.g. `1`
- `expires_at` *(string, optional)* — The date the license key expires. Null if it does not have an expiration date. — e.g. `2023-09-13T00:00:00Z`
- `created_at` *(string, required)* — The creation date of the license key. — e.g. `2023-09-13T00:00:00Z`
- `instance` *(LicenseInstanceEntity, optional)* — Associated license instances.
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — A string representing the object’s type. Objects of the same type share the same value. — e.g. `license-instance`
  - `name` *(string, required)* — The name of the license instance. — e.g. `My Customer License Instance`
  - `status` *(enum: active|deactivated, required)* — The status of the license instance. — e.g. `active`
  - `created_at` *(string, required)* — The creation date of the license instance. — e.g. `2023-09-13T00:00:00Z`

---

### `GET /v1/licenses/{id}/instances` — List license instances.

Retrieve a paginated list of instances (activations) for a license key. Use an instance id from this list to deactivate it via the deactivate endpoint.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `listLicenseInstances`.


**Path parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | The unique identifier of the license key |
| `page_number` | number | no (default: `1`) | The page number for pagination. |
| `page_size` | number | no (default: `10`) | The number of items per page. |


**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully retrieved license instances | LicenseInstanceListEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `LicenseInstanceListEntity`:**

- `items` *(array<LicenseInstanceEntity>, required)* — List of license instance items
  *(fields of `LicenseInstanceEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — A string representing the object’s type. Objects of the same type share the same value. — e.g. `license-instance`
  - `name` *(string, required)* — The name of the license instance. — e.g. `My Customer License Instance`
  - `status` *(enum: active|deactivated, required)* — The status of the license instance. — e.g. `active`
  - `created_at` *(string, required)* — The creation date of the license instance. — e.g. `2023-09-13T00:00:00Z`
- `pagination` *(PaginationEntity, required)* — Pagination details for the list
  - `total_records` *(number, required)* — Total number of records in the list — e.g. `0`
  - `total_pages` *(number, required)* — Total number of pages available — e.g. `0`
  - `current_page` *(number, required)* — The current page number — e.g. `1`
  - `next_page` *(number, required)* — The next page number, or null if there is no next page — e.g. `2`
  - `prev_page` *(number, required)* — The previous page number, or null if there is no previous page

---

### Customer Credits

> **Experimental:** this API is tagged `Customer Credits - Accounts (Experimental)` in the official spec and may change.

### `GET /v1/customer-credits/accounts` — List customer credits accounts

List accounts for the authenticated store with cursor pagination. System accounts are excluded.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `listCustomerCreditsAccounts`.


**Query parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `limit` | number | no (default: `10`) | Maximum number of accounts to return |
| `customer_id` | string | no | Filter by owner ID (e.g. customer ID) |
| `starting_after` | string | no | Cursor for forward pagination — account ID to start after |
| `ending_before` | string | no | Cursor for backward pagination — account ID to end before |


**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Paginated list of accounts | AccountListResponseDto |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `AccountListResponseDto`:**

- `object` *(string, required)* — Object type — e.g. `list`
- `data` *(array<AccountResponseDto>, required)* — Array of accounts
  *(fields of `AccountResponseDto`)*
  - `id` *(string, required)* — Account ID — e.g. `cca_abc123`
  - `store_id` *(string, required)* — Store ID
  - `customer_id` *(string, required)* — Owner ID — e.g. `cust_abc123`
  - `name` *(string, required)* — Account name — e.g. `default`
  - `unit_label` *(string, required)* — Unit label — e.g. `credits`
  - `status` *(enum: active|frozen|closed, required)* — Account status
  - `created_at` *(string, required)* — Creation timestamp
  - `updated_at` *(string, required)* — Last update timestamp
- `has_more` *(boolean, required)* — Whether more items exist beyond this page

---

### `POST /v1/customer-credits/accounts` — Create a customer credits account

Create a new credits account for a customer. Optionally seed it with an initial balance.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `createCustomerCreditsAccount`.


**Request body** (application/json, required):

Schema: `CreateAccountDto`

- `name` *(string, optional)* — Human-readable name for the account — e.g. `default`
- `customer_id` *(string, required)* — The owner ID this account belongs to (e.g. customer ID) — e.g. `cust_abc123`
- `unit_label` *(string, optional)* — Label for the unit of currency/credits — e.g. `credits`
- `initial_balance` *(string, optional)* — Seed the account with this many credits on creation — e.g. `300`

**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `201` | Account created | AccountResponseDto |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

---

### `GET /v1/customer-credits/accounts/{id}` — Retrieve a customer credits account

Get details of a customer credits account by ID.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `getCustomerCreditsAccount`.


**Path parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes |  |


**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Account details | AccountResponseDto |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `AccountResponseDto`:**

- `id` *(string, required)* — Account ID — e.g. `cca_abc123`
- `store_id` *(string, required)* — Store ID
- `customer_id` *(string, required)* — Owner ID — e.g. `cust_abc123`
- `name` *(string, required)* — Account name — e.g. `default`
- `unit_label` *(string, required)* — Unit label — e.g. `credits`
- `status` *(enum: active|frozen|closed, required)* — Account status
- `created_at` *(string, required)* — Creation timestamp
- `updated_at` *(string, required)* — Last update timestamp

---

### `GET /v1/customer-credits/accounts/{id}/balance` — Get account balance

Get the current balance of an account. Optionally pass ?at= for historical balance.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `getCustomerCreditsAccountBalance`.


**Path parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes |  |
| `at` | string | no | ISO 8601 date. If present, computes balance at that point in time. If absent, returns O(1) projected balance. |


**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Account balance | BalanceResponseDto |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `BalanceResponseDto`:**

- `balance` *(string, required)* — Current balance as string for bigint safety — e.g. `5000`
- `updated_at` *(string, optional)* — Last update timestamp (present for projected balance)
- `as_of` *(string, optional)* — Point-in-time the balance was computed at (present for at-time queries)

---

### `GET /v1/customer-credits/accounts/{id}/entries` — List account entries

List the credit and debit history for an account with cursor pagination.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `listCustomerCreditsAccountEntries`.


**Path parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes |  |
| `limit` | number | no (default: `10`) | Maximum number of entries to return |
| `starting_after` | string | no | Cursor for forward pagination — entry ID to start after |
| `ending_before` | string | no | Cursor for backward pagination — entry ID to end before |


**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Paginated list of entries | EntryListResponseDto |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `EntryListResponseDto`:**

- `object` *(string, required)* — Object type — e.g. `list`
- `data` *(array<EntryResponseDto>, required)* — Array of entries
  *(fields of `EntryResponseDto`)*
  - `id` *(string, required)* — Entry ID — e.g. `cce_abc123`
  - `transaction_id` *(string, required)* — Transaction ID — e.g. `cct_abc123`
  - `account_id` *(string, required)* — Account ID — e.g. `cca_abc123`
  - `side` *(enum: debit|credit, required)* — Debit or credit side
  - `amount` *(string, required)* — Amount as string for bigint safety — e.g. `1000`
  - `created_at` *(string, required)* — Creation timestamp
- `has_more` *(boolean, required)* — Whether more items exist beyond this page

---

### `POST /v1/customer-credits/accounts/{id}/freeze` — Freeze an account

Freeze an account to prevent new transactions.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `freezeCustomerCreditsAccount`.


**Path parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes |  |


**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Account frozen | AccountResponseDto |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |
| `409` | Account already frozen or closed | CustomerCreditsErrorResponseDto |

**Response 200 body — `AccountResponseDto`:**

- `id` *(string, required)* — Account ID — e.g. `cca_abc123`
- `store_id` *(string, required)* — Store ID
- `customer_id` *(string, required)* — Owner ID — e.g. `cust_abc123`
- `name` *(string, required)* — Account name — e.g. `default`
- `unit_label` *(string, required)* — Unit label — e.g. `credits`
- `status` *(enum: active|frozen|closed, required)* — Account status
- `created_at` *(string, required)* — Creation timestamp
- `updated_at` *(string, required)* — Last update timestamp

---

### `POST /v1/customer-credits/accounts/{id}/unfreeze` — Unfreeze an account

Unfreeze a frozen account to allow transactions again.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `unfreezeCustomerCreditsAccount`.


**Path parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes |  |


**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Account unfrozen | AccountResponseDto |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |
| `409` | Account is not frozen or is closed | CustomerCreditsErrorResponseDto |

**Response 200 body — `AccountResponseDto`:**

- `id` *(string, required)* — Account ID — e.g. `cca_abc123`
- `store_id` *(string, required)* — Store ID
- `customer_id` *(string, required)* — Owner ID — e.g. `cust_abc123`
- `name` *(string, required)* — Account name — e.g. `default`
- `unit_label` *(string, required)* — Unit label — e.g. `credits`
- `status` *(enum: active|frozen|closed, required)* — Account status
- `created_at` *(string, required)* — Creation timestamp
- `updated_at` *(string, required)* — Last update timestamp

---

### `POST /v1/customer-credits/accounts/{id}/credit` — Credit an account

Add credits to a customer account. Returns the resulting transaction record.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `creditCustomerCreditsAccount`.


**Path parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes |  |

**Request body** (application/json, required):

Schema: `CreditDebitRequestDto`

- `amount` *(string, required)* — Amount to credit or debit (string to support large numbers) — e.g. `1000`
- `reference` *(string, required)* — Your reference ID to link this transaction to an event in your system (e.g. order ID, campaign ID) — e.g. `signup_bonus`
- `idempotency_key` *(string, required)* — Idempotency key to prevent duplicate transactions — e.g. `idem_abc123`

**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `201` | Credit transaction created | TransactionResponseDto |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |
| `409` | Account frozen or closed | CustomerCreditsErrorResponseDto |

---

### `POST /v1/customer-credits/accounts/{id}/debit` — Debit an account

Deduct credits from a customer account. Returns the resulting transaction record.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `debitCustomerCreditsAccount`.


**Path parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes |  |

**Request body** (application/json, required):

Schema: `CreditDebitRequestDto`

- `amount` *(string, required)* — Amount to credit or debit (string to support large numbers) — e.g. `1000`
- `reference` *(string, required)* — Your reference ID to link this transaction to an event in your system (e.g. order ID, campaign ID) — e.g. `signup_bonus`
- `idempotency_key` *(string, required)* — Idempotency key to prevent duplicate transactions — e.g. `idem_abc123`

**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `201` | Debit transaction created | TransactionResponseDto |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |
| `409` | Account frozen or closed | CustomerCreditsErrorResponseDto |

---

### `POST /v1/customer-credits/accounts/{id}/reverse` — Reverse a transaction

Reverse a previous credit or debit on this account. Creates a new transaction that undoes the original, preserving the full history.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `reverseCustomerCreditsAccountTransaction`.


**Path parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes |  |

**Request body** (application/json, required):

Schema: `ReverseTransactionRequestDto`

- `transaction_id` *(string, required)* — ID of the transaction to reverse — e.g. `cct_abc123`

**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `201` | Reversal transaction created | TransactionResponseDto |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

---

### `POST /v1/customer-credits/accounts/{id}/close` — Close an account

Permanently close an account. This action cannot be undone.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `closeCustomerCreditsAccount`.


**Path parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes |  |


**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Account closed | AccountResponseDto |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |
| `409` | Account already closed | CustomerCreditsErrorResponseDto |

**Response 200 body — `AccountResponseDto`:**

- `id` *(string, required)* — Account ID — e.g. `cca_abc123`
- `store_id` *(string, required)* — Store ID
- `customer_id` *(string, required)* — Owner ID — e.g. `cust_abc123`
- `name` *(string, required)* — Account name — e.g. `default`
- `unit_label` *(string, required)* — Unit label — e.g. `credits`
- `status` *(enum: active|frozen|closed, required)* — Account status
- `created_at` *(string, required)* — Creation timestamp
- `updated_at` *(string, required)* — Last update timestamp

---

### Refunds

### `POST /v1/refunds` — Refund a payment

Issue a full refund for a payment, identified by its transaction ID. The full remaining refundable amount is resolved automatically. Returns `pending` when the payment provider confirms the refund asynchronously.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `refundPayment`.


**Request body** (application/json, required):

Schema: `CreateRefundRequestEntity`

- `transaction_id` *(string, required)* — The unique identifier of the transaction to refund in full. — e.g. `tran_1234567890`

**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully created the refund | RefundResponseEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `RefundResponseEntity`:**

- `status` *(RefundStatus, required)* — e.g. `succeeded`

---

### Affiliates

### `GET /v1/affiliates` — List all affiliates

Retrieve a paginated list of your affiliates with their referral link, click and conversion counts, and lifetime commission. Affiliates who were invited but have not yet joined a program are not included.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `listAffiliates`.


**Query parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `page_number` | number | no (default: `1`) | The page number for pagination. |
| `page_size` | number | no (default: `50`) | The number of items per page. |


**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully retrieved affiliates | AffiliateListEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `AffiliateListEntity`:**

- `items` *(array<AffiliateEntity>, required)* — List of affiliate items
  *(fields of `AffiliateEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value. — e.g. `affiliate`
  - `email` *(string, required)* — The email address the affiliate was invited with. — e.g. `partner@example.com`
  - `name` *(string, optional)* — The display name of the affiliate, if set. — e.g. `Jane Partner`
  - `status` *(string, required)* — The affiliate's status within your program, reflecting their membership standing: `active`, `pending` (awaiting approval), `rejected`, `suspended`, or `inactive` (left or removed). Invited-but-not-yet-joined affiliates are not returned by this endpoint. — e.g. `active`
  - `referral_code` *(string, required)* — The affiliate's unique referral code. — e.g. `a1b2c3d4`
  - `referral_link` *(string, required)* — The affiliate's shareable referral link. Traffic arriving through it is attributed to this affiliate. — e.g. `https://creem.io/affiliate?code=a1b2c3d4`
  - `clicks` *(number, required)* — Total number of clicks recorded on the affiliate’s links. — e.g. `128`
  - `conversions` *(number, required)* — Total number of conversions attributed to the affiliate. — e.g. `12`
  - `earnings` *(number, required)* — Lifetime commission earned by the affiliate, in cents (1000 = $10.00), reported in a single primary currency (see `currency`). Affiliates earning in multiple currencies show only their highest-earning currency here; use the affiliate's commissions endpoint for the full per-currency breakdown. — e.g. `4200`
  - `currency` *(string, required)* — Three-letter ISO currency code, in uppercase, for the `earnings` amount. This is the affiliate's primary (highest-earning) currency; commissions in other currencies are listed individually on the commissions endpoint. — e.g. `USD`
- `pagination` *(PaginationEntity, required)* — Pagination details for the list
  - `total_records` *(number, required)* — Total number of records in the list — e.g. `0`
  - `total_pages` *(number, required)* — Total number of pages available — e.g. `0`
  - `current_page` *(number, required)* — The current page number — e.g. `1`
  - `next_page` *(number, required)* — The next page number, or null if there is no next page — e.g. `2`
  - `prev_page` *(number, required)* — The previous page number, or null if there is no previous page

---

### `GET /v1/affiliates/{id}` — Retrieve an affiliate

Retrieve a single affiliate by ID, including referral link, click and conversion counts, and lifetime commission.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `retrieveAffiliate`.


**Path parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | The unique identifier of the affiliate |


**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully retrieved the affiliate | AffiliateEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `AffiliateEntity`:**

- `id` *(string, required)* — Unique identifier for the object.
- `mode` *(EnvironmentMode, required)*
- `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value. — e.g. `affiliate`
- `email` *(string, required)* — The email address the affiliate was invited with. — e.g. `partner@example.com`
- `name` *(string, optional)* — The display name of the affiliate, if set. — e.g. `Jane Partner`
- `status` *(string, required)* — The affiliate's status within your program, reflecting their membership standing: `active`, `pending` (awaiting approval), `rejected`, `suspended`, or `inactive` (left or removed). Invited-but-not-yet-joined affiliates are not returned by this endpoint. — e.g. `active`
- `referral_code` *(string, required)* — The affiliate's unique referral code. — e.g. `a1b2c3d4`
- `referral_link` *(string, required)* — The affiliate's shareable referral link. Traffic arriving through it is attributed to this affiliate. — e.g. `https://creem.io/affiliate?code=a1b2c3d4`
- `clicks` *(number, required)* — Total number of clicks recorded on the affiliate’s links. — e.g. `128`
- `conversions` *(number, required)* — Total number of conversions attributed to the affiliate. — e.g. `12`
- `earnings` *(number, required)* — Lifetime commission earned by the affiliate, in cents (1000 = $10.00), reported in a single primary currency (see `currency`). Affiliates earning in multiple currencies show only their highest-earning currency here; use the affiliate's commissions endpoint for the full per-currency breakdown. — e.g. `4200`
- `currency` *(string, required)* — Three-letter ISO currency code, in uppercase, for the `earnings` amount. This is the affiliate's primary (highest-earning) currency; commissions in other currencies are listed individually on the commissions endpoint. — e.g. `USD`

---

### `GET /v1/affiliates/{id}/commissions` — List affiliate commissions

Retrieve a paginated list of an affiliate’s commissions. Filter by settlement status (pending, approved, paid).

Authentication: **`x-api-key` header** (required: yes). Operation ID: `listAffiliateCommissions`.


**Path parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | The unique identifier of the affiliate |
| `status` | CommissionStatus | no | The settlement status of the commission. `pending` while on hold, `approved` once cleared and available, `paid` once settled by a payout. |
| `page_number` | number | no (default: `1`) | The page number for pagination. |
| `page_size` | number | no (default: `10`) | The number of items per page. |


**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully retrieved affiliate commissions | CommissionListEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `CommissionListEntity`:**

- `items` *(array<CommissionEntity>, required)* — List of commission items
  *(fields of `CommissionEntity`)*
  - `id` *(string, required)* — Unique identifier for the object.
  - `mode` *(EnvironmentMode, required)*
  - `object` *(string, required)* — String representing the object's type. Objects of the same type share the same value. — e.g. `commission`
  - `affiliate` *(string, required)* — The ID of the affiliate this commission belongs to. — e.g. `aff_1234567890`
  - `amount` *(number, required)* — The commission amount in cents. 1000 = $10.00 — e.g. `600`
  - `currency` *(string, required)* — Three-letter ISO currency code, in uppercase, for the commission amount. — e.g. `USD`
  - `status` *(CommissionStatus, required)* — e.g. `pending`
  - `sale` *(string, optional)* — The ID of the sale transaction that generated this commission, if available. — e.g. `tran_1234567890`
  - `created_at` *(number, required)* — Creation date of the commission as a timestamp.
- `pagination` *(PaginationEntity, required)* — Pagination details for the list
  - `total_records` *(number, required)* — Total number of records in the list — e.g. `0`
  - `total_pages` *(number, required)* — Total number of pages available — e.g. `0`
  - `current_page` *(number, required)* — The current page number — e.g. `1`
  - `next_page` *(number, required)* — The next page number, or null if there is no next page — e.g. `2`
  - `prev_page` *(number, required)* — The previous page number, or null if there is no previous page

---

### Stats & Metrics

### `GET /v1/stats/summary` — Get store metrics summary

Retrieve aggregated store metrics including counts, revenue, and MRR. When startDate and endDate are provided, totals are filtered to that date range. When interval is also provided, the response includes a periods array with time-series data points grouped by that interval. The periods array starts from the store's first transaction or startDate, whichever is later, to avoid empty leading buckets. All monetary amounts are in cents (integer, no decimals).

Authentication: **`x-api-key` header** (required: yes). Operation ID: `getMetricsSummary`.


**Query parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `startDate` | number | no | Start of the date range as a Unix timestamp in milliseconds (e.g. 1740614400000). When provided with endDate, filters totals to this range. Required when interval is specified. |
| `endDate` | number | no | End of the date range as a Unix timestamp in milliseconds (e.g. 1772150400000). When provided with startDate, filters totals to this range. Required when interval is specified. |
| `interval` | enum: day\|week\|month | no | Groups time-series data into buckets of this size. Requires startDate and endDate. Returns a periods array with one entry per bucket containing grossRevenue and netRevenue. |
| `currency` | enum: EUR\|USD | yes |  |


**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Successfully retrieved store metrics summary | StatsSummaryEntity |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `StatsSummaryEntity`:**

- `totals` *(StatsMetricTotalsEntity, required)* — Aggregated totals for the queried date range
  - `totalProducts` *(number, required)* — Total number of products in the store — e.g. `12`
  - `totalSubscriptions` *(number, required)* — Total number of subscriptions within the queried date range — e.g. `48`
  - `totalCustomers` *(number, required)* — Total number of customers within the queried date range — e.g. `35`
  - `totalPayments` *(number, required)* — Total number of payments within the queried date range — e.g. `62`
  - `activeSubscriptions` *(number, required)* — Number of currently active subscriptions — e.g. `21`
  - `totalRevenue` *(number, required)* — Total gross revenue in cents within the queried date range — e.g. `553939`
  - `totalNetRevenue` *(number, required)* — Total net revenue in cents within the queried date range (after fees and taxes) — e.g. `478094`
  - `netMonthlyRecurringRevenue` *(number, required)* — Net monthly recurring revenue in cents (after estimated fees) — e.g. `89500`
  - `monthlyRecurringRevenue` *(number, required)* — Gross monthly recurring revenue in cents — e.g. `94200`
- `periods` *(array<StatsMetricPeriodEntity>, optional)* — Time-series data points grouped by the requested interval. Only present when interval, startDate, and endDate are provided. — e.g. `[{'timestamp': 1763337600000, 'grossRevenue': 2999, 'netRevenue': 2909}, {'timestamp': 1763942400000, 'grossRevenue': 32989, 'netRevenue': 31998}, {'timestamp': 1764547200000, 'grossRevenue': 47984, 'netRevenue': 46542}, {'timestamp': 1765152000000, 'grossRevenue': 125958, 'netRevenue': 122173}, {'timestamp': 1765756800000, 'grossRevenue': 343968, 'netRevenue': 278372}, {'timestamp': 1766361600000, 'grossRevenue': 0, 'netRevenue': 0}, {'timestamp': 1766966400000, 'grossRevenue': 0, 'netRevenue': 0}, {'timestamp': 1767571200000, 'grossRevenue': 225240, 'netRevenue': 192096}]`
  *(fields of `StatsMetricPeriodEntity`)*
  - `timestamp` *(number, required)* — Start of the period as a Unix timestamp in milliseconds (e.g. Monday of that week for weekly intervals) — e.g. `1765152000000`
  - `grossRevenue` *(number, required)* — Gross revenue in cents for this period — e.g. `125958`
  - `netRevenue` *(number, required)* — Net revenue in cents for this period (after fees and taxes) — e.g. `122173`

---

### Moderation

### `POST /v1/moderation/prompt` — Screen a prompt

Evaluate a text prompt against content policies before generation. This endpoint is experimental and may change.

Authentication: **`x-api-key` header** (required: yes). Operation ID: `screenPrompt`.


**Request body** (application/json, required):

Schema: `ScreenPromptRequest`

- `prompt` *(string, required)* — The text prompt to evaluate against content policies.
- `external_id` *(string, optional)* — An optional identifier to associate this request with.

**Responses:**

| Status | Description | Response schema |
|---|---|---|
| `200` | Prompt screening result | ScreenPromptResponse |
| `400` | Bad Request - Invalid input parameters | — |
| `401` | Unauthorized - Invalid or missing API key | — |
| `404` | Not Found - Resource does not exist | — |

**Response 200 body — `ScreenPromptResponse`:**

- `id` *(string, required)* — Unique identifier for the moderation result.
- `object` *(string, required)* — Object type. — e.g. `moderation_result`
- `prompt` *(string, required)* — The prompt that was screened.
- `external_id` *(string, optional)* — The external identifier provided in the request.
- `decision` *(enum: allow|deny|flag, required)* — The moderation decision.
- `usage` *(UsageEntity, required)* — Usage information for this call.
  - `units` *(number, required)* — Number of units consumed by this call.

---

## Webhooks

Creem pushes real-time event notifications to HTTPS endpoints you register in the dashboard (Developers > Webhook). Acknowledge delivery by responding with HTTP 200.

### Signature verification

Every webhook request carries a **`creem-signature`** header: the hex HMAC-SHA256 of the **raw request body**, keyed with your webhook secret (dashboard > Developers > Webhook). Verify it before processing:

```python
import hashlib, hmac

def verify_webhook_signature(raw_body: bytes, signature_header: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)
```

Use the raw body bytes as received — do not re-serialize parsed JSON. Creem does not provide static source IPs; do not rely on IP allowlists.

### Retry policy

If your endpoint does not return HTTP 200, Creem retries with progressive backoff: **30 seconds, 1 minute, 5 minutes, 1 hour**. Events can also be re-sent manually from the dashboard.

### Event types

| Event | Description |
|---|---|
| `checkout.completed` | A checkout session was completed (payment + order created) |
| `subscription.active` | New subscription created after a successful first payment |
| `subscription.paid` | A subscription payment was collected — use to grant access |
| `subscription.canceled` | Subscription canceled (by merchant or customer) |
| `subscription.scheduled_cancel` | Cancellation scheduled at period end; subscription still active until `current_period_end_date` |
| `subscription.past_due` | A payment attempt failed; Creem retries automatically |
| `subscription.unpaid` | Subscription moved to `unpaid` after failed collection |
| `subscription.expired` | Period ended without payment; status is terminal only when it becomes `canceled` |
| `subscription.trialing` | A subscription started a trial period |
| `subscription.paused` | A subscription was paused |
| `subscription.update` | A subscription object was updated |
| `refund.created` | A refund was issued by the merchant |
| `dispute.created` | A dispute was opened by a customer |

### Payload envelope

```json
{
  "id": "evt_5WHHcZPv7VS0YUsberIuOz",
  "eventType": "checkout.completed",
  "created_at": 1728734325927,
  "object": { }
}
```

The `object` field contains the affected resource(s) with the entity shapes documented in the [Schema Appendix](#schema-appendix). `checkout.completed` objects include the checkout plus nested `order`, `product`, `customer`, and `subscription`. `refund.created` objects include `refund`, `transaction`, `subscription`, `checkout`, `order`, and `customer`. Subscription events embed `product` (full object) and `customer`, and include `items` when the subscription has explicit items.

Best practice: grant access on `subscription.paid` / `checkout.completed`, revoke on `subscription.canceled` / `subscription.expired`, and map events to your internal users with `metadata.referenceId`.

---

## Test Mode

Toggle Test Mode in the dashboard (bottom of the left sidebar) to get test API keys. Test data is fully isolated and payments are simulated. Test API keys only work against `https://test-api.creem.io`.

### Test cards

| Card number | Behavior |
|---|---|
| `4111 1111 1111 1111` | Successful payment |
| `4507 9900 0000 0028` | Card declined |
| `4507 9900 0000 0010` | Insufficient funds |
| `4507 9900 0000 0044` | Incorrect CVC |

Any future expiration date, any CVV, and any billing info work with the cards above.

---

## Schema Appendix

All object schemas referenced by the endpoints, in alphabetical order.

### `AccountListResponseDto`

| Field | Type | Required | Description |
|---|---|---|---|
| `object` | string | yes | Object type (e.g. `list`) |
| `data` | array<AccountResponseDto> | yes | Array of accounts |
| `has_more` | boolean | yes | Whether more items exist beyond this page |

---

### `AccountResponseDto`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Account ID (e.g. `cca_abc123`) |
| `store_id` | string | yes | Store ID |
| `customer_id` | string | yes | Owner ID (e.g. `cust_abc123`) |
| `name` | string | yes | Account name (e.g. `default`) |
| `unit_label` | string | yes | Unit label (e.g. `credits`) |
| `status` | enum: active\|frozen\|closed | yes | Account status |
| `created_at` | string | yes | Creation timestamp |
| `updated_at` | string | yes | Last update timestamp |

---

### `ActivateLicenseRequestEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `key` | string | yes | The license key to activate. |
| `instance_name` | string | yes | A label for the new instance to identify it in Creem. |

---

### `AffiliateEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the object. |
| `mode` | EnvironmentMode | yes |  |
| `object` | string | yes | String representing the object's type. Objects of the same type share the same value. (e.g. `affiliate`) |
| `email` | string | yes | The email address the affiliate was invited with. (e.g. `partner@example.com`) |
| `name` | string | no | The display name of the affiliate, if set. (e.g. `Jane Partner`) |
| `status` | string | yes | The affiliate's status within your program, reflecting their membership standing: `active`, `pending` (awaiting approval), `rejected`, `suspended`, or `inactive` (left or removed). Invited-but-not-yet-joined affiliates are not returned by this endpoint. (e.g. `active`) |
| `referral_code` | string | yes | The affiliate's unique referral code. (e.g. `a1b2c3d4`) |
| `referral_link` | string | yes | The affiliate's shareable referral link. Traffic arriving through it is attributed to this affiliate. (e.g. `https://creem.io/affiliate?code=a1b2c3d4`) |
| `clicks` | number | yes | Total number of clicks recorded on the affiliate’s links. (e.g. `128`) |
| `conversions` | number | yes | Total number of conversions attributed to the affiliate. (e.g. `12`) |
| `earnings` | number | yes | Lifetime commission earned by the affiliate, in cents (1000 = $10.00), reported in a single primary currency (see `currency`). Affiliates earning in multiple currencies show only their highest-earning currency here; use the affiliate's commissions endpoint for the full per-currency breakdown. (e.g. `4200`) |
| `currency` | string | yes | Three-letter ISO currency code, in uppercase, for the `earnings` amount. This is the affiliate's primary (highest-earning) currency; commissions in other currencies are listed individually on the commissions endpoint. (e.g. `USD`) |

---

### `AffiliateListEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `items` | array<AffiliateEntity> | yes | List of affiliate items |
| `pagination` | PaginationEntity | yes | Pagination details for the list |

---

### `BalanceResponseDto`

| Field | Type | Required | Description |
|---|---|---|---|
| `balance` | string | yes | Current balance as string for bigint safety (e.g. `5000`) |
| `updated_at` | string | no | Last update timestamp (present for projected balance) |
| `as_of` | string | no | Point-in-time the balance was computed at (present for at-time queries) |

---

### `CancelSubscriptionRequestEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `mode` | enum: immediate\|scheduled | no | The mode of cancellation (immediate or scheduled), default can be configured in the store billing settings. (e.g. `immediate`) |
| `onExecute` | enum: cancel\|pause | no | The action to execute when canceling (cancel or pause) when mode is scheduled, ignored when mode is immediate or not provided (e.g. `cancel`) |

---

### `Checkbox`

| Field | Type | Required | Description |
|---|---|---|---|
| `label` | string | no | The markdown text to display for the checkbox. |
| `value` | boolean | no | The value of the checkbox (checked or not). |

---

### `CheckboxFieldConfig`

| Field | Type | Required | Description |
|---|---|---|---|
| `label` | string | no | The markdown text to display for the checkbox. (e.g. `I agree to the [terms and conditions](https://example.com/terms)`) |

---

### `CheckoutEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the object. |
| `mode` | EnvironmentMode | yes |  |
| `object` | string | yes | String representing the object's type. Objects of the same type share the same value. |
| `status` | enum: pending\|processing\|completed\|expired | yes | Status of the checkout. (e.g. `completed`) |
| `request_id` | string | no | Identify and track each checkout request. |
| `product` | string \| ProductEntity | yes | The product associated with the checkout session. |
| `units` | number | no | The number of units for the of the product. |
| `custom_price` | integer | no | The per-unit price override (in cents, product currency) this checkout was created with. Only present when the checkout was created with a custom_price. One-time payment products only. (e.g. `1500`) |
| `order` | OrderEntity | no | The order associated with the checkout session. |
| `subscription` | string \| SubscriptionEntity | no | The subscription associated with the checkout session. |
| `customer` | string \| CustomerEntity | no | The customer associated with the checkout session. |
| `custom_fields` | array<CustomField> | no | Additional information collected from your customer during the checkout process. |
| `checkout_url` | string | no | The URL to which the customer will be redirected to complete the payment. |
| `success_url` | string | no | The URL to which the user will be redirected after the checkout process is completed. (e.g. `https://example.com/return`) |
| `license_keys` | array<LicenseEntity> | no | License keys issued for the order. |
| `feature` | array<ProductFeatureEntity> | no | DEPRECATED: Use `license_keys` instead. Features issued for the order. |
| `metadata` | object | no | Metadata for the checkout in the form of key-value pairs (e.g. `{'userId': 'user_123', 'visitCount': 42, 'lastVisit': '2023-04-01'}`) |
| `discount` | object{id, discountCode, name, type, amount, duration, durationI...} | no | The discount applied to the checkout, if any. |

---

### `CommissionEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the object. |
| `mode` | EnvironmentMode | yes |  |
| `object` | string | yes | String representing the object's type. Objects of the same type share the same value. (e.g. `commission`) |
| `affiliate` | string | yes | The ID of the affiliate this commission belongs to. (e.g. `aff_1234567890`) |
| `amount` | number | yes | The commission amount in cents. 1000 = $10.00 (e.g. `600`) |
| `currency` | string | yes | Three-letter ISO currency code, in uppercase, for the commission amount. (e.g. `USD`) |
| `status` | CommissionStatus | yes |  (e.g. `pending`) |
| `sale` | string | no | The ID of the sale transaction that generated this commission, if available. (e.g. `tran_1234567890`) |
| `created_at` | number | yes | Creation date of the commission as a timestamp. |

---

### `CommissionListEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `items` | array<CommissionEntity> | yes | List of commission items |
| `pagination` | PaginationEntity | yes | Pagination details for the list |

---

### `CommissionStatus`

The settlement status of the commission. `pending` while on hold, `approved` once cleared and available, `paid` once settled by a payout.

Enum values: `pending`, `approved`, `paid`

---

### `CouponDurationType`

The duration type for the discount.

Enum values: `forever`, `once`, `repeating`

---

### `CreateAccountDto`

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | no | Human-readable name for the account (e.g. `default`) |
| `customer_id` | string | yes | The owner ID this account belongs to (e.g. customer ID) (e.g. `cust_abc123`) |
| `unit_label` | string | no | Label for the unit of currency/credits (e.g. `credits`) |
| `initial_balance` | string | no | Seed the account with this many credits on creation (e.g. `300`) |

---

### `CreateCheckoutRequest`

| Field | Type | Required | Description |
|---|---|---|---|
| `request_id` | string | no | Identify and track each checkout request. |
| `product_id` | string | yes | The ID of the product associated with the checkout session. (e.g. `prod_1234567890`) |
| `units` | number | no | The number of units for the order. (e.g. `1`) |
| `custom_price` | integer | no | Override the unit price of the product for this checkout session, in cents (e.g. 1500 = $15.00). The product currency is used, and the amount is per unit: with `units: 3` and `custom_price: 1500` the customer pays 4500. Must be between 100 (one whole unit of the currency) and 99999999. Only supported for one-time payment products. Use this for dynamic pricing models such as pay-what-you-want, donations, or amounts calculated by your application. (e.g. `1500`) |
| `discount_code` | string | no | Prefill the checkout session with a discount code. (e.g. `SUMMER2024`) |
| `customer` | CustomerRequestEntity | no | Customer data for checkout session. This will prefill the customer info on the checkout page. |
| `custom_fields` | array<CustomFieldRequestEntity> | no | Collect additional information from your customer using custom fields. Up to 3 fields are supported. |
| `custom_field` | array<CustomFieldRequestEntity> | no | DEPRECATED: Use `custom_fields` instead. Collect additional information from your customer using custom fields. Up to 3 fields are supported. |
| `success_url` | string | no | The URL to which the user will be redirected after the checkout process is completed. |
| `metadata` | object | no | Metadata for the checkout in the form of key-value pairs (e.g. `{'userId': 'user_123', 'visitCount': 42, 'lastVisit': '2023-04-01'}`) |

---

### `CreateCustomerPortalLinkRequestEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `customer_id` | string | yes | Unique identifier of the customer. |

---

### `CreateCustomerRequestEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `email` | string | yes | The email address of the customer. (e.g. `john@example.com`) |
| `name` | string | yes | The full name of the customer. (e.g. `John Doe`) |
| `metadata` | object | no | Additional metadata for the customer. (e.g. `{'key': 'value'}`) |

---

### `CreateDiscountRequestEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | The name of the discount. (e.g. `Holiday Sale`) |
| `code` | string | no | Optional discount code. If left empty, a code will be generated. (e.g. `HOLIDAY2024`) |
| `type` | DiscountType | yes |  |
| `amount` | number | no | The fixed value for the discount. Only applicable if the type is "fixed". (e.g. `20`) |
| `currency` | string | no | The currency of the discount. Only required if type is "fixed". (e.g. `USD`) |
| `percentage` | number | no | The percentage value for the discount. Only applicable if the type is "percentage". (e.g. `15`) |
| `expiry_date` | string | no | The expiry date of the discount. (e.g. `2024-12-31T23:59:59Z`) |
| `max_redemptions` | number | no | The maximum number of redemptions for the discount. (e.g. `100`) |
| `duration` | CouponDurationType | yes |  (e.g. `repeating`) |
| `duration_in_months` | number | no | The number of months the discount is valid for. Only applicable if the duration is "repeating" and the product is a subscription. (e.g. `6`) |
| `applies_to_products` | array<string> | yes | The list of product IDs to which this discount applies. (e.g. `['prod_123', 'prod_456']`) |

---

### `CreateProductRequestEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Name of the product |
| `description` | string | yes | Description of the product |
| `image_url` | string | no | URL of the product image (e.g. `https://picsum.photos/200/300`) |
| `image_urls` | array<string> | no | Ordered list of product image URLs (max 8). The first entry is the cover image; when provided it takes precedence over image_url. (e.g. `['https://picsum.photos/200/300', 'https://picsum.photos/200/301']`) |
| `price` | integer | yes | The price of the product in cents. Must be 0 (free product) or at least 100 (one whole unit of the currency). (e.g. `400`) |
| `currency` | ProductCurrency | yes |  (e.g. `USD`) |
| `billing_type` | ProductRequestBillingType | yes |  (e.g. `recurring`) |
| `billing_period` | ProductRequestBillingPeriod | no |  (e.g. `every-month`) |
| `tax_mode` | TaxMode | no |  (e.g. `inclusive`) |
| `tax_category` | TaxCategory | no |  (e.g. `saas`) |
| `pay_what_you_want` | boolean | no | Enable pay-what-you-want pricing: the customer chooses the amount at checkout. The `price` field acts as the minimum the customer must pay. Only supported for one-time payment products. (e.g. `False`) |
| `suggested_price` | integer | no | Suggested amount in cents, pre-filled at checkout when pay_what_you_want is enabled. Must be greater than or equal to `price` (the minimum). Ignored when pay_what_you_want is disabled. (e.g. `1500`) |
| `default_success_url` | string | no | The URL to which the user will be redirected after successfull payment. (e.g. `https://example.com/?status=successful`) |
| `custom_fields` | array<CustomFieldRequestEntity> | no | Collect additional information from your customer using custom fields during checkout. Up to 3 fields are supported. |
| `custom_field` | array<CustomFieldRequestEntity> | no | DEPRECATED: Use `custom_fields` instead. Collect additional information from your customer using custom fields during checkout. Up to 3 fields are supported. |
| `abandoned_cart_recovery_enabled` | boolean | no | Enable abandoned cart recovery for this product |

---

### `CreateRefundRequestEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `transaction_id` | string | yes | The unique identifier of the transaction to refund in full. (e.g. `tran_1234567890`) |

---

### `CreditDebitRequestDto`

| Field | Type | Required | Description |
|---|---|---|---|
| `amount` | string | yes | Amount to credit or debit (string to support large numbers) (e.g. `1000`) |
| `reference` | string | yes | Your reference ID to link this transaction to an event in your system (e.g. order ID, campaign ID) (e.g. `signup_bonus`) |
| `idempotency_key` | string | yes | Idempotency key to prevent duplicate transactions (e.g. `idem_abc123`) |

---

### `CustomField`

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | CustomFieldType | yes |  |
| `key` | string | yes | Unique key for custom field. Must be unique to this field, alphanumeric, and up to 200 characters. |
| `label` | string | yes | The label for the field, displayed to the customer, up to 50 characters |
| `optional` | boolean | no | Whether the customer is required to complete the field. Defaults to `false`. |
| `text` | Text | no | Configuration for text field type. |
| `checkbox` | Checkbox | no | Configuration for checkbox field type. |

---

### `CustomFieldRequestEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | CustomFieldRequestType | yes |  (e.g. `text`) |
| `key` | string | yes | Unique key for custom field. Must be unique to this field, alphanumeric, and up to 200 characters. (e.g. `companyName`) |
| `label` | string | yes | The label for the field, displayed to the customer, up to 50 characters. (e.g. `Company Name`) |
| `optional` | boolean | no | Whether the customer is required to complete the field. Defaults to `false` |
| `text` | TextFieldConfig | no | Configuration for text field type. |
| `checkbox` | CheckboxFieldConfig | no | Configuration for checkbox field type. |

---

### `CustomFieldRequestType`

The type of the field.

Enum values: `text`, `checkbox`

---

### `CustomFieldType`

The type of the field.

Enum values: `text`, `checkbox`

---

### `CustomerCreditsErrorDetailDto`

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | enum: invalid_request_error\|api_error\|authentication_error\|rate_limit_error | yes | Error category (e.g. `invalid_request_error`) |
| `code` | string | yes | Machine-readable error code (e.g. `unbalanced_transaction`) |
| `message` | string | yes | Human-readable error message (e.g. `Total debits must equal total credits`) |
| `param` | string | no | The parameter related to the error, if applicable (e.g. `entries`) |
| `request_id` | string | yes | Unique request identifier for support (e.g. `req_abc123def456`) |

---

### `CustomerCreditsErrorResponseDto`

| Field | Type | Required | Description |
|---|---|---|---|
| `error` | CustomerCreditsErrorDetailDto | yes | Error details |

---

### `CustomerCreditsFeatureEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `amount` | string | yes | The number of credits to grant. String to preserve BigInt precision. (e.g. `100`) |
| `unit_label` | string | no | Optional label for the credit unit (e.g. "tokens", "credits"). (e.g. `tokens`) |

---

### `CustomerEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the object. |
| `mode` | EnvironmentMode | yes |  |
| `object` | string | yes | String representing the object’s type. Objects of the same type share the same value. |
| `email` | string | yes | Customer email address. (e.g. `user@example.com`) |
| `name` | string | no | Customer name. (e.g. `John Doe`) |
| `metadata` | object | no | Additional metadata associated with the customer. (e.g. `{'key': 'value'}`) |
| `country` | string | yes | The ISO 3166-1 alpha-2 country code for the customer. (e.g. `US`) |
| `created_at` | string | yes | Creation date of the customer (e.g. `2023-01-01T00:00:00Z`) |
| `updated_at` | string | yes | Last updated date of the customer (e.g. `2023-01-01T00:00:00Z`) |

---

### `CustomerLinksEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `customer_portal_link` | string | yes | Customer portal link. |

---

### `CustomerListEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `items` | array<CustomerEntity> | yes | List of customer items |
| `pagination` | PaginationEntity | yes | Pagination details for the list |

---

### `CustomerRequestEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | no | Unique identifier of the customer. You may specify only one of these parameters: id or email. (e.g. `cust_1234567890`) |
| `email` | string | no | Customer email address. You may only specify one of these parameters: id, email. (e.g. `user@example.com`) |

---

### `DeactivateLicenseRequestEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `key` | string | yes | The license key to deactivate. |
| `instance_id` | string | yes | Id of the instance to deactivate. |

---

### `DiscountEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the object. |
| `mode` | EnvironmentMode | yes |  |
| `object` | string | yes | A string representing the object’s type. Objects of the same type share the same value. (e.g. `discount`) |
| `status` | enum: deleted\|active\|draft\|expired\|scheduled | yes | The status of the discount (e.g., active, inactive). (e.g. `active`) |
| `name` | string | yes | The name of the discount. (e.g. `Holiday Sale`) |
| `code` | string | yes | The discount code. A unique identifier for the discount. (e.g. `HOLIDAY2024`) |
| `type` | enum: percentage\|fixed | yes | The type of the discount, either "percentage" or "fixed". (e.g. `percentage`) |
| `amount` | number | no | The amount of the discount. Can be a percentage or a fixed amount. (e.g. `20`) |
| `currency` | string | no | The currency of the discount. Only required if type is "fixed". (e.g. `USD`) |
| `percentage` | number | no | The percentage of the discount. Only applicable if type is "percentage". (e.g. `15`) |
| `expiry_date` | string | no | The expiry date of the discount. (e.g. `2024-12-31T23:59:59Z`) |
| `max_redemptions` | number | no | The maximum number of redemptions allowed for the discount. (e.g. `100`) |
| `duration` | enum: forever\|once\|repeating | no | The duration type for the discount. (e.g. `repeating`) |
| `duration_in_months` | number | no | The number of months the discount is valid for. Only applicable if the duration is "repeating" and the product is a subscription. (e.g. `6`) |
| `applies_to_products` | array<string> | no | The list of product IDs to which this discount applies. (e.g. `['prod_123', 'prod_456']`) |
| `redeem_count` | number | no | The number of times this discount has been redeemed. (e.g. `15`) |

---

### `DiscountListEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `items` | array<DiscountEntity> | yes | List of discount items |
| `pagination` | PaginationEntity | yes | Pagination details for the list |

---

### `DiscountType`

The type of the discount, either "percentage" or "fixed".

Enum values: `percentage`, `fixed`

---

### `DisputeEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the object. |
| `mode` | EnvironmentMode | yes |  |
| `object` | string | yes | String representing the object's type. Objects of the same type share the same value. |
| `amount` | number | yes | The disputed amount in cents. 1000 = $10.00 (e.g. `1000`) |
| `currency` | string | yes | Three-letter ISO currency code, in uppercase. Must be a supported currency. (e.g. `USD`) |
| `transaction` | TransactionEntity | yes | The transaction associated with the dispute. |
| `checkout` | string \| CheckoutEntity | no | The checkout associated with the dispute. |
| `order` | string \| OrderEntity | no | The order associated with the dispute. |
| `subscription` | string \| SubscriptionEntity | no | The subscription associated with the dispute. |
| `customer` | string \| CustomerEntity | no | The customer associated with the dispute. |
| `created_at` | number | yes | Creation date of the dispute as timestamp |

---

### `EntryListResponseDto`

| Field | Type | Required | Description |
|---|---|---|---|
| `object` | string | yes | Object type (e.g. `list`) |
| `data` | array<EntryResponseDto> | yes | Array of entries |
| `has_more` | boolean | yes | Whether more items exist beyond this page |

---

### `EntryResponseDto`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Entry ID (e.g. `cce_abc123`) |
| `transaction_id` | string | yes | Transaction ID (e.g. `cct_abc123`) |
| `account_id` | string | yes | Account ID (e.g. `cca_abc123`) |
| `side` | enum: debit\|credit | yes | Debit or credit side |
| `amount` | string | yes | Amount as string for bigint safety (e.g. `1000`) |
| `created_at` | string | yes | Creation timestamp |

---

### `EnvironmentMode`

String representing the environment.

Enum values: `test`, `prod`, `sandbox`

---

### `FeatureEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the feature. (e.g. `feat_abc123`) |
| `type` | ProductFeatureType | yes |  (e.g. `licenseKey`) |
| `description` | string | yes | A brief description of the feature. (e.g. `Access to premium course materials.`) |

---

### `FeatureFileEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the file. (e.g. `file_abc123`) |
| `file_name` | string | yes | The name of the file. (e.g. `ebook.pdf`) |
| `url` | string | yes | The URL to download the file. (e.g. `https://storage.creem.io/files/ebook.pdf`) |
| `type` | string | yes | The MIME type of the file. (e.g. `application/pdf`) |
| `size` | number | yes | The size of the file in bytes. (e.g. `1024000`) |

---

### `FileFeatureEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `files` | array<FeatureFileEntity> | yes | List of downloadable files. |

---

### `LicenseEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the object. |
| `mode` | EnvironmentMode | yes |  |
| `object` | string | yes | A string representing the object's type. Objects of the same type share the same value. |
| `product_id` | string | yes | The ID of the product this license belongs to. (e.g. `prod_abc123`) |
| `status` | LicenseStatus | yes |  (e.g. `active`) |
| `key` | string | yes | The license key. (e.g. `ABC123-XYZ456-XYZ456-XYZ456`) |
| `activation` | number | yes | The number of instances that this license key was activated. (e.g. `5`) |
| `activation_limit` | number | no | The activation limit. Null if activations are unlimited. (e.g. `1`) |
| `expires_at` | string | no | The date the license key expires. Null if it does not have an expiration date. (e.g. `2023-09-13T00:00:00Z`) |
| `created_at` | string | yes | The creation date of the license key. (e.g. `2023-09-13T00:00:00Z`) |
| `instance` | LicenseInstanceEntity | no | Associated license instances. |

---

### `LicenseInstanceEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the object. |
| `mode` | EnvironmentMode | yes |  |
| `object` | string | yes | A string representing the object’s type. Objects of the same type share the same value. (e.g. `license-instance`) |
| `name` | string | yes | The name of the license instance. (e.g. `My Customer License Instance`) |
| `status` | enum: active\|deactivated | yes | The status of the license instance. (e.g. `active`) |
| `created_at` | string | yes | The creation date of the license instance. (e.g. `2023-09-13T00:00:00Z`) |

---

### `LicenseInstanceListEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `items` | array<LicenseInstanceEntity> | yes | List of license instance items |
| `pagination` | PaginationEntity | yes | Pagination details for the list |

---

### `LicenseListEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `items` | array<LicenseEntity> | yes | List of license items |
| `pagination` | PaginationEntity | yes | Pagination details for the list |

---

### `LicenseStatus`

The current status of the license key.

Enum values: `inactive`, `active`, `expired`, `disabled`

---

### `OrderEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the object. |
| `mode` | EnvironmentMode | yes |  |
| `object` | string | yes | String representing the object's type. Objects of the same type share the same value. |
| `customer` | string | no | The customer who placed the order. |
| `product` | string | yes | The product associated with the order. |
| `transaction` | string | no | The transaction ID of the order (e.g. `tx_1234567890`) |
| `discount` | string | no | The discount ID of the order (e.g. `dis_1234567890`) |
| `amount` | number | yes | The total amount of the order in cents. 1000 = $10.00 (e.g. `2000`) |
| `sub_total` | number | no | The subtotal of the order in cents. 1000 = $10.00 (e.g. `1800`) |
| `tax_amount` | number | no | The tax amount of the order in cents. 1000 = $10.00 (e.g. `200`) |
| `discount_amount` | number | no | The discount amount of the order in cents. 1000 = $10.00 (e.g. `100`) |
| `amount_due` | number | no | The amount due for the order in cents. 1000 = $10.00 (e.g. `1900`) |
| `amount_paid` | number | no | The amount paid for the order in cents. 1000 = $10.00 (e.g. `1900`) |
| `currency` | string | yes | Three-letter ISO currency code, in uppercase. Must be a supported currency. (e.g. `USD`) |
| `fx_amount` | number | no | The amount in the foreign currency, if applicable. (e.g. `15`) |
| `fx_currency` | string | no | Three-letter ISO code of the foreign currency, if applicable. (e.g. `EUR`) |
| `fx_rate` | number | no | The exchange rate used for converting between currencies, if applicable. (e.g. `1.2`) |
| `status` | OrderStatus | yes |  (e.g. `pending`) |
| `type` | OrderType | yes |  (e.g. `recurring`) |
| `affiliate` | string | no | The affiliate associated with the order, if applicable. |
| `created_at` | string | yes | Creation date of the order (e.g. `2023-09-13T00:00:00Z`) |
| `updated_at` | string | yes | Last updated date of the order (e.g. `2023-09-13T00:00:00Z`) |

---

### `OrderListEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `items` | array<OrderEntity> | yes | List of order items |
| `pagination` | PaginationEntity | yes | Pagination details for the list |

---

### `OrderStatus`

Current status of the order.

Enum values: `pending`, `paid`

---

### `OrderType`

The type of order. This can specify whether it's a regular purchase, subscription, etc.

Enum values: `recurring`, `onetime`

---

### `PaginationEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `total_records` | number | yes | Total number of records in the list (e.g. `0`) |
| `total_pages` | number | yes | Total number of pages available (e.g. `0`) |
| `current_page` | number | yes | The current page number (e.g. `1`) |
| `next_page` | number | yes | The next page number, or null if there is no next page (e.g. `2`) |
| `prev_page` | number | yes | The previous page number, or null if there is no previous page |

---

### `ProductBillingPeriod`

Billing period

Enum values: `every-month`, `every-three-months`, `every-six-months`, `every-year`, `every-day`, `once`

---

### `ProductBillingType`

Indicates the billing method for the customer. It can either be a `recurring` billing cycle or a `onetime` payment.

Enum values: `recurring`, `onetime`

---

### `ProductCurrency`

Three-letter uppercase ISO 4217 currency code. Must be one of Creem's supported currencies.

Enum values: `EUR`, `USD`

---

### `ProductEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the object. |
| `mode` | EnvironmentMode | yes |  |
| `object` | string | yes | String representing the object's type. Objects of the same type share the same value. |
| `name` | string | yes | The name of the product |
| `description` | string | yes | A brief description of the product (e.g. `This is a sample product description.`) |
| `image_url` | string | no | URL of the product image. Only png as jpg are supported (e.g. `https://example.com/image.jpg`) |
| `image_urls` | array<string> | no | Ordered list of product image URLs. The first entry is the cover image (mirrored in image_url). (e.g. `['https://example.com/image.jpg']`) |
| `features` | array<FeatureEntity> | no | Features of the product. |
| `price` | number | yes | The price of the product in cents. 1000 = $10.00 (e.g. `400`) |
| `currency` | string | yes | Three-letter ISO currency code, in uppercase. Must be a supported currency. (e.g. `USD`) |
| `billing_type` | ProductBillingType | yes |  (e.g. `recurring`) |
| `billing_period` | ProductBillingPeriod | yes |  (e.g. `every-month`) |
| `status` | ProductStatus | yes |  (e.g. `active`) |
| `tax_mode` | TaxMode | yes |  (e.g. `inclusive`) |
| `tax_category` | TaxCategory | yes |  (e.g. `saas`) |
| `product_url` | string | no | The product page you can redirect your customers to for express checkout. (e.g. `https://creem.io/product/prod_123123123123`) |
| `default_success_url` | string | no | The URL to which the user will be redirected after successfull payment. (e.g. `https://example.com/?status=successful`) |
| `custom_fields` | array<CustomField> | no | Custom fields configured for the product. Collect additional information from your customer during checkout. |
| `created_at` | string | yes | Creation date of the product (e.g. `2023-01-01T00:00:00Z`) |
| `updated_at` | string | yes | Last updated date of the product (e.g. `2023-01-01T00:00:00Z`) |

---

### `ProductFeatureEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | no | Unique identifier for the feature. (e.g. `feat_abc123`) |
| `description` | string | no | A brief description of the feature. (e.g. `Get access to the full course materials.`) |
| `type` | ProductFeatureType | no |  (e.g. `licenseKey`) |
| `private_note` | string | no | Private note from the seller. This is only visible to the customer after purchase. (e.g. `Thank you for your purchase! Here is your access code: XYZ123`) |
| `file` | FileFeatureEntity | no | File feature data containing downloadable files. |
| `license_key` | LicenseEntity | no | License key issued for the order. |
| `customer_credits` | CustomerCreditsFeatureEntity | no | Customer credits feature data. |
| `license` | LicenseEntity | no | DEPRECATED: Use `license_key` instead. License key issued for the order. |

---

### `ProductFeatureType`

The type of the feature: `custom` (private note), `file` (downloadable files), `licenseKey` (license key), or `customerCredits` (customer credit grant).

Enum values: `custom`, `file`, `licenseKey`, `customerCredits`

---

### `ProductListEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `items` | array<ProductEntity> | yes | List of product items |
| `pagination` | PaginationEntity | yes | Pagination details for the list |

---

### `ProductRequestBillingPeriod`

Billing interval. Required when `billing_type` is `recurring`.

Enum values: `once`, `every-day`, `every-month`, `every-three-months`, `every-six-months`, `every-year`

---

### `ProductRequestBillingType`

Billing method for the product: `recurring` subscription or `onetime` payment.

Enum values: `recurring`, `onetime`

---

### `ProductStatus`

Lifecycle status of the product: `active` or `archived`.

Enum values: `active`, `archived`

---

### `RefundEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the object. |
| `mode` | EnvironmentMode | yes |  |
| `object` | string | yes | String representing the object’s type. Objects of the same type share the same value. |
| `status` | RefundStatus | yes |  (e.g. `succeeded`) |
| `refund_amount` | number | yes | The refunded amount in cents. 1000 = $10.00 (e.g. `1000`) |
| `refund_currency` | string | yes | Three-letter ISO currency code, in uppercase. Must be a supported currency. (e.g. `USD`) |
| `reason` | RefundReason | yes |  |
| `transaction` | TransactionEntity | yes | The transaction associated with the refund. |
| `checkout` | string \| CheckoutEntity | no | The checkout associated with the refund. |
| `order` | string \| OrderEntity | no | The order associated with the refund. |
| `subscription` | string \| SubscriptionEntity | no | The subscription associated with the refund. |
| `customer` | string \| CustomerEntity | no | The customer associated with the refund. |
| `created_at` | number | yes | Creation date of the order as timestamp |

---

### `RefundReason`

Reason for the refund.

Enum values: `duplicate`, `fraudulent`, `requested_by_customer`, `other`

---

### `RefundResponseEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `status` | RefundStatus | yes |  (e.g. `succeeded`) |

---

### `RefundStatus`

Status of the refund. `pending` and `requiresAction` represent non-terminal provider processing states.

Enum values: `pending`, `requiresAction`, `succeeded`, `failed`, `canceled`

---

### `ReverseTransactionRequestDto`

| Field | Type | Required | Description |
|---|---|---|---|
| `transaction_id` | string | yes | ID of the transaction to reverse (e.g. `cct_abc123`) |

---

### `ScreenPromptRequest`

| Field | Type | Required | Description |
|---|---|---|---|
| `prompt` | string | yes | The text prompt to evaluate against content policies. |
| `external_id` | string | no | An optional identifier to associate this request with. |

---

### `ScreenPromptResponse`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the moderation result. |
| `object` | string | yes | Object type. (e.g. `moderation_result`) |
| `prompt` | string | yes | The prompt that was screened. |
| `external_id` | string | no | The external identifier provided in the request. |
| `decision` | enum: allow\|deny\|flag | yes | The moderation decision. |
| `usage` | UsageEntity | yes | Usage information for this call. |

---

### `StatsMetricPeriodEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `timestamp` | number | yes | Start of the period as a Unix timestamp in milliseconds (e.g. Monday of that week for weekly intervals) (e.g. `1765152000000`) |
| `grossRevenue` | number | yes | Gross revenue in cents for this period (e.g. `125958`) |
| `netRevenue` | number | yes | Net revenue in cents for this period (after fees and taxes) (e.g. `122173`) |

---

### `StatsMetricTotalsEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `totalProducts` | number | yes | Total number of products in the store (e.g. `12`) |
| `totalSubscriptions` | number | yes | Total number of subscriptions within the queried date range (e.g. `48`) |
| `totalCustomers` | number | yes | Total number of customers within the queried date range (e.g. `35`) |
| `totalPayments` | number | yes | Total number of payments within the queried date range (e.g. `62`) |
| `activeSubscriptions` | number | yes | Number of currently active subscriptions (e.g. `21`) |
| `totalRevenue` | number | yes | Total gross revenue in cents within the queried date range (e.g. `553939`) |
| `totalNetRevenue` | number | yes | Total net revenue in cents within the queried date range (after fees and taxes) (e.g. `478094`) |
| `netMonthlyRecurringRevenue` | number | yes | Net monthly recurring revenue in cents (after estimated fees) (e.g. `89500`) |
| `monthlyRecurringRevenue` | number | yes | Gross monthly recurring revenue in cents (e.g. `94200`) |

---

### `StatsSummaryEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `totals` | StatsMetricTotalsEntity | yes | Aggregated totals for the queried date range |
| `periods` | array<StatsMetricPeriodEntity> | no | Time-series data points grouped by the requested interval. Only present when interval, startDate, and endDate are provided. (e.g. `[{'timestamp': 1763337600000, 'grossRevenue': 2999, 'netRevenue': 2909}, {'timestamp': 1763942400000, 'grossRevenue': 32989, 'netRevenue': 31998}, {'timestamp': 1764547200000, 'grossRevenue': 47984, 'netRevenue': 46542}, {'timestamp': 1765152000000, 'grossRevenue': 125958, 'netRevenue': 122173}, {'timestamp': 1765756800000, 'grossRevenue': 343968, 'netRevenue': 278372}, {'timestamp': 1766361600000, 'grossRevenue': 0, 'netRevenue': 0}, {'timestamp': 1766966400000, 'grossRevenue': 0, 'netRevenue': 0}, {'timestamp': 1767571200000, 'grossRevenue': 225240, 'netRevenue': 192096}]`) |

---

### `SubscriptionCollectionMethod`

The method used for collecting payments for the subscription.

Enum values: `charge_automatically`

---

### `SubscriptionEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the object. |
| `mode` | EnvironmentMode | yes |  |
| `object` | string | yes | String representing the object's type. Objects of the same type share the same value. (e.g. `subscription`) |
| `product` | ProductEntity \| string | yes | The product associated with the subscription. |
| `customer` | CustomerEntity \| string | yes | The customer who owns the subscription. |
| `items` | array<SubscriptionItemEntity> | no | Subscription items. |
| `collection_method` | SubscriptionCollectionMethod | yes |  (e.g. `charge_automatically`) |
| `status` | SubscriptionStatus | yes |  (e.g. `active`) |
| `last_transaction_id` | string | no | The ID of the last paid transaction. (e.g. `tran_3e6Z6TzvHKdsjEgXnGDEp0`) |
| `last_transaction` | TransactionEntity | no | The last paid transaction. |
| `last_transaction_date` | string | no | The date of the last paid transaction. (e.g. `2024-09-12T12:34:56Z`) |
| `next_transaction_date` | string | no | The date when the next subscription transaction will be charged. (e.g. `2024-09-12T12:34:56Z`) |
| `current_period_start_date` | string | no | The start date of the current subscription period. (e.g. `2024-09-12T12:34:56Z`) |
| `current_period_end_date` | string | no | The end date of the current subscription period. (e.g. `2024-09-12T12:34:56Z`) |
| `canceled_at` | string | no | The date and time when the subscription was canceled, if applicable. (e.g. `2024-09-12T12:34:56Z`) |
| `created_at` | string | yes | The date and time when the subscription was created. (e.g. `2024-01-01T00:00:00Z`) |
| `updated_at` | string | yes | The date and time when the subscription was last updated. (e.g. `2024-09-12T12:34:56Z`) |
| `discount` | object{id, discountCode, name, type, amount, duration, durationI...} | no | The discount applied to the subscription, if any. |
| `metadata` | object | no | Metadata for the subscription in the form of key-value pairs. (e.g. `{'userId': 'user_123', 'plan': 'pro'}`) |

---

### `SubscriptionItemEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the object. |
| `mode` | EnvironmentMode | yes |  |
| `object` | string | yes | String representing the object’s type. Objects of the same type share the same value. |
| `product_id` | string | no | The ID of the product associated with the subscription item. |
| `price_id` | string | no | The ID of the price associated with the subscription item. |
| `units` | number | no | The number of units for the subscription item. |

---

### `SubscriptionListEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `items` | array<SubscriptionEntity> | yes | List of subscription items |
| `pagination` | PaginationEntity | yes | Pagination details for the list |

---

### `SubscriptionStatus`

The current status of the subscription.

Enum values: `active`, `canceled`, `unpaid`, `paused`, `trialing`, `scheduled_cancel`, `past_due`

---

### `TaxCategory`

Categorizes the type of product or service for tax purposes. This helps determine the applicable tax rules based on the nature of the item or service.

Enum values: `saas`, `digital-goods-service`, `ebooks`

---

### `TaxMode`

Specifies the tax calculation mode for the transaction. If set to "inclusive," the tax is included in the price. If set to "exclusive," the tax is added on top of the price.

Enum values: `inclusive`, `exclusive`

---

### `Text`

| Field | Type | Required | Description |
|---|---|---|---|
| `max_length` | number | no | Maximum character length constraint for the input. |
| `minimum_length` | number | no | Minimum character length requirement for the input. |
| `value` | string | no | The value of the input. |

---

### `TextFieldConfig`

| Field | Type | Required | Description |
|---|---|---|---|
| `max_length` | number | no | Maximum character length constraint for the input. (e.g. `200`) |
| `min_length` | number | no | Minimum character length requirement for the input. (e.g. `1`) |

---

### `TransactionEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the object. |
| `mode` | EnvironmentMode | yes |  |
| `object` | string | yes | String representing the object's type. Objects of the same type share the same value. (e.g. `transaction`) |
| `amount` | number | yes | The transaction amount in cents. 1000 = $10.00 (e.g. `2000`) |
| `amount_paid` | number | no | The amount the customer paid in cents. 1000 = $10.00 (e.g. `2000`) |
| `discount_amount` | number | no | The discount amount in cents. 1000 = $10.00 (e.g. `2000`) |
| `currency` | string | yes | Three-letter ISO currency code, in uppercase. Must be a supported currency. (e.g. `USD`) |
| `type` | TransactionType | yes |  |
| `tax_country` | string | no | The ISO alpha-2 country code where tax is collected. (e.g. `US`) |
| `tax_amount` | number | no | The sale tax amount in cents. 1000 = $10.00 (e.g. `2000`) |
| `status` | TransactionStatus | yes |  |
| `refunded_amount` | number | no | The amount that has been refunded in cents. 1000 = $10.00 (e.g. `2000`) |
| `order` | string | no | The order associated with the transaction. |
| `subscription` | string | no | The subscription associated with the transaction. |
| `customer` | string | no | The customer associated with the transaction. |
| `description` | string | no | The description of the transaction. |
| `period_start` | number | no | Start period for the invoice as timestamp |
| `period_end` | number | no | End period for the invoice as timestamp |
| `created_at` | number | yes | Creation date of the order as timestamp |

---

### `TransactionListEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `items` | array<TransactionEntity> | yes | List of transactions items |
| `pagination` | PaginationEntity | yes | Pagination details for the list |

---

### `TransactionResponseDto`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Transaction ID (e.g. `cct_abc123`) |
| `store_id` | string | yes | Store ID |
| `reference` | string | yes | Reference string (e.g. `order_xyz`) |
| `idempotency_key` | string | yes | Idempotency key |
| `reversal_of` | string | no | ID of the transaction this reverses, if applicable (e.g. `cct_abc123`) |
| `entries` | array<EntryResponseDto> | yes | Transaction entries |
| `created_at` | string | yes | Creation timestamp |

---

### `TransactionStatus`

Status of the transaction.

Enum values: `pending`, `paid`, `refunded`, `partialRefund`, `chargedBack`, `uncollectible`, `declined`, `canceled`, `void`

---

### `TransactionType`

The type of transaction. payment(one time payments) and invoice(subscription)

Enum values: `payment`, `invoice`

---

### `UpdateCustomerRequestEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `customer_id` | string | yes | The ID of the customer to update. (e.g. `cust_abc123`) |
| `name` | string | no | The full name of the customer. (e.g. `John Doe`) |
| `metadata` | object | no | Additional metadata for the customer. (e.g. `{'key': 'value'}`) |

---

### `UpdateProductRequestEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | no | Name of the product |
| `description` | string | no | Description of the product |
| `image_url` | string | no | URL of the product image |
| `image_urls` | array<string> | no | Ordered list of product image URLs (max 8). The first entry is the cover image; when provided it takes precedence over image_url. An empty list removes all images. |
| `default_success_url` | string | no | Redirect URL after successful payment. |
| `price` | integer | no | The price of the product in cents. Must be 0 (free product) or at least 100 (one whole unit of the currency). |
| `currency` | ProductCurrency | no |  (e.g. `USD`) |
| `billing_type` | ProductRequestBillingType | no |  (e.g. `recurring`) |
| `billing_period` | ProductRequestBillingPeriod | no |  (e.g. `every-month`) |
| `tax_mode` | TaxMode | no |  (e.g. `inclusive`) |
| `pay_what_you_want` | boolean | no | Enable pay-what-you-want pricing (one-time only). |
| `suggested_price` | integer | no | Suggested amount in cents when pay_what_you_want is enabled. |

---

### `UpdateSubscriptionRequestEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `items` | array<UpsertSubscriptionItemEntity> | no | List of subscription items to update/create. If no item ID is provided, the item will be created. |
| `update_behavior` | enum: proration-charge-immediately\|proration-charge\|proration-none | no | The update behavior for the subscription (defaults to proration) |

---

### `UpgradeSubscriptionRequestEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `product_id` | string | yes | The ID of the product to upgrade to (e.g. `prod_123`) |
| `update_behavior` | enum: proration-charge-immediately\|proration-charge\|proration-none | no | The update behavior for the subscription (defaults to proration-charge-immediately) |

---

### `UpsertSubscriptionItemEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | no | The id of the item to update. |
| `product_id` | string | no | The ID of the product associated with the subscription item. |
| `price_id` | string | no | The ID of the price associated with the subscription item. |
| `units` | number | no | The number of units for the subscription item. |

---

### `UsageEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `units` | number | yes | Number of units consumed by this call. |

---

### `ValidateLicenseRequestEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `key` | string | yes | The license key to validate. |
| `instance_id` | string | yes | Id of the instance to validate. |

---

### `WebhookCheckoutCompletedEventEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the event. |
| `eventType` | enum: checkout.completed | yes | The event name. |
| `created_at` | number | yes | Creation date of the event. |
| `object` | CheckoutEntity | yes | Object related to the event. |

---

### `WebhookDisputeCreatedEventEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the event. |
| `eventType` | enum: dispute.created | yes | The event name. |
| `created_at` | number | yes | Creation date of the event. |
| `object` | DisputeEntity | yes | Object related to the event. |

---

### `WebhookEventEntity`

Webhook event delivered by Creem. The eventType property determines the shape of object.

No documented fields.

### `WebhookRefundCreatedEventEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the event. |
| `eventType` | enum: refund.created | yes | The event name. |
| `created_at` | number | yes | Creation date of the event. |
| `object` | RefundEntity | yes | Object related to the event. |

---

### `WebhookSubscriptionActiveEventEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the event. |
| `eventType` | enum: subscription.active | yes | The event name. |
| `created_at` | number | yes | Creation date of the event. |
| `object` | WebhookSubscriptionEntity | yes | Object related to the event. |

---

### `WebhookSubscriptionCanceledEventEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the event. |
| `eventType` | enum: subscription.canceled | yes | The event name. |
| `created_at` | number | yes | Creation date of the event. |
| `object` | WebhookSubscriptionEntity | yes | Object related to the event. |

---

### `WebhookSubscriptionEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the object. |
| `mode` | EnvironmentMode | yes |  |
| `object` | string | yes | String representing the object's type. Objects of the same type share the same value. (e.g. `subscription`) |
| `product` | ProductEntity | yes | The product associated with the subscription. |
| `customer` | CustomerEntity | yes | The customer who owns the subscription. |
| `items` | array<SubscriptionItemEntity> | no | Subscription items. |
| `collection_method` | SubscriptionCollectionMethod | yes |  (e.g. `charge_automatically`) |
| `status` | SubscriptionStatus | yes |  (e.g. `active`) |
| `last_transaction_id` | string | no | The ID of the last paid transaction. (e.g. `tran_3e6Z6TzvHKdsjEgXnGDEp0`) |
| `last_transaction` | TransactionEntity | no | The last paid transaction. |
| `last_transaction_date` | string | no | The date of the last paid transaction. (e.g. `2024-09-12T12:34:56Z`) |
| `next_transaction_date` | string | no | The date when the next subscription transaction will be charged. (e.g. `2024-09-12T12:34:56Z`) |
| `current_period_start_date` | string | no | The start date of the current subscription period. (e.g. `2024-09-12T12:34:56Z`) |
| `current_period_end_date` | string | no | The end date of the current subscription period. (e.g. `2024-09-12T12:34:56Z`) |
| `canceled_at` | string | no | The date and time when the subscription was canceled, if applicable. (e.g. `2024-09-12T12:34:56Z`) |
| `created_at` | string | yes | The date and time when the subscription was created. (e.g. `2024-01-01T00:00:00Z`) |
| `updated_at` | string | yes | The date and time when the subscription was last updated. (e.g. `2024-09-12T12:34:56Z`) |
| `discount` | object{id, discountCode, name, type, amount, duration, durationI...} | no | The discount applied to the subscription, if any. |
| `metadata` | object | no | Metadata for the subscription in the form of key-value pairs. (e.g. `{'userId': 'user_123', 'plan': 'pro'}`) |

---

### `WebhookSubscriptionExpiredEventEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the event. |
| `eventType` | enum: subscription.expired | yes | The event name. |
| `created_at` | number | yes | Creation date of the event. |
| `object` | WebhookSubscriptionEntity | yes | Object related to the event. |

---

### `WebhookSubscriptionPaidEventEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the event. |
| `eventType` | enum: subscription.paid | yes | The event name. |
| `created_at` | number | yes | Creation date of the event. |
| `object` | WebhookSubscriptionEntity | yes | Object related to the event. |

---

### `WebhookSubscriptionPastDueEventEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the event. |
| `eventType` | enum: subscription.past_due | yes | The event name. |
| `created_at` | number | yes | Creation date of the event. |
| `object` | WebhookSubscriptionEntity | yes | Object related to the event. |

---

### `WebhookSubscriptionPausedEventEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the event. |
| `eventType` | enum: subscription.paused | yes | The event name. |
| `created_at` | number | yes | Creation date of the event. |
| `object` | WebhookSubscriptionEntity | yes | Object related to the event. |

---

### `WebhookSubscriptionScheduledCancelEventEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the event. |
| `eventType` | enum: subscription.scheduled_cancel | yes | The event name. |
| `created_at` | number | yes | Creation date of the event. |
| `object` | WebhookSubscriptionEntity | yes | Object related to the event. |

---

### `WebhookSubscriptionTrialingEventEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the event. |
| `eventType` | enum: subscription.trialing | yes | The event name. |
| `created_at` | number | yes | Creation date of the event. |
| `object` | WebhookSubscriptionEntity | yes | Object related to the event. |

---

### `WebhookSubscriptionUnpaidEventEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the event. |
| `eventType` | enum: subscription.unpaid | yes | The event name. |
| `created_at` | number | yes | Creation date of the event. |
| `object` | WebhookSubscriptionEntity | yes | Object related to the event. |

---

### `WebhookSubscriptionUpdateEventEntity`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the event. |
| `eventType` | enum: subscription.update | yes | The event name. |
| `created_at` | number | yes | Creation date of the event. |
| `object` | WebhookSubscriptionEntity | yes | Object related to the event. |

---
