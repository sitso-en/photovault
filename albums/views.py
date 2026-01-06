from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.cache import cache
from django.conf import settings
from django.db import transaction
from core.permissions import IsAdmin
from core.throttles import AlbumCreateThrottle, AlbumModifyThrottle
from photos.models import Photo
from .models import Album, AlbumPhoto
from .serializers import (
    AlbumSerializer, 
    AlbumDetailSerializer,
    AddPhotoToAlbumSerializer,
    RemovePhotoFromAlbumSerializer
)
from .permissions import IsAlbumOwner


class AlbumViewSet(viewsets.ModelViewSet):
    serializer_class = AlbumSerializer
    permission_classes = [IsAlbumOwner]
    
    def get_queryset(self):
        user = self.request.user
        
        if user.role == 'admin':
            return Album.objects.all()
        
        return Album.objects.filter(owner=user)
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return AlbumDetailSerializer
        return AlbumSerializer
    
    def get_throttles(self):
        if self.action == 'create':
            return [AlbumCreateThrottle()]
        elif self.action in ['add_photo', 'remove_photo']:
            return [AlbumModifyThrottle()]
        return super().get_throttles()
    
    def list(self, request, *args, **kwargs):
        user = request.user
        page = request.query_params.get('page', 1)
        cache_key = f'albums_list_user_{user.id}_page_{page}'

        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)
        
        queryset = self.filter_queryset(self.get_queryset())
        page_obj = self.paginate_queryset(queryset)
        
        if page_obj is not None:
            serializer = self.get_serializer(page_obj, many=True)
            response_data = self.get_paginated_response(serializer.data).data
        else:
            serializer = self.get_serializer(queryset, many=True)
            response_data = serializer.data
        
        cache.set(cache_key, response_data, timeout=settings.CACHE_TTL)
        
        return Response(response_data)
    
    def retrieve(self, request, *args, **kwargs):
        album_id = kwargs.get('pk')
        user_id = request.user.id
        cache_key = f'album_detail_{album_id}_user_{user_id}'
        
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)
        
        instance = self.get_object()
        serializer = self.get_serializer(instance, context={'request': request})
        response_data = serializer.data
        
        cache.set(cache_key, response_data, timeout=settings.CACHE_TTL)
        
        return Response(response_data)
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        album = serializer.save(owner=request.user)
        
        self._invalidate_album_caches(request.user)
        
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        album = self.get_object()
        serializer = self.get_serializer(album, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        self._invalidate_album_caches(request.user, album.id)
        
        return Response(serializer.data)
    
    def destroy(self, request, *args, **kwargs):
        album = self.get_object()
        album_id = album.id
        
        album.delete()
        
        self._invalidate_album_caches(request.user, album_id)
        
        return Response(
            {'message': 'Album deleted successfully'},
            status=status.HTTP_204_NO_CONTENT
        )
    
    @action(detail=True, methods=['post'], permission_classes=[IsAlbumOwner])
    def add_photo(self, request, pk=None):
        album = self.get_object()
        serializer = AddPhotoToAlbumSerializer(
            data=request.data, 
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        photo_id = serializer.validated_data['photo_id']
        
        try:
            photo = Photo.objects.get(id=photo_id)
            
            if album.photos.filter(id=photo_id).exists():
                return Response(
                    {'error': 'Photo is already in this album'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            album.photos.add(photo)
            
            self._invalidate_album_caches(request.user, album.id)
            
            return Response(
                {
                    'message': 'Photo added to album successfully',
                    'album_id': album.id,
                    'photo_id': photo.id
                },
                status=status.HTTP_200_OK
            )
            
        except Photo.DoesNotExist:
            return Response(
                {'error': 'Photo not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'], permission_classes=[IsAlbumOwner])
    def remove_photo(self, request, pk=None):
        album = self.get_object()
        serializer = RemovePhotoFromAlbumSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        photo_id = serializer.validated_data['photo_id']
        
        try:
            photo = Photo.objects.get(id=photo_id)
        
            if not album.photos.filter(id=photo_id).exists():
                return Response(
                    {'error': 'Photo is not in this album'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            album.photos.remove(photo)
            
            self._invalidate_album_caches(request.user, album.id)
            
            return Response(
                {
                    'message': 'Photo removed from album successfully',
                    'album_id': album.id,
                    'photo_id': photo.id
                },
                status=status.HTTP_200_OK
            )
            
        except Photo.DoesNotExist:
            return Response(
                {'error': 'Photo not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['get'], permission_classes=[IsAlbumOwner])
    def photos(self, request, pk=None):
        album = self.get_object()
        user = request.user
        
        cache_key = f'album_{album.id}_photos_user_{user.id}'
        
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)
        
        visible_photos = album.get_visible_photos(user)
        
        from .serializers import AlbumPhotoSerializer
        album_photos = AlbumPhoto.objects.filter(
            album=album,
            photo__in=visible_photos
        ).select_related('photo')
        
        serializer = AlbumPhotoSerializer(album_photos, many=True)
        response_data = serializer.data
        
        cache.set(cache_key, response_data, timeout=settings.CACHE_TTL)
        
        return Response(response_data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_albums(self, request):
        cache_key = f'my_albums_user_{request.user.id}'
        
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)
        
        albums = Album.objects.filter(owner=request.user)
        serializer = self.get_serializer(albums, many=True)
        response_data = serializer.data
        
        cache.set(cache_key, response_data, timeout=settings.CACHE_TTL)
        
        return Response(response_data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def flag_inappropriate(self, request, pk=None):
        album = self.get_object()
        reason = request.data.get('reason', 'Inappropriate content')
        
        album_info = {
            'id': album.id,
            'title': album.title,
            'owner': album.owner.username,
            'photo_count': album.photos.count(),
            'reason': reason
        }
        
        album.delete()
        
        self._invalidate_all_album_caches()
        
        return Response(
            {
                'message': 'Album flagged and deleted',
                'details': album_info
            },
            status=status.HTTP_200_OK
        )
    
    def _invalidate_album_caches(self, user, album_id=None):
        for page in range(1, 11):
            cache.delete(f'albums_list_user_{user.id}_page_{page}')
        
        if album_id:
            cache.delete(f'album_detail_{album_id}_user_{user.id}')
            cache.delete(f'album_{album_id}_photos_user_{user.id}')
        
        cache.delete(f'my_albums_user_{user.id}')
    
    def _invalidate_all_album_caches(self):
        pass