from django.contrib import admin
from .models import Album, AlbumPhoto


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = ['title', 'owner', 'photo_count', 'created_at']
    list_filter = ['created_at', 'owner']
    search_fields = ['title', 'description', 'owner__username']
    readonly_fields = ['created_at', 'updated_at']
    
    def photo_count(self, obj):
        return obj.photos.count()
    photo_count.short_description = 'Photos'


@admin.register(AlbumPhoto)
class AlbumPhotoAdmin(admin.ModelAdmin):
    list_display = ['album', 'photo', 'added_at']
    list_filter = ['added_at']
    search_fields = ['album__title', 'photo__title']