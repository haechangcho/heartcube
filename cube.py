"""Cube Core OSS configuration.

JWT API auth is enforced through Python `check_auth`.
`context_to_groups` maps authenticated JWT claims to access-policy groups.
"""

from typing import Any, Dict, List, Optional

import jwt
import os

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


@config('check_auth')
def check_auth(ctx: Dict[str, Any], token: str) -> Dict[str, Any]:
    del ctx

    payload = jwt.decode(
        _normalize_token(token),
        _load_api_secret(),
        algorithms=['HS256'],
    )

    groups = payload.get('groups')
    if not isinstance(groups, list) or not groups:
        raise Exception('JWT is missing groups')

    if not all(isinstance(group, str) and group.strip() for group in groups):
        raise Exception('JWT groups must be a non-empty list of strings')

    sub = payload.get('sub')
    if not isinstance(sub, str) or not sub.strip():
        raise Exception('JWT is missing sub')

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
