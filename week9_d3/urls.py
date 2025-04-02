from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('d3_w9_app/', include('d3_w9_app.urls')),  
]
