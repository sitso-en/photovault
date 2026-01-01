from rest_framework import serializers
from .models import Album
from photos.serializers import PhotoSerializer

class AlbumSerializer(serializers.ModelSerializer):
    photos = PhotoSerializer(many=True, read_only=True)

    class Meta:
        model = Album
        fields = [
            "id", 
            "title", 
            "description", 
            "owner", 
            "photos", 
            "created_at"
        ]