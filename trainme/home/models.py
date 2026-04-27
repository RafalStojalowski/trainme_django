from django.db import models
from django.contrib.auth.models import User
# Create your models here.

class Conversation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateField(auto_created=True)
    ended_at = models.DateField(null=True, blank=True) 
    
class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE)
    text = models.TextField()
    from_user = models.BooleanField()
    count = models.IntegerField()
    created_at = models.DateField(auto_created=True)

class AudioRecord(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE)
    wav_path = models.FilePathField()
    created_at = models.DateField(auto_created=True)





