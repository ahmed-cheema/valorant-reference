"""valorant URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from match import views

urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('admin/', admin.site.urls),

    path('match/', include('match.urls')),
    path('matches/', views.match_list, name='match_list'),

    path('player-stats/', views.player_stats, name='player_stats'),
    path('game-log/', views.gamelog, name='gamelog'),

    path('player/<str:username>/', views.player_detail, name='player_detail'),
    path('player/<str:username>/splits/', views.player_splits, name='player_splits'),
    path('player/<str:username>/game-log/', views.player_gamelog, name='player_gamelog'),
    path('player/<str:username>/teammates/', views.player_teammates, name='player_teammates'),

    path('maps/', views.maps_overview, name='maps_overview'),
    path('map/<str:map>/', views.map_detail, name='map_detail'),
    path('map/<str:map>/splits/', views.map_splits, name='map_splits'),

    path('agents/', views.agents_overview, name='agents_overview'),
    path('agent/<str:agent>/', views.agent_detail, name='agent_detail'),
    path('agent/<str:agent>/splits/', views.agent_splits, name='agent_splits'),

    path('records/', views.record_overview, name='record_overview'),
    path('records/single-game/', views.record_game, name='record_game'),
    path('records/streaks/', views.record_streak, name='record_streak'),
    path('records/career/', views.record_career, name='record_career'),

    path('lineups/', views.lineups, name='lineups'),

    path('blog/', views.blog, name='blog'),
    
    path('about/', views.about, name='about')
]
