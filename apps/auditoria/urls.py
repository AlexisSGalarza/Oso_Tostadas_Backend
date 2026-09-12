from django.urls import path

from . import views

urlpatterns = [
    path('auditoria/', views.RegistroAuditoriaListView.as_view(), name='auditoria'),
]
