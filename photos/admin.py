from django.contrib import admin
from .models import Photo

@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "uploaded_at","visibility")
    list_filter = ("uploaded_at","visibility")
    search_fields = ( "owner__username","title", "description")
    ordering = ("-uploaded_at",)