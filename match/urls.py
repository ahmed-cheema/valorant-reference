from django.urls import path
from . import views

urlpatterns = [
    path('<slug:match_id>/', views.match_detail, name='match_detail'),
    path('player-stats/', views.player_stats, name='player_stats')
]