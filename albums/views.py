from rest_framework import viewsets
from .models import Album
from .serializers import AlbumSerializer
from core.permissions import IsOwnerOrAdmin

class AlbumViewSet(viewsets.ModelViewSet):
    queryset = Album.objects.all()
    serializer_class = AlbumSerializer
    permission_classes = [IsOwnerOrAdmin]