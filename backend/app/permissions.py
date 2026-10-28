"""Role-based access control for staff.

Deliberately, no permission here grants reading private case content, conversations or
documents. Any future "break-glass" access must be a separate, purpose-bound, audited flow.
"""
from enum import StrEnum


class Role(StrEnum):
    SYSADMIN = "sysadmin"
    LEGAL_RESEARCHER = "legal_researcher"
    CONTENT_REVIEWER = "content_reviewer"
    SUPPORT = "support"
    BILLING_ADMIN = "billing_admin"


class Perm(StrEnum):
    USERS_READ = "users.read"
    USERS_SUSPEND = "users.suspend"
    ROLES_MANAGE = "roles.manage"
    SUBSCRIPTIONS_MANAGE = "subscriptions.manage"
    PLANS_MANAGE = "plans.manage"
    SOURCES_READ = "sources.read"
    SOURCES_WRITE = "sources.write"
    SOURCES_REVIEW = "sources.review"
    JURISDICTIONS_MANAGE = "jurisdictions.manage"
    FLAGS_MANAGE = "flags.manage"
    AUDIT_READ = "audit.read"
    HEALTH_READ = "health.read"


ROLE_PERMISSIONS: dict[Role, set[Perm]] = {
    Role.SYSADMIN: {
        Perm.USERS_READ, Perm.USERS_SUSPEND, Perm.ROLES_MANAGE, Perm.PLANS_MANAGE,
        Perm.SOURCES_READ, Perm.JURISDICTIONS_MANAGE, Perm.FLAGS_MANAGE, Perm.AUDIT_READ,
        Perm.HEALTH_READ,
    },
    Role.LEGAL_RESEARCHER: {Perm.SOURCES_READ, Perm.SOURCES_WRITE, Perm.JURISDICTIONS_MANAGE},
    Role.CONTENT_REVIEWER: {Perm.SOURCES_READ, Perm.SOURCES_REVIEW},
    Role.SUPPORT: {Perm.USERS_READ, Perm.USERS_SUSPEND},
    Role.BILLING_ADMIN: {Perm.USERS_READ, Perm.SUBSCRIPTIONS_MANAGE, Perm.PLANS_MANAGE},
}


def permissions_for(roles: set[str]) -> set[Perm]:
    perms: set[Perm] = set()
    for r in roles:
        if r in Role._value2member_map_:
            perms |= ROLE_PERMISSIONS[Role(r)]
    return perms
