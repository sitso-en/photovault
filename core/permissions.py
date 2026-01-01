from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsOwnerOrAdmin(BasePermission):
    """
    Permission class for photo ownership and admin access.
    
    Rules:
    - Public photos: Anyone can view (GET, HEAD, OPTIONS)
    - Private photos: Only owner and admins can view
    - Create: Authenticated users only
    - Update/Delete: Owner or admin only
    """
    
    def has_permission(self, request, view):
        """
        View-level permission check.
        Runs before fetching objects.
        """
        # Allow anonymous users to browse public photos (list view)
        if request.method in SAFE_METHODS:
            return True
        
        # For creating, updating, deleting - must be authenticated
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """
        Object-level permission check.
        Runs when accessing a specific photo.
        
        Args:
            request: The HTTP request
            view: The view being accessed
            obj: The Photo object being accessed
        """
        # Admins can do anything
        if request.user.is_authenticated and request.user.role == 'admin':
            return True
        
        # For read-only requests (GET, HEAD, OPTIONS)
        if request.method in SAFE_METHODS:
            # Public photos: Anyone can view
            if obj.visibility == 'public':
                return True
            
            # Private photos: Only owner can view
            if obj.visibility == 'private':
                return request.user.is_authenticated and obj.owner == request.user
        
        # For write requests (PUT, PATCH, DELETE)
        # Only owner can modify their own photos
        return request.user.is_authenticated and obj.owner == request.user


class IsAdmin(BasePermission):
    """
    Permission for admin-only actions.
    Used for sensitive operations like force-deleting inappropriate content.
    """
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'
    
    def has_object_permission(self, request, view, obj):
        return request.user.is_authenticated and request.user.role == 'admin'