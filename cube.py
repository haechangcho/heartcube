# Cube Core OSS 설정 파일
# 문서: https://cube.dev/docs/config
#
# context_to_groups: JWT securityContext → access_policy 그룹 매핑
# Access Control 테스트: model/views/claims_access_test.yml 참고

from cube import config


@config('context_to_groups')
def context_to_groups(ctx: dict) -> list:
    """
    JWT payload(securityContext)에서 groups 배열을 읽어 정책 그룹을 반환합니다.

    JWT 예시:
        { "groups": ["admin"] }                              → admin 정책
        { "groups": ["regional_manager"], "claim_center": "서울본부" }  → regional_manager 정책
        { "groups": ["analyst"] }                            → analyst 정책 (마스킹 적용)
        { "groups": ["guest"] }                              → guest 정책 (제한 접근)
        { "groups": ["analyst", "audit"] }                   → 두 정책 OR 합산 적용

    groups 필드가 없거나 비어있으면 'guest'로 fallback합니다.
    """
    security_context = ctx.get('securityContext') or {}
    groups = security_context.get('groups') or []
    return groups if groups else ['guest']
