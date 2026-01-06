from rest_framework import serializers
from .models import Album, AlbumPhoto
from photos.serializers import PhotoSerializer
from photos.models import Photo


class AlbumPhotoSerializer(serializers.ModelSerializer):
    photo = PhotoSerializer(read_only=True)
    
    class Meta:
        model = AlbumPhoto
        fields = ['id', 'photo', 'added_at']
        read_only_fields = ['added_at']


class AlbumSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source='owner.username', read_only=True)
    photo_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Album
        fields = [
            'id','title', 'description', 'owner','owner_username','photo_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['owner', 'created_at', 'updated_at']
    
    def get_photo_count(self, obj):
        return obj.photos.count()


class AlbumDetailSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source='owner.username', read_only=True)
    photos = serializers.SerializerMethodField()
    photo_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Album
        fields = [
            'id','title', 'description', 'owner', 'owner_username', 'photos','photo_count','created_at', 'updated_at'
        ]
        read_only_fields = ['owner', 'created_at', 'updated_at']
    
    def get_photos(self, obj):
        request = self.context.get('request')
        user = request.user if request else None
        
        visible_photos = obj.get_visible_photos(user)
        
        album_photos = AlbumPhoto.objects.filter(
            album=obj,
            photo__in=visible_photos
        ).select_related('photo')
        
        return AlbumPhotoSerializer(album_photos, many=True).data
    
    def get_photo_count(self, obj):
        request = self.context.get('request')
        user = request.user if request else None
        return obj.get_visible_photos(user).count()


class AddPhotoToAlbumSerializer(serializers.Serializer):
    photo_id = serializers.IntegerField()
    
    def validate_photo_id(self, value):
        #Validate that photo exists and belongs to user
        request = self.context.get('request')
        
        try:
            photo = Photo.objects.get(id=value)
        except Photo.DoesNotExist:
            raise serializers.ValidationError("Photo not found")
        
        if photo.owner != request.user:
            raise serializers.ValidationError("You can only add your own photos to albums")
        
        return value


class RemovePhotoFromAlbumSerializer(serializers.Serializer):
    photo_id = serializers.IntegerField()
    
    def validate_photo_id(self, value):
        #validate that photo exists
        try:
            Photo.objects.get(id=value)
        except Photo.DoesNotExist:
            raise serializers.ValidationError("Photo not found")
        
        return value