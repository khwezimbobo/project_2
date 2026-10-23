from rest_framework import serializers
from .models import Customer

class CustomerSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Customer
        fields = '__all__'
    
    agent = serializers.StringRelatedField(read_only=True)