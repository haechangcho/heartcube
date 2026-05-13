"""Cube Core OSS configuration.

JWT API auth is handled by Cube's built-in JWT verification.
`context_to_groups` maps authenticated JWT claims to access-policy groups.
"""

from typing import List

from cube import config


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
