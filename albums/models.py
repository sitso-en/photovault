from django.db import models
from django.conf import settings
from photos.models import Photo


class Album(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="albums"
    )
    photos = models.ManyToManyField(Photo, related_name="albums", blank=True,)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.owner.username})"

    class Meta:
        ordering = ['-created_at']
        
    def photo_count(self):
        return self.photos.count()
    
    def get_visible_photos(self, user):
        if user.is_authenticated and self.owner == user:
            return self.photos.all()
        
        return self.photos.filter(visibility='public')


class AlbumPhoto(models.Model):
    album = models.ForeignKey(Album, on_delete=models.CASCADE)
    photo = models.ForeignKey(Photo, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['added_at']
        unique_together = ['album', 'photo']
        
    def __str__(self):
        return f"{self.photo.title} in {self.album.title}"