from rest_framework import serializers
from .models import Photo

class PhotoSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(write_only=True, required=False)

    class Meta:
        model = Photo
        fields = [
            "id", "title", "description", "visibility", "image_url", "image", "owner", "uploaded_at"
        ]
        read_only_fields=['image_url', 'owner', 'uploaded_at']

    def create(self, validated_data):
        validated_data.pop("image", None)
        return super().create(validated_data)
