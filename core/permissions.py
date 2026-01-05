from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsOwnerOrAdmin(BasePermission):    
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_authenticated and request.user.role == 'admin':
            return True
        
        if request.method in SAFE_METHODS:
            if obj.visibility == 'public':
                return True
            
            if obj.visibility == 'private':
                return request.user.is_authenticated and obj.owner == request.user
        
        return request.user.is_authenticated and obj.owner == request.user


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'
    
    def has_object_permission(self, request, view, obj):
        return request.user.is_authenticated and request.user.role == 'admin'