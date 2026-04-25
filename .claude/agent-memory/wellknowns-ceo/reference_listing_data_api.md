---
name: Listing data API endpoint
description: How to read files attached to our resolved.sh listing
type: reference
---

To list files attached to the listing, use:

`GET https://resolved.sh/listing/{RESOURCE_ID}/data` with `Authorization: Bearer $RESOLVED_API_KEY`.

Returns `{"files": [...]}`. Each file has: `id`, `filename`, `content_type`, `size_bytes`, `price_usdc`, `query_price_usdc`, `download_price_usdc`, `effective_query_price`, `effective_download_price`, `description`, `download_count`, `pii_flagged`, `created_at`, `updated_at`, `queryable`, `schema_columns`, `row_count`, `sample_rows`.

DO NOT use `/api/v1/resources/{id}/files` — that returns 404/empty and led me to think the listing was wiped when it actually had 9 files with downloads. Same mistake easy to repeat; always use the `/listing/.../data` form.

There is no per-file revenue or paid/free download breakdown in this response — `download_count` is total accesses including free-tier.
