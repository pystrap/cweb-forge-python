"""cWeb Forge: bounded HTTP clients, no hidden global credentials or retries."""
import asyncio
import json
import re
import uuid
from urllib.parse import urlsplit
import httpx

__all__ = ['ForgeClient', 'AsyncForgeClient', 'ForgeError']


class ForgeError(Exception):
    def __init__(self, message, status=0, code='network_error', request_id=''):
        super().__init__(message)
        self.status, self.code, self.request_id = status, code, request_id


def _endpoint(url):
    p = urlsplit(url)
    local = p.hostname in ('localhost', '127.0.0.1', '::1') or (p.hostname or '').endswith('.localhost')
    if not p.hostname or (p.scheme != 'https' and not (p.scheme == 'http' and local)) or p.username or p.password or p.query or p.fragment:
        raise ValueError('Use an HTTPS endpoint; HTTP is permitted only for local development.')
    return url.rstrip('/')


def _name(value):
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', value):
        raise ValueError('Invalid collection name.')
    return value


def _result(response):
    if response.status_code == 204:
        return None
    try:
        value = response.json()
    except ValueError:
        raise ForgeError('Forge returned an invalid response.', response.status_code, 'invalid_response')
    if not response.is_success:
        error = value.get('error', {})
        raise ForgeError(error.get('message', 'Forge request failed.'), response.status_code,
                         error.get('code', 'request_failed'), response.headers.get('X-Request-ID', ''))
    return value


class ForgeClient:
    def __init__(self, endpoint: str, token=None, *, timeout: float = 15, transport=None):
        self.endpoint, self.token = _endpoint(endpoint), token
        self._http = httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False, transport=transport)

    def request(self, method, path, *, body=None, headers=None, params=None):
        token = self.token() if callable(self.token) else self.token
        auth = {'Authorization': 'Bearer ' + token} if token else {}
        try:
            return _result(self._http.request(method, self.endpoint + path, json=body, params=params,
                           headers={**auth, **(headers or {})}))
        except httpx.HTTPError:
            raise ForgeError('Unable to complete the Forge request.') from None

    def collection(self, name: str):
        return Collection(self, name)

    def close(self): self._http.close()
    def __enter__(self): return self
    def __exit__(self, *args): self.close()


class Collection:
    def __init__(self, client, name):
        self.client, self.path = client, '/collections/' + _name(name) + '/documents'

    def list(self, *, limit=50, after=None, field=None, equals=None):
        params = {'limit': limit}
        if after: params['after'] = after
        if field: params.update(field=field, value=json.dumps(equals, allow_nan=False))
        return self.client.request('GET', self.path, params=params)

    def get(self, document_id):
        return self.client.request('GET', self.path + '/' + str(uuid.UUID(str(document_id))))

    def create(self, data, *, idempotency_key=None):
        return self.client.request('POST', self.path, body=data, headers={'Idempotency-Key': idempotency_key or str(uuid.uuid4())})

    def replace(self, document_id, data, *, version):
        return self.client.request('PUT', self.path + '/' + str(uuid.UUID(str(document_id))), body=data, headers={'If-Match': f'"{version}"'})

    def update(self, document_id, data, *, version):
        return self.client.request('PATCH', self.path + '/' + str(uuid.UUID(str(document_id))), body=data, headers={'If-Match': f'"{version}"'})

    def delete(self, document_id, *, version):
        return self.client.request('DELETE', self.path + '/' + str(uuid.UUID(str(document_id))), headers={'If-Match': f'"{version}"'})

    def iterate(self, **options):
        after = None
        while True:
            result = self.list(after=after, **options)
            yield from result['items']
            cursor = result.get('next_cursor')
            if not cursor: return
            if cursor == after: raise ForgeError('Invalid pagination cursor.', code='invalid_response')
            after = cursor


class AsyncForgeClient:
    def __init__(self, endpoint: str, token=None, *, timeout: float = 15, transport=None):
        self.endpoint, self.token = _endpoint(endpoint), token
        self._http = httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False, transport=transport)

    async def request(self, method, path, *, body=None, headers=None, params=None):
        import inspect
        token = self.token() if callable(self.token) else self.token
        if inspect.isawaitable(token): token = await token
        auth = {'Authorization': 'Bearer ' + token} if token else {}
        try:
            return _result(await self._http.request(method, self.endpoint + path, json=body, params=params, headers={**auth, **(headers or {})}))
        except httpx.HTTPError:
            raise ForgeError('Unable to complete the Forge request.') from None

    def collection(self, name: str): return AsyncCollection(self, name)
    async def close(self): await self._http.aclose()
    async def __aenter__(self): return self
    async def __aexit__(self, *args): await self.close()


class AsyncCollection(Collection):
    async def iterate(self, **options):
        after = None
        while True:
            result = await self.list(after=after, **options)
            for item in result['items']: yield item
            cursor = result.get('next_cursor')
            if not cursor: return
            if cursor == after: raise ForgeError('Invalid pagination cursor.', code='invalid_response')
            after = cursor
