from django.contrib import admin
from .models import Photo

@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "visibility", "uploaded_at")
    list_filter = ("visibility","uploaded_at")
    search_fields = ("title", "description", "owner__username")
    ordering = ("-uploaded_at",)