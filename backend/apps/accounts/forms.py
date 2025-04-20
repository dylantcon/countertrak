from django import forms
from .models import SteamAccount

class SteamAccountForm(forms.ModelForm):
    class Meta:
        model = SteamAccount
        fields = ['steam_id', 'player_name']
        widgets = {
            'steam_id': forms.TextInput(attrs={'placeholder': 'e.g., 76561198015777160'}),
            'player_name': forms.TextInput(attrs={'placeholder': 'Your in-game name'})
        }
        
    def clean_steam_id(self):
        """Validate Steam ID format"""
        steam_id = self.cleaned_data.get('steam_id')
        # Basic format validation
        if not steam_id.isdigit() or len(steam_id) < 10:
            raise forms.ValidationError("Invalid Steam ID format. Use your 17-digit Steam ID.")
        return steam_id