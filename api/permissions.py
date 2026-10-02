from rest_framework.permissions import BasePermission


class IsOwnerObjectPermission(BasePermission):
    """Require object-level owner fields to match the authenticated account."""

    def has_object_permission(self, request, view, obj):
        return getattr(obj, "user_id", None) == request.user.id