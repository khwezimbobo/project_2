from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class Customer(models.Model):
    
    name = models.CharField(max_length=100)

    email = models.EmailField(unique=True)

    phone = models.CharField(max_length=10)

    address = models.TextField()

    agent = models.ForeignKey(User, on_delete=models.CASCADE)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name