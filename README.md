# cWeb Forge · Python

**Serverless data and authentication API for your next application.**

Use cWeb Forge collections from Python backends, scripts and notebooks without
building a separate data API. This is the official Python SDK for
[cWeb Forge](https://cweb.app/forge), with synchronous and asynchronous clients for
applications on cWeb or any other host.

- JSON document operations with collection access rules.
- Cursor pagination, equality filters and streaming iteration over pages.
- Version checks for concurrent edits and idempotency keys for create retries.
- Backend service keys or application-user access tokens.
- Works with Django, FastAPI, cWeb Studio and other Python notebook environments.

[Documentation](https://cweb.app/docs/forge/) · [Full Python guide](https://cweb.app/docs/forge/python) ·
[Getting started](#getting-started) · [Async usage](#async-usage) ·
[Notebooks](#notebooks) · [Contributing](#contributing)

## Installation

Requires Python 3.10 or later.

Install from PyPI:

```sh
python -m pip install cweb-forge
```

The package name is `cweb-forge`; import it as `cweb_forge`.

## Getting started

1. Create a Forge application in the [cWeb dashboard](https://portal.cweb.app)
   and copy its API endpoint, including `/v1/`.
2. Create a service key restricted to the collections and actions your backend
   needs. Supply it as `CWEB_FORGE_KEY` through your environment or secret manager.
3. Use the application's `records` collection to try the SDK:

```python
import os
from cweb_forge import ForgeClient

endpoint = 'https://my-app.forge.cweb.app/v1/'  # Replace with your endpoint.

with ForgeClient(endpoint, token=os.environ['CWEB_FORGE_KEY']) as forge:
    records = forge.collection('records')
    created = records.create({'title': 'Draft', 'status': 'active'})
    saved = records.update(
        created['id'], {'title': 'Published'}, version=created['version']
    )
    print(saved['id'])
```

Use a context manager to close connections, or call `forge.close()` when
finished. A service key may access records across application users according
to its scopes. Never embed one in frontend code, mobile apps or shared notebooks.

### Application-user tokens

`token` can instead be an application user's access token or a callable that
returns a fresh token before each request. The asynchronous client also accepts
an async callable. Token validation and collection policies are enforced by the
service; default owner access keeps a user's documents private to that user.

The Python SDK does not perform interactive sign-in or automatically refresh a
fixed token string. Your application's authentication integration must supply
and refresh its tokens. Use the
[JavaScript SDK](https://github.com/pystrap/cweb-forge-js#authentication) for
browser sign-in. Never use a cWeb dashboard login token as a Forge application token.

### Public reads without a token

Set the collection's read policy to **Anyone (public)** under **Collections &
rules**, then omit `token`:

```python
from cweb_forge import ForgeClient

with ForgeClient('https://my-app.forge.cweb.app/v1/') as forge:
    page = forge.collection('products').list(limit=50)
    for document in page['items']:
        print(document['data'])
```

Every document and field in that collection is public. Keep private data in
separate collections. Anonymous writes are not supported, and public reads
still consume the application's request allowances.

## Working with documents

Your JSON object is returned in `document['data']`, alongside metadata including
`id`, `owner`, `version`, `created_at` and `updated_at`.

| Method | Purpose |
| --- | --- |
| `list(limit=50, after=None, field=None, equals=None)` | Read a page with `items` and `next_cursor`. |
| `get(document_id)` | Read one document. |
| `create(data, idempotency_key=None)` | Create a document; a key is generated if omitted. |
| `update(document_id, data, version=...)` | Patch the supplied fields. |
| `replace(document_id, data, version=...)` | Replace the document's data. |
| `delete(document_id, version=...)` | Delete a document. |
| `iterate(limit=50, field=None, equals=None)` | Iterate over documents across successive pages. |

Collection names start with a lowercase letter, contain lowercase letters,
numbers or underscores, and have a maximum length of 64 characters. Document
IDs are UUIDs returned by Forge.

```python
with ForgeClient(endpoint, token=os.environ['CWEB_FORGE_KEY']) as forge:
    records = forge.collection('records')
    page = records.list(limit=50, field='status', equals='active')
    if page['next_cursor']:
        next_page = records.list(
            limit=50, after=page['next_cursor'], field='status', equals='active'
        )

    for document in records.iterate(limit=100, field='status', equals='active'):
        print(document['id'])
```

Equality filters accept scalar field values. Page limits range from 1 to 100
documents. Iteration fetches one page at a time; collecting every result into a
list still uses memory for the entire result.

Use the latest returned `version` for each update, replacement or deletion.
On a `409` conflict, reload and resolve the change before retrying. To retry a
create after an uncertain network outcome, reuse the same `idempotency_key`
for that logical operation within the server's 24-hour window. The SDK does not
automatically retry writes.

## Async usage

Use `AsyncForgeClient` in asynchronous applications. Await document operations,
and use `async for` when iterating:

```python
import asyncio
import os
from cweb_forge import AsyncForgeClient

async def main():
    async with AsyncForgeClient(
        'https://my-app.forge.cweb.app/v1/',
        token=os.environ['CWEB_FORGE_KEY'],
    ) as forge:
        records = forge.collection('records')
        created = await records.create({'title': 'Async example'})
        print(created['id'])
        async for document in records.iterate(limit=100):
            print(document['id'])

asyncio.run(main())
```

In notebooks with an existing event loop, use `await main()` instead of
`asyncio.run(main())`. Close a manually managed async client with
`await forge.close()`.

## Notebooks

The SDK can fetch data for pandas, DuckDB or your own analysis code. Those
libraries are optional and installed separately. Start with a read-only key and
a bounded sample:

```python
import os
import pandas as pd
from cweb_forge import ForgeClient

# Configure this secret in the notebook environment; do not paste it into a cell.
with ForgeClient(
    'https://my-app.forge.cweb.app/v1/',
    token=os.environ['CWEB_FORGE_KEY'],
) as forge:
    page = forge.collection('sales').list(limit=100)
    frame = pd.DataFrame([document['data'] for document in page['items']])
```

This reads a page of JSON documents; it does not mount a database or automatically
copy the whole collection into Studio's catalog. Do not save credentials or
sensitive results in notebook outputs that you intend to share.

## Errors and timeouts

Catch `ForgeError` for API or transport failures. It includes `status`, `code`
and `request_id`; network failures use status `0`.

| Status | Suggested handling |
| --- | --- |
| `401` | Renew credentials or sign the application user in again. |
| `403` | Check collection rules and service-key permissions. |
| `409` | Resolve a concurrent edit or idempotency conflict. |
| `429` | Inspect the error code for rate or quota limits before retrying. |
| `503` | Retry later with bounded backoff when safe. |

```python
from cweb_forge import ForgeError

try:
    with ForgeClient(endpoint, token=os.environ['CWEB_FORGE_KEY']) as forge:
        page = forge.collection('records').list()
except ForgeError as error:
    print(f'Forge request failed: {error.status} {error.code}')
    # Share error.request_id with support if present; never log credentials.
```

HTTPX timeouts default to 15 seconds and can be configured with `timeout=30`
on the client. These are transport timeouts, not a deadline for a complete
multi-page iteration. HTTPS is required except on localhost; redirects and
proxy settings inherited from environment variables are disabled.

## Security and support

Use narrowly scoped keys and rotate them if exposed. Keep keys, application-user
tokens, private data and authentication headers out of logs and Git commits.
For vulnerabilities, follow the
[security policy](https://github.com/pystrap/cweb-forge-python/blob/main/SECURITY.md).

Report SDK bugs through
[GitHub issues](https://github.com/pystrap/cweb-forge-python/issues), with the
SDK/Python versions and a minimal reproduction. For account or billing help,
contact cWeb Support at [support@cweb.app](mailto:support@cweb.app).

## Contributing

Focused fixes, regression tests and documentation improvements are welcome.
From a clone of this repository:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
```

Tests use mocked HTTP responses and do not require a live Forge account.
Include tests for changed behavior and never submit customer data or credentials.

## License

[MIT](https://github.com/pystrap/cweb-forge-python/blob/main/LICENSE).
Maintained by [PyStrap](https://pystrap.co.uk), the team behind cWeb.
