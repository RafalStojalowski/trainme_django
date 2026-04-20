from django.urls import path
from .views import home, speech_input

urlpatterns = [
    path('', home, name='home'),
    path('speech/', speech_input, name='speech_input'),
]