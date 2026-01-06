from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAlbumOwner(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        if request.user.role == 'admin':
            return True
        
        return obj.owner == request.user