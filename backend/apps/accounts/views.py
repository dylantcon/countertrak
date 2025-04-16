# apps/accounts/views.py
from rest_framework import viewsets, permissions
from django.shortcuts import render
from .models import SteamAccount
from .serializers import SteamAccountSerializer

class SteamAccountViewSet(viewsets.ModelViewSet):
    queryset = SteamAccount.objects.all()
    serializer_class = SteamAccountSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Filter by current user if not staff/admin
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return SteamAccount.objects.all()
        return SteamAccount.objects.filter(user=user)
