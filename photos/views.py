from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, AllowAny
from django.db.models import Q
from django.core.cache import cache
from django.conf import settings
from core.permissions import IsOwnerOrAdmin, IsAdmin
from core.throttles import PhotoUploadThrottle, PhotoViewThrottle
from core.services.storage import S3StorageService, StorageException
from .models import Photo
from .serializers import PhotoSerializer


class PhotoViewSet(viewsets.ModelViewSet):
    serializer_class = PhotoSerializer
    permission_classes = [IsOwnerOrAdmin]

    def get_queryset(self):
        """Filter photos based on user and visibility"""
        user = self.request.user
        
        if user.is_authenticated and user.role == 'admin':
            return Photo.objects.all()
        
        if user.is_authenticated:
            return Photo.objects.filter(
                Q(visibility='public') | Q(owner=user)
            )
        
        return Photo.objects.filter(visibility='public')

    def get_throttles(self):
        """Apply different throttles based on action"""
        if self.action == 'create':
            return [PhotoUploadThrottle()]
        elif self.action in ['list', 'retrieve']:
            return [PhotoViewThrottle()]
        return super().get_throttles()

    def list(self, request, *args, **kwargs):
        """
        List photos with Redis caching.
        Cache key includes user ID to cache different views for different users.
        """
        user = request.user
        page = request.query_params.get('page', 1)
        
        # Generate cache key based on user and page
        if user.is_authenticated:
            cache_key = f'photos_list_user_{user.id}_page_{page}'
        else:
            cache_key = f'photos_list_anon_page_{page}'
        
        # Try to get from cache
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)
        
        # If not in cache, get from database
        queryset = self.filter_queryset(self.get_queryset())
        page_obj = self.paginate_queryset(queryset)
        
        if page_obj is not None:
            serializer = self.get_serializer(page_obj, many=True)
            response_data = self.get_paginated_response(serializer.data).data
        else:
            serializer = self.get_serializer(queryset, many=True)
            response_data = serializer.data
        
        # Cache the response for 5 minutes
        cache.set(cache_key, response_data, timeout=settings.CACHE_TTL)
        
        return Response(response_data)

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve single photo with Redis caching.
        Public photos are cached longer than private photos.
        """
        photo_id = kwargs.get('pk')
        cache_key = f'photo_detail_{photo_id}'
        
        # Try to get from cache
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)
        
        # If not in cache, get from database
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        response_data = serializer.data
        
        # Cache based on visibility
        if instance.visibility == 'public':
            # Public photos cached for 1 hour
            cache.set(cache_key, response_data, timeout=settings.CACHE_TTL_LONG)
        else:
            # Private photos cached for 5 minutes
            cache.set(cache_key, response_data, timeout=settings.CACHE_TTL)
        
        return Response(response_data)

    def create(self, request, *args, **kwargs):
        """Handle photo upload with cache invalidation"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        file = request.FILES.get('image')
        if not file:
            return Response(
                {'error': 'No image file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            storage = S3StorageService()
            folder = f"users/{request.user.username}"
            image_url = storage.upload(file, file.name, folder=folder)
            
            photo = serializer.save(owner=request.user, image_url=image_url)
            
            # Invalidate cache after creating new photo
            self._invalidate_photo_caches(request.user)
            
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )
            
        except StorageException as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'Upload failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def update(self, request, *args, **kwargs):
        """Update photo with cache invalidation"""
        partial = kwargs.pop('partial', False)
        photo = self.get_object()
        serializer = self.get_serializer(photo, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        new_file = request.FILES.get('image')
        
        if new_file:
            try:
                storage = S3StorageService()
                
                if photo.image_url:
                    try:
                        storage.delete(photo.image_url)
                    except StorageException:
                        pass
                
                folder = f"users/{request.user.username}"
                new_image_url = storage.upload(new_file, new_file.name, folder=folder)
                serializer.save(image_url=new_image_url)
                
            except StorageException as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            serializer.save()
        
        # Invalidate caches
        self._invalidate_photo_caches(request.user, photo.id)
        
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """Delete photo with cache invalidation"""
        photo = self.get_object()
        image_url = photo.image_url
        photo_id = photo.id
        
        try:
            storage = S3StorageService()
            storage.delete(image_url)
            self.perform_destroy(photo)
            
            # Invalidate caches
            self._invalidate_photo_caches(request.user, photo_id)
            
            return Response(
                {'message': 'Photo deleted successfully'},
                status=status.HTTP_204_NO_CONTENT
            )
            
        except StorageException as e:
            self.perform_destroy(photo)
            self._invalidate_photo_caches(request.user, photo_id)
            
            return Response(
                {
                    'message': 'Photo deleted from database',
                    'warning': f'S3 deletion failed: {str(e)}'
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': f'Delete failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _invalidate_photo_caches(self, user, photo_id=None):
        """
        Helper method to invalidate relevant caches.
        
        Invalidates:
        - User's photo list cache (all pages)
        - Anonymous photo list cache (if photo is public)
        - Specific photo detail cache
        - Custom endpoint caches (my_photos, public)
        """
        # Invalidate user's list cache (we don't know exact page count, so delete pattern)
        # In production, you'd use cache.delete_pattern() with redis
        # For now, we'll delete common pages
        for page in range(1, 11):  # Clear first 10 pages
            cache.delete(f'photos_list_user_{user.id}_page_{page}')
            cache.delete(f'photos_list_anon_page_{page}')
        
        # Invalidate specific photo cache
        if photo_id:
            cache.delete(f'photo_detail_{photo_id}')
        
        # Invalidate custom endpoint caches
        cache.delete(f'my_photos_user_{user.id}')
        cache.delete('public_photos')

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticatedOrReadOnly])
    def my_photos(self, request):
        """
        Get authenticated user's photos with caching.
        GET /api/photos/my_photos/
        """
        if not request.user.is_authenticated:
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        cache_key = f'my_photos_user_{request.user.id}'
        
        # Try cache first
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)
        
        # Get from database
        photos = Photo.objects.filter(owner=request.user)
        serializer = self.get_serializer(photos, many=True)
        response_data = serializer.data
        
        # Cache for 5 minutes
        cache.set(cache_key, response_data, timeout=settings.CACHE_TTL)
        
        return Response(response_data)

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def public(self, request):
        """
        Get all public photos with caching.
        GET /api/photos/public/
        Cached for longer since public photos change less frequently.
        """
        cache_key = 'public_photos'
        
        # Try cache first
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)
        
        # Get from database
        photos = Photo.objects.filter(visibility='public')
        serializer = self.get_serializer(photos, many=True)
        response_data = serializer.data
        
        # Cache for 10 minutes (public photos change less often)
        cache.set(cache_key, response_data, timeout=settings.CACHE_TTL * 2)
        
        return Response(response_data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def flag_inappropriate(self, request, pk=None):
        """Admin-only action to flag and delete inappropriate photos"""
        photo = self.get_object()
        reason = request.data.get('reason', 'Inappropriate content')
        
        photo_info = {
            'id': photo.id,
            'title': photo.title,
            'owner': photo.owner.username,
            'reason': reason
        }
        
        try:
            storage = S3StorageService()
            storage.delete(photo.image_url)
            photo.delete()
            
            # Invalidate all caches since we don't know whose feed this affected
            self._invalidate_all_caches()
            
            return Response(
                {
                    'message': 'Photo flagged and deleted',
                    'details': photo_info
                },
                status=status.HTTP_200_OK
            )
            
        except StorageException as e:
            photo.delete()
            self._invalidate_all_caches()
            
            return Response(
                {
                    'message': 'Photo deleted from database',
                    'warning': f'S3 deletion failed: {str(e)}',
                    'details': photo_info
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': f'Delete failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _invalidate_all_caches(self):
        """
        Invalidate all photo-related caches.
        Used when admin deletes photos.
        """
        # In production with django-redis, you'd use:
        # cache.delete_pattern('photos_list_*')
        # cache.delete_pattern('photo_detail_*')
        
        # For now, clear common cache keys
        cache.delete('public_photos')
        for page in range(1, 11):
            cache.delete(f'photos_list_anon_page_{page}')