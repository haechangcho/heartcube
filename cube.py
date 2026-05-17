"""Cube Core OSS configuration.

JWT API auth is enforced through Python `check_auth`.
`context_to_groups` maps authenticated JWT claims to access-policy groups.
"""

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict, List, Optional

from cube import config


def _normalize_token(token: Optional[str]) -> str:
    if not token:
        raise Exception('Authorization header is required')

    normalized = token.strip()
    if normalized.lower().startswith('bearer '):
        normalized = normalized[7:].strip()

    if not normalized:
        raise Exception('Authorization header is required')

    return normalized


def _load_api_secret() -> str:
    secret = os.getenv('CUBEJS_API_SECRET')
    if not secret:
        raise Exception('CUBEJS_API_SECRET is not configured')
    return secret


def _base64url_decode(value: str) -> bytes:
    padding = '=' * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _decode_json_segment(segment: str, label: str) -> Dict[str, Any]:
    try:
        decoded = _base64url_decode(segment).decode('utf-8')
        payload = json.loads(decoded)
    except Exception as exc:  # pragma: no cover - defensive guard
        raise Exception(f'Invalid JWT {label}') from exc

    if not isinstance(payload, dict):
        raise Exception(f'Invalid JWT {label}')

    return payload


def _verify_hs256_jwt(token: str, secret: str) -> Dict[str, Any]:
    parts = token.split('.')
    if len(parts) != 3:
        raise Exception('Invalid JWT format')

    header = _decode_json_segment(parts[0], 'header')
    payload = _decode_json_segment(parts[1], 'payload')

    if header.get('alg') != 'HS256':
        raise Exception('Unsupported JWT algorithm')

    signing_input = f'{parts[0]}.{parts[1]}'.encode('ascii')
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        signing_input,
        hashlib.sha256,
    ).digest()

    try:
        provided_signature = _base64url_decode(parts[2])
    except Exception as exc:  # pragma: no cover - defensive guard
        raise Exception('Invalid JWT signature') from exc

    if not hmac.compare_digest(expected_signature, provided_signature):
        raise Exception('Invalid JWT signature')

    exp = payload.get('exp')
    if not isinstance(exp, (int, float)):
        raise Exception('JWT is missing exp')

    if int(time.time()) >= int(exp):
        raise Exception('JWT has expired')

    sub = payload.get('sub')
    if not isinstance(sub, str) or not sub.strip():
        raise Exception('JWT is missing sub')

    groups = payload.get('groups')
    if not isinstance(groups, list) or not groups:
        raise Exception('JWT is missing groups')

    if not all(isinstance(group, str) and group.strip() for group in groups):
        raise Exception('JWT groups must be a non-empty list of strings')

    return payload


@config('check_auth')
def check_auth(ctx: Dict[str, Any], token: str) -> Dict[str, Any]:
    del ctx

    payload = _verify_hs256_jwt(_normalize_token(token), _load_api_secret())
    return {'security_context': payload}


@config('context_to_groups')
def context_to_groups(ctx: dict) -> List[str]:
    """
    JWT payload(securityContext)에서 groups 배열을 읽어 정책 그룹을 반환합니다.

    JWT 예시:
        { "sub": "analyst_01", "groups": ["admin"] } → admin 정책
        { "sub": "mgr_seoul", "groups": ["regional_manager"], "claim_center": "서울본부" }
            → regional_manager 정책
        { "sub": "analyst_01", "groups": ["analyst"] } → analyst 정책 (마스킹 적용)
        { "sub": "test_guest", "groups": ["guest"] } → guest 정책 (제한 접근)
        { "sub": "auditor_01", "groups": ["analyst", "audit"] } → 두 정책 OR 합산 적용

    check_auth에서 groups를 필수로 검증하므로, 여기서는 안전망으로만 guest fallback을 둡니다.
    """
    security_context = ctx.get('securityContext') or {}
    groups = security_context.get('groups') or []
    return groups if groups else ['guest']
