from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('speech/', views.speech_input, name='speech_input'),
    path('conversations/', views.conversation_list, name='conversation_list'),
    path('conversations/new/', views.new_conversation, name='new_conversation'),
    path('conversations/<int:conv_id>/messages/', views.conversation_messages, name='conversation_messages'),
    path('login/', auth_views.LoginView.as_view(template_name='home/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', views.register, name='register'),
    path('profile/', views.profile, name='profile'),
]
