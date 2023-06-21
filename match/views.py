from django.shortcuts import render, get_object_or_404
from .models import Match, Player

from django.db import models
from django.db.models import Subquery, OuterRef, Sum, Count, Min, Max, Case, When, Avg, F, IntegerField, FloatField, ExpressionWrapper, Value, Q
from django.db.models.functions import Cast, Round

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from urllib.parse import unquote

from django.http import Http404

from collections import Counter
from datetime import datetime

from django.contrib.staticfiles import finders

from django.views.decorators.cache import cache_page
#from django.core.cache import cache
#from django.db.models.signals import post_save, post_delete
#from django.dispatch import receiver

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio

agent_map = {"41fb69c1-4189-7b37-f117-bcaf1e96f1bf":"Astra",
             "5f8d3a7f-467b-97f3-062c-13acf203c006":"Breach",
             "9f0d8ba9-4140-b941-57d3-a7ad57c6b417":"Brimstone",
             "22697a3d-45bf-8dd7-4fec-84a9e28c69d7":"Chamber",
             "117ed9e3-49f3-6512-3ccf-0cada7e3823b":"Cypher",
             "dade69b4-4f5a-8528-247b-219e5a1facd6":"Fade",
             "e370fa57-4757-3604-3648-499e1f642d3f":"Gekko",
             "95b78ed7-4637-86d9-7e41-71ba8c293152":"Harbor",
             "add6443a-41bd-e414-f6ad-e58d267f4e95":"Jett",
             "601dbbe7-43ce-be57-2a40-4abd24953621":"KAY/O",
             "1e58de9c-4950-5125-93e9-a0aee9f98746":"Killjoy",
             "bb2a4828-46eb-8cd1-e765-15848195d751":"Neon",
             "8e253930-4c05-31dd-1b6c-968525494517":"Omen",
             "eb93336a-449b-9c1b-0a54-a891f7921d69":"Phoenix",
             "f94c3b30-42be-e959-889c-5aa313dba261":"Raze",
             "a3bfb853-43b2-7238-a4f1-ad90e9e46bcc":"Reyna",
             "569fdd95-4d10-43ab-ca70-79becc718b46":"Sage",
             "6f2a04ca-43e0-be17-7f36-b3908627744d":"Skye",
             "320b2a48-4d9b-a075-30f1-1f93a9b638fa":"Sova",
             "707eab51-4836-f488-046a-cda6bf494859":"Viper",
             "7f94d92c-4234-0a36-9646-3a87eb8b5c89":"Yoru"}

def AgentImage(agent):
        agent_id = None
        for k, v in agent_map.items():
            if v == agent:
                agent_id = k
                break
        if agent_id:
            return f"https://titles.trackercdn.com/valorant-api/agents/{agent_id}/displayicon.png"
        return None

def AgentPortrait(agent):
        return f"https://trackercdn.com/cdn/tracker.gg/valorant/db/agents/{agent.lower()}_portrait.png"

def FilterPlayers(players, map_filter, outcome_filter, agent_filter, role_filter, date_filter, mvp_filter=None, n_duelists=None):
    if map_filter:
        players = players.filter(Match__Map=map_filter)
    if outcome_filter:
        if outcome_filter == "win":
            players = players.filter(Match__TeamOneWon=1)
        elif outcome_filter == "loss":
            players = players.filter(Match__TeamOneLost=1)
        elif outcome_filter == "draw":
            players = players.filter(Match__MatchDraw=1)
    if agent_filter:
        players = players.filter(Agent=agent_filter)
    if role_filter:
        players = players.filter(Role=role_filter)
    if date_filter:
        date_split = date_filter.split(' - ')
        start = datetime.strptime(date_split[0], '%m/%d/%Y')
        end = datetime.strptime(date_split[1], '%m/%d/%Y')
        players = players.filter(Match__Date__range=(start, end))
    if mvp_filter:
        players = players.filter(MVP=mvp_filter)
    if n_duelists:
        players = players.filter(Match__N_Duelists=n_duelists)
    return players

def FilterMatches(matches, map_filter, outcome_filter, date_filter, mvp_filter):
    if map_filter:
        matches = matches.filter(Map=map_filter)
    if outcome_filter:
        if outcome_filter == "win":
            matches = matches.filter(TeamOneWon=1)
        elif outcome_filter == "loss":
            matches = matches.filter(TeamOneLost=1)
        elif outcome_filter == "draw":
            matches = matches.filter(MatchDraw=1)
    if date_filter:
        date_split = date_filter.split(' - ')
        start = datetime.strptime(date_split[0], '%m/%d/%Y')
        end = datetime.strptime(date_split[1], '%m/%d/%Y')
        matches = matches.filter(Date__range=(start, end))
    if mvp_filter:
        matches = matches.filter(MVP=mvp_filter)
    return matches

def FilterPlayerParticipation(matches, button_values):
    include_q_objects = Q()
    exclude_q_objects = Q()
    include_count = 0

    for player, value in button_values.items():
        if value == 1:
            # Include matches where the player with the given display name participated and the team is "Team A"
            include_q_objects |= Q(player__DisplayName=player, player__Team="Team A")
            include_count += 1
        elif value == 0:
            # Exclude matches where the player with the given display name participated and the team is "Team A"
            exclude_q_objects |= Q(player__DisplayName=player, player__Team="Team A")

    if include_count > 0:
        filtered_matches = matches.filter(include_q_objects)\
                                  .annotate(num_players=Count('player__DisplayName', distinct=True))\
                                  .filter(num_players=include_count)\
                                  .exclude(exclude_q_objects)\
                                  .distinct()
    else:
        filtered_matches = matches.exclude(exclude_q_objects).distinct()

    return filtered_matches

def homepage(request):
    LastMatch = Match.objects.order_by('-Date').values().first()

    context = {
        "LastMatchDate": LastMatch['Date'],
        "LastMatchID": LastMatch['MatchID']
    }

    return render(request, 'match/homepage.html', context)

def about(request):
    return render(request, 'match/about.html')

def analysis(request):

    """
    nmd = Player.objects.filter(Username="jit#jits").values_list("Kills","Deaths","CombatScore","RoundsPlayed").order_by("Match__Date")

    df = pd.DataFrame(nmd)
    df.columns = ["Kills","Deaths","CombatScore","Rounds"]

    WINDOW = 20
    
    df['CareerKDRatio'] = df['Kills'].cumsum() / (df['Deaths'].cumsum())
    df['CareerACS'] = df['CombatScore'].cumsum() / (df['Rounds'].cumsum())

    df['RollingKDRatio'] = (df['Kills'].rolling(window=WINDOW).sum()) / (df['Deaths'].rolling(window=WINDOW).sum())
    df['RollingAvgCombatScore'] = (df['CombatScore'].rolling(window=WINDOW).sum()) / (df['Rounds'].rolling(window=WINDOW).sum())

    df.reset_index(inplace=True)

    df['GameNumber'] = df.index + 1

    df2 = df.dropna()

    df = df[df.GameNumber >= 20]

    fig = make_subplots(rows=1, cols=2)

    # Add trace for RollingKDRatio to the first column
    fig.add_trace(go.Scatter(x=df['GameNumber'], y=df['CareerACS'], 
                            mode='lines', name='Career ACS'), row=1, col=1)

    # Add trace for RollingAvgCombatScore to the second column
    fig.add_trace(go.Scatter(x=df2['GameNumber'], y=df2['RollingAvgCombatScore'], 
                            mode='lines', name='Rolling ACS'), row=1, col=2)

    # Update layout to include titles
    fig.update_layout(title_text="nmd#219: The Decline?", title_x=0.5, template="simple_white",
                      title_font=dict(size=22))

    # Update xaxis and yaxis properties for the subplots
    fig.update_xaxes(title_text="Game", row=1, col=1, title_font=dict(family="sans-serif",size=14))
    fig.update_yaxes(title_text="Career ACS", row=1, col=1, title_font=dict(family="sans-serif",size=14))
    fig.update_xaxes(title_text="Game", row=1, col=2, title_font=dict(family="sans-serif",size=14))
    fig.update_yaxes(title_text="Rolling ACS", row=1, col=2, title_font=dict(family="sans-serif",size=14))

    fig.add_annotation(text="Career ACS Over Time", 
                   xref="paper", yref="paper", 
                   x=0.16, y=1.1, showarrow=False, font=dict(family="sans-serif",size=14))

    fig.add_annotation(text="20 Game Rolling ACS", 
                   xref="paper", yref="paper", 
                   x=0.835, y=1.1, showarrow=False, font=dict(family="sans-serif",size=14))
    
    fig.update_layout(showlegend=False)

    fig_div = pio.to_html(fig, full_html=False)

    pio.write_image(fig, 'rolling_averages_plot.svg', width=1400)

    context = {
        "fig":fig_div,
    }
    """

    return render(request, 'match/analysis.html')#, context)

def match_detail(request, match_id):
    match = get_object_or_404(Match, MatchID=match_id)
    players = Player.objects.filter(Match=match).annotate(
        kpr=F('Kills')/Cast(F('RoundsPlayed'), FloatField())
    )
    return render(request, 'match/match_detail.html', {'match': match, 'players': players})

def match_list(request):
    matches = Match.objects.all().order_by('-Date')

    colorClasses = ["btn-danger", "btn-success", "btn-outline-dark"]
    unique_maps = sorted(list(Match.objects.values_list("Map", flat=True).distinct()))
    unique_players = sorted(list(Player.objects.filter(Team="Team A").values_list("DisplayName", flat=True).distinct()),
                            key=lambda x: x.lower())

    start_date = None
    end_date = None

    # Apply filters based on user input
    map_filter = request.GET.get('map')
    outcome_filter = request.GET.get('outcome')
    date_filter = request.GET.get('dateRange')

    mvp_filter = request.GET.get('mvp')

    hour = request.GET.get('hour')
    time_class = request.GET.get('time_class')

    n_duelists = request.GET.get('n_duelists')

    if map_filter == "None":
        map_filter = None
    if outcome_filter == "None":
        outcome_filter = None
    if mvp_filter == "None":
        mvp_filter = None
    if date_filter == "None":
        date_filter = None

    button_values = {}
    for player in unique_players:
        value = request.GET.get(str(player), None)
        if value is not None:
            button_values[player] = int(value)

    if date_filter is not None:
        start_date = date_filter.split(' - ')[0]
        end_date = date_filter.split(' - ')[1]

    matches = FilterMatches(matches, map_filter, outcome_filter, date_filter, mvp_filter)
    matches = matches.annotate(hour=ExtractHour('Date'))

    if n_duelists is not None:
        matches = matches.filter(N_Duelists=n_duelists)

    if hour is not None:
        matches = matches.filter(hour=hour)

    if time_class is not None:
        if "Pre-Night" in time_class:
            matches = matches.filter(hour__range=(12,19))
        elif "Early Night" in time_class:
            matches = matches.filter(hour__range=(20, 23))
        elif "Late Night" in time_class:
            matches = matches.filter(hour__range=(0, 4))

    matches = FilterPlayerParticipation(matches, button_values)

    wins = sum([x[0] for x in list(matches.values_list("TeamOneWon"))])
    losses = sum([x[0] for x in list(matches.values_list("TeamOneLost"))])
    draws = sum([x[0] for x in list(matches.values_list("MatchDraw"))])

    if wins+losses+draws == 0:
        win_pct = 0
    else:
        win_pct = (wins+0.5*draws)/(wins+losses+draws)

    context = {
        'matches': matches,

        'unique_maps': unique_maps,
        'unique_players': unique_players,

        'map_filter': map_filter,
        'outcome_filter': outcome_filter,

        'date_filter': date_filter,
        'start_date': start_date,
        'end_date': end_date,

        'mvp_filter': mvp_filter,

        'button_values': button_values,

        'colorClasses': colorClasses,

        'wins': wins,
        'losses': losses,
        'draws': draws,
        'win_pct': win_pct,
    }

    return render(request, 'match/match_list.html', context)

def gamelog(request):
    players = Player.objects.filter(Team="Team A").order_by('-ACS').annotate(KPR=F('Kills')/Cast(F('RoundsPlayed'), FloatField()))

    unique_maps = sorted(list(Match.objects.values_list("Map", flat=True).distinct()))
    unique_agents = sorted(list(Player.objects.values_list("Agent", flat=True).distinct()))
    unique_roles = sorted(list(Player.objects.values_list("Role", flat=True).distinct()))

    start_date = None
    end_date = None

    # Apply filters based on user input
    map_filter = request.GET.get('map')
    outcome_filter = request.GET.get('outcome')

    agent_filter = request.GET.get('agent')
    role_filter = request.GET.get('role')

    date_filter = request.GET.get('dateRange')

    n_duelists = request.GET.get('n_duelists')

    if map_filter == "None":
        map_filter = None
    if outcome_filter == "None":
        outcome_filter = None
    if agent_filter == "None":
        agent_filter = None
    if role_filter == "None":
        role_filter = None
    if date_filter == "None":
        date_filter = None

    if date_filter is not None:
        start_date = date_filter.split(' - ')[0]
        end_date = date_filter.split(' - ')[1]
    
    players = FilterPlayers(players, 
                            map_filter, outcome_filter, agent_filter, role_filter, date_filter, n_duelists=n_duelists)

    rounds_le = request.GET.get('rounds_le')
    rounds = request.GET.get('rounds')
    rounds_ge = request.GET.get('rounds_ge')

    if rounds_le:
        players = players.filter(Match__RoundsPlayed__lte=rounds_le)
    if rounds:
        players = players.filter(Match__RoundsPlayed=rounds)
    if rounds_ge:
        players = players.filter(Match__RoundsPlayed__gte=rounds_ge)
    
    context = {
        'players': players,

        'unique_maps': unique_maps,
        'unique_agents': unique_agents,
        'unique_roles': unique_roles,

        'map_filter': map_filter,
        'outcome_filter': outcome_filter,
        'agent_filter': agent_filter,
        'role_filter': role_filter,
        'date_filter': date_filter,
        'start_date': start_date,
        'end_date': end_date,
    }

    return render(request, 'match/game_log.html', context)

def player_stats(request):
    # Get all players
    players = Player.objects.filter(Team="Team A")

    unique_maps = sorted(list(Match.objects.values_list("Map", flat=True).distinct()))
    unique_agents = sorted(list(Player.objects.values_list("Agent", flat=True).distinct()))
    unique_roles = sorted(list(Player.objects.values_list("Role", flat=True).distinct()))

    start_date = None
    end_date = None

    # Apply filters based on user input
    map_filter = request.GET.get('map')
    outcome_filter = request.GET.get('outcome')

    agent_filter = request.GET.get('agent')
    role_filter = request.GET.get('role')

    mp_filter = request.GET.get('minMP')

    date_filter = request.GET.get('dateRange')

    if map_filter == "None":
        map_filter = None
    if outcome_filter == "None":
        outcome_filter = None
    if agent_filter == "None":
        agent_filter = None
    if role_filter == "None":
        role_filter = None
    if date_filter == "None":
        date_filter = None

    if date_filter is not None:
        start_date = date_filter.split(' - ')[0]
        end_date = date_filter.split(' - ')[1]
    
    players = FilterPlayers(players, 
                            map_filter, outcome_filter, agent_filter, role_filter, date_filter)

    start = request.GET.get('start')
    end = request.GET.get('end')
    if start and end:
        start = parse(unquote(start))
        end = parse(unquote(end))
        players = players.filter(Match__Date__range=(start, end))

    # Aggregate data
    player_stats = players.values('Username').annotate(
        num_matches=Count('Match'),

        matches_won=Sum('MatchWon'),
        matches_lost=Sum('MatchLost'),
        matches_draw=Sum('MatchDraw'),

        total_kills=Sum('Kills'),
        total_deaths=Sum('Deaths'),
        total_assists=Sum('Assists'),

        total_score=Sum('CombatScore'),
        total_damage=Sum('TotalDamage'),

        first_bloods=Sum('FirstBloods'),
        first_deaths=Sum('FirstDeaths'),
        fb_fd_ratio = F('first_bloods')/Cast('first_deaths', FloatField()),

        kast_rounds=Sum('KASTRounds'),

        hs_pct=Sum(F('HS_Pct') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),
        damage_delta=Sum(F('DamageDelta') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),

        zero_kills=Sum('ZeroKillRounds'),
        one_kills=Sum('OneKillRounds'),
        two_kills=Sum('TwoKillRounds'),
        three_kills=Sum('ThreeKillRounds'),
        four_kills=Sum('FourKillRounds'),
        five_kills=Sum('FiveKillRounds'),
        six_kills=Sum('SixKillRounds'),

        attack_kills=Sum('AttackKills'),
        attack_deaths=Sum('AttackDeaths'),
        attack_damage=Sum('AttackDamage'),
        defense_kills=Sum('DefenseKills'),
        defense_deaths=Sum('DefenseDeaths'),
        defense_damage=Sum('DefenseDamage'),
        
        win_kills=Sum('WinKills'),
        win_deaths=Sum('WinDeaths'),
        win_damage=Sum('WinDamage'),
        loss_kills=Sum('LossKills'),
        loss_deaths=Sum('LossDeaths'),
        loss_damage=Sum('LossDamage'),

        attack_rounds=Sum('AttackRounds'),
        attack_wins=Sum('AttackWins'),
        attack_losses=Sum('AttackLosses'),

        defense_rounds=Sum('DefenseRounds'),
        defense_wins=Sum('DefenseWins'),
        defense_losses=Sum('DefenseLosses'),

        rounds_won=Sum('AttackWins')+Sum('DefenseWins'),
        rounds_lost=Sum('AttackLosses')+Sum('DefenseLosses'),

        rounds = Sum('RoundsPlayed'),

        kdr=F('total_kills')/Cast('total_deaths', FloatField()),
        kpr=F('total_kills')/Cast('rounds', FloatField()),
        acs=F('total_score')/Cast('rounds', FloatField()),
        adr=F('total_damage')/Cast('rounds', FloatField()),

        kast=F('kast_rounds')/Cast('rounds', FloatField()),
        k_pct=(F('rounds')-F('zero_kills'))/Cast('rounds', FloatField()),

        win_pct=(F('matches_won')+0.5*F('matches_draw'))/Cast('num_matches', FloatField()),
        round_win_pct=F('rounds_won')/Cast('rounds', FloatField()),
        attack_win_pct=F('attack_wins')/Cast('attack_rounds', FloatField()),
        defense_win_pct=F('defense_wins')/Cast('defense_rounds', FloatField()),

        kills_per_20 = (F('total_kills')/Cast('rounds', FloatField()))*20,
        deaths_per_20 = (F('total_deaths')/Cast('rounds', FloatField()))*20,
        assists_per_20 = (F('total_assists')/Cast('rounds', FloatField()))*20,

        fb_per_20 = (F('first_bloods')/Cast('rounds', FloatField()))*20,
        fd_per_20 = (F('first_deaths')/Cast('rounds', FloatField()))*20,

        attack_kdr = F('attack_kills')/Cast('attack_deaths', FloatField()), 
        attack_adr = F('attack_damage')/Cast('attack_rounds', FloatField()), 
        defense_kdr = F('defense_kills')/Cast('defense_deaths', FloatField()), 
        defense_adr = F('defense_damage')/Cast('defense_rounds', FloatField()),

        attack_kp12 = (F('attack_kills')/Cast('attack_rounds', FloatField()))*12,
        attack_dp12 = (F('attack_deaths')/Cast('attack_rounds', FloatField()))*12,
        defense_kp12 = (F('defense_kills')/Cast('defense_rounds', FloatField()))*12,
        defense_dp12 = (F('defense_deaths')/Cast('defense_rounds', FloatField()))*12,

        max_kills = Max('Kills'),
        max_deaths = Max('Deaths'),
        max_assists = Max('Assists'),
        max_kdr = Max(F('Kills') / Cast('Deaths', FloatField())),
        max_acs = Max(F('CombatScore') / F('RoundsPlayed')),
        max_adr = Max(F('TotalDamage') / Cast('RoundsPlayed', FloatField())),
        max_fb = Max('FirstBloods'),
        max_fd = Max('FirstDeaths')
    )

    max_matches = player_stats.aggregate(Max('num_matches'))['num_matches__max']
    if mp_filter:
        player_stats = player_stats.filter(Q(num_matches__gte=mp_filter)).all()

    player_stats = player_stats.order_by('-num_matches')

    for p in player_stats:
        filtered_players = FilterPlayers(
            Player.objects.filter(Team="Team A", Username=p['Username']), 
            map_filter, outcome_filter, agent_filter, role_filter, date_filter
        )

        tagSplit = p['Username'].split("#")

        p['DisplayName'] = tagSplit[0]
        p['UserTag'] = "#" + tagSplit[1]

        p['WinLossRecord'] = "{}-{}-{}".format(p['matches_won'],p['matches_lost'],p['matches_draw'])
        p['RoundRecord'] = "{}-{}".format(p["rounds_won"],p["rounds_lost"])
        p['AttackRecord'] = "{}-{}".format(p["attack_wins"],p["attack_losses"])
        p['DefenseRecord'] = "{}-{}".format(p["defense_wins"],p["defense_losses"])

        agent_counter = Counter(filtered_players.values_list('Agent', flat=True))
        if agent_counter:
            p['TopAgent'] = agent_counter.most_common(1)[0][0]
        p['TopAgentImage'] = AgentImage(p['TopAgent'])

        p['max_kills_id'] = filtered_players.filter(Kills=p['max_kills']).values('Match__MatchID').first()['Match__MatchID']
        p['max_deaths_id'] = filtered_players.filter(Deaths=p['max_deaths']).values('Match__MatchID').first()['Match__MatchID']
        p['max_assists_id'] = filtered_players.filter(Assists=p['max_assists']).values('Match__MatchID').first()['Match__MatchID']
        p['max_kdr_id'] = filtered_players.annotate(kdr=F('Kills') / Cast('Deaths', FloatField()))\
                                     .filter(kdr=p['max_kdr']).values('Match__MatchID').first()['Match__MatchID']
        p['max_acs_id'] = filtered_players.filter(ACS=p['max_acs']).values('Match__MatchID').first()['Match__MatchID']
        p['max_adr_id'] = filtered_players.annotate(adr=F('TotalDamage') / Cast('RoundsPlayed', FloatField()))\
                                     .filter(adr=p['max_adr']).values('Match__MatchID').first()['Match__MatchID']
        p['max_fb_id'] = filtered_players.filter(FirstBloods=p['max_fb']).values('Match__MatchID').first()['Match__MatchID']
        p['max_fd_id'] = filtered_players.filter(FirstDeaths=p['max_fd']).values('Match__MatchID').first()['Match__MatchID']

    context = {
        'player_stats': player_stats,

        'unique_maps': unique_maps,
        'unique_agents': unique_agents,
        'unique_roles': unique_roles,

        'map_filter': map_filter,
        'outcome_filter': outcome_filter,
        'agent_filter': agent_filter,
        'role_filter': role_filter,
        'mp_filter': mp_filter,
        'date_filter': date_filter,
        'start_date': start_date,
        'end_date': end_date,

        'max_matches': max_matches
    }

    # Render template
    return render(request, 'match/player_stats.html', context)

def player_detail(request, username):
    players = Player.objects.filter(Team="Team A", Username=username).order_by('Match__Date')

    if (players.count() == 0):
        raise Http404
    
    firstRow = players.values().first()

    tagSplit = firstRow['Username'].split("#")
    displayName = tagSplit[0]
    userTag = "#" + tagSplit[1]

    agent_counter = Counter(players.values_list('Agent', flat=True))
    topAgent = agent_counter.most_common(1)[0][0]
    topAgentImage = AgentImage(topAgent)

    last_five = players.order_by('-Match__Date')[:5]
    last_ten = players.order_by('-Match__Date')[:10]
    last_twenty = players.order_by('-Match__Date')[:20]

    last_five_aggregates = CalculateAggregates(last_five)
    last_ten_aggregates = CalculateAggregates(last_ten)
    last_twenty_aggregates = CalculateAggregates(last_twenty)
    all_aggregates = CalculateAggregates(players)

    last_five_aggregates["Label"] = "Last 5 Matches"
    last_ten_aggregates["Label"] = "Last 10 Matches"
    last_twenty_aggregates["Label"] = "Last 20 Matches"
    all_aggregates["Label"] = "All Matches"

    mvps = players.aggregate(
        mvps=Sum('MVP')
    )['mvps']
    
    context = {
        'lst': [last_five_aggregates, last_ten_aggregates, 
                last_twenty_aggregates, all_aggregates],

        'username': username,
        'displayName': displayName,
        'userTag': userTag,
        'topAgent': topAgent,
        'topAgentImage': topAgentImage,

        'mvps': mvps
    }

    return render(request, 'match/player/player_detail.html', context)

def CalculateAggregates(players, field="Username", agent=None):
    username = players.values(field).first()[field]

    max_kdr = players.values(field).annotate(
        max_kdr=ExpressionWrapper(F('Kills') / Cast(F('Deaths'), output_field=FloatField()), output_field=FloatField())
    ).aggregate(max_kdr=Max('max_kdr'))['max_kdr']

    max_acs = players.values(field).annotate(
        max_acs=ExpressionWrapper(F('CombatScore') / F('RoundsPlayed'), output_field=FloatField())
    ).aggregate(max_acs=Max('max_acs'))['max_acs']

    max_adr = players.values(field).annotate(
        max_adr=ExpressionWrapper(F('TotalDamage') / Cast(F('RoundsPlayed'), output_field=FloatField()), output_field=FloatField())
    ).aggregate(max_adr=Max('max_adr'))['max_adr']

    if field == "Role":
                
        dict_players = players.values(field).aggregate(
            num_matches=Count('Match', distinct=True),
            num_performances=Count('Match'),

            perf_per_match=Cast(Count('Match'), FloatField())/len(players),

            matches_won=Sum('MatchWon'),
            matches_lost=Sum('MatchLost'),
            matches_draw=Sum('MatchDraw'),

            total_kills=Sum('Kills'),
            total_deaths=Sum('Deaths'),
            total_assists=Sum('Assists'),

            total_score=Sum('CombatScore'),
            total_damage=Sum('TotalDamage'),

            first_bloods=Sum('FirstBloods'),
            first_deaths=Sum('FirstDeaths'),
            fb_fd_ratio=Sum('FirstBloods')/Cast(Sum('FirstDeaths'), output_field=FloatField()),

            kast_rounds=Sum('KASTRounds'),

            hs_pct=Sum(F('HS_Pct') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),
            damage_delta=Sum(F('DamageDelta') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),

            zero_kills=Sum('ZeroKillRounds'),
            one_kills=Sum('OneKillRounds'),
            two_kills=Sum('TwoKillRounds'),
            three_kills=Sum('ThreeKillRounds'),
            four_kills=Sum('FourKillRounds'),
            five_kills=Sum('FiveKillRounds'),
            six_kills=Sum('SixKillRounds'),

            zero_kills_p20=Sum('ZeroKillRounds')/Cast(Sum('RoundsPlayed'), output_field=FloatField())*20,
            one_kills_p20=Sum('OneKillRounds')/Cast(Sum('RoundsPlayed'), output_field=FloatField())*20,
            two_kills_p20=Sum('TwoKillRounds')/Cast(Sum('RoundsPlayed'), output_field=FloatField())*20,
            three_kills_p20=Sum('ThreeKillRounds')/Cast(Sum('RoundsPlayed'), output_field=FloatField())*20,
            four_kills_p20=Sum('FourKillRounds')/Cast(Sum('RoundsPlayed'), output_field=FloatField())*20,
            five_kills_p20=Sum('FiveKillRounds')/Cast(Sum('RoundsPlayed'), output_field=FloatField())*20,
            six_kills_p20=Sum('SixKillRounds')/Cast(Sum('RoundsPlayed'), output_field=FloatField())*20,

            attack_kills=Sum('AttackKills'),
            attack_deaths=Sum('AttackDeaths'),
            attack_damage=Sum('AttackDamage'),
            defense_kills=Sum('DefenseKills'),
            defense_deaths=Sum('DefenseDeaths'),
            defense_damage=Sum('DefenseDamage'),
            
            win_kills=Sum('WinKills'),
            win_deaths=Sum('WinDeaths'),
            win_damage=Sum('WinDamage'),
            loss_kills=Sum('LossKills'),
            loss_deaths=Sum('LossDeaths'),
            loss_damage=Sum('LossDamage'),
            
            win_kills_avg=Sum('WinKills')/Cast(Sum('AttackWins')+Sum('DefenseWins'), output_field=FloatField()),
            win_deaths_avg=Sum('WinDeaths')/Cast(Sum('AttackWins')+Sum('DefenseWins'), output_field=FloatField()),
            loss_kills_avg=Sum('LossKills')/Cast(Sum('AttackLosses')+Sum('DefenseLosses'), output_field=FloatField()),
            loss_deaths_avg=Sum('LossDeaths')/Cast(Sum('AttackLosses')+Sum('DefenseLosses'), output_field=FloatField()),

            win_kdr = Sum('WinKills')/Cast(Sum('WinDeaths'), output_field=FloatField()),
            loss_kdr = Sum('LossKills')/Cast(Sum('LossDeaths'), output_field=FloatField()),
            win_adr = Sum('WinDamage')/Cast(Sum('AttackWins')+Sum('DefenseWins'), output_field=FloatField()),
            loss_adr = Sum('LossDamage')/Cast(Sum('AttackLosses')+Sum('DefenseLosses'), output_field=FloatField()),

            attack_rounds=Sum('AttackRounds'),
            attack_wins=Sum('AttackWins'),
            attack_losses=Sum('AttackLosses'),

            defense_rounds=Sum('DefenseRounds'),
            defense_wins=Sum('DefenseWins'),
            defense_losses=Sum('DefenseLosses'),

            rounds_won=Sum('AttackWins')+Sum('DefenseWins'),
            rounds_lost=Sum('AttackLosses')+Sum('DefenseLosses'),

            avg_rounds_won=(Sum('AttackWins')+Sum('DefenseWins'))/Cast(Count('Match'), output_field=FloatField()),
            avg_rounds_lost=(Sum('AttackLosses')+Sum('DefenseLosses'))/Cast(Count('Match'), output_field=FloatField()),

            rounds=Sum('RoundsPlayed'),

            kdr=Sum('Kills')/Cast(Sum('Deaths'), output_field=FloatField()),
            kpr=Sum('Kills')/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
            acs=Sum('CombatScore')/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
            adr=Sum('TotalDamage')/Cast(Sum('RoundsPlayed'), output_field=FloatField()),

            kast=Sum('KASTRounds')/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
            k_pct=(Sum('RoundsPlayed')-Sum('ZeroKillRounds'))/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
            d_pct=Sum('Deaths')/Cast(Sum('RoundsPlayed'), output_field=FloatField()),

            win_pct=(Sum('MatchWon')+0.5*Sum('MatchDraw'))/Cast(Count('Match'), FloatField()),
            round_win_pct=(Sum('AttackWins')+Sum('DefenseWins'))/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
            attack_win_pct=Sum('AttackWins')/Cast(Sum('AttackRounds'), output_field=FloatField()),
            defense_win_pct=Sum('DefenseWins')/Cast(Sum('DefenseRounds'), output_field=FloatField()),

            kills_per_20=(Sum('Kills')/Cast(Sum('RoundsPlayed'), output_field=FloatField()))*20,
            deaths_per_20=(Sum('Deaths')/Cast(Sum('RoundsPlayed'), output_field=FloatField()))*20,
            assists_per_20=(Sum('Assists')/Cast(Sum('RoundsPlayed'), output_field=FloatField()))*20,

            fb_pct=(Sum('FirstBloods')/Cast(Sum('RoundsPlayed'), output_field=FloatField())),
            fd_pct=(Sum('FirstDeaths')/Cast(Sum('RoundsPlayed'), output_field=FloatField())),
                    
            fb_per_20=(Sum('FirstBloods')/Cast(Sum('RoundsPlayed'), output_field=FloatField()))*20,
            fd_per_20=(Sum('FirstDeaths')/Cast(Sum('RoundsPlayed'), output_field=FloatField()))*20,

            attack_kdr=Sum('AttackKills')/Cast(Sum('AttackDeaths'), output_field=FloatField()),
            attack_adr=Sum('AttackDamage')/Cast(Sum('AttackRounds'), output_field=FloatField()),
            defense_kdr=Sum('DefenseKills')/Cast(Sum('DefenseDeaths'), output_field=FloatField()),
            defense_adr=Sum('DefenseDamage')/Cast(Sum('DefenseRounds'), output_field=FloatField()),

            attack_kp12=(Sum('AttackKills')/Cast(Sum('AttackRounds'), output_field=FloatField()))*12,
            attack_dp12=(Sum('AttackDeaths')/Cast(Sum('AttackRounds'), output_field=FloatField()))*12,
            defense_kp12=(Sum('DefenseKills')/Cast(Sum('DefenseRounds'), output_field=FloatField()))*12,
            defense_dp12=(Sum('DefenseDeaths')/Cast(Sum('DefenseRounds'), output_field=FloatField()))*12,

            max_kills=Max('Kills'),
            max_deaths=Max('Deaths'),
            max_assists=Max('Assists'),
            max_fb=Max('FirstBloods'),
            max_fd=Max('FirstDeaths')
        )

    else:

        dict_players = players.values(field).aggregate(
            num_matches=Count('Match__MatchID', distinct=True),

            matches_won=Sum('MatchWon'),
            matches_lost=Sum('MatchLost'),
            matches_draw=Sum('MatchDraw'),

            total_kills=Sum('Kills'),
            total_deaths=Sum('Deaths'),
            total_assists=Sum('Assists'),

            total_score=Sum('CombatScore'),
            total_damage=Sum('TotalDamage'),

            first_bloods=Sum('FirstBloods'),
            first_deaths=Sum('FirstDeaths'),
            fb_fd_ratio=Sum('FirstBloods')/Cast(Sum('FirstDeaths'), output_field=FloatField()),

            kast_rounds=Sum('KASTRounds'),

            hs_pct=Sum(F('HS_Pct') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),
            damage_delta=Sum(F('DamageDelta') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),

            zero_kills=Sum('ZeroKillRounds'),
            one_kills=Sum('OneKillRounds'),
            two_kills=Sum('TwoKillRounds'),
            three_kills=Sum('ThreeKillRounds'),
            four_kills=Sum('FourKillRounds'),
            five_kills=Sum('FiveKillRounds'),
            six_kills=Sum('SixKillRounds'),

            zero_kills_p20=Sum('ZeroKillRounds')/Cast(Sum('RoundsPlayed'), output_field=FloatField())*20,
            one_kills_p20=Sum('OneKillRounds')/Cast(Sum('RoundsPlayed'), output_field=FloatField())*20,
            two_kills_p20=Sum('TwoKillRounds')/Cast(Sum('RoundsPlayed'), output_field=FloatField())*20,
            three_kills_p20=Sum('ThreeKillRounds')/Cast(Sum('RoundsPlayed'), output_field=FloatField())*20,
            four_kills_p20=Sum('FourKillRounds')/Cast(Sum('RoundsPlayed'), output_field=FloatField())*20,
            five_kills_p20=Sum('FiveKillRounds')/Cast(Sum('RoundsPlayed'), output_field=FloatField())*20,
            six_kills_p20=Sum('SixKillRounds')/Cast(Sum('RoundsPlayed'), output_field=FloatField())*20,

            attack_kills=Sum('AttackKills'),
            attack_deaths=Sum('AttackDeaths'),
            attack_damage=Sum('AttackDamage'),
            defense_kills=Sum('DefenseKills'),
            defense_deaths=Sum('DefenseDeaths'),
            defense_damage=Sum('DefenseDamage'),
            
            win_kills=Sum('WinKills'),
            win_deaths=Sum('WinDeaths'),
            win_damage=Sum('WinDamage'),
            loss_kills=Sum('LossKills'),
            loss_deaths=Sum('LossDeaths'),
            loss_damage=Sum('LossDamage'),
            
            win_kills_avg=Sum('WinKills')/Cast(Sum('AttackWins')+Sum('DefenseWins'), output_field=FloatField()),
            win_deaths_avg=Sum('WinDeaths')/Cast(Sum('AttackWins')+Sum('DefenseWins'), output_field=FloatField()),
            loss_kills_avg=Sum('LossKills')/Cast(Sum('AttackLosses')+Sum('DefenseLosses'), output_field=FloatField()),
            loss_deaths_avg=Sum('LossDeaths')/Cast(Sum('AttackLosses')+Sum('DefenseLosses'), output_field=FloatField()),

            win_kdr = Sum('WinKills')/Cast(Sum('WinDeaths'), output_field=FloatField()),
            loss_kdr = Sum('LossKills')/Cast(Sum('LossDeaths'), output_field=FloatField()),
            win_adr = Sum('WinDamage')/Cast(Sum('AttackWins')+Sum('DefenseWins'), output_field=FloatField()),
            loss_adr = Sum('LossDamage')/Cast(Sum('AttackLosses')+Sum('DefenseLosses'), output_field=FloatField()),

            attack_rounds=Sum('AttackRounds'),
            attack_wins=Sum('AttackWins'),
            attack_losses=Sum('AttackLosses'),

            defense_rounds=Sum('DefenseRounds'),
            defense_wins=Sum('DefenseWins'),
            defense_losses=Sum('DefenseLosses'),

            rounds_won=Sum('AttackWins')+Sum('DefenseWins'),
            rounds_lost=Sum('AttackLosses')+Sum('DefenseLosses'),

            avg_rounds_won=(Sum('AttackWins')+Sum('DefenseWins'))/Cast(Count('Match'), output_field=FloatField()),
            avg_rounds_lost=(Sum('AttackLosses')+Sum('DefenseLosses'))/Cast(Count('Match'), output_field=FloatField()),

            rounds=Sum('RoundsPlayed'),

            kdr=Sum('Kills')/Cast(Sum('Deaths'), output_field=FloatField()),
            kpr=Sum('Kills')/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
            acs=Sum('CombatScore')/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
            adr=Sum('TotalDamage')/Cast(Sum('RoundsPlayed'), output_field=FloatField()),

            kast=Sum('KASTRounds')/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
            k_pct=(Sum('RoundsPlayed')-Sum('ZeroKillRounds'))/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
            d_pct=Sum('Deaths')/Cast(Sum('RoundsPlayed'), output_field=FloatField()),

            win_pct=(Sum('MatchWon')+0.5*Sum('MatchDraw'))/Cast(Count('Match'), FloatField()),
            round_win_pct=(Sum('AttackWins')+Sum('DefenseWins'))/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
            attack_win_pct=Sum('AttackWins')/Cast(Sum('AttackRounds'), output_field=FloatField()),
            defense_win_pct=Sum('DefenseWins')/Cast(Sum('DefenseRounds'), output_field=FloatField()),

            kills_per_20=(Sum('Kills')/Cast(Sum('RoundsPlayed'), output_field=FloatField()))*20,
            deaths_per_20=(Sum('Deaths')/Cast(Sum('RoundsPlayed'), output_field=FloatField()))*20,
            assists_per_20=(Sum('Assists')/Cast(Sum('RoundsPlayed'), output_field=FloatField()))*20,

            fb_pct=(Sum('FirstBloods')/Cast(Sum('RoundsPlayed'), output_field=FloatField())),
            fd_pct=(Sum('FirstDeaths')/Cast(Sum('RoundsPlayed'), output_field=FloatField())),
                    
            fb_per_20=(Sum('FirstBloods')/Cast(Sum('RoundsPlayed'), output_field=FloatField()))*20,
            fd_per_20=(Sum('FirstDeaths')/Cast(Sum('RoundsPlayed'), output_field=FloatField()))*20,

            attack_kdr=Sum('AttackKills')/Cast(Sum('AttackDeaths'), output_field=FloatField()),
            attack_adr=Sum('AttackDamage')/Cast(Sum('AttackRounds'), output_field=FloatField()),
            defense_kdr=Sum('DefenseKills')/Cast(Sum('DefenseDeaths'), output_field=FloatField()),
            defense_adr=Sum('DefenseDamage')/Cast(Sum('DefenseRounds'), output_field=FloatField()),

            attack_kp12=(Sum('AttackKills')/Cast(Sum('AttackRounds'), output_field=FloatField()))*12,
            attack_dp12=(Sum('AttackDeaths')/Cast(Sum('AttackRounds'), output_field=FloatField()))*12,
            defense_kp12=(Sum('DefenseKills')/Cast(Sum('DefenseRounds'), output_field=FloatField()))*12,
            defense_dp12=(Sum('DefenseDeaths')/Cast(Sum('DefenseRounds'), output_field=FloatField()))*12,

            max_kills=Max('Kills'),
            max_deaths=Max('Deaths'),
            max_assists=Max('Assists'),
            max_fb=Max('FirstBloods'),
            max_fd=Max('FirstDeaths')
        )

    dict_players['max_kdr'] = max_kdr
    dict_players['max_acs'] = max_acs
    dict_players['max_adr'] = max_adr

    matching_match_ids = players.values_list('Match__MatchID', flat=True)
    if field == "Username":
        filtered_players = Player.objects.filter(Match__MatchID__in=matching_match_ids,
                                                 Team="Team A",
                                                 Username=username)
    elif field == "Agent":
        filtered_players = Player.objects.filter(Match__MatchID__in=matching_match_ids,
                                                 Team="Team A",
                                                 Agent=username)
    elif field == "Role":
        filtered_players = Player.objects.filter(Match__MatchID__in=matching_match_ids,
                                                 Team="Team A",
                                                 Role=username)
    else: 
        filtered_players = Player.objects.filter(Match__MatchID__in=matching_match_ids,
                                                 Team="Team A",
                                                 Match__Map=username)
        
    p = dict_players

    p[field] = username

    p['WinLossRecord'] = "{}-{}-{}".format(p['matches_won'],p['matches_lost'],p['matches_draw'])
    p['RoundRecord'] = "{}-{}".format(p["rounds_won"],p["rounds_lost"])
    p['AttackRecord'] = "{}-{}".format(p["attack_wins"],p["attack_losses"])
    p['DefenseRecord'] = "{}-{}".format(p["defense_wins"],p["defense_losses"])

    if agent is None:
        agent_counter = Counter(filtered_players.values_list('Agent', flat=True))
        if agent_counter:
            p['TopAgent'] = agent_counter.most_common(1)[0][0]
            p['AgentString'] =", ".join(f"{key} ({value})" for key, value in agent_counter.most_common())
        p['TopAgentImage'] = AgentImage(p['TopAgent'])

    max_kills = filtered_players.filter(Kills=p['max_kills']).order_by('-ACS','-KillDeathRatio')
    max_deaths = filtered_players.filter(Deaths=p['max_deaths']).order_by('Kills','ACS')
    max_assists = filtered_players.filter(Assists=p['max_assists']).order_by('-Kills','-ACS','-KillDeathRatio')
    max_kdr = filtered_players.annotate(kdr=F('Kills') / Cast('Deaths', FloatField()))\
                                .filter(kdr=p['max_kdr']).order_by('-Kills','-ACS')
    max_acs = filtered_players.filter(ACS=p['max_acs']).order_by('-Kills','-KillDeathRatio')
    max_adr = filtered_players.annotate(adr=F('TotalDamage') / Cast('RoundsPlayed', FloatField()))\
                                .filter(adr=p['max_adr']).order_by('-ACS','-Kills','-KillDeathRatio')
    max_fb = filtered_players.annotate(fb_pct=(Sum('FirstBloods')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                .filter(FirstBloods=p['max_fb']).order_by('-fb_pct','FirstDeaths','-ACS','-Kills','-KillDeathRatio')
    max_fd = filtered_players.annotate(fd_pct=(Sum('FirstDeaths')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                .filter(FirstDeaths=p['max_fd']).order_by('-fd_pct','FirstBloods','ACS','Kills','KillDeathRatio')  

    p['max_kills_id'] = max_kills.values('Match__MatchID').first()['Match__MatchID']
    p['max_kills_player'] = max_kills.values('DisplayName').first()['DisplayName']

    p['max_deaths_id'] = max_deaths.values('Match__MatchID').first()['Match__MatchID']
    p['max_deaths_player'] = max_deaths.values('DisplayName').first()['DisplayName']

    p['max_assists_id'] = max_assists.values('Match__MatchID').first()['Match__MatchID']
    p['max_assists_player'] = max_assists.values('DisplayName').first()['DisplayName']

    p['max_kdr_id'] = max_kdr.values('Match__MatchID').first()['Match__MatchID']
    p['max_kdr_player'] = max_kdr.values('DisplayName').first()['DisplayName']

    p['max_acs_id'] = max_acs.values('Match__MatchID').first()['Match__MatchID']
    p['max_acs_player'] = max_acs.values('DisplayName').first()['DisplayName']

    p['max_adr_id'] = max_adr.values('Match__MatchID').first()['Match__MatchID']
    p['max_adr_player'] = max_adr.values('DisplayName').first()['DisplayName']

    p['max_fb_id'] = max_fb.values('Match__MatchID').first()['Match__MatchID']
    p['max_fb_player'] = max_fb.values('DisplayName').first()['DisplayName']

    p['max_fd_id'] = max_fd.values('Match__MatchID').first()['Match__MatchID']
    p['max_fd_player'] = max_fd.values('DisplayName').first()['DisplayName']

    return p

def player_splits(request, username):
    players = Player.objects.filter(Team="Team A", Username=username).order_by('-Match__Date')

    if (players.count() == 0):
        raise Http404
    
    firstRow = players.values().first()
    tagSplit = firstRow['Username'].split("#")
    displayName = tagSplit[0]
    agent_counter = Counter(players.values_list('Agent', flat=True))
    topAgent = agent_counter.most_common(1)[0][0]
    topAgentImage = AgentImage(topAgent)

    agent_splits = players.values('Agent').annotate(
        num_matches=Count('Match'),

        matches_won=Sum('MatchWon'),
        matches_lost=Sum('MatchLost'),
        matches_draw=Sum('MatchDraw'),

        total_kills=Sum('Kills'),
        total_deaths=Sum('Deaths'),
        total_assists=Sum('Assists'),

        total_score=Sum('CombatScore'),
        total_damage=Sum('TotalDamage'),

        first_bloods=Sum('FirstBloods'),
        first_deaths=Sum('FirstDeaths'),
        fb_fd_ratio=F('first_bloods')/Cast('first_deaths', FloatField()),

        kast_rounds=Sum('KASTRounds'),

        hs_pct=Sum(F('HS_Pct') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),
        damage_delta=Sum(F('DamageDelta') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),

        zero_kills=Sum('ZeroKillRounds'),
        one_kills=Sum('OneKillRounds'),
        two_kills=Sum('TwoKillRounds'),
        three_kills=Sum('ThreeKillRounds'),
        four_kills=Sum('FourKillRounds'),
        five_kills=Sum('FiveKillRounds'),
        six_kills=Sum('SixKillRounds'),

        attack_kills=Sum('AttackKills'),
        attack_deaths=Sum('AttackDeaths'),
        attack_damage=Sum('AttackDamage'),
        defense_kills=Sum('DefenseKills'),
        defense_deaths=Sum('DefenseDeaths'),
        defense_damage=Sum('DefenseDamage'),
        
        win_kills=Sum('WinKills'),
        win_deaths=Sum('WinDeaths'),
        win_damage=Sum('WinDamage'),
        loss_kills=Sum('LossKills'),
        loss_deaths=Sum('LossDeaths'),
        loss_damage=Sum('LossDamage'),

        attack_rounds=Sum('AttackRounds'),
        attack_wins=Sum('AttackWins'),
        attack_losses=Sum('AttackLosses'),

        defense_rounds=Sum('DefenseRounds'),
        defense_wins=Sum('DefenseWins'),
        defense_losses=Sum('DefenseLosses'),

        rounds_won=Sum('AttackWins')+Sum('DefenseWins'),
        rounds_lost=Sum('AttackLosses')+Sum('DefenseLosses'),

        rounds = Sum('RoundsPlayed'),

        kdr=F('total_kills')/Cast('total_deaths', FloatField()),
        kpr=F('total_kills')/Cast('rounds', FloatField()),
        acs=F('total_score')/Cast('rounds', FloatField()),
        adr=F('total_damage')/Cast('rounds', FloatField()),

        kast=F('kast_rounds')/Cast('rounds', FloatField()),
        k_pct=(F('rounds')-F('zero_kills'))/Cast('rounds', FloatField()),

        win_pct=(F('matches_won')+0.5*F('matches_draw'))/Cast('num_matches', FloatField()),
        round_win_pct=F('rounds_won')/Cast('rounds', FloatField()),
        attack_win_pct=F('attack_wins')/Cast('attack_rounds', FloatField()),
        defense_win_pct=F('defense_wins')/Cast('defense_rounds', FloatField()),

        kills_per_20 = (F('total_kills')/Cast('rounds', FloatField()))*20,
        deaths_per_20 = (F('total_deaths')/Cast('rounds', FloatField()))*20,
        assists_per_20 = (F('total_assists')/Cast('rounds', FloatField()))*20,

        fb_per_20 = (F('first_bloods')/Cast('rounds', FloatField()))*20,
        fd_per_20 = (F('first_deaths')/Cast('rounds', FloatField()))*20,

        attack_kdr = F('attack_kills')/Cast('attack_deaths', FloatField()), 
        attack_adr = F('attack_damage')/Cast('attack_rounds', FloatField()), 
        defense_kdr = F('defense_kills')/Cast('defense_deaths', FloatField()), 
        defense_adr = F('defense_damage')/Cast('defense_rounds', FloatField()),

        attack_kp12 = (F('attack_kills')/Cast('attack_rounds', FloatField()))*12,
        attack_dp12 = (F('attack_deaths')/Cast('attack_rounds', FloatField()))*12,
        defense_kp12 = (F('defense_kills')/Cast('defense_rounds', FloatField()))*12,
        defense_dp12 = (F('defense_deaths')/Cast('defense_rounds', FloatField()))*12,

        max_kills = Max('Kills'),
        max_deaths = Max('Deaths'),
        max_assists = Max('Assists'),
        max_kdr = Max(F('Kills') / Cast('Deaths', FloatField())),
        max_acs = Max(F('CombatScore') / F('RoundsPlayed')),
        max_adr = Max(F('TotalDamage') / Cast('RoundsPlayed', FloatField())),
        max_fb = Max('FirstBloods'),
        max_fd = Max('FirstDeaths')
    ).order_by('-num_matches')

    for p in agent_splits:
        filtered_players = players.filter(Agent=p['Agent'])

        p['AgentImage'] = AgentImage(p['Agent'])

        p['WinLossRecord'] = "{}-{}-{}".format(p['matches_won'],p['matches_lost'],p['matches_draw'])
        p['RoundRecord'] = "{}-{}".format(p["rounds_won"],p["rounds_lost"])
        p['AttackRecord'] = "{}-{}".format(p["attack_wins"],p["attack_losses"])
        p['DefenseRecord'] = "{}-{}".format(p["defense_wins"],p["defense_losses"])

        p['max_kills_id'] = filtered_players.filter(Kills=p['max_kills']).values('Match__MatchID').first()['Match__MatchID']
        p['max_deaths_id'] = filtered_players.filter(Deaths=p['max_deaths']).values('Match__MatchID').first()['Match__MatchID']
        p['max_assists_id'] = filtered_players.filter(Assists=p['max_assists']).values('Match__MatchID').first()['Match__MatchID']
        p['max_kdr_id'] = filtered_players.annotate(kdr=F('Kills') / Cast('Deaths', FloatField()))\
                                     .filter(kdr=p['max_kdr']).values('Match__MatchID').first()['Match__MatchID']
        p['max_acs_id'] = filtered_players.filter(ACS=p['max_acs']).values('Match__MatchID').first()['Match__MatchID']
        p['max_adr_id'] = filtered_players.annotate(adr=F('TotalDamage') / Cast('RoundsPlayed', FloatField()))\
                                     .filter(adr=p['max_adr']).values('Match__MatchID').first()['Match__MatchID']
        p['max_fb_id'] = filtered_players.filter(FirstBloods=p['max_fb']).values('Match__MatchID').first()['Match__MatchID']
        p['max_fd_id'] = filtered_players.filter(FirstDeaths=p['max_fd']).values('Match__MatchID').first()['Match__MatchID']

    role_splits = players.values('Role').annotate(
        num_matches=Count('Match'),

        matches_won=Sum('MatchWon'),
        matches_lost=Sum('MatchLost'),
        matches_draw=Sum('MatchDraw'),

        total_kills=Sum('Kills'),
        total_deaths=Sum('Deaths'),
        total_assists=Sum('Assists'),

        total_score=Sum('CombatScore'),
        total_damage=Sum('TotalDamage'),

        first_bloods=Sum('FirstBloods'),
        first_deaths=Sum('FirstDeaths'),
        fb_fd_ratio=F('first_bloods')/Cast('first_deaths', FloatField()),

        kast_rounds=Sum('KASTRounds'),

        hs_pct=Sum(F('HS_Pct') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),
        damage_delta=Sum(F('DamageDelta') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),

        zero_kills=Sum('ZeroKillRounds'),
        one_kills=Sum('OneKillRounds'),
        two_kills=Sum('TwoKillRounds'),
        three_kills=Sum('ThreeKillRounds'),
        four_kills=Sum('FourKillRounds'),
        five_kills=Sum('FiveKillRounds'),
        six_kills=Sum('SixKillRounds'),

        attack_kills=Sum('AttackKills'),
        attack_deaths=Sum('AttackDeaths'),
        attack_damage=Sum('AttackDamage'),
        defense_kills=Sum('DefenseKills'),
        defense_deaths=Sum('DefenseDeaths'),
        defense_damage=Sum('DefenseDamage'),
        
        win_kills=Sum('WinKills'),
        win_deaths=Sum('WinDeaths'),
        win_damage=Sum('WinDamage'),
        loss_kills=Sum('LossKills'),
        loss_deaths=Sum('LossDeaths'),
        loss_damage=Sum('LossDamage'),

        attack_rounds=Sum('AttackRounds'),
        attack_wins=Sum('AttackWins'),
        attack_losses=Sum('AttackLosses'),

        defense_rounds=Sum('DefenseRounds'),
        defense_wins=Sum('DefenseWins'),
        defense_losses=Sum('DefenseLosses'),

        rounds_won=Sum('AttackWins')+Sum('DefenseWins'),
        rounds_lost=Sum('AttackLosses')+Sum('DefenseLosses'),

        rounds = Sum('RoundsPlayed'),

        kdr=F('total_kills')/Cast('total_deaths', FloatField()),
        kpr=F('total_kills')/Cast('rounds', FloatField()),
        acs=F('total_score')/Cast('rounds', FloatField()),
        adr=F('total_damage')/Cast('rounds', FloatField()),

        kast=F('kast_rounds')/Cast('rounds', FloatField()),
        k_pct=(F('rounds')-F('zero_kills'))/Cast('rounds', FloatField()),

        win_pct=(F('matches_won')+0.5*F('matches_draw'))/Cast('num_matches', FloatField()),
        round_win_pct=F('rounds_won')/Cast('rounds', FloatField()),
        attack_win_pct=F('attack_wins')/Cast('attack_rounds', FloatField()),
        defense_win_pct=F('defense_wins')/Cast('defense_rounds', FloatField()),

        kills_per_20 = (F('total_kills')/Cast('rounds', FloatField()))*20,
        deaths_per_20 = (F('total_deaths')/Cast('rounds', FloatField()))*20,
        assists_per_20 = (F('total_assists')/Cast('rounds', FloatField()))*20,

        fb_per_20 = (F('first_bloods')/Cast('rounds', FloatField()))*20,
        fd_per_20 = (F('first_deaths')/Cast('rounds', FloatField()))*20,

        attack_kdr = F('attack_kills')/Cast('attack_deaths', FloatField()), 
        attack_adr = F('attack_damage')/Cast('attack_rounds', FloatField()), 
        defense_kdr = F('defense_kills')/Cast('defense_deaths', FloatField()), 
        defense_adr = F('defense_damage')/Cast('defense_rounds', FloatField()),

        attack_kp12 = (F('attack_kills')/Cast('attack_rounds', FloatField()))*12,
        attack_dp12 = (F('attack_deaths')/Cast('attack_rounds', FloatField()))*12,
        defense_kp12 = (F('defense_kills')/Cast('defense_rounds', FloatField()))*12,
        defense_dp12 = (F('defense_deaths')/Cast('defense_rounds', FloatField()))*12,

        max_kills = Max('Kills'),
        max_deaths = Max('Deaths'),
        max_assists = Max('Assists'),
        max_kdr = Max(F('Kills') / Cast('Deaths', FloatField())),
        max_acs = Max(F('CombatScore') / F('RoundsPlayed')),
        max_adr = Max(F('TotalDamage') / Cast('RoundsPlayed', FloatField())),
        max_fb = Max('FirstBloods'),
        max_fd = Max('FirstDeaths')
    ).order_by('-num_matches')

    for p in role_splits:
        filtered_players = players.filter(Role=p['Role'])

        p['Username'] = username

        p['WinLossRecord'] = "{}-{}-{}".format(p['matches_won'],p['matches_lost'],p['matches_draw'])
        p['RoundRecord'] = "{}-{}".format(p["rounds_won"],p["rounds_lost"])
        p['AttackRecord'] = "{}-{}".format(p["attack_wins"],p["attack_losses"])
        p['DefenseRecord'] = "{}-{}".format(p["defense_wins"],p["defense_losses"])

        agent_counter = Counter(filtered_players.values_list('Agent', flat=True))
        if agent_counter:
            p['TopAgent'] = agent_counter.most_common(1)[0][0]
            p['AgentString'] =", ".join(f"{key} ({value})" for key, value in agent_counter.most_common())
        p['TopAgentImage'] = AgentImage(p['TopAgent'])

        p['max_kills_id'] = filtered_players.filter(Kills=p['max_kills']).values('Match__MatchID').first()['Match__MatchID']
        p['max_deaths_id'] = filtered_players.filter(Deaths=p['max_deaths']).values('Match__MatchID').first()['Match__MatchID']
        p['max_assists_id'] = filtered_players.filter(Assists=p['max_assists']).values('Match__MatchID').first()['Match__MatchID']
        p['max_kdr_id'] = filtered_players.annotate(kdr=F('Kills') / Cast('Deaths', FloatField()))\
                                     .filter(kdr=p['max_kdr']).values('Match__MatchID').first()['Match__MatchID']
        p['max_acs_id'] = filtered_players.filter(ACS=p['max_acs']).values('Match__MatchID').first()['Match__MatchID']
        p['max_adr_id'] = filtered_players.annotate(adr=F('TotalDamage') / Cast('RoundsPlayed', FloatField()))\
                                     .filter(adr=p['max_adr']).values('Match__MatchID').first()['Match__MatchID']
        p['max_fb_id'] = filtered_players.filter(FirstBloods=p['max_fb']).values('Match__MatchID').first()['Match__MatchID']
        p['max_fd_id'] = filtered_players.filter(FirstDeaths=p['max_fd']).values('Match__MatchID').first()['Match__MatchID']

    map_splits = players.values('Match__Map').annotate(
        num_matches=Count('Match'),

        matches_won=Sum('MatchWon'),
        matches_lost=Sum('MatchLost'),
        matches_draw=Sum('MatchDraw'),

        total_kills=Sum('Kills'),
        total_deaths=Sum('Deaths'),
        total_assists=Sum('Assists'),

        total_score=Sum('CombatScore'),
        total_damage=Sum('TotalDamage'),

        first_bloods=Sum('FirstBloods'),
        first_deaths=Sum('FirstDeaths'),
        fb_fd_ratio=F('first_bloods')/Cast('first_deaths', FloatField()),

        kast_rounds=Sum('KASTRounds'),

        hs_pct=Sum(F('HS_Pct') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),
        damage_delta=Sum(F('DamageDelta') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),

        zero_kills=Sum('ZeroKillRounds'),
        one_kills=Sum('OneKillRounds'),
        two_kills=Sum('TwoKillRounds'),
        three_kills=Sum('ThreeKillRounds'),
        four_kills=Sum('FourKillRounds'),
        five_kills=Sum('FiveKillRounds'),
        six_kills=Sum('SixKillRounds'),

        attack_kills=Sum('AttackKills'),
        attack_deaths=Sum('AttackDeaths'),
        attack_damage=Sum('AttackDamage'),
        defense_kills=Sum('DefenseKills'),
        defense_deaths=Sum('DefenseDeaths'),
        defense_damage=Sum('DefenseDamage'),
        
        win_kills=Sum('WinKills'),
        win_deaths=Sum('WinDeaths'),
        win_damage=Sum('WinDamage'),
        loss_kills=Sum('LossKills'),
        loss_deaths=Sum('LossDeaths'),
        loss_damage=Sum('LossDamage'),

        attack_rounds=Sum('AttackRounds'),
        attack_wins=Sum('AttackWins'),
        attack_losses=Sum('AttackLosses'),

        defense_rounds=Sum('DefenseRounds'),
        defense_wins=Sum('DefenseWins'),
        defense_losses=Sum('DefenseLosses'),

        rounds_won=Sum('AttackWins')+Sum('DefenseWins'),
        rounds_lost=Sum('AttackLosses')+Sum('DefenseLosses'),

        rounds = Sum('RoundsPlayed'),

        kdr=F('total_kills')/Cast('total_deaths', FloatField()),
        kpr=F('total_kills')/Cast('rounds', FloatField()),
        acs=F('total_score')/Cast('rounds', FloatField()),
        adr=F('total_damage')/Cast('rounds', FloatField()),

        kast=F('kast_rounds')/Cast('rounds', FloatField()),
        k_pct=(F('rounds')-F('zero_kills'))/Cast('rounds', FloatField()),

        win_pct=(F('matches_won')+0.5*F('matches_draw'))/Cast('num_matches', FloatField()),
        round_win_pct=F('rounds_won')/Cast('rounds', FloatField()),
        attack_win_pct=F('attack_wins')/Cast('attack_rounds', FloatField()),
        defense_win_pct=F('defense_wins')/Cast('defense_rounds', FloatField()),

        kills_per_20 = (F('total_kills')/Cast('rounds', FloatField()))*20,
        deaths_per_20 = (F('total_deaths')/Cast('rounds', FloatField()))*20,
        assists_per_20 = (F('total_assists')/Cast('rounds', FloatField()))*20,

        fb_per_20 = (F('first_bloods')/Cast('rounds', FloatField()))*20,
        fd_per_20 = (F('first_deaths')/Cast('rounds', FloatField()))*20,

        attack_kdr = F('attack_kills')/Cast('attack_deaths', FloatField()), 
        attack_adr = F('attack_damage')/Cast('attack_rounds', FloatField()), 
        defense_kdr = F('defense_kills')/Cast('defense_deaths', FloatField()), 
        defense_adr = F('defense_damage')/Cast('defense_rounds', FloatField()),

        attack_kp12 = (F('attack_kills')/Cast('attack_rounds', FloatField()))*12,
        attack_dp12 = (F('attack_deaths')/Cast('attack_rounds', FloatField()))*12,
        defense_kp12 = (F('defense_kills')/Cast('defense_rounds', FloatField()))*12,
        defense_dp12 = (F('defense_deaths')/Cast('defense_rounds', FloatField()))*12,

        max_kills = Max('Kills'),
        max_deaths = Max('Deaths'),
        max_assists = Max('Assists'),
        max_kdr = Max(F('Kills') / Cast('Deaths', FloatField())),
        max_acs = Max(F('CombatScore') / F('RoundsPlayed')),
        max_adr = Max(F('TotalDamage') / Cast('RoundsPlayed', FloatField())),
        max_fb = Max('FirstBloods'),
        max_fd = Max('FirstDeaths')
    ).order_by('-num_matches')

    for p in map_splits:
        filtered_players = players.filter(Match__Map=p['Match__Map'])

        p['Username'] = username

        p['WinLossRecord'] = "{}-{}-{}".format(p['matches_won'],p['matches_lost'],p['matches_draw'])
        p['RoundRecord'] = "{}-{}".format(p["rounds_won"],p["rounds_lost"])
        p['AttackRecord'] = "{}-{}".format(p["attack_wins"],p["attack_losses"])
        p['DefenseRecord'] = "{}-{}".format(p["defense_wins"],p["defense_losses"])

        agent_counter = Counter(filtered_players.values_list('Agent', flat=True))
        if agent_counter:
            p['TopAgent'] = agent_counter.most_common(1)[0][0]
            p['AgentString'] =", ".join(f"{key} ({value})" for key, value in agent_counter.most_common())
        p['TopAgentImage'] = AgentImage(p['TopAgent'])

        p['max_kills_id'] = filtered_players.filter(Kills=p['max_kills']).values('Match__MatchID').first()['Match__MatchID']
        p['max_deaths_id'] = filtered_players.filter(Deaths=p['max_deaths']).values('Match__MatchID').first()['Match__MatchID']
        p['max_assists_id'] = filtered_players.filter(Assists=p['max_assists']).values('Match__MatchID').first()['Match__MatchID']
        p['max_kdr_id'] = filtered_players.annotate(kdr=F('Kills') / Cast('Deaths', FloatField()))\
                                     .filter(kdr=p['max_kdr']).values('Match__MatchID').first()['Match__MatchID']
        p['max_acs_id'] = filtered_players.filter(ACS=p['max_acs']).values('Match__MatchID').first()['Match__MatchID']
        p['max_adr_id'] = filtered_players.annotate(adr=F('TotalDamage') / Cast('RoundsPlayed', FloatField()))\
                                     .filter(adr=p['max_adr']).values('Match__MatchID').first()['Match__MatchID']
        p['max_fb_id'] = filtered_players.filter(FirstBloods=p['max_fb']).values('Match__MatchID').first()['Match__MatchID']
        p['max_fd_id'] = filtered_players.filter(FirstDeaths=p['max_fd']).values('Match__MatchID').first()['Match__MatchID']

    outcome_splits = players.values('MatchWon','MatchLost','MatchDraw').annotate(
        num_matches=Count('Match'),

        matches_won=Sum('MatchWon'),
        matches_lost=Sum('MatchLost'),
        matches_draw=Sum('MatchDraw'),

        total_kills=Sum('Kills'),
        total_deaths=Sum('Deaths'),
        total_assists=Sum('Assists'),

        total_score=Sum('CombatScore'),
        total_damage=Sum('TotalDamage'),

        first_bloods=Sum('FirstBloods'),
        first_deaths=Sum('FirstDeaths'),
        fb_fd_ratio=F('first_bloods')/Cast('first_deaths', FloatField()),

        kast_rounds=Sum('KASTRounds'),

        hs_pct=Sum(F('HS_Pct') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),
        damage_delta=Sum(F('DamageDelta') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),

        zero_kills=Sum('ZeroKillRounds'),
        one_kills=Sum('OneKillRounds'),
        two_kills=Sum('TwoKillRounds'),
        three_kills=Sum('ThreeKillRounds'),
        four_kills=Sum('FourKillRounds'),
        five_kills=Sum('FiveKillRounds'),
        six_kills=Sum('SixKillRounds'),

        attack_kills=Sum('AttackKills'),
        attack_deaths=Sum('AttackDeaths'),
        attack_damage=Sum('AttackDamage'),
        defense_kills=Sum('DefenseKills'),
        defense_deaths=Sum('DefenseDeaths'),
        defense_damage=Sum('DefenseDamage'),
        
        win_kills=Sum('WinKills'),
        win_deaths=Sum('WinDeaths'),
        win_damage=Sum('WinDamage'),
        loss_kills=Sum('LossKills'),
        loss_deaths=Sum('LossDeaths'),
        loss_damage=Sum('LossDamage'),

        attack_rounds=Sum('AttackRounds'),
        attack_wins=Sum('AttackWins'),
        attack_losses=Sum('AttackLosses'),

        defense_rounds=Sum('DefenseRounds'),
        defense_wins=Sum('DefenseWins'),
        defense_losses=Sum('DefenseLosses'),

        rounds_won=Sum('AttackWins')+Sum('DefenseWins'),
        rounds_lost=Sum('AttackLosses')+Sum('DefenseLosses'),

        rounds = Sum('RoundsPlayed'),

        kdr=F('total_kills')/Cast('total_deaths', FloatField()),
        kpr=F('total_kills')/Cast('rounds', FloatField()),
        acs=F('total_score')/Cast('rounds', FloatField()),
        adr=F('total_damage')/Cast('rounds', FloatField()),

        kast=F('kast_rounds')/Cast('rounds', FloatField()),
        k_pct=(F('rounds')-F('zero_kills'))/Cast('rounds', FloatField()),

        win_pct=(F('matches_won')+0.5*F('matches_draw'))/Cast('num_matches', FloatField()),
        round_win_pct=F('rounds_won')/Cast('rounds', FloatField()),
        attack_win_pct=F('attack_wins')/Cast('attack_rounds', FloatField()),
        defense_win_pct=F('defense_wins')/Cast('defense_rounds', FloatField()),

        kills_per_20 = (F('total_kills')/Cast('rounds', FloatField()))*20,
        deaths_per_20 = (F('total_deaths')/Cast('rounds', FloatField()))*20,
        assists_per_20 = (F('total_assists')/Cast('rounds', FloatField()))*20,

        fb_per_20 = (F('first_bloods')/Cast('rounds', FloatField()))*20,
        fd_per_20 = (F('first_deaths')/Cast('rounds', FloatField()))*20,

        attack_kdr = F('attack_kills')/Cast('attack_deaths', FloatField()), 
        attack_adr = F('attack_damage')/Cast('attack_rounds', FloatField()), 
        defense_kdr = F('defense_kills')/Cast('defense_deaths', FloatField()), 
        defense_adr = F('defense_damage')/Cast('defense_rounds', FloatField()),

        attack_kp12 = (F('attack_kills')/Cast('attack_rounds', FloatField()))*12,
        attack_dp12 = (F('attack_deaths')/Cast('attack_rounds', FloatField()))*12,
        defense_kp12 = (F('defense_kills')/Cast('defense_rounds', FloatField()))*12,
        defense_dp12 = (F('defense_deaths')/Cast('defense_rounds', FloatField()))*12,

        max_kills = Max('Kills'),
        max_deaths = Max('Deaths'),
        max_assists = Max('Assists'),
        max_kdr = Max(F('Kills') / Cast('Deaths', FloatField())),
        max_acs = Max(F('CombatScore') / F('RoundsPlayed')),
        max_adr = Max(F('TotalDamage') / Cast('RoundsPlayed', FloatField())),
        max_fb = Max('FirstBloods'),
        max_fd = Max('FirstDeaths')
    ).order_by('-MatchWon')

    for p in outcome_splits:
        filtered_players = players.filter(MatchWon=p['MatchWon'])

        p['Outcome'] = "Win" if p['MatchWon'] == 1 else "Loss" if p['MatchLost'] == 1 else "Draw"

        p['Username'] = username

        p['WinLossRecord'] = "{}-{}-{}".format(p['matches_won'],p['matches_lost'],p['matches_draw'])
        p['RoundRecord'] = "{}-{}".format(p["rounds_won"],p["rounds_lost"])
        p['AttackRecord'] = "{}-{}".format(p["attack_wins"],p["attack_losses"])
        p['DefenseRecord'] = "{}-{}".format(p["defense_wins"],p["defense_losses"])

        agent_counter = Counter(filtered_players.values_list('Agent', flat=True))
        if agent_counter:
            p['TopAgent'] = agent_counter.most_common(1)[0][0]
            p['AgentString'] =", ".join(f"{key} ({value})" for key, value in agent_counter.most_common())
        p['TopAgentImage'] = AgentImage(p['TopAgent'])

        p['max_kills_id'] = filtered_players.filter(Kills=p['max_kills']).values('Match__MatchID').first()['Match__MatchID']
        p['max_deaths_id'] = filtered_players.filter(Deaths=p['max_deaths']).values('Match__MatchID').first()['Match__MatchID']
        p['max_assists_id'] = filtered_players.filter(Assists=p['max_assists']).values('Match__MatchID').first()['Match__MatchID']
        p['max_kdr_id'] = filtered_players.annotate(kdr=F('Kills') / Cast('Deaths', FloatField()))\
                                     .filter(kdr=p['max_kdr']).values('Match__MatchID').first()['Match__MatchID']
        p['max_acs_id'] = filtered_players.filter(ACS=p['max_acs']).values('Match__MatchID').first()['Match__MatchID']
        p['max_adr_id'] = filtered_players.annotate(adr=F('TotalDamage') / Cast('RoundsPlayed', FloatField()))\
                                     .filter(adr=p['max_adr']).values('Match__MatchID').first()['Match__MatchID']
        p['max_fb_id'] = filtered_players.filter(FirstBloods=p['max_fb']).values('Match__MatchID').first()['Match__MatchID']
        p['max_fd_id'] = filtered_players.filter(FirstDeaths=p['max_fd']).values('Match__MatchID').first()['Match__MatchID']

    mvps = players.aggregate(
        mvps=Sum('MVP')
    )['mvps']

    context = {
        'role_splits': role_splits,
        'agent_splits': agent_splits,
        'map_splits': map_splits,
        'outcome_splits': outcome_splits,

        'username': username,
        'displayName': displayName,
        'topAgent': topAgent,
        'topAgentImage': topAgentImage,

        'mvps': mvps,
    }

    return render(request, 'match/player/player_splits.html', context)

from dateutil.parser import parse
def player_gamelog(request, username):

    players = Player.objects.filter(Team="Team A", Username=username)

    if (players.count() == 0):
        raise Http404
    
    mvps = players.aggregate(
        mvps=Sum('MVP')
    )['mvps']

    firstRow = players.values().first()

    tagSplit = firstRow['Username'].split("#")
    displayName = tagSplit[0]
    userTag = "#" + tagSplit[1]

    agent_counter = Counter(players.values_list('Agent', flat=True))
    topAgent = agent_counter.most_common(1)[0][0]
    topAgentImage = AgentImage(topAgent)

    players = players.order_by('-Match__Date').annotate(KPR=F('Kills')/Cast(F('RoundsPlayed'), FloatField()))

    unique_maps = sorted(list(Match.objects.values_list("Map", flat=True).distinct()))
    unique_agents = sorted(list(Player.objects.values_list("Agent", flat=True).distinct()))
    unique_roles = sorted(list(Player.objects.values_list("Role", flat=True).distinct()))

    start_date = None
    end_date = None

    # Apply filters based on user input
    map_filter = request.GET.get('map')
    outcome_filter = request.GET.get('outcome')

    agent_filter = request.GET.get('agent')
    role_filter = request.GET.get('role')

    date_filter = request.GET.get('dateRange')

    mvp_filter = request.GET.get('mvp')

    time_class = request.GET.get('time_class')

    n_duelists = request.GET.get('n_duelists')

    if map_filter == "None":
        map_filter = None
    if outcome_filter == "None":
        outcome_filter = None
    if agent_filter == "None":
        agent_filter = None
    if role_filter == "None":
        role_filter = None
    if date_filter == "None":
        date_filter = None

    if date_filter is not None:
        start_date = date_filter.split(' - ')[0]
        end_date = date_filter.split(' - ')[1]

    players = FilterPlayers(players, 
                            map_filter, outcome_filter, agent_filter, role_filter, date_filter, mvp_filter, n_duelists=n_duelists)
    
    rounds_le = request.GET.get('rounds_le')
    rounds = request.GET.get('rounds')
    rounds_ge = request.GET.get('rounds_ge')

    if rounds_le:
        players = players.filter(Match__RoundsPlayed__lte=rounds_le)
    if rounds:
        players = players.filter(Match__RoundsPlayed=rounds)
    if rounds_ge:
        players = players.filter(Match__RoundsPlayed__gte=rounds_ge)
    
    if time_class is not None:
        players = players.annotate(hour=ExtractHour('Match__Date'))
        if "Pre-Night" in time_class:
            players = players.filter(hour__range=(12,19))
        elif "Early Night" in time_class:
            players = players.filter(hour__range=(20, 23))
        elif "Late Night" in time_class:
            players = players.filter(hour__range=(0, 4))

    start = request.GET.get('start')
    end = request.GET.get('end')
    if start and end:
        start = parse(unquote(start))
        end = parse(unquote(end))
        players = players.filter(Match__Date__range=(start, end))

    context = {
        'players': players,

        'username': username,
        'displayName': displayName,
        'userTag': userTag,
        'topAgent': topAgent,
        'topAgentImage': topAgentImage,

        'unique_maps': unique_maps,
        'unique_agents': unique_agents,
        'unique_roles': unique_roles,

        'map_filter': map_filter,
        'outcome_filter': outcome_filter,
        'agent_filter': agent_filter,
        'role_filter': role_filter,
        'date_filter': date_filter,
        'start_date': start_date,
        'end_date': end_date,

        'mvps': mvps,
    }

    return render(request, 'match/player/player_gamelog.html', context)

def maps_overview(request):

    players = Player.objects.filter(Team="Team A")

    date_filter = request.GET.get('dateRange')

    start_date = None
    end_date = None

    if date_filter is not None:
        date_split = date_filter.split(' - ')
        start_date = date_filter.split(' - ')[0]
        end_date = date_filter.split(' - ')[1]
        start = datetime.strptime(date_split[0], '%m/%d/%Y')
        end = datetime.strptime(date_split[1], '%m/%d/%Y')

        players = players.filter(Match__Date__range=(start, end))

    maps = players.values('Match__Map').annotate(
        num_matches=Count('Match')/5,

        matches_won=Sum('MatchWon')/5,
        matches_lost=Sum('MatchLost')/5,
        matches_draw=Sum('MatchDraw')/5,

        total_kills=Sum('Kills'),
        total_deaths=Sum('Deaths'),
        total_assists=Sum('Assists'),

        total_score=Sum('CombatScore'),
        total_damage=Sum('TotalDamage'),

        first_bloods=Sum('FirstBloods'),
        first_deaths=Sum('FirstDeaths'),
        fb_fd_ratio=Sum('FirstBloods')/Cast(Sum('FirstDeaths'), output_field=FloatField()),

        kast_rounds=Sum('KASTRounds'),

        attack_kills=Sum('AttackKills'),
        attack_deaths=Sum('AttackDeaths'),
        attack_damage=Sum('AttackDamage'),
        defense_kills=Sum('DefenseKills'),
        defense_deaths=Sum('DefenseDeaths'),
        defense_damage=Sum('DefenseDamage'),
        
        win_kills=Sum('WinKills'),
        win_deaths=Sum('WinDeaths'),
        win_damage=Sum('WinDamage'),
        loss_kills=Sum('LossKills'),
        loss_deaths=Sum('LossDeaths'),
        loss_damage=Sum('LossDamage'),

        kast=Sum('KASTRounds')/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
        k_pct=(Sum('RoundsPlayed')-Sum('ZeroKillRounds'))/Cast(Sum('RoundsPlayed'), output_field=FloatField()),

        win_pct=(Sum('MatchWon')+0.5*Sum('MatchDraw'))/Cast(Count('Match'), FloatField()),
        round_win_pct=(Sum('AttackWins')+Sum('DefenseWins'))/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
        attack_win_pct=Sum('AttackWins')/Cast(Sum('AttackRounds'), output_field=FloatField()),
        defense_win_pct=Sum('DefenseWins')/Cast(Sum('DefenseRounds'), output_field=FloatField()),

        kdr=Sum('Kills')/Cast(Sum('Deaths'), output_field=FloatField()),
        kpr=Sum('Kills')/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
        acs=Sum('CombatScore')/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
        adr=Sum('TotalDamage')/Cast(Sum('RoundsPlayed'), output_field=FloatField()),

        attack_rounds=Sum('AttackRounds')/5,
        attack_wins=Sum('AttackWins')/5,
        attack_losses=Sum('AttackLosses')/5,

        defense_rounds=Sum('DefenseRounds')/5,
        defense_wins=Sum('DefenseWins')/5,
        defense_losses=Sum('DefenseLosses')/5,

        rounds_won=(Sum('AttackWins')+Sum('DefenseWins'))/5,
        rounds_lost=(Sum('AttackLosses')+Sum('DefenseLosses'))/5,
        rounds_played=Sum('RoundsPlayed')/5,

        fb_pct=(Sum('FirstBloods')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())),
        fd_pct=(Sum('FirstDeaths')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())),

        attack_kdr=Sum('AttackKills')/Cast(Sum('AttackDeaths'), output_field=FloatField()),
        attack_adr=Sum('AttackDamage')/Cast(Sum('AttackRounds'), output_field=FloatField()),
        defense_kdr=Sum('DefenseKills')/Cast(Sum('DefenseDeaths'), output_field=FloatField()),
        defense_adr=Sum('DefenseDamage')/Cast(Sum('DefenseRounds'), output_field=FloatField()),

        max_kills = Max('Kills'),
        max_deaths = Max('Deaths'),
        max_assists = Max('Assists'),
        max_kdr = Max(F('Kills') / Cast('Deaths', FloatField())),
        max_acs = Max(F('CombatScore') / F('RoundsPlayed')),
        max_adr = Max(F('TotalDamage') / Cast('RoundsPlayed', FloatField())),
        max_fb = Max('FirstBloods'),
        max_fd = Max('FirstDeaths')
    )

    maps = maps.order_by('-num_matches')

    for m in maps:
        filtered_players = players.filter(Team="Team A", Match__Map=m['Match__Map'])

        m['WinLossRecord'] = "{}-{}-{}".format(m['matches_won'],m['matches_lost'],m['matches_draw'])
        m['RoundRecord'] = "{}-{}".format(m["rounds_won"],m["rounds_lost"])
        m['AttackRecord'] = "{}-{}".format(m["attack_wins"],m["attack_losses"])
        m['DefenseRecord'] = "{}-{}".format(m["defense_wins"],m["defense_losses"])

        max_kills = filtered_players.filter(Kills=m['max_kills']).order_by('-ACS','-KillDeathRatio')
        max_deaths = filtered_players.filter(Deaths=m['max_deaths']).order_by('Kills','ACS')
        max_assists = filtered_players.filter(Assists=m['max_assists']).order_by('-Kills','-ACS','-KillDeathRatio')
        max_kdr = filtered_players.annotate(kdr=F('Kills') / Cast('Deaths', FloatField()))\
                                  .filter(kdr=m['max_kdr']).order_by('-Kills','-ACS')
        max_acs = filtered_players.filter(ACS=m['max_acs']).order_by('-Kills','-KillDeathRatio')
        max_adr = filtered_players.annotate(adr=F('TotalDamage') / Cast('RoundsPlayed', FloatField()))\
                                  .filter(adr=m['max_adr']).order_by('-ACS','-Kills','-KillDeathRatio')
        max_fb = filtered_players.annotate(fb_pct=(Sum('FirstBloods')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                 .filter(FirstBloods=m['max_fb']).order_by('-fb_pct','FirstDeaths','-ACS','-Kills','-KillDeathRatio')
        max_fd = filtered_players.annotate(fd_pct=(Sum('FirstDeaths')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                 .filter(FirstDeaths=m['max_fd']).order_by('-fd_pct','FirstBloods','ACS','Kills','KillDeathRatio')

        m['max_kills_id'] = max_kills.values('Match__MatchID').first()['Match__MatchID']
        m['max_kills_player'] = max_kills.values('DisplayName').first()['DisplayName']

        m['max_deaths_id'] = max_deaths.values('Match__MatchID').first()['Match__MatchID']
        m['max_deaths_player'] = max_deaths.values('DisplayName').first()['DisplayName']

        m['max_assists_id'] = max_assists.values('Match__MatchID').first()['Match__MatchID']
        m['max_assists_player'] = max_assists.values('DisplayName').first()['DisplayName']

        m['max_kdr_id'] = max_kdr.values('Match__MatchID').first()['Match__MatchID']
        m['max_kdr_player'] = max_kdr.values('DisplayName').first()['DisplayName']

        m['max_acs_id'] = max_acs.values('Match__MatchID').first()['Match__MatchID']
        m['max_acs_player'] = max_acs.values('DisplayName').first()['DisplayName']

        m['max_adr_id'] = max_adr.values('Match__MatchID').first()['Match__MatchID']
        m['max_adr_player'] = max_adr.values('DisplayName').first()['DisplayName']

        m['max_fb_id'] = max_fb.values('Match__MatchID').first()['Match__MatchID']
        m['max_fb_player'] = max_fb.values('DisplayName').first()['DisplayName']

        m['max_fd_id'] = max_fd.values('Match__MatchID').first()['Match__MatchID']
        m['max_fd_player'] = max_fd.values('DisplayName').first()['DisplayName']

    context = {
        'maps': maps,

        'date_filter': date_filter,
        'start_date': start_date,
        'end_date': end_date,
    }

    # Render template
    return render(request, 'match/maps.html', context)

def agents_overview(request):
    # Get all players
    players = Player.objects.filter(Team="Team A")

    unique_maps = sorted(list(Match.objects.values_list("Map", flat=True).distinct()))
    unique_roles = sorted(list(Player.objects.values_list("Role", flat=True).distinct()))

    start_date = None
    end_date = None

    # Apply filters based on user input
    map_filter = request.GET.get('map')
    outcome_filter = request.GET.get('outcome')

    role_filter = request.GET.get('role')

    mp_filter = request.GET.get('minMP')

    date_filter = request.GET.get('dateRange')

    if date_filter is not None:
        start_date = date_filter.split(' - ')[0]
        end_date = date_filter.split(' - ')[1]
    
    players = FilterPlayers(players, 
                            map_filter, outcome_filter, None, role_filter, date_filter)

    agents = players.values('Agent').annotate(
        num_matches=Count('Match'),

        matches_won=Sum('MatchWon'),
        matches_lost=Sum('MatchLost'),
        matches_draw=Sum('MatchDraw'),

        total_kills=Sum('Kills'),
        total_deaths=Sum('Deaths'),
        total_assists=Sum('Assists'),

        total_score=Sum('CombatScore'),
        total_damage=Sum('TotalDamage'),

        first_bloods=Sum('FirstBloods'),
        first_deaths=Sum('FirstDeaths'),
        fb_fd_ratio=F('first_bloods')/Cast('first_deaths', FloatField()),

        kast_rounds=Sum('KASTRounds'),

        hs_pct=Sum(F('HS_Pct') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),
        damage_delta=Sum(F('DamageDelta') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),

        zero_kills=Sum('ZeroKillRounds'),
        one_kills=Sum('OneKillRounds'),
        two_kills=Sum('TwoKillRounds'),
        three_kills=Sum('ThreeKillRounds'),
        four_kills=Sum('FourKillRounds'),
        five_kills=Sum('FiveKillRounds'),
        six_kills=Sum('SixKillRounds'),

        attack_kills=Sum('AttackKills'),
        attack_deaths=Sum('AttackDeaths'),
        attack_damage=Sum('AttackDamage'),
        defense_kills=Sum('DefenseKills'),
        defense_deaths=Sum('DefenseDeaths'),
        defense_damage=Sum('DefenseDamage'),
        
        win_kills=Sum('WinKills'),
        win_deaths=Sum('WinDeaths'),
        win_damage=Sum('WinDamage'),
        loss_kills=Sum('LossKills'),
        loss_deaths=Sum('LossDeaths'),
        loss_damage=Sum('LossDamage'),

        attack_rounds=Sum('AttackRounds'),
        attack_wins=Sum('AttackWins'),
        attack_losses=Sum('AttackLosses'),

        defense_rounds=Sum('DefenseRounds'),
        defense_wins=Sum('DefenseWins'),
        defense_losses=Sum('DefenseLosses'),

        rounds_won=Sum('AttackWins')+Sum('DefenseWins'),
        rounds_lost=Sum('AttackLosses')+Sum('DefenseLosses'),

        rounds = Sum('RoundsPlayed'),

        kdr=F('total_kills')/Cast('total_deaths', FloatField()),
        kpr=F('total_kills')/Cast('rounds', FloatField()),
        acs=F('total_score')/Cast('rounds', FloatField()),
        adr=F('total_damage')/Cast('rounds', FloatField()),

        kast=F('kast_rounds')/Cast('rounds', FloatField()),
        k_pct=(F('rounds')-F('zero_kills'))/Cast('rounds', FloatField()),

        win_pct=(F('matches_won')+0.5*F('matches_draw'))/Cast('num_matches', FloatField()),
        round_win_pct=F('rounds_won')/Cast('rounds', FloatField()),
        attack_win_pct=F('attack_wins')/Cast('attack_rounds', FloatField()),
        defense_win_pct=F('defense_wins')/Cast('defense_rounds', FloatField()),

        kills_per_20 = (F('total_kills')/Cast('rounds', FloatField()))*20,
        deaths_per_20 = (F('total_deaths')/Cast('rounds', FloatField()))*20,
        assists_per_20 = (F('total_assists')/Cast('rounds', FloatField()))*20,

        fb_per_20 = (F('first_bloods')/Cast('rounds', FloatField()))*20,
        fd_per_20 = (F('first_deaths')/Cast('rounds', FloatField()))*20,

        attack_kdr = F('attack_kills')/Cast('attack_deaths', FloatField()), 
        attack_adr = F('attack_damage')/Cast('attack_rounds', FloatField()), 
        defense_kdr = F('defense_kills')/Cast('defense_deaths', FloatField()), 
        defense_adr = F('defense_damage')/Cast('defense_rounds', FloatField()),

        attack_kp12 = (F('attack_kills')/Cast('attack_rounds', FloatField()))*12,
        attack_dp12 = (F('attack_deaths')/Cast('attack_rounds', FloatField()))*12,
        defense_kp12 = (F('defense_kills')/Cast('defense_rounds', FloatField()))*12,
        defense_dp12 = (F('defense_deaths')/Cast('defense_rounds', FloatField()))*12,

        max_kills = Max('Kills'),
        max_deaths = Max('Deaths'),
        max_assists = Max('Assists'),
        max_kdr = Max(F('Kills') / Cast('Deaths', FloatField())),
        max_acs = Max(F('CombatScore') / F('RoundsPlayed')),
        max_adr = Max(F('TotalDamage') / Cast('RoundsPlayed', FloatField())),
        max_fb = Max('FirstBloods'),
        max_fd = Max('FirstDeaths')
    ).order_by('-num_matches')

    max_matches = agents.aggregate(Max('num_matches'))['num_matches__max']
    if mp_filter:
        agents = agents.filter(Q(num_matches__gte=mp_filter)).all()

    for m in agents:
        filtered_players = players.filter(Agent=m['Agent'])

        m['WinLossRecord'] = "{}-{}-{}".format(m['matches_won'],m['matches_lost'],m['matches_draw'])
        m['RoundRecord'] = "{}-{}".format(m["rounds_won"],m["rounds_lost"])
        m['AttackRecord'] = "{}-{}".format(m["attack_wins"],m["attack_losses"])
        m['DefenseRecord'] = "{}-{}".format(m["defense_wins"],m["defense_losses"])

        m['AgentImage'] = AgentImage(m['Agent'])

        max_kills = filtered_players.filter(Kills=m['max_kills']).order_by('-ACS','-KillDeathRatio')
        max_deaths = filtered_players.filter(Deaths=m['max_deaths']).order_by('Kills','ACS')
        max_assists = filtered_players.filter(Assists=m['max_assists']).order_by('-Kills','-ACS','-KillDeathRatio')
        max_kdr = filtered_players.annotate(kdr=F('Kills') / Cast('Deaths', FloatField()))\
                                  .filter(kdr=m['max_kdr']).order_by('-Kills','-ACS')
        max_acs = filtered_players.filter(ACS=m['max_acs']).order_by('-Kills','-KillDeathRatio')
        max_adr = filtered_players.annotate(adr=F('TotalDamage') / Cast('RoundsPlayed', FloatField()))\
                                  .filter(adr=m['max_adr']).order_by('-ACS','-Kills','-KillDeathRatio')
        max_fb = filtered_players.annotate(fb_pct=(Sum('FirstBloods')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                 .filter(FirstBloods=m['max_fb']).order_by('-fb_pct','FirstDeaths','-ACS','-Kills','-KillDeathRatio')
        max_fd = filtered_players.annotate(fd_pct=(Sum('FirstDeaths')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                 .filter(FirstDeaths=m['max_fd']).order_by('-fd_pct','FirstBloods','ACS','Kills','KillDeathRatio')

        m['max_kills_id'] = max_kills.values('Match__MatchID').first()['Match__MatchID']
        m['max_kills_player'] = max_kills.values('DisplayName').first()['DisplayName']

        m['max_deaths_id'] = max_deaths.values('Match__MatchID').first()['Match__MatchID']
        m['max_deaths_player'] = max_deaths.values('DisplayName').first()['DisplayName']

        m['max_assists_id'] = max_assists.values('Match__MatchID').first()['Match__MatchID']
        m['max_assists_player'] = max_assists.values('DisplayName').first()['DisplayName']

        m['max_kdr_id'] = max_kdr.values('Match__MatchID').first()['Match__MatchID']
        m['max_kdr_player'] = max_kdr.values('DisplayName').first()['DisplayName']

        m['max_acs_id'] = max_acs.values('Match__MatchID').first()['Match__MatchID']
        m['max_acs_player'] = max_acs.values('DisplayName').first()['DisplayName']

        m['max_adr_id'] = max_adr.values('Match__MatchID').first()['Match__MatchID']
        m['max_adr_player'] = max_adr.values('DisplayName').first()['DisplayName']

        m['max_fb_id'] = max_fb.values('Match__MatchID').first()['Match__MatchID']
        m['max_fb_player'] = max_fb.values('DisplayName').first()['DisplayName']

        m['max_fd_id'] = max_fd.values('Match__MatchID').first()['Match__MatchID']
        m['max_fd_player'] = max_fd.values('DisplayName').first()['DisplayName']

    context = {
        'agents': agents,

        'unique_maps': unique_maps,
        'unique_roles': unique_roles,

        'map_filter': map_filter,
        'outcome_filter': outcome_filter,
        'role_filter': role_filter,
        'mp_filter': mp_filter,
        'date_filter': date_filter,
        'start_date': start_date,
        'end_date': end_date,

        'max_matches': max_matches
    }

    # Render template
    return render(request, 'match/agents.html', context)

def agent_detail(request, agent):
    if agent == "KAYO":
        agent = "KAY/O"

    players = Player.objects.filter(Team="Team A", Agent=agent).order_by('Match__Date')

    if (players.count() == 0):
        raise Http404
    
    last_five = players.order_by('-Match__Date')[:5]
    last_ten = players.order_by('-Match__Date')[:10]
    last_twenty = players.order_by('-Match__Date')[:20]

    last_five_aggregates = CalculateAggregates(last_five,"Agent",agent)
    last_ten_aggregates = CalculateAggregates(last_ten,"Agent",agent)
    last_twenty_aggregates = CalculateAggregates(last_twenty,"Agent",agent)
    all_aggregates = CalculateAggregates(players,"Agent",agent)

    last_five_aggregates["Label"] = "Last 5 Matches"
    last_ten_aggregates["Label"] = "Last 10 Matches"
    last_twenty_aggregates["Label"] = "Last 20 Matches"
    all_aggregates["Label"] = "All Matches"
    
    context = {
        'lst': [last_five_aggregates, last_ten_aggregates, 
                last_twenty_aggregates, all_aggregates],

        'agent': agent,

        'agentImage': AgentImage(agent)
    }

    return render(request, 'match/agent/agent_detail.html', context)

def roles_overview(request):
    # Get all players
    players = Player.objects.filter(Team="Team A")

    unique_maps = sorted(list(Match.objects.values_list("Map", flat=True).distinct()))
    unique_roles = sorted(list(Player.objects.values_list("Role", flat=True).distinct()))

    start_date = None
    end_date = None

    # Apply filters based on user input
    map_filter = request.GET.get('map')
    outcome_filter = request.GET.get('outcome')
    date_filter = request.GET.get('dateRange')
    if date_filter is not None:
        start_date = date_filter.split(' - ')[0]
        end_date = date_filter.split(' - ')[1]
    
    players = FilterPlayers(players, 
                            map_filter, outcome_filter, None, None, date_filter)
    
    n_matches = len(players)/5

    roles = players.values('Role').annotate(
        num_matches=Count('Match', distinct=True),
        num_performances=Count('Match'),

        perf_per_match=Cast(Count('Match'), FloatField())/n_matches,

        matches_won=Sum('MatchWon'),
        matches_lost=Sum('MatchLost'),
        matches_draw=Sum('MatchDraw'),

        total_kills=Sum('Kills'),
        total_deaths=Sum('Deaths'),
        total_assists=Sum('Assists'),

        total_score=Sum('CombatScore'),
        total_damage=Sum('TotalDamage'),

        first_bloods=Sum('FirstBloods'),
        first_deaths=Sum('FirstDeaths'),
        fb_fd_ratio=F('first_bloods')/Cast('first_deaths', FloatField()),

        kast_rounds=Sum('KASTRounds'),

        hs_pct=Sum(F('HS_Pct') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),
        damage_delta=Sum(F('DamageDelta') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),

        zero_kills=Sum('ZeroKillRounds'),
        one_kills=Sum('OneKillRounds'),
        two_kills=Sum('TwoKillRounds'),
        three_kills=Sum('ThreeKillRounds'),
        four_kills=Sum('FourKillRounds'),
        five_kills=Sum('FiveKillRounds'),
        six_kills=Sum('SixKillRounds'),

        attack_kills=Sum('AttackKills'),
        attack_deaths=Sum('AttackDeaths'),
        attack_damage=Sum('AttackDamage'),
        defense_kills=Sum('DefenseKills'),
        defense_deaths=Sum('DefenseDeaths'),
        defense_damage=Sum('DefenseDamage'),
        
        win_kills=Sum('WinKills'),
        win_deaths=Sum('WinDeaths'),
        win_damage=Sum('WinDamage'),
        loss_kills=Sum('LossKills'),
        loss_deaths=Sum('LossDeaths'),
        loss_damage=Sum('LossDamage'),

        attack_rounds=Sum('AttackRounds'),
        attack_wins=Sum('AttackWins'),
        attack_losses=Sum('AttackLosses'),

        defense_rounds=Sum('DefenseRounds'),
        defense_wins=Sum('DefenseWins'),
        defense_losses=Sum('DefenseLosses'),

        rounds_won=Sum('AttackWins')+Sum('DefenseWins'),
        rounds_lost=Sum('AttackLosses')+Sum('DefenseLosses'),

        rounds = Sum('RoundsPlayed'),

        kdr=F('total_kills')/Cast('total_deaths', FloatField()),
        kpr=F('total_kills')/Cast('rounds', FloatField()),
        acs=F('total_score')/Cast('rounds', FloatField()),
        adr=F('total_damage')/Cast('rounds', FloatField()),

        kast=F('kast_rounds')/Cast('rounds', FloatField()),
        k_pct=(F('rounds')-F('zero_kills'))/Cast('rounds', FloatField()),

        win_pct=(F('matches_won')+0.5*F('matches_draw'))/Cast('num_performances', FloatField()),
        round_win_pct=F('rounds_won')/Cast('rounds', FloatField()),
        attack_win_pct=F('attack_wins')/Cast('attack_rounds', FloatField()),
        defense_win_pct=F('defense_wins')/Cast('defense_rounds', FloatField()),

        kills_per_20 = (F('total_kills')/Cast('rounds', FloatField()))*20,
        deaths_per_20 = (F('total_deaths')/Cast('rounds', FloatField()))*20,
        assists_per_20 = (F('total_assists')/Cast('rounds', FloatField()))*20,

        fb_per_20 = (F('first_bloods')/Cast('rounds', FloatField()))*20,
        fd_per_20 = (F('first_deaths')/Cast('rounds', FloatField()))*20,

        attack_kdr = F('attack_kills')/Cast('attack_deaths', FloatField()), 
        attack_adr = F('attack_damage')/Cast('attack_rounds', FloatField()), 
        defense_kdr = F('defense_kills')/Cast('defense_deaths', FloatField()), 
        defense_adr = F('defense_damage')/Cast('defense_rounds', FloatField()),

        attack_kp12 = (F('attack_kills')/Cast('attack_rounds', FloatField()))*12,
        attack_dp12 = (F('attack_deaths')/Cast('attack_rounds', FloatField()))*12,
        defense_kp12 = (F('defense_kills')/Cast('defense_rounds', FloatField()))*12,
        defense_dp12 = (F('defense_deaths')/Cast('defense_rounds', FloatField()))*12,

        max_kills = Max('Kills'),
        max_deaths = Max('Deaths'),
        max_assists = Max('Assists'),
        max_kdr = Max(F('Kills') / Cast('Deaths', FloatField())),
        max_acs = Max(F('CombatScore') / F('RoundsPlayed')),
        max_adr = Max(F('TotalDamage') / Cast('RoundsPlayed', FloatField())),
        max_fb = Max('FirstBloods'),
        max_fd = Max('FirstDeaths')
    ).order_by('Role')

    for m in roles:
        filtered_players = players.filter(Role=m['Role'])

        m['WinLossRecord'] = "{}-{}-{}".format(m['matches_won'],m['matches_lost'],m['matches_draw'])
        m['RoundRecord'] = "{}-{}".format(m["rounds_won"],m["rounds_lost"])
        m['AttackRecord'] = "{}-{}".format(m["attack_wins"],m["attack_losses"])
        m['DefenseRecord'] = "{}-{}".format(m["defense_wins"],m["defense_losses"])

        agent_counter = Counter(filtered_players.values_list('Agent', flat=True))
        if agent_counter:
            m['TopAgent'] = agent_counter.most_common(1)[0][0]
            m['AgentString'] =", ".join(f"{key} ({value})" for key, value in agent_counter.most_common())
        m['TopAgentImage'] = AgentImage(m['TopAgent'])

        max_kills = filtered_players.filter(Kills=m['max_kills']).order_by('-ACS','-KillDeathRatio')
        max_deaths = filtered_players.filter(Deaths=m['max_deaths']).order_by('Kills','ACS')
        max_assists = filtered_players.filter(Assists=m['max_assists']).order_by('-Kills','-ACS','-KillDeathRatio')
        max_kdr = filtered_players.annotate(kdr=F('Kills') / Cast('Deaths', FloatField()))\
                                  .filter(kdr=m['max_kdr']).order_by('-Kills','-ACS')
        max_acs = filtered_players.filter(ACS=m['max_acs']).order_by('-Kills','-KillDeathRatio')
        max_adr = filtered_players.annotate(adr=F('TotalDamage') / Cast('RoundsPlayed', FloatField()))\
                                  .filter(adr=m['max_adr']).order_by('-ACS','-Kills','-KillDeathRatio')
        max_fb = filtered_players.annotate(fb_pct=(Sum('FirstBloods')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                 .filter(FirstBloods=m['max_fb']).order_by('-fb_pct','FirstDeaths','-ACS','-Kills','-KillDeathRatio')
        max_fd = filtered_players.annotate(fd_pct=(Sum('FirstDeaths')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                 .filter(FirstDeaths=m['max_fd']).order_by('-fd_pct','FirstBloods','ACS','Kills','KillDeathRatio')

        m['max_kills_id'] = max_kills.values('Match__MatchID').first()['Match__MatchID']
        m['max_kills_player'] = max_kills.values('DisplayName').first()['DisplayName']

        m['max_deaths_id'] = max_deaths.values('Match__MatchID').first()['Match__MatchID']
        m['max_deaths_player'] = max_deaths.values('DisplayName').first()['DisplayName']

        m['max_assists_id'] = max_assists.values('Match__MatchID').first()['Match__MatchID']
        m['max_assists_player'] = max_assists.values('DisplayName').first()['DisplayName']

        m['max_kdr_id'] = max_kdr.values('Match__MatchID').first()['Match__MatchID']
        m['max_kdr_player'] = max_kdr.values('DisplayName').first()['DisplayName']

        m['max_acs_id'] = max_acs.values('Match__MatchID').first()['Match__MatchID']
        m['max_acs_player'] = max_acs.values('DisplayName').first()['DisplayName']

        m['max_adr_id'] = max_adr.values('Match__MatchID').first()['Match__MatchID']
        m['max_adr_player'] = max_adr.values('DisplayName').first()['DisplayName']

        m['max_fb_id'] = max_fb.values('Match__MatchID').first()['Match__MatchID']
        m['max_fb_player'] = max_fb.values('DisplayName').first()['DisplayName']

        m['max_fd_id'] = max_fd.values('Match__MatchID').first()['Match__MatchID']
        m['max_fd_player'] = max_fd.values('DisplayName').first()['DisplayName']

    combinations = players.values("Match__N_Controllers","Match__N_Duelists","Match__N_Initiators","Match__N_Sentinels").annotate(
        num_matches=Count('Match')/5,

        matches_won=Sum('MatchWon')/5,
        matches_lost=Sum('MatchLost')/5,
        matches_draw=Sum('MatchDraw')/5,

        total_kills=Sum('Kills'),
        total_deaths=Sum('Deaths'),
        total_assists=Sum('Assists'),

        total_score=Sum('CombatScore'),
        total_damage=Sum('TotalDamage'),

        first_bloods=Sum('FirstBloods'),
        first_deaths=Sum('FirstDeaths'),
        fb_fd_ratio=Sum('FirstBloods')/Cast(Sum('FirstDeaths'), output_field=FloatField()),

        kast_rounds=Sum('KASTRounds'),

        attack_kills=Sum('AttackKills'),
        attack_deaths=Sum('AttackDeaths'),
        attack_damage=Sum('AttackDamage'),
        defense_kills=Sum('DefenseKills'),
        defense_deaths=Sum('DefenseDeaths'),
        defense_damage=Sum('DefenseDamage'),
        
        win_kills=Sum('WinKills'),
        win_deaths=Sum('WinDeaths'),
        win_damage=Sum('WinDamage'),
        loss_kills=Sum('LossKills'),
        loss_deaths=Sum('LossDeaths'),
        loss_damage=Sum('LossDamage'),

        kast=Sum('KASTRounds')/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
        k_pct=(Sum('RoundsPlayed')-Sum('ZeroKillRounds'))/Cast(Sum('RoundsPlayed'), output_field=FloatField()),

        win_pct=(Sum('MatchWon')+0.5*Sum('MatchDraw'))/Cast(Count('Match'), FloatField()),
        round_win_pct=(Sum('AttackWins')+Sum('DefenseWins'))/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
        attack_win_pct=Sum('AttackWins')/Cast(Sum('AttackRounds'), output_field=FloatField()),
        defense_win_pct=Sum('DefenseWins')/Cast(Sum('DefenseRounds'), output_field=FloatField()),

        kdr=Sum('Kills')/Cast(Sum('Deaths'), output_field=FloatField()),
        kpr=Sum('Kills')/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
        acs=Sum('CombatScore')/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
        adr=Sum('TotalDamage')/Cast(Sum('RoundsPlayed'), output_field=FloatField()),

        attack_rounds=Sum('AttackRounds')/5,
        attack_wins=Sum('AttackWins')/5,
        attack_losses=Sum('AttackLosses')/5,

        defense_rounds=Sum('DefenseRounds')/5,
        defense_wins=Sum('DefenseWins')/5,
        defense_losses=Sum('DefenseLosses')/5,

        rounds_won=(Sum('AttackWins')+Sum('DefenseWins'))/5,
        rounds_lost=(Sum('AttackLosses')+Sum('DefenseLosses'))/5,
        rounds_played=Sum('RoundsPlayed')/5,

        fb_pct=(Sum('FirstBloods')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())),
        fd_pct=(Sum('FirstDeaths')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())),

        attack_kdr=Sum('AttackKills')/Cast(Sum('AttackDeaths'), output_field=FloatField()),
        attack_adr=Sum('AttackDamage')/Cast(Sum('AttackRounds'), output_field=FloatField()),
        defense_kdr=Sum('DefenseKills')/Cast(Sum('DefenseDeaths'), output_field=FloatField()),
        defense_adr=Sum('DefenseDamage')/Cast(Sum('DefenseRounds'), output_field=FloatField()),

        max_kills = Max('Kills'),
        max_deaths = Max('Deaths'),
        max_assists = Max('Assists'),
        max_kdr = Max(F('Kills') / Cast('Deaths', FloatField())),
        max_acs = Max(F('CombatScore') / F('RoundsPlayed')),
        max_adr = Max(F('TotalDamage') / Cast('RoundsPlayed', FloatField())),
        max_fb = Max('FirstBloods'),
        max_fd = Max('FirstDeaths')
    )

    combinations = combinations.order_by('-num_matches')

    for m in combinations:
        filtered_players = players.filter(Team="Team A",
                                          Match__N_Controllers=m['Match__N_Controllers'],
                                          Match__N_Duelists=m['Match__N_Duelists'],
                                          Match__N_Initiators=m['Match__N_Initiators'],
                                          Match__N_Sentinels=m['Match__N_Sentinels'])

        m['WinLossRecord'] = "{}-{}-{}".format(m['matches_won'],m['matches_lost'],m['matches_draw'])
        m['RoundRecord'] = "{}-{}".format(m["rounds_won"],m["rounds_lost"])
        m['AttackRecord'] = "{}-{}".format(m["attack_wins"],m["attack_losses"])
        m['DefenseRecord'] = "{}-{}".format(m["defense_wins"],m["defense_losses"])

    context = {
        'roles': roles,
        'combinations': combinations,

        'unique_maps': unique_maps,
        'unique_roles': unique_roles,

        'map_filter': map_filter,
        'outcome_filter': outcome_filter,
        'date_filter': date_filter,
        'start_date': start_date,
        'end_date': end_date,
    }

    # Render template
    return render(request, 'match/roles.html', context)

def role_detail(request, role):
    players = Player.objects.filter(Team="Team A", Role=role).order_by('Match__Date')

    if (players.count() == 0):
        raise Http404
    
    last_five = players.order_by('-Match__Date')[:5]
    last_ten = players.order_by('-Match__Date')[:10]
    last_twenty = players.order_by('-Match__Date')[:20]

    last_five_aggregates = CalculateAggregates(last_five,"Role",role)
    last_ten_aggregates = CalculateAggregates(last_ten,"Role",role)
    last_twenty_aggregates = CalculateAggregates(last_twenty,"Role",role)
    all_aggregates = CalculateAggregates(players,"Role",role)

    last_five_aggregates["Label"] = "Last 5 Performances"
    last_ten_aggregates["Label"] = "Last 10 Performances"
    last_twenty_aggregates["Label"] = "Last 20 Performances"
    all_aggregates["Label"] = "All Performances"
    
    context = {
        'lst': [last_five_aggregates, last_ten_aggregates, 
                last_twenty_aggregates, all_aggregates],
        'role': role,
    }

    return render(request, 'match/role/role_detail.html', context)

def role_splits(request, role):
    players = Player.objects.filter(Team="Team A", Role=role).order_by('-Match__Date')

    if (players.count() == 0):
        raise Http404
    
    count_splits = Player.objects.filter(Team="Team A").values('Match__N_{}s'.format(role)).annotate(
        num_matches=Count('Match')/5,

        matches_won=Sum('MatchWon')/5,
        matches_lost=Sum('MatchLost')/5,
        matches_draw=Sum('MatchDraw')/5,

        win_pct=(Sum('MatchWon')+0.5*Sum('MatchDraw'))/Cast(Count('Match'), FloatField()),
        round_win_pct=(Sum('AttackWins')+Sum('DefenseWins'))/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
        attack_win_pct=Sum('AttackWins')/Cast(Sum('AttackRounds'), output_field=FloatField()),
        defense_win_pct=Sum('DefenseWins')/Cast(Sum('DefenseRounds'), output_field=FloatField()),

        attack_rounds=Sum('AttackRounds')/5,
        attack_wins=Sum('AttackWins')/5,
        attack_losses=Sum('AttackLosses')/5,

        defense_rounds=Sum('DefenseRounds')/5,
        defense_wins=Sum('DefenseWins')/5,
        defense_losses=Sum('DefenseLosses')/5,

        rounds_won=(Sum('AttackWins')+Sum('DefenseWins'))/5,
        rounds_lost=(Sum('AttackLosses')+Sum('DefenseLosses'))/5,
        rounds_played=Sum('RoundsPlayed')/5,
    )

    count_splits = count_splits.order_by('Match__N_{}s'.format(role))

    for m in count_splits:
        filter_dict = {'Match__N_{}s'.format(role): m['Match__N_{}s'.format(role)]}
        filtered_players = players.filter(**filter_dict)

        m['WinLossRecord'] = "{}-{}-{}".format(m['matches_won'],m['matches_lost'],m['matches_draw'])
        m['RoundRecord'] = "{}-{}".format(m["rounds_won"],m["rounds_lost"])
        m['AttackRecord'] = "{}-{}".format(m["attack_wins"],m["attack_losses"])
        m['DefenseRecord'] = "{}-{}".format(m["defense_wins"],m["defense_losses"])

        m['Count'] = m['Match__N_{}s'.format(role)]

    count_splits_combat = Player.objects.filter(Team="Team A", Role=role).values('Match__N_{}s'.format(role)).annotate(
        num_matches=Count('Match'),

        matches_won=Sum('MatchWon'),
        matches_lost=Sum('MatchLost'),
        matches_draw=Sum('MatchDraw'),

        total_kills=Sum('Kills'),
        total_deaths=Sum('Deaths'),
        total_assists=Sum('Assists'),

        total_score=Sum('CombatScore'),
        total_damage=Sum('TotalDamage'),

        first_bloods=Sum('FirstBloods'),
        first_deaths=Sum('FirstDeaths'),
        fb_fd_ratio=Sum('FirstBloods')/Cast(Sum('FirstDeaths'), output_field=FloatField()),

        kast_rounds=Sum('KASTRounds'),

        attack_kills=Sum('AttackKills'),
        attack_deaths=Sum('AttackDeaths'),
        attack_damage=Sum('AttackDamage'),
        defense_kills=Sum('DefenseKills'),
        defense_deaths=Sum('DefenseDeaths'),
        defense_damage=Sum('DefenseDamage'),
        
        win_kills=Sum('WinKills'),
        win_deaths=Sum('WinDeaths'),
        win_damage=Sum('WinDamage'),
        loss_kills=Sum('LossKills'),
        loss_deaths=Sum('LossDeaths'),
        loss_damage=Sum('LossDamage'),

        kast=Sum('KASTRounds')/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
        k_pct=(Sum('RoundsPlayed')-Sum('ZeroKillRounds'))/Cast(Sum('RoundsPlayed'), output_field=FloatField()),

        win_pct=(Sum('MatchWon')+0.5*Sum('MatchDraw'))/Cast(Count('Match'), FloatField()),
        round_win_pct=(Sum('AttackWins')+Sum('DefenseWins'))/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
        attack_win_pct=Sum('AttackWins')/Cast(Sum('AttackRounds'), output_field=FloatField()),
        defense_win_pct=Sum('DefenseWins')/Cast(Sum('DefenseRounds'), output_field=FloatField()),

        kdr=Sum('Kills')/Cast(Sum('Deaths'), output_field=FloatField()),
        kpr=Sum('Kills')/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
        acs=Sum('CombatScore')/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
        adr=Sum('TotalDamage')/Cast(Sum('RoundsPlayed'), output_field=FloatField()),

        attack_rounds=Sum('AttackRounds')/5,
        attack_wins=Sum('AttackWins')/5,
        attack_losses=Sum('AttackLosses')/5,

        defense_rounds=Sum('DefenseRounds')/5,
        defense_wins=Sum('DefenseWins')/5,
        defense_losses=Sum('DefenseLosses')/5,

        rounds_won=(Sum('AttackWins')+Sum('DefenseWins'))/5,
        rounds_lost=(Sum('AttackLosses')+Sum('DefenseLosses'))/5,
        rounds_played=Sum('RoundsPlayed')/5,

        fb_pct=(Sum('FirstBloods')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())),
        fd_pct=(Sum('FirstDeaths')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())),

        attack_kdr=Sum('AttackKills')/Cast(Sum('AttackDeaths'), output_field=FloatField()),
        attack_adr=Sum('AttackDamage')/Cast(Sum('AttackRounds'), output_field=FloatField()),
        defense_kdr=Sum('DefenseKills')/Cast(Sum('DefenseDeaths'), output_field=FloatField()),
        defense_adr=Sum('DefenseDamage')/Cast(Sum('DefenseRounds'), output_field=FloatField()),

        max_kills = Max('Kills'),
        max_deaths = Max('Deaths'),
        max_assists = Max('Assists'),
        max_kdr = Max(F('Kills') / Cast('Deaths', FloatField())),
        max_acs = Max(F('CombatScore') / F('RoundsPlayed')),
        max_adr = Max(F('TotalDamage') / Cast('RoundsPlayed', FloatField())),
        max_fb = Max('FirstBloods'),
        max_fd = Max('FirstDeaths')
    )

    for m in count_splits_combat:
        filter_dict = {'Match__N_{}s'.format(role): m['Match__N_{}s'.format(role)]}
        filtered_players = players.filter(**filter_dict)

        m['WinLossRecord'] = "{}-{}-{}".format(m['matches_won'],m['matches_lost'],m['matches_draw'])
        m['RoundRecord'] = "{}-{}".format(m["rounds_won"],m["rounds_lost"])
        m['AttackRecord'] = "{}-{}".format(m["attack_wins"],m["attack_losses"])
        m['DefenseRecord'] = "{}-{}".format(m["defense_wins"],m["defense_losses"])

        m['Count'] = m['Match__N_{}s'.format(role)]

    player_splits = players.values('Username').annotate(
        num_matches=Count('Match'),

        matches_won=Sum('MatchWon'),
        matches_lost=Sum('MatchLost'),
        matches_draw=Sum('MatchDraw'),

        total_kills=Sum('Kills'),
        total_deaths=Sum('Deaths'),
        total_assists=Sum('Assists'),

        total_score=Sum('CombatScore'),
        total_damage=Sum('TotalDamage'),

        first_bloods=Sum('FirstBloods'),
        first_deaths=Sum('FirstDeaths'),
        fb_fd_ratio=F('first_bloods')/Cast('first_deaths', FloatField()),

        kast_rounds=Sum('KASTRounds'),

        hs_pct=Sum(F('HS_Pct') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),
        damage_delta=Sum(F('DamageDelta') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),

        zero_kills=Sum('ZeroKillRounds'),
        one_kills=Sum('OneKillRounds'),
        two_kills=Sum('TwoKillRounds'),
        three_kills=Sum('ThreeKillRounds'),
        four_kills=Sum('FourKillRounds'),
        five_kills=Sum('FiveKillRounds'),
        six_kills=Sum('SixKillRounds'),

        attack_kills=Sum('AttackKills'),
        attack_deaths=Sum('AttackDeaths'),
        attack_damage=Sum('AttackDamage'),
        defense_kills=Sum('DefenseKills'),
        defense_deaths=Sum('DefenseDeaths'),
        defense_damage=Sum('DefenseDamage'),
        
        win_kills=Sum('WinKills'),
        win_deaths=Sum('WinDeaths'),
        win_damage=Sum('WinDamage'),
        loss_kills=Sum('LossKills'),
        loss_deaths=Sum('LossDeaths'),
        loss_damage=Sum('LossDamage'),

        attack_rounds=Sum('AttackRounds'),
        attack_wins=Sum('AttackWins'),
        attack_losses=Sum('AttackLosses'),

        defense_rounds=Sum('DefenseRounds'),
        defense_wins=Sum('DefenseWins'),
        defense_losses=Sum('DefenseLosses'),

        rounds_won=Sum('AttackWins')+Sum('DefenseWins'),
        rounds_lost=Sum('AttackLosses')+Sum('DefenseLosses'),

        rounds = Sum('RoundsPlayed'),

        kdr=F('total_kills')/Cast('total_deaths', FloatField()),
        kpr=F('total_kills')/Cast('rounds', FloatField()),
        acs=F('total_score')/Cast('rounds', FloatField()),
        adr=F('total_damage')/Cast('rounds', FloatField()),

        kast=F('kast_rounds')/Cast('rounds', FloatField()),
        k_pct=(F('rounds')-F('zero_kills'))/Cast('rounds', FloatField()),

        win_pct=(F('matches_won')+0.5*F('matches_draw'))/Cast('num_matches', FloatField()),
        round_win_pct=F('rounds_won')/Cast('rounds', FloatField()),
        attack_win_pct=F('attack_wins')/Cast('attack_rounds', FloatField()),
        defense_win_pct=F('defense_wins')/Cast('defense_rounds', FloatField()),

        kills_per_20 = (F('total_kills')/Cast('rounds', FloatField()))*20,
        deaths_per_20 = (F('total_deaths')/Cast('rounds', FloatField()))*20,
        assists_per_20 = (F('total_assists')/Cast('rounds', FloatField()))*20,

        fb_per_20 = (F('first_bloods')/Cast('rounds', FloatField()))*20,
        fd_per_20 = (F('first_deaths')/Cast('rounds', FloatField()))*20,

        attack_kdr = F('attack_kills')/Cast('attack_deaths', FloatField()), 
        attack_adr = F('attack_damage')/Cast('attack_rounds', FloatField()), 
        defense_kdr = F('defense_kills')/Cast('defense_deaths', FloatField()), 
        defense_adr = F('defense_damage')/Cast('defense_rounds', FloatField()),

        attack_kp12 = (F('attack_kills')/Cast('attack_rounds', FloatField()))*12,
        attack_dp12 = (F('attack_deaths')/Cast('attack_rounds', FloatField()))*12,
        defense_kp12 = (F('defense_kills')/Cast('defense_rounds', FloatField()))*12,
        defense_dp12 = (F('defense_deaths')/Cast('defense_rounds', FloatField()))*12,

        max_kills = Max('Kills'),
        max_deaths = Max('Deaths'),
        max_assists = Max('Assists'),
        max_kdr = Max(F('Kills') / Cast('Deaths', FloatField())),
        max_acs = Max(F('CombatScore') / F('RoundsPlayed')),
        max_adr = Max(F('TotalDamage') / Cast('RoundsPlayed', FloatField())),
        max_fb = Max('FirstBloods'),
        max_fd = Max('FirstDeaths')
    ).order_by('-num_matches')

    for p in player_splits:
        filtered_players = players.filter(Username=p['Username'])

        UserSplit = p['Username'].split('#')
        p['DisplayName'] = UserSplit[0]
        p['UserTag'] = "#"+UserSplit[1]

        agent_counter = Counter(filtered_players.values_list('Agent', flat=True))
        if agent_counter:
            p['TopAgent'] = agent_counter.most_common(1)[0][0]
            p['AgentString'] =", ".join(f"{key} ({value})" for key, value in agent_counter.most_common())
        p['TopAgentImage'] = AgentImage(p['TopAgent'])

        p['WinLossRecord'] = "{}-{}-{}".format(p['matches_won'],p['matches_lost'],p['matches_draw'])
        p['RoundRecord'] = "{}-{}".format(p["rounds_won"],p["rounds_lost"])
        p['AttackRecord'] = "{}-{}".format(p["attack_wins"],p["attack_losses"])
        p['DefenseRecord'] = "{}-{}".format(p["defense_wins"],p["defense_losses"])

        max_kills = filtered_players.filter(Kills=p['max_kills']).order_by('-ACS','-KillDeathRatio')
        max_deaths = filtered_players.filter(Deaths=p['max_deaths']).order_by('Kills','ACS')
        max_assists = filtered_players.filter(Assists=p['max_assists']).order_by('-Kills','-ACS','-KillDeathRatio')
        max_kdr = filtered_players.annotate(kdr=F('Kills') / Cast('Deaths', FloatField()))\
                                  .filter(kdr=p['max_kdr']).order_by('-Kills','-ACS')
        max_acs = filtered_players.filter(ACS=p['max_acs']).order_by('-Kills','-KillDeathRatio')
        max_adr = filtered_players.annotate(adr=F('TotalDamage') / Cast('RoundsPlayed', FloatField()))\
                                  .filter(adr=p['max_adr']).order_by('-ACS','-Kills','-KillDeathRatio')
        max_fb = filtered_players.annotate(fb_pct=(Sum('FirstBloods')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                 .filter(FirstBloods=p['max_fb']).order_by('-fb_pct','FirstDeaths','-ACS','-Kills','-KillDeathRatio')
        max_fd = filtered_players.annotate(fd_pct=(Sum('FirstDeaths')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                 .filter(FirstDeaths=p['max_fd']).order_by('-fd_pct','FirstBloods','ACS','Kills','KillDeathRatio')

        p['max_kills_id'] = max_kills.values('Match__MatchID').first()['Match__MatchID']
        p['max_kills_player'] = max_kills.values('DisplayName').first()['DisplayName']

        p['max_deaths_id'] = max_deaths.values('Match__MatchID').first()['Match__MatchID']
        p['max_deaths_player'] = max_deaths.values('DisplayName').first()['DisplayName']

        p['max_assists_id'] = max_assists.values('Match__MatchID').first()['Match__MatchID']
        p['max_assists_player'] = max_assists.values('DisplayName').first()['DisplayName']

        p['max_kdr_id'] = max_kdr.values('Match__MatchID').first()['Match__MatchID']
        p['max_kdr_player'] = max_kdr.values('DisplayName').first()['DisplayName']

        p['max_acs_id'] = max_acs.values('Match__MatchID').first()['Match__MatchID']
        p['max_acs_player'] = max_acs.values('DisplayName').first()['DisplayName']

        p['max_adr_id'] = max_adr.values('Match__MatchID').first()['Match__MatchID']
        p['max_adr_player'] = max_adr.values('DisplayName').first()['DisplayName']

        p['max_fb_id'] = max_fb.values('Match__MatchID').first()['Match__MatchID']
        p['max_fb_player'] = max_fb.values('DisplayName').first()['DisplayName']

        p['max_fd_id'] = max_fd.values('Match__MatchID').first()['Match__MatchID']
        p['max_fd_player'] = max_fd.values('DisplayName').first()['DisplayName']

    agent_splits = players.values('Agent').annotate(
        num_matches=Count('Match'),

        matches_won=Sum('MatchWon'),
        matches_lost=Sum('MatchLost'),
        matches_draw=Sum('MatchDraw'),

        total_kills=Sum('Kills'),
        total_deaths=Sum('Deaths'),
        total_assists=Sum('Assists'),

        total_score=Sum('CombatScore'),
        total_damage=Sum('TotalDamage'),

        first_bloods=Sum('FirstBloods'),
        first_deaths=Sum('FirstDeaths'),
        fb_fd_ratio=F('first_bloods')/Cast('first_deaths', FloatField()),

        kast_rounds=Sum('KASTRounds'),

        hs_pct=Sum(F('HS_Pct') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),
        damage_delta=Sum(F('DamageDelta') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),
        
        zero_kills=Sum('ZeroKillRounds'),
        one_kills=Sum('OneKillRounds'),
        two_kills=Sum('TwoKillRounds'),
        three_kills=Sum('ThreeKillRounds'),
        four_kills=Sum('FourKillRounds'),
        five_kills=Sum('FiveKillRounds'),
        six_kills=Sum('SixKillRounds'),

        attack_kills=Sum('AttackKills'),
        attack_deaths=Sum('AttackDeaths'),
        attack_damage=Sum('AttackDamage'),
        defense_kills=Sum('DefenseKills'),
        defense_deaths=Sum('DefenseDeaths'),
        defense_damage=Sum('DefenseDamage'),
        
        win_kills=Sum('WinKills'),
        win_deaths=Sum('WinDeaths'),
        win_damage=Sum('WinDamage'),
        loss_kills=Sum('LossKills'),
        loss_deaths=Sum('LossDeaths'),
        loss_damage=Sum('LossDamage'),

        attack_rounds=Sum('AttackRounds'),
        attack_wins=Sum('AttackWins'),
        attack_losses=Sum('AttackLosses'),

        defense_rounds=Sum('DefenseRounds'),
        defense_wins=Sum('DefenseWins'),
        defense_losses=Sum('DefenseLosses'),

        rounds_won=Sum('AttackWins')+Sum('DefenseWins'),
        rounds_lost=Sum('AttackLosses')+Sum('DefenseLosses'),

        rounds = Sum('RoundsPlayed'),

        kdr=F('total_kills')/Cast('total_deaths', FloatField()),
        kpr=F('total_kills')/Cast('rounds', FloatField()),
        acs=F('total_score')/Cast('rounds', FloatField()),
        adr=F('total_damage')/Cast('rounds', FloatField()),

        kast=F('kast_rounds')/Cast('rounds', FloatField()),
        k_pct=(F('rounds')-F('zero_kills'))/Cast('rounds', FloatField()),

        win_pct=(F('matches_won')+0.5*F('matches_draw'))/Cast('num_matches', FloatField()),
        round_win_pct=F('rounds_won')/Cast('rounds', FloatField()),
        attack_win_pct=F('attack_wins')/Cast('attack_rounds', FloatField()),
        defense_win_pct=F('defense_wins')/Cast('defense_rounds', FloatField()),

        kills_per_20 = (F('total_kills')/Cast('rounds', FloatField()))*20,
        deaths_per_20 = (F('total_deaths')/Cast('rounds', FloatField()))*20,
        assists_per_20 = (F('total_assists')/Cast('rounds', FloatField()))*20,

        fb_per_20 = (F('first_bloods')/Cast('rounds', FloatField()))*20,
        fd_per_20 = (F('first_deaths')/Cast('rounds', FloatField()))*20,

        attack_kdr = F('attack_kills')/Cast('attack_deaths', FloatField()), 
        attack_adr = F('attack_damage')/Cast('attack_rounds', FloatField()), 
        defense_kdr = F('defense_kills')/Cast('defense_deaths', FloatField()), 
        defense_adr = F('defense_damage')/Cast('defense_rounds', FloatField()),

        attack_kp12 = (F('attack_kills')/Cast('attack_rounds', FloatField()))*12,
        attack_dp12 = (F('attack_deaths')/Cast('attack_rounds', FloatField()))*12,
        defense_kp12 = (F('defense_kills')/Cast('defense_rounds', FloatField()))*12,
        defense_dp12 = (F('defense_deaths')/Cast('defense_rounds', FloatField()))*12,

        max_kills = Max('Kills'),
        max_deaths = Max('Deaths'),
        max_assists = Max('Assists'),
        max_kdr = Max(F('Kills') / Cast('Deaths', FloatField())),
        max_acs = Max(F('CombatScore') / F('RoundsPlayed')),
        max_adr = Max(F('TotalDamage') / Cast('RoundsPlayed', FloatField())),
        max_fb = Max('FirstBloods'),
        max_fd = Max('FirstDeaths')
    ).order_by('-num_matches')

    for p in agent_splits:
        filtered_players = players.filter(Agent=p['Agent'])

        p['AgentImage'] = AgentImage(p['Agent'])

        p['WinLossRecord'] = "{}-{}-{}".format(p['matches_won'],p['matches_lost'],p['matches_draw'])
        p['RoundRecord'] = "{}-{}".format(p["rounds_won"],p["rounds_lost"])
        p['AttackRecord'] = "{}-{}".format(p["attack_wins"],p["attack_losses"])
        p['DefenseRecord'] = "{}-{}".format(p["defense_wins"],p["defense_losses"])

        max_kills = filtered_players.filter(Kills=p['max_kills']).order_by('-ACS','-KillDeathRatio')
        max_deaths = filtered_players.filter(Deaths=p['max_deaths']).order_by('Kills','ACS')
        max_assists = filtered_players.filter(Assists=p['max_assists']).order_by('-Kills','-ACS','-KillDeathRatio')
        max_kdr = filtered_players.annotate(kdr=F('Kills') / Cast('Deaths', FloatField()))\
                                    .filter(kdr=p['max_kdr']).order_by('-Kills','-ACS')
        max_acs = filtered_players.filter(ACS=p['max_acs']).order_by('-Kills','-KillDeathRatio')
        max_adr = filtered_players.annotate(adr=F('TotalDamage') / Cast('RoundsPlayed', FloatField()))\
                                    .filter(adr=p['max_adr']).order_by('-ACS','-Kills','-KillDeathRatio')
        max_fb = filtered_players.annotate(fb_pct=(Sum('FirstBloods')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                    .filter(FirstBloods=p['max_fb']).order_by('-fb_pct','FirstDeaths','-ACS','-Kills','-KillDeathRatio')
        max_fd = filtered_players.annotate(fd_pct=(Sum('FirstDeaths')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                    .filter(FirstDeaths=p['max_fd']).order_by('-fd_pct','FirstBloods','ACS','Kills','KillDeathRatio')
        

        p['max_kills_id'] = max_kills.values('Match__MatchID').first()['Match__MatchID']
        p['max_kills_player'] = max_kills.values('DisplayName').first()['DisplayName']

        p['max_deaths_id'] = max_deaths.values('Match__MatchID').first()['Match__MatchID']
        p['max_deaths_player'] = max_deaths.values('DisplayName').first()['DisplayName']

        p['max_assists_id'] = max_assists.values('Match__MatchID').first()['Match__MatchID']
        p['max_assists_player'] = max_assists.values('DisplayName').first()['DisplayName']

        p['max_kdr_id'] = max_kdr.values('Match__MatchID').first()['Match__MatchID']
        p['max_kdr_player'] = max_kdr.values('DisplayName').first()['DisplayName']

        p['max_acs_id'] = max_acs.values('Match__MatchID').first()['Match__MatchID']
        p['max_acs_player'] = max_acs.values('DisplayName').first()['DisplayName']

        p['max_adr_id'] = max_adr.values('Match__MatchID').first()['Match__MatchID']
        p['max_adr_player'] = max_adr.values('DisplayName').first()['DisplayName']

        p['max_fb_id'] = max_fb.values('Match__MatchID').first()['Match__MatchID']
        p['max_fb_player'] = max_fb.values('DisplayName').first()['DisplayName']

        p['max_fd_id'] = max_fd.values('Match__MatchID').first()['Match__MatchID']
        p['max_fd_player'] = max_fd.values('DisplayName').first()['DisplayName']

    map_splits = players.values('Match__Map').annotate(
        num_matches=Count('Match'),

        matches_won=Sum('MatchWon'),
        matches_lost=Sum('MatchLost'),
        matches_draw=Sum('MatchDraw'),

        total_kills=Sum('Kills'),
        total_deaths=Sum('Deaths'),
        total_assists=Sum('Assists'),

        total_score=Sum('CombatScore'),
        total_damage=Sum('TotalDamage'),

        first_bloods=Sum('FirstBloods'),
        first_deaths=Sum('FirstDeaths'),
        fb_fd_ratio=F('first_bloods')/Cast('first_deaths', FloatField()),

        kast_rounds=Sum('KASTRounds'),

        hs_pct=Sum(F('HS_Pct') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),
        damage_delta=Sum(F('DamageDelta') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),

        zero_kills=Sum('ZeroKillRounds'),
        one_kills=Sum('OneKillRounds'),
        two_kills=Sum('TwoKillRounds'),
        three_kills=Sum('ThreeKillRounds'),
        four_kills=Sum('FourKillRounds'),
        five_kills=Sum('FiveKillRounds'),
        six_kills=Sum('SixKillRounds'),

        attack_kills=Sum('AttackKills'),
        attack_deaths=Sum('AttackDeaths'),
        attack_damage=Sum('AttackDamage'),
        defense_kills=Sum('DefenseKills'),
        defense_deaths=Sum('DefenseDeaths'),
        defense_damage=Sum('DefenseDamage'),
        
        win_kills=Sum('WinKills'),
        win_deaths=Sum('WinDeaths'),
        win_damage=Sum('WinDamage'),
        loss_kills=Sum('LossKills'),
        loss_deaths=Sum('LossDeaths'),
        loss_damage=Sum('LossDamage'),

        attack_rounds=Sum('AttackRounds'),
        attack_wins=Sum('AttackWins'),
        attack_losses=Sum('AttackLosses'),

        defense_rounds=Sum('DefenseRounds'),
        defense_wins=Sum('DefenseWins'),
        defense_losses=Sum('DefenseLosses'),

        rounds_won=Sum('AttackWins')+Sum('DefenseWins'),
        rounds_lost=Sum('AttackLosses')+Sum('DefenseLosses'),

        rounds = Sum('RoundsPlayed'),

        kdr=F('total_kills')/Cast('total_deaths', FloatField()),
        kpr=F('total_kills')/Cast('rounds', FloatField()),
        acs=F('total_score')/Cast('rounds', FloatField()),
        adr=F('total_damage')/Cast('rounds', FloatField()),

        kast=F('kast_rounds')/Cast('rounds', FloatField()),
        k_pct=(F('rounds')-F('zero_kills'))/Cast('rounds', FloatField()),

        win_pct=(F('matches_won')+0.5*F('matches_draw'))/Cast('num_matches', FloatField()),
        round_win_pct=F('rounds_won')/Cast('rounds', FloatField()),
        attack_win_pct=F('attack_wins')/Cast('attack_rounds', FloatField()),
        defense_win_pct=F('defense_wins')/Cast('defense_rounds', FloatField()),

        kills_per_20 = (F('total_kills')/Cast('rounds', FloatField()))*20,
        deaths_per_20 = (F('total_deaths')/Cast('rounds', FloatField()))*20,
        assists_per_20 = (F('total_assists')/Cast('rounds', FloatField()))*20,

        fb_per_20 = (F('first_bloods')/Cast('rounds', FloatField()))*20,
        fd_per_20 = (F('first_deaths')/Cast('rounds', FloatField()))*20,

        attack_kdr = F('attack_kills')/Cast('attack_deaths', FloatField()), 
        attack_adr = F('attack_damage')/Cast('attack_rounds', FloatField()), 
        defense_kdr = F('defense_kills')/Cast('defense_deaths', FloatField()), 
        defense_adr = F('defense_damage')/Cast('defense_rounds', FloatField()),

        attack_kp12 = (F('attack_kills')/Cast('attack_rounds', FloatField()))*12,
        attack_dp12 = (F('attack_deaths')/Cast('attack_rounds', FloatField()))*12,
        defense_kp12 = (F('defense_kills')/Cast('defense_rounds', FloatField()))*12,
        defense_dp12 = (F('defense_deaths')/Cast('defense_rounds', FloatField()))*12,

        max_kills = Max('Kills'),
        max_deaths = Max('Deaths'),
        max_assists = Max('Assists'),
        max_kdr = Max(F('Kills') / Cast('Deaths', FloatField())),
        max_acs = Max(F('CombatScore') / F('RoundsPlayed')),
        max_adr = Max(F('TotalDamage') / Cast('RoundsPlayed', FloatField())),
        max_fb = Max('FirstBloods'),
        max_fd = Max('FirstDeaths')
    ).order_by('-num_matches')

    for p in map_splits:
        filtered_players = players.filter(Match__Map=p['Match__Map'])

        p['WinLossRecord'] = "{}-{}-{}".format(p['matches_won'],p['matches_lost'],p['matches_draw'])
        p['RoundRecord'] = "{}-{}".format(p["rounds_won"],p["rounds_lost"])
        p['AttackRecord'] = "{}-{}".format(p["attack_wins"],p["attack_losses"])
        p['DefenseRecord'] = "{}-{}".format(p["defense_wins"],p["defense_losses"])

        agent_counter = Counter(filtered_players.values_list('Agent', flat=True))
        if agent_counter:
            p['TopAgent'] = agent_counter.most_common(1)[0][0]
            p['AgentString'] =", ".join(f"{key} ({value})" for key, value in agent_counter.most_common())
        p['TopAgentImage'] = AgentImage(p['TopAgent'])

        max_kills = filtered_players.filter(Kills=p['max_kills']).order_by('-ACS','-KillDeathRatio')
        max_deaths = filtered_players.filter(Deaths=p['max_deaths']).order_by('Kills','ACS')
        max_assists = filtered_players.filter(Assists=p['max_assists']).order_by('-Kills','-ACS','-KillDeathRatio')
        max_kdr = filtered_players.annotate(kdr=F('Kills') / Cast('Deaths', FloatField()))\
                                  .filter(kdr=p['max_kdr']).order_by('-Kills','-ACS')
        max_acs = filtered_players.filter(ACS=p['max_acs']).order_by('-Kills','-KillDeathRatio')
        max_adr = filtered_players.annotate(adr=F('TotalDamage') / Cast('RoundsPlayed', FloatField()))\
                                  .filter(adr=p['max_adr']).order_by('-ACS','-Kills','-KillDeathRatio')
        max_fb = filtered_players.annotate(fb_pct=(Sum('FirstBloods')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                 .filter(FirstBloods=p['max_fb']).order_by('-fb_pct','FirstDeaths','-ACS','-Kills','-KillDeathRatio')
        max_fd = filtered_players.annotate(fd_pct=(Sum('FirstDeaths')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                 .filter(FirstDeaths=p['max_fd']).order_by('-fd_pct','FirstBloods','ACS','Kills','KillDeathRatio')

        p['max_kills_id'] = max_kills.values('Match__MatchID').first()['Match__MatchID']
        p['max_kills_player'] = max_kills.values('DisplayName').first()['DisplayName']

        p['max_deaths_id'] = max_deaths.values('Match__MatchID').first()['Match__MatchID']
        p['max_deaths_player'] = max_deaths.values('DisplayName').first()['DisplayName']

        p['max_assists_id'] = max_assists.values('Match__MatchID').first()['Match__MatchID']
        p['max_assists_player'] = max_assists.values('DisplayName').first()['DisplayName']

        p['max_kdr_id'] = max_kdr.values('Match__MatchID').first()['Match__MatchID']
        p['max_kdr_player'] = max_kdr.values('DisplayName').first()['DisplayName']

        p['max_acs_id'] = max_acs.values('Match__MatchID').first()['Match__MatchID']
        p['max_acs_player'] = max_acs.values('DisplayName').first()['DisplayName']

        p['max_adr_id'] = max_adr.values('Match__MatchID').first()['Match__MatchID']
        p['max_adr_player'] = max_adr.values('DisplayName').first()['DisplayName']

        p['max_fb_id'] = max_fb.values('Match__MatchID').first()['Match__MatchID']
        p['max_fb_player'] = max_fb.values('DisplayName').first()['DisplayName']

        p['max_fd_id'] = max_fd.values('Match__MatchID').first()['Match__MatchID']
        p['max_fd_player'] = max_fd.values('DisplayName').first()['DisplayName']

    outcome_splits = players.values('MatchWon','MatchLost','MatchDraw').annotate(
        num_matches=Count('Match'),

        matches_won=Sum('MatchWon'),
        matches_lost=Sum('MatchLost'),
        matches_draw=Sum('MatchDraw'),

        total_kills=Sum('Kills'),
        total_deaths=Sum('Deaths'),
        total_assists=Sum('Assists'),

        total_score=Sum('CombatScore'),
        total_damage=Sum('TotalDamage'),

        first_bloods=Sum('FirstBloods'),
        first_deaths=Sum('FirstDeaths'),
        fb_fd_ratio=F('first_bloods')/Cast('first_deaths', FloatField()),

        kast_rounds=Sum('KASTRounds'),

        hs_pct=Sum(F('HS_Pct') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),
        damage_delta=Sum(F('DamageDelta') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),

        zero_kills=Sum('ZeroKillRounds'),
        one_kills=Sum('OneKillRounds'),
        two_kills=Sum('TwoKillRounds'),
        three_kills=Sum('ThreeKillRounds'),
        four_kills=Sum('FourKillRounds'),
        five_kills=Sum('FiveKillRounds'),
        six_kills=Sum('SixKillRounds'),

        attack_kills=Sum('AttackKills'),
        attack_deaths=Sum('AttackDeaths'),
        attack_damage=Sum('AttackDamage'),
        defense_kills=Sum('DefenseKills'),
        defense_deaths=Sum('DefenseDeaths'),
        defense_damage=Sum('DefenseDamage'),
        
        win_kills=Sum('WinKills'),
        win_deaths=Sum('WinDeaths'),
        win_damage=Sum('WinDamage'),
        loss_kills=Sum('LossKills'),
        loss_deaths=Sum('LossDeaths'),
        loss_damage=Sum('LossDamage'),

        attack_rounds=Sum('AttackRounds'),
        attack_wins=Sum('AttackWins'),
        attack_losses=Sum('AttackLosses'),

        defense_rounds=Sum('DefenseRounds'),
        defense_wins=Sum('DefenseWins'),
        defense_losses=Sum('DefenseLosses'),

        rounds_won=Sum('AttackWins')+Sum('DefenseWins'),
        rounds_lost=Sum('AttackLosses')+Sum('DefenseLosses'),

        rounds = Sum('RoundsPlayed'),

        kdr=F('total_kills')/Cast('total_deaths', FloatField()),
        kpr=F('total_kills')/Cast('rounds', FloatField()),
        acs=F('total_score')/Cast('rounds', FloatField()),
        adr=F('total_damage')/Cast('rounds', FloatField()),

        kast=F('kast_rounds')/Cast('rounds', FloatField()),
        k_pct=(F('rounds')-F('zero_kills'))/Cast('rounds', FloatField()),

        win_pct=(F('matches_won')+0.5*F('matches_draw'))/Cast('num_matches', FloatField()),
        round_win_pct=F('rounds_won')/Cast('rounds', FloatField()),
        attack_win_pct=F('attack_wins')/Cast('attack_rounds', FloatField()),
        defense_win_pct=F('defense_wins')/Cast('defense_rounds', FloatField()),

        kills_per_20 = (F('total_kills')/Cast('rounds', FloatField()))*20,
        deaths_per_20 = (F('total_deaths')/Cast('rounds', FloatField()))*20,
        assists_per_20 = (F('total_assists')/Cast('rounds', FloatField()))*20,

        fb_per_20 = (F('first_bloods')/Cast('rounds', FloatField()))*20,
        fd_per_20 = (F('first_deaths')/Cast('rounds', FloatField()))*20,

        attack_kdr = F('attack_kills')/Cast('attack_deaths', FloatField()), 
        attack_adr = F('attack_damage')/Cast('attack_rounds', FloatField()), 
        defense_kdr = F('defense_kills')/Cast('defense_deaths', FloatField()), 
        defense_adr = F('defense_damage')/Cast('defense_rounds', FloatField()),

        attack_kp12 = (F('attack_kills')/Cast('attack_rounds', FloatField()))*12,
        attack_dp12 = (F('attack_deaths')/Cast('attack_rounds', FloatField()))*12,
        defense_kp12 = (F('defense_kills')/Cast('defense_rounds', FloatField()))*12,
        defense_dp12 = (F('defense_deaths')/Cast('defense_rounds', FloatField()))*12,

        max_kills = Max('Kills'),
        max_deaths = Max('Deaths'),
        max_assists = Max('Assists'),
        max_kdr = Max(F('Kills') / Cast('Deaths', FloatField())),
        max_acs = Max(F('CombatScore') / F('RoundsPlayed')),
        max_adr = Max(F('TotalDamage') / Cast('RoundsPlayed', FloatField())),
        max_fb = Max('FirstBloods'),
        max_fd = Max('FirstDeaths')
    ).order_by('-MatchWon')

    for p in outcome_splits:
        filtered_players = players.filter(MatchWon=p['MatchWon'])

        p['Outcome'] = "Win" if p['MatchWon'] == 1 else "Loss" if p['MatchLost'] == 1 else "Draw"\

        p['WinLossRecord'] = "{}-{}-{}".format(p['matches_won'],p['matches_lost'],p['matches_draw'])
        p['RoundRecord'] = "{}-{}".format(p["rounds_won"],p["rounds_lost"])
        p['AttackRecord'] = "{}-{}".format(p["attack_wins"],p["attack_losses"])
        p['DefenseRecord'] = "{}-{}".format(p["defense_wins"],p["defense_losses"])

        agent_counter = Counter(filtered_players.values_list('Agent', flat=True))
        if agent_counter:
            p['TopAgent'] = agent_counter.most_common(1)[0][0]
            p['AgentString'] =", ".join(f"{key} ({value})" for key, value in agent_counter.most_common())
        p['TopAgentImage'] = AgentImage(p['TopAgent'])

        max_kills = filtered_players.filter(Kills=p['max_kills']).order_by('-ACS','-KillDeathRatio')
        max_deaths = filtered_players.filter(Deaths=p['max_deaths']).order_by('Kills','ACS')
        max_assists = filtered_players.filter(Assists=p['max_assists']).order_by('-Kills','-ACS','-KillDeathRatio')
        max_kdr = filtered_players.annotate(kdr=F('Kills') / Cast('Deaths', FloatField()))\
                                  .filter(kdr=p['max_kdr']).order_by('-Kills','-ACS')
        max_acs = filtered_players.filter(ACS=p['max_acs']).order_by('-Kills','-KillDeathRatio')
        max_adr = filtered_players.annotate(adr=F('TotalDamage') / Cast('RoundsPlayed', FloatField()))\
                                  .filter(adr=p['max_adr']).order_by('-ACS','-Kills','-KillDeathRatio')
        max_fb = filtered_players.annotate(fb_pct=(Sum('FirstBloods')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                 .filter(FirstBloods=p['max_fb']).order_by('-fb_pct','FirstDeaths','-ACS','-Kills','-KillDeathRatio')
        max_fd = filtered_players.annotate(fd_pct=(Sum('FirstDeaths')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                 .filter(FirstDeaths=p['max_fd']).order_by('-fd_pct','FirstBloods','ACS','Kills','KillDeathRatio')

        p['max_kills_id'] = max_kills.values('Match__MatchID').first()['Match__MatchID']
        p['max_kills_player'] = max_kills.values('DisplayName').first()['DisplayName']

        p['max_deaths_id'] = max_deaths.values('Match__MatchID').first()['Match__MatchID']
        p['max_deaths_player'] = max_deaths.values('DisplayName').first()['DisplayName']

        p['max_assists_id'] = max_assists.values('Match__MatchID').first()['Match__MatchID']
        p['max_assists_player'] = max_assists.values('DisplayName').first()['DisplayName']

        p['max_kdr_id'] = max_kdr.values('Match__MatchID').first()['Match__MatchID']
        p['max_kdr_player'] = max_kdr.values('DisplayName').first()['DisplayName']

        p['max_acs_id'] = max_acs.values('Match__MatchID').first()['Match__MatchID']
        p['max_acs_player'] = max_acs.values('DisplayName').first()['DisplayName']

        p['max_adr_id'] = max_adr.values('Match__MatchID').first()['Match__MatchID']
        p['max_adr_player'] = max_adr.values('DisplayName').first()['DisplayName']

        p['max_fb_id'] = max_fb.values('Match__MatchID').first()['Match__MatchID']
        p['max_fb_player'] = max_fb.values('DisplayName').first()['DisplayName']

        p['max_fd_id'] = max_fd.values('Match__MatchID').first()['Match__MatchID']
        p['max_fd_player'] = max_fd.values('DisplayName').first()['DisplayName']

    context = {
        'count_splits': count_splits,
        'count_splits_combat': count_splits_combat,
        'player_splits': player_splits,
        'agent_splits': agent_splits,
        'map_splits': map_splits,
        'outcome_splits': outcome_splits,

        'role': role,
    }

    return render(request, 'match/role/role_splits.html', context)

def agent_splits(request, agent):
    if agent == "KAYO":
        agent = "KAY/O"

    players = Player.objects.filter(Team="Team A", Agent=agent).order_by('-Match__Date')

    if (players.count() == 0):
        raise Http404
    
    agentImage = AgentImage(agent)

    player_splits = players.values('Username').annotate(
        num_matches=Count('Match'),

        matches_won=Sum('MatchWon'),
        matches_lost=Sum('MatchLost'),
        matches_draw=Sum('MatchDraw'),

        total_kills=Sum('Kills'),
        total_deaths=Sum('Deaths'),
        total_assists=Sum('Assists'),

        total_score=Sum('CombatScore'),
        total_damage=Sum('TotalDamage'),

        first_bloods=Sum('FirstBloods'),
        first_deaths=Sum('FirstDeaths'),
        fb_fd_ratio=F('first_bloods')/Cast('first_deaths', FloatField()),

        kast_rounds=Sum('KASTRounds'),

        hs_pct=Sum(F('HS_Pct') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),
        damage_delta=Sum(F('DamageDelta') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),

        zero_kills=Sum('ZeroKillRounds'),
        one_kills=Sum('OneKillRounds'),
        two_kills=Sum('TwoKillRounds'),
        three_kills=Sum('ThreeKillRounds'),
        four_kills=Sum('FourKillRounds'),
        five_kills=Sum('FiveKillRounds'),
        six_kills=Sum('SixKillRounds'),

        attack_kills=Sum('AttackKills'),
        attack_deaths=Sum('AttackDeaths'),
        attack_damage=Sum('AttackDamage'),
        defense_kills=Sum('DefenseKills'),
        defense_deaths=Sum('DefenseDeaths'),
        defense_damage=Sum('DefenseDamage'),
        
        win_kills=Sum('WinKills'),
        win_deaths=Sum('WinDeaths'),
        win_damage=Sum('WinDamage'),
        loss_kills=Sum('LossKills'),
        loss_deaths=Sum('LossDeaths'),
        loss_damage=Sum('LossDamage'),

        attack_rounds=Sum('AttackRounds'),
        attack_wins=Sum('AttackWins'),
        attack_losses=Sum('AttackLosses'),

        defense_rounds=Sum('DefenseRounds'),
        defense_wins=Sum('DefenseWins'),
        defense_losses=Sum('DefenseLosses'),

        rounds_won=Sum('AttackWins')+Sum('DefenseWins'),
        rounds_lost=Sum('AttackLosses')+Sum('DefenseLosses'),

        rounds = Sum('RoundsPlayed'),

        kdr=F('total_kills')/Cast('total_deaths', FloatField()),
        kpr=F('total_kills')/Cast('rounds', FloatField()),
        acs=F('total_score')/Cast('rounds', FloatField()),
        adr=F('total_damage')/Cast('rounds', FloatField()),

        kast=F('kast_rounds')/Cast('rounds', FloatField()),
        k_pct=(F('rounds')-F('zero_kills'))/Cast('rounds', FloatField()),

        win_pct=(F('matches_won')+0.5*F('matches_draw'))/Cast('num_matches', FloatField()),
        round_win_pct=F('rounds_won')/Cast('rounds', FloatField()),
        attack_win_pct=F('attack_wins')/Cast('attack_rounds', FloatField()),
        defense_win_pct=F('defense_wins')/Cast('defense_rounds', FloatField()),

        kills_per_20 = (F('total_kills')/Cast('rounds', FloatField()))*20,
        deaths_per_20 = (F('total_deaths')/Cast('rounds', FloatField()))*20,
        assists_per_20 = (F('total_assists')/Cast('rounds', FloatField()))*20,

        fb_per_20 = (F('first_bloods')/Cast('rounds', FloatField()))*20,
        fd_per_20 = (F('first_deaths')/Cast('rounds', FloatField()))*20,

        attack_kdr = F('attack_kills')/Cast('attack_deaths', FloatField()), 
        attack_adr = F('attack_damage')/Cast('attack_rounds', FloatField()), 
        defense_kdr = F('defense_kills')/Cast('defense_deaths', FloatField()), 
        defense_adr = F('defense_damage')/Cast('defense_rounds', FloatField()),

        attack_kp12 = (F('attack_kills')/Cast('attack_rounds', FloatField()))*12,
        attack_dp12 = (F('attack_deaths')/Cast('attack_rounds', FloatField()))*12,
        defense_kp12 = (F('defense_kills')/Cast('defense_rounds', FloatField()))*12,
        defense_dp12 = (F('defense_deaths')/Cast('defense_rounds', FloatField()))*12,

        max_kills = Max('Kills'),
        max_deaths = Max('Deaths'),
        max_assists = Max('Assists'),
        max_kdr = Max(F('Kills') / Cast('Deaths', FloatField())),
        max_acs = Max(F('CombatScore') / F('RoundsPlayed')),
        max_adr = Max(F('TotalDamage') / Cast('RoundsPlayed', FloatField())),
        max_fb = Max('FirstBloods'),
        max_fd = Max('FirstDeaths')
    ).order_by('-num_matches')

    for p in player_splits:
        filtered_players = players.filter(Username=p['Username'])

        UserSplit = p['Username'].split('#')
        p['DisplayName'] = UserSplit[0]
        p['UserTag'] = "#"+UserSplit[1]

        p['AgentImage'] = agentImage

        p['WinLossRecord'] = "{}-{}-{}".format(p['matches_won'],p['matches_lost'],p['matches_draw'])
        p['RoundRecord'] = "{}-{}".format(p["rounds_won"],p["rounds_lost"])
        p['AttackRecord'] = "{}-{}".format(p["attack_wins"],p["attack_losses"])
        p['DefenseRecord'] = "{}-{}".format(p["defense_wins"],p["defense_losses"])

        max_kills = filtered_players.filter(Kills=p['max_kills']).order_by('-ACS','-KillDeathRatio')
        max_deaths = filtered_players.filter(Deaths=p['max_deaths']).order_by('Kills','ACS')
        max_assists = filtered_players.filter(Assists=p['max_assists']).order_by('-Kills','-ACS','-KillDeathRatio')
        max_kdr = filtered_players.annotate(kdr=F('Kills') / Cast('Deaths', FloatField()))\
                                  .filter(kdr=p['max_kdr']).order_by('-Kills','-ACS')
        max_acs = filtered_players.filter(ACS=p['max_acs']).order_by('-Kills','-KillDeathRatio')
        max_adr = filtered_players.annotate(adr=F('TotalDamage') / Cast('RoundsPlayed', FloatField()))\
                                  .filter(adr=p['max_adr']).order_by('-ACS','-Kills','-KillDeathRatio')
        max_fb = filtered_players.annotate(fb_pct=(Sum('FirstBloods')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                 .filter(FirstBloods=p['max_fb']).order_by('-fb_pct','FirstDeaths','-ACS','-Kills','-KillDeathRatio')
        max_fd = filtered_players.annotate(fd_pct=(Sum('FirstDeaths')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                 .filter(FirstDeaths=p['max_fd']).order_by('-fd_pct','FirstBloods','ACS','Kills','KillDeathRatio')

        p['max_kills_id'] = max_kills.values('Match__MatchID').first()['Match__MatchID']
        p['max_kills_player'] = max_kills.values('DisplayName').first()['DisplayName']

        p['max_deaths_id'] = max_deaths.values('Match__MatchID').first()['Match__MatchID']
        p['max_deaths_player'] = max_deaths.values('DisplayName').first()['DisplayName']

        p['max_assists_id'] = max_assists.values('Match__MatchID').first()['Match__MatchID']
        p['max_assists_player'] = max_assists.values('DisplayName').first()['DisplayName']

        p['max_kdr_id'] = max_kdr.values('Match__MatchID').first()['Match__MatchID']
        p['max_kdr_player'] = max_kdr.values('DisplayName').first()['DisplayName']

        p['max_acs_id'] = max_acs.values('Match__MatchID').first()['Match__MatchID']
        p['max_acs_player'] = max_acs.values('DisplayName').first()['DisplayName']

        p['max_adr_id'] = max_adr.values('Match__MatchID').first()['Match__MatchID']
        p['max_adr_player'] = max_adr.values('DisplayName').first()['DisplayName']

        p['max_fb_id'] = max_fb.values('Match__MatchID').first()['Match__MatchID']
        p['max_fb_player'] = max_fb.values('DisplayName').first()['DisplayName']

        p['max_fd_id'] = max_fd.values('Match__MatchID').first()['Match__MatchID']
        p['max_fd_player'] = max_fd.values('DisplayName').first()['DisplayName']

    map_splits = players.values('Match__Map').annotate(
        num_matches=Count('Match'),

        matches_won=Sum('MatchWon'),
        matches_lost=Sum('MatchLost'),
        matches_draw=Sum('MatchDraw'),

        total_kills=Sum('Kills'),
        total_deaths=Sum('Deaths'),
        total_assists=Sum('Assists'),

        total_score=Sum('CombatScore'),
        total_damage=Sum('TotalDamage'),

        first_bloods=Sum('FirstBloods'),
        first_deaths=Sum('FirstDeaths'),
        fb_fd_ratio=F('first_bloods')/Cast('first_deaths', FloatField()),

        kast_rounds=Sum('KASTRounds'),

        hs_pct=Sum(F('HS_Pct') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),
        damage_delta=Sum(F('DamageDelta') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),

        zero_kills=Sum('ZeroKillRounds'),
        one_kills=Sum('OneKillRounds'),
        two_kills=Sum('TwoKillRounds'),
        three_kills=Sum('ThreeKillRounds'),
        four_kills=Sum('FourKillRounds'),
        five_kills=Sum('FiveKillRounds'),
        six_kills=Sum('SixKillRounds'),

        attack_kills=Sum('AttackKills'),
        attack_deaths=Sum('AttackDeaths'),
        attack_damage=Sum('AttackDamage'),
        defense_kills=Sum('DefenseKills'),
        defense_deaths=Sum('DefenseDeaths'),
        defense_damage=Sum('DefenseDamage'),
        
        win_kills=Sum('WinKills'),
        win_deaths=Sum('WinDeaths'),
        win_damage=Sum('WinDamage'),
        loss_kills=Sum('LossKills'),
        loss_deaths=Sum('LossDeaths'),
        loss_damage=Sum('LossDamage'),

        attack_rounds=Sum('AttackRounds'),
        attack_wins=Sum('AttackWins'),
        attack_losses=Sum('AttackLosses'),

        defense_rounds=Sum('DefenseRounds'),
        defense_wins=Sum('DefenseWins'),
        defense_losses=Sum('DefenseLosses'),

        rounds_won=Sum('AttackWins')+Sum('DefenseWins'),
        rounds_lost=Sum('AttackLosses')+Sum('DefenseLosses'),

        rounds = Sum('RoundsPlayed'),

        kdr=F('total_kills')/Cast('total_deaths', FloatField()),
        kpr=F('total_kills')/Cast('rounds', FloatField()),
        acs=F('total_score')/Cast('rounds', FloatField()),
        adr=F('total_damage')/Cast('rounds', FloatField()),

        kast=F('kast_rounds')/Cast('rounds', FloatField()),
        k_pct=(F('rounds')-F('zero_kills'))/Cast('rounds', FloatField()),

        win_pct=(F('matches_won')+0.5*F('matches_draw'))/Cast('num_matches', FloatField()),
        round_win_pct=F('rounds_won')/Cast('rounds', FloatField()),
        attack_win_pct=F('attack_wins')/Cast('attack_rounds', FloatField()),
        defense_win_pct=F('defense_wins')/Cast('defense_rounds', FloatField()),

        kills_per_20 = (F('total_kills')/Cast('rounds', FloatField()))*20,
        deaths_per_20 = (F('total_deaths')/Cast('rounds', FloatField()))*20,
        assists_per_20 = (F('total_assists')/Cast('rounds', FloatField()))*20,

        fb_per_20 = (F('first_bloods')/Cast('rounds', FloatField()))*20,
        fd_per_20 = (F('first_deaths')/Cast('rounds', FloatField()))*20,

        attack_kdr = F('attack_kills')/Cast('attack_deaths', FloatField()), 
        attack_adr = F('attack_damage')/Cast('attack_rounds', FloatField()), 
        defense_kdr = F('defense_kills')/Cast('defense_deaths', FloatField()), 
        defense_adr = F('defense_damage')/Cast('defense_rounds', FloatField()),

        attack_kp12 = (F('attack_kills')/Cast('attack_rounds', FloatField()))*12,
        attack_dp12 = (F('attack_deaths')/Cast('attack_rounds', FloatField()))*12,
        defense_kp12 = (F('defense_kills')/Cast('defense_rounds', FloatField()))*12,
        defense_dp12 = (F('defense_deaths')/Cast('defense_rounds', FloatField()))*12,

        max_kills = Max('Kills'),
        max_deaths = Max('Deaths'),
        max_assists = Max('Assists'),
        max_kdr = Max(F('Kills') / Cast('Deaths', FloatField())),
        max_acs = Max(F('CombatScore') / F('RoundsPlayed')),
        max_adr = Max(F('TotalDamage') / Cast('RoundsPlayed', FloatField())),
        max_fb = Max('FirstBloods'),
        max_fd = Max('FirstDeaths')
    ).order_by('-num_matches')

    for p in map_splits:
        filtered_players = players.filter(Match__Map=p['Match__Map'])

        p['AgentImage'] = agentImage

        p['WinLossRecord'] = "{}-{}-{}".format(p['matches_won'],p['matches_lost'],p['matches_draw'])
        p['RoundRecord'] = "{}-{}".format(p["rounds_won"],p["rounds_lost"])
        p['AttackRecord'] = "{}-{}".format(p["attack_wins"],p["attack_losses"])
        p['DefenseRecord'] = "{}-{}".format(p["defense_wins"],p["defense_losses"])

        max_kills = filtered_players.filter(Kills=p['max_kills']).order_by('-ACS','-KillDeathRatio')
        max_deaths = filtered_players.filter(Deaths=p['max_deaths']).order_by('Kills','ACS')
        max_assists = filtered_players.filter(Assists=p['max_assists']).order_by('-Kills','-ACS','-KillDeathRatio')
        max_kdr = filtered_players.annotate(kdr=F('Kills') / Cast('Deaths', FloatField()))\
                                  .filter(kdr=p['max_kdr']).order_by('-Kills','-ACS')
        max_acs = filtered_players.filter(ACS=p['max_acs']).order_by('-Kills','-KillDeathRatio')
        max_adr = filtered_players.annotate(adr=F('TotalDamage') / Cast('RoundsPlayed', FloatField()))\
                                  .filter(adr=p['max_adr']).order_by('-ACS','-Kills','-KillDeathRatio')
        max_fb = filtered_players.annotate(fb_pct=(Sum('FirstBloods')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                 .filter(FirstBloods=p['max_fb']).order_by('-fb_pct','FirstDeaths','-ACS','-Kills','-KillDeathRatio')
        max_fd = filtered_players.annotate(fd_pct=(Sum('FirstDeaths')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                 .filter(FirstDeaths=p['max_fd']).order_by('-fd_pct','FirstBloods','ACS','Kills','KillDeathRatio')

        p['max_kills_id'] = max_kills.values('Match__MatchID').first()['Match__MatchID']
        p['max_kills_player'] = max_kills.values('DisplayName').first()['DisplayName']

        p['max_deaths_id'] = max_deaths.values('Match__MatchID').first()['Match__MatchID']
        p['max_deaths_player'] = max_deaths.values('DisplayName').first()['DisplayName']

        p['max_assists_id'] = max_assists.values('Match__MatchID').first()['Match__MatchID']
        p['max_assists_player'] = max_assists.values('DisplayName').first()['DisplayName']

        p['max_kdr_id'] = max_kdr.values('Match__MatchID').first()['Match__MatchID']
        p['max_kdr_player'] = max_kdr.values('DisplayName').first()['DisplayName']

        p['max_acs_id'] = max_acs.values('Match__MatchID').first()['Match__MatchID']
        p['max_acs_player'] = max_acs.values('DisplayName').first()['DisplayName']

        p['max_adr_id'] = max_adr.values('Match__MatchID').first()['Match__MatchID']
        p['max_adr_player'] = max_adr.values('DisplayName').first()['DisplayName']

        p['max_fb_id'] = max_fb.values('Match__MatchID').first()['Match__MatchID']
        p['max_fb_player'] = max_fb.values('DisplayName').first()['DisplayName']

        p['max_fd_id'] = max_fd.values('Match__MatchID').first()['Match__MatchID']
        p['max_fd_player'] = max_fd.values('DisplayName').first()['DisplayName']

    outcome_splits = players.values('MatchWon','MatchLost','MatchDraw').annotate(
        num_matches=Count('Match'),

        matches_won=Sum('MatchWon'),
        matches_lost=Sum('MatchLost'),
        matches_draw=Sum('MatchDraw'),

        total_kills=Sum('Kills'),
        total_deaths=Sum('Deaths'),
        total_assists=Sum('Assists'),

        total_score=Sum('CombatScore'),
        total_damage=Sum('TotalDamage'),

        first_bloods=Sum('FirstBloods'),
        first_deaths=Sum('FirstDeaths'),
        fb_fd_ratio=F('first_bloods')/Cast('first_deaths', FloatField()),

        kast_rounds=Sum('KASTRounds'),

        hs_pct=Sum(F('HS_Pct') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),
        damage_delta=Sum(F('DamageDelta') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),

        zero_kills=Sum('ZeroKillRounds'),
        one_kills=Sum('OneKillRounds'),
        two_kills=Sum('TwoKillRounds'),
        three_kills=Sum('ThreeKillRounds'),
        four_kills=Sum('FourKillRounds'),
        five_kills=Sum('FiveKillRounds'),
        six_kills=Sum('SixKillRounds'),

        attack_kills=Sum('AttackKills'),
        attack_deaths=Sum('AttackDeaths'),
        attack_damage=Sum('AttackDamage'),
        defense_kills=Sum('DefenseKills'),
        defense_deaths=Sum('DefenseDeaths'),
        defense_damage=Sum('DefenseDamage'),
        
        win_kills=Sum('WinKills'),
        win_deaths=Sum('WinDeaths'),
        win_damage=Sum('WinDamage'),
        loss_kills=Sum('LossKills'),
        loss_deaths=Sum('LossDeaths'),
        loss_damage=Sum('LossDamage'),

        attack_rounds=Sum('AttackRounds'),
        attack_wins=Sum('AttackWins'),
        attack_losses=Sum('AttackLosses'),

        defense_rounds=Sum('DefenseRounds'),
        defense_wins=Sum('DefenseWins'),
        defense_losses=Sum('DefenseLosses'),

        rounds_won=Sum('AttackWins')+Sum('DefenseWins'),
        rounds_lost=Sum('AttackLosses')+Sum('DefenseLosses'),

        rounds = Sum('RoundsPlayed'),

        kdr=F('total_kills')/Cast('total_deaths', FloatField()),
        kpr=F('total_kills')/Cast('rounds', FloatField()),
        acs=F('total_score')/Cast('rounds', FloatField()),
        adr=F('total_damage')/Cast('rounds', FloatField()),

        kast=F('kast_rounds')/Cast('rounds', FloatField()),
        k_pct=(F('rounds')-F('zero_kills'))/Cast('rounds', FloatField()),

        win_pct=(F('matches_won')+0.5*F('matches_draw'))/Cast('num_matches', FloatField()),
        round_win_pct=F('rounds_won')/Cast('rounds', FloatField()),
        attack_win_pct=F('attack_wins')/Cast('attack_rounds', FloatField()),
        defense_win_pct=F('defense_wins')/Cast('defense_rounds', FloatField()),

        kills_per_20 = (F('total_kills')/Cast('rounds', FloatField()))*20,
        deaths_per_20 = (F('total_deaths')/Cast('rounds', FloatField()))*20,
        assists_per_20 = (F('total_assists')/Cast('rounds', FloatField()))*20,

        fb_per_20 = (F('first_bloods')/Cast('rounds', FloatField()))*20,
        fd_per_20 = (F('first_deaths')/Cast('rounds', FloatField()))*20,

        attack_kdr = F('attack_kills')/Cast('attack_deaths', FloatField()), 
        attack_adr = F('attack_damage')/Cast('attack_rounds', FloatField()), 
        defense_kdr = F('defense_kills')/Cast('defense_deaths', FloatField()), 
        defense_adr = F('defense_damage')/Cast('defense_rounds', FloatField()),

        attack_kp12 = (F('attack_kills')/Cast('attack_rounds', FloatField()))*12,
        attack_dp12 = (F('attack_deaths')/Cast('attack_rounds', FloatField()))*12,
        defense_kp12 = (F('defense_kills')/Cast('defense_rounds', FloatField()))*12,
        defense_dp12 = (F('defense_deaths')/Cast('defense_rounds', FloatField()))*12,

        max_kills = Max('Kills'),
        max_deaths = Max('Deaths'),
        max_assists = Max('Assists'),
        max_kdr = Max(F('Kills') / Cast('Deaths', FloatField())),
        max_acs = Max(F('CombatScore') / F('RoundsPlayed')),
        max_adr = Max(F('TotalDamage') / Cast('RoundsPlayed', FloatField())),
        max_fb = Max('FirstBloods'),
        max_fd = Max('FirstDeaths')
    ).order_by('-MatchWon')

    for p in outcome_splits:
        filtered_players = players.filter(MatchWon=p['MatchWon'])

        p['Outcome'] = "Win" if p['MatchWon'] == 1 else "Loss" if p['MatchLost'] == 1 else "Draw"\

        p['AgentImage'] = agentImage

        p['WinLossRecord'] = "{}-{}-{}".format(p['matches_won'],p['matches_lost'],p['matches_draw'])
        p['RoundRecord'] = "{}-{}".format(p["rounds_won"],p["rounds_lost"])
        p['AttackRecord'] = "{}-{}".format(p["attack_wins"],p["attack_losses"])
        p['DefenseRecord'] = "{}-{}".format(p["defense_wins"],p["defense_losses"])

        max_kills = filtered_players.filter(Kills=p['max_kills']).order_by('-ACS','-KillDeathRatio')
        max_deaths = filtered_players.filter(Deaths=p['max_deaths']).order_by('Kills','ACS')
        max_assists = filtered_players.filter(Assists=p['max_assists']).order_by('-Kills','-ACS','-KillDeathRatio')
        max_kdr = filtered_players.annotate(kdr=F('Kills') / Cast('Deaths', FloatField()))\
                                  .filter(kdr=p['max_kdr']).order_by('-Kills','-ACS')
        max_acs = filtered_players.filter(ACS=p['max_acs']).order_by('-Kills','-KillDeathRatio')
        max_adr = filtered_players.annotate(adr=F('TotalDamage') / Cast('RoundsPlayed', FloatField()))\
                                  .filter(adr=p['max_adr']).order_by('-ACS','-Kills','-KillDeathRatio')
        max_fb = filtered_players.annotate(fb_pct=(Sum('FirstBloods')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                 .filter(FirstBloods=p['max_fb']).order_by('-fb_pct','FirstDeaths','-ACS','-Kills','-KillDeathRatio')
        max_fd = filtered_players.annotate(fd_pct=(Sum('FirstDeaths')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                 .filter(FirstDeaths=p['max_fd']).order_by('-fd_pct','FirstBloods','ACS','Kills','KillDeathRatio')

        p['max_kills_id'] = max_kills.values('Match__MatchID').first()['Match__MatchID']
        p['max_kills_player'] = max_kills.values('DisplayName').first()['DisplayName']

        p['max_deaths_id'] = max_deaths.values('Match__MatchID').first()['Match__MatchID']
        p['max_deaths_player'] = max_deaths.values('DisplayName').first()['DisplayName']

        p['max_assists_id'] = max_assists.values('Match__MatchID').first()['Match__MatchID']
        p['max_assists_player'] = max_assists.values('DisplayName').first()['DisplayName']

        p['max_kdr_id'] = max_kdr.values('Match__MatchID').first()['Match__MatchID']
        p['max_kdr_player'] = max_kdr.values('DisplayName').first()['DisplayName']

        p['max_acs_id'] = max_acs.values('Match__MatchID').first()['Match__MatchID']
        p['max_acs_player'] = max_acs.values('DisplayName').first()['DisplayName']

        p['max_adr_id'] = max_adr.values('Match__MatchID').first()['Match__MatchID']
        p['max_adr_player'] = max_adr.values('DisplayName').first()['DisplayName']

        p['max_fb_id'] = max_fb.values('Match__MatchID').first()['Match__MatchID']
        p['max_fb_player'] = max_fb.values('DisplayName').first()['DisplayName']

        p['max_fd_id'] = max_fd.values('Match__MatchID').first()['Match__MatchID']
        p['max_fd_player'] = max_fd.values('DisplayName').first()['DisplayName']
    
    context = {
        'player_splits': player_splits,
        'map_splits': map_splits,
        'outcome_splits': outcome_splits,

        'agent': agent,
        'agentImage': agentImage,
    }

    return render(request, 'match/agent/agent_splits.html', context)

def map_detail(request, map):
    players = Player.objects.filter(Team="Team A", Match__Map=map).order_by('Match__Date')

    if (players.count() == 0):
        raise Http404
    
    last_five = players.order_by('-Match__Date')[:25]
    last_ten = players.order_by('-Match__Date')[:50]
    last_twenty = players.order_by('-Match__Date')[:100]

    last_five_aggregates = CalculateAggregates(last_five,"Match__Map")
    last_ten_aggregates = CalculateAggregates(last_ten,"Match__Map")
    last_twenty_aggregates = CalculateAggregates(last_twenty,"Match__Map")
    all_aggregates = CalculateAggregates(players,"Match__Map")

    last_five_aggregates["Label"] = "Last 5 Matches"
    last_ten_aggregates["Label"] = "Last 10 Matches"
    last_twenty_aggregates["Label"] = "Last 20 Matches"
    all_aggregates["Label"] = "All Matches"
    
    context = {
        'lst': [last_five_aggregates, last_ten_aggregates, 
                last_twenty_aggregates, all_aggregates],

        'map': map,
    }

    return render(request, 'match/map/map_detail.html', context)

def map_splits(request, map):
    players = Player.objects.filter(Team="Team A", Match__Map=map).order_by('-Match__Date')

    if (players.count() == 0):
        raise Http404
    
    player_splits = players.values('Username').annotate(
        num_matches=Count('Match'),

        matches_won=Sum('MatchWon'),
        matches_lost=Sum('MatchLost'),
        matches_draw=Sum('MatchDraw'),

        total_kills=Sum('Kills'),
        total_deaths=Sum('Deaths'),
        total_assists=Sum('Assists'),

        total_score=Sum('CombatScore'),
        total_damage=Sum('TotalDamage'),

        first_bloods=Sum('FirstBloods'),
        first_deaths=Sum('FirstDeaths'),
        fb_fd_ratio=F('first_bloods')/Cast('first_deaths', FloatField()),

        kast_rounds=Sum('KASTRounds'),

        hs_pct=Sum(F('HS_Pct') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),
        damage_delta=Sum(F('DamageDelta') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),

        zero_kills=Sum('ZeroKillRounds'),
        one_kills=Sum('OneKillRounds'),
        two_kills=Sum('TwoKillRounds'),
        three_kills=Sum('ThreeKillRounds'),
        four_kills=Sum('FourKillRounds'),
        five_kills=Sum('FiveKillRounds'),
        six_kills=Sum('SixKillRounds'),

        attack_kills=Sum('AttackKills'),
        attack_deaths=Sum('AttackDeaths'),
        attack_damage=Sum('AttackDamage'),
        defense_kills=Sum('DefenseKills'),
        defense_deaths=Sum('DefenseDeaths'),
        defense_damage=Sum('DefenseDamage'),
        
        win_kills=Sum('WinKills'),
        win_deaths=Sum('WinDeaths'),
        win_damage=Sum('WinDamage'),
        loss_kills=Sum('LossKills'),
        loss_deaths=Sum('LossDeaths'),
        loss_damage=Sum('LossDamage'),

        attack_rounds=Sum('AttackRounds'),
        attack_wins=Sum('AttackWins'),
        attack_losses=Sum('AttackLosses'),

        defense_rounds=Sum('DefenseRounds'),
        defense_wins=Sum('DefenseWins'),
        defense_losses=Sum('DefenseLosses'),

        rounds_won=Sum('AttackWins')+Sum('DefenseWins'),
        rounds_lost=Sum('AttackLosses')+Sum('DefenseLosses'),

        rounds = Sum('RoundsPlayed'),

        kdr=F('total_kills')/Cast('total_deaths', FloatField()),
        kpr=F('total_kills')/Cast('rounds', FloatField()),
        acs=F('total_score')/Cast('rounds', FloatField()),
        adr=F('total_damage')/Cast('rounds', FloatField()),

        kast=F('kast_rounds')/Cast('rounds', FloatField()),
        k_pct=(F('rounds')-F('zero_kills'))/Cast('rounds', FloatField()),

        win_pct=(F('matches_won')+0.5*F('matches_draw'))/Cast('num_matches', FloatField()),
        round_win_pct=F('rounds_won')/Cast('rounds', FloatField()),
        attack_win_pct=F('attack_wins')/Cast('attack_rounds', FloatField()),
        defense_win_pct=F('defense_wins')/Cast('defense_rounds', FloatField()),

        kills_per_20 = (F('total_kills')/Cast('rounds', FloatField()))*20,
        deaths_per_20 = (F('total_deaths')/Cast('rounds', FloatField()))*20,
        assists_per_20 = (F('total_assists')/Cast('rounds', FloatField()))*20,

        fb_per_20 = (F('first_bloods')/Cast('rounds', FloatField()))*20,
        fd_per_20 = (F('first_deaths')/Cast('rounds', FloatField()))*20,

        attack_kdr = F('attack_kills')/Cast('attack_deaths', FloatField()), 
        attack_adr = F('attack_damage')/Cast('attack_rounds', FloatField()), 
        defense_kdr = F('defense_kills')/Cast('defense_deaths', FloatField()), 
        defense_adr = F('defense_damage')/Cast('defense_rounds', FloatField()),

        attack_kp12 = (F('attack_kills')/Cast('attack_rounds', FloatField()))*12,
        attack_dp12 = (F('attack_deaths')/Cast('attack_rounds', FloatField()))*12,
        defense_kp12 = (F('defense_kills')/Cast('defense_rounds', FloatField()))*12,
        defense_dp12 = (F('defense_deaths')/Cast('defense_rounds', FloatField()))*12,

        max_kills = Max('Kills'),
        max_deaths = Max('Deaths'),
        max_assists = Max('Assists'),
        max_kdr = Max(F('Kills') / Cast('Deaths', FloatField())),
        max_acs = Max(F('CombatScore') / F('RoundsPlayed')),
        max_adr = Max(F('TotalDamage') / Cast('RoundsPlayed', FloatField())),
        max_fb = Max('FirstBloods'),
        max_fd = Max('FirstDeaths')
    ).order_by('-num_matches')

    for p in player_splits:
        filtered_players = players.filter(Username=p['Username'])

        UserSplit = p['Username'].split('#')
        p['DisplayName'] = UserSplit[0]
        p['UserTag'] = "#"+UserSplit[1]

        agent_counter = Counter(filtered_players.values_list('Agent', flat=True))
        if agent_counter:
            p['TopAgent'] = agent_counter.most_common(1)[0][0]
            p['AgentString'] =", ".join(f"{key} ({value})" for key, value in agent_counter.most_common())
        p['TopAgentImage'] = AgentImage(p['TopAgent'])

        p['WinLossRecord'] = "{}-{}-{}".format(p['matches_won'],p['matches_lost'],p['matches_draw'])
        p['RoundRecord'] = "{}-{}".format(p["rounds_won"],p["rounds_lost"])
        p['AttackRecord'] = "{}-{}".format(p["attack_wins"],p["attack_losses"])
        p['DefenseRecord'] = "{}-{}".format(p["defense_wins"],p["defense_losses"])

        max_kills = filtered_players.filter(Kills=p['max_kills']).order_by('-ACS','-KillDeathRatio')
        max_deaths = filtered_players.filter(Deaths=p['max_deaths']).order_by('Kills','ACS')
        max_assists = filtered_players.filter(Assists=p['max_assists']).order_by('-Kills','-ACS','-KillDeathRatio')
        max_kdr = filtered_players.annotate(kdr=F('Kills') / Cast('Deaths', FloatField()))\
                                  .filter(kdr=p['max_kdr']).order_by('-Kills','-ACS')
        max_acs = filtered_players.filter(ACS=p['max_acs']).order_by('-Kills','-KillDeathRatio')
        max_adr = filtered_players.annotate(adr=F('TotalDamage') / Cast('RoundsPlayed', FloatField()))\
                                  .filter(adr=p['max_adr']).order_by('-ACS','-Kills','-KillDeathRatio')
        max_fb = filtered_players.annotate(fb_pct=(Sum('FirstBloods')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                 .filter(FirstBloods=p['max_fb']).order_by('-fb_pct','FirstDeaths','-ACS','-Kills','-KillDeathRatio')
        max_fd = filtered_players.annotate(fd_pct=(Sum('FirstDeaths')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                 .filter(FirstDeaths=p['max_fd']).order_by('-fd_pct','FirstBloods','ACS','Kills','KillDeathRatio')

        p['max_kills_id'] = max_kills.values('Match__MatchID').first()['Match__MatchID']
        p['max_kills_player'] = max_kills.values('DisplayName').first()['DisplayName']

        p['max_deaths_id'] = max_deaths.values('Match__MatchID').first()['Match__MatchID']
        p['max_deaths_player'] = max_deaths.values('DisplayName').first()['DisplayName']

        p['max_assists_id'] = max_assists.values('Match__MatchID').first()['Match__MatchID']
        p['max_assists_player'] = max_assists.values('DisplayName').first()['DisplayName']

        p['max_kdr_id'] = max_kdr.values('Match__MatchID').first()['Match__MatchID']
        p['max_kdr_player'] = max_kdr.values('DisplayName').first()['DisplayName']

        p['max_acs_id'] = max_acs.values('Match__MatchID').first()['Match__MatchID']
        p['max_acs_player'] = max_acs.values('DisplayName').first()['DisplayName']

        p['max_adr_id'] = max_adr.values('Match__MatchID').first()['Match__MatchID']
        p['max_adr_player'] = max_adr.values('DisplayName').first()['DisplayName']

        p['max_fb_id'] = max_fb.values('Match__MatchID').first()['Match__MatchID']
        p['max_fb_player'] = max_fb.values('DisplayName').first()['DisplayName']

        p['max_fd_id'] = max_fd.values('Match__MatchID').first()['Match__MatchID']
        p['max_fd_player'] = max_fd.values('DisplayName').first()['DisplayName']

    agent_splits = players.values('Agent').annotate(
        num_matches=Count('Match'),

        matches_won=Sum('MatchWon'),
        matches_lost=Sum('MatchLost'),
        matches_draw=Sum('MatchDraw'),

        total_kills=Sum('Kills'),
        total_deaths=Sum('Deaths'),
        total_assists=Sum('Assists'),

        total_score=Sum('CombatScore'),
        total_damage=Sum('TotalDamage'),

        first_bloods=Sum('FirstBloods'),
        first_deaths=Sum('FirstDeaths'),
        fb_fd_ratio=F('first_bloods')/Cast('first_deaths', FloatField()),

        kast_rounds=Sum('KASTRounds'),

        hs_pct=Sum(F('HS_Pct') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),
        damage_delta=Sum(F('DamageDelta') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),

        zero_kills=Sum('ZeroKillRounds'),
        one_kills=Sum('OneKillRounds'),
        two_kills=Sum('TwoKillRounds'),
        three_kills=Sum('ThreeKillRounds'),
        four_kills=Sum('FourKillRounds'),
        five_kills=Sum('FiveKillRounds'),
        six_kills=Sum('SixKillRounds'),

        attack_kills=Sum('AttackKills'),
        attack_deaths=Sum('AttackDeaths'),
        attack_damage=Sum('AttackDamage'),
        defense_kills=Sum('DefenseKills'),
        defense_deaths=Sum('DefenseDeaths'),
        defense_damage=Sum('DefenseDamage'),
        
        win_kills=Sum('WinKills'),
        win_deaths=Sum('WinDeaths'),
        win_damage=Sum('WinDamage'),
        loss_kills=Sum('LossKills'),
        loss_deaths=Sum('LossDeaths'),
        loss_damage=Sum('LossDamage'),

        attack_rounds=Sum('AttackRounds'),
        attack_wins=Sum('AttackWins'),
        attack_losses=Sum('AttackLosses'),

        defense_rounds=Sum('DefenseRounds'),
        defense_wins=Sum('DefenseWins'),
        defense_losses=Sum('DefenseLosses'),

        rounds_won=Sum('AttackWins')+Sum('DefenseWins'),
        rounds_lost=Sum('AttackLosses')+Sum('DefenseLosses'),

        rounds = Sum('RoundsPlayed'),

        kdr=F('total_kills')/Cast('total_deaths', FloatField()),
        kpr=F('total_kills')/Cast('rounds', FloatField()),
        acs=F('total_score')/Cast('rounds', FloatField()),
        adr=F('total_damage')/Cast('rounds', FloatField()),

        kast=F('kast_rounds')/Cast('rounds', FloatField()),
        k_pct=(F('rounds')-F('zero_kills'))/Cast('rounds', FloatField()),

        win_pct=(F('matches_won')+0.5*F('matches_draw'))/Cast('num_matches', FloatField()),
        round_win_pct=F('rounds_won')/Cast('rounds', FloatField()),
        attack_win_pct=F('attack_wins')/Cast('attack_rounds', FloatField()),
        defense_win_pct=F('defense_wins')/Cast('defense_rounds', FloatField()),

        kills_per_20 = (F('total_kills')/Cast('rounds', FloatField()))*20,
        deaths_per_20 = (F('total_deaths')/Cast('rounds', FloatField()))*20,
        assists_per_20 = (F('total_assists')/Cast('rounds', FloatField()))*20,

        fb_per_20 = (F('first_bloods')/Cast('rounds', FloatField()))*20,
        fd_per_20 = (F('first_deaths')/Cast('rounds', FloatField()))*20,

        attack_kdr = F('attack_kills')/Cast('attack_deaths', FloatField()), 
        attack_adr = F('attack_damage')/Cast('attack_rounds', FloatField()), 
        defense_kdr = F('defense_kills')/Cast('defense_deaths', FloatField()), 
        defense_adr = F('defense_damage')/Cast('defense_rounds', FloatField()),

        attack_kp12 = (F('attack_kills')/Cast('attack_rounds', FloatField()))*12,
        attack_dp12 = (F('attack_deaths')/Cast('attack_rounds', FloatField()))*12,
        defense_kp12 = (F('defense_kills')/Cast('defense_rounds', FloatField()))*12,
        defense_dp12 = (F('defense_deaths')/Cast('defense_rounds', FloatField()))*12,

        max_kills = Max('Kills'),
        max_deaths = Max('Deaths'),
        max_assists = Max('Assists'),
        max_kdr = Max(F('Kills') / Cast('Deaths', FloatField())),
        max_acs = Max(F('CombatScore') / F('RoundsPlayed')),
        max_adr = Max(F('TotalDamage') / Cast('RoundsPlayed', FloatField())),
        max_fb = Max('FirstBloods'),
        max_fd = Max('FirstDeaths')
    ).order_by('-num_matches')

    for p in agent_splits:
        filtered_players = players.filter(Agent=p['Agent'])

        p['AgentImage'] = AgentImage(p['Agent'])

        p['WinLossRecord'] = "{}-{}-{}".format(p['matches_won'],p['matches_lost'],p['matches_draw'])
        p['RoundRecord'] = "{}-{}".format(p["rounds_won"],p["rounds_lost"])
        p['AttackRecord'] = "{}-{}".format(p["attack_wins"],p["attack_losses"])
        p['DefenseRecord'] = "{}-{}".format(p["defense_wins"],p["defense_losses"])

        max_kills = filtered_players.filter(Kills=p['max_kills']).order_by('-ACS','-KillDeathRatio')
        max_deaths = filtered_players.filter(Deaths=p['max_deaths']).order_by('Kills','ACS')
        max_assists = filtered_players.filter(Assists=p['max_assists']).order_by('-Kills','-ACS','-KillDeathRatio')
        max_kdr = filtered_players.annotate(kdr=F('Kills') / Cast('Deaths', FloatField()))\
                                    .filter(kdr=p['max_kdr']).order_by('-Kills','-ACS')
        max_acs = filtered_players.filter(ACS=p['max_acs']).order_by('-Kills','-KillDeathRatio')
        max_adr = filtered_players.annotate(adr=F('TotalDamage') / Cast('RoundsPlayed', FloatField()))\
                                    .filter(adr=p['max_adr']).order_by('-ACS','-Kills','-KillDeathRatio')
        max_fb = filtered_players.annotate(fb_pct=(Sum('FirstBloods')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                    .filter(FirstBloods=p['max_fb']).order_by('-fb_pct','FirstDeaths','-ACS','-Kills','-KillDeathRatio')
        max_fd = filtered_players.annotate(fd_pct=(Sum('FirstDeaths')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                    .filter(FirstDeaths=p['max_fd']).order_by('-fd_pct','FirstBloods','ACS','Kills','KillDeathRatio')
        

        p['max_kills_id'] = max_kills.values('Match__MatchID').first()['Match__MatchID']
        p['max_kills_player'] = max_kills.values('DisplayName').first()['DisplayName']

        p['max_deaths_id'] = max_deaths.values('Match__MatchID').first()['Match__MatchID']
        p['max_deaths_player'] = max_deaths.values('DisplayName').first()['DisplayName']

        p['max_assists_id'] = max_assists.values('Match__MatchID').first()['Match__MatchID']
        p['max_assists_player'] = max_assists.values('DisplayName').first()['DisplayName']

        p['max_kdr_id'] = max_kdr.values('Match__MatchID').first()['Match__MatchID']
        p['max_kdr_player'] = max_kdr.values('DisplayName').first()['DisplayName']

        p['max_acs_id'] = max_acs.values('Match__MatchID').first()['Match__MatchID']
        p['max_acs_player'] = max_acs.values('DisplayName').first()['DisplayName']

        p['max_adr_id'] = max_adr.values('Match__MatchID').first()['Match__MatchID']
        p['max_adr_player'] = max_adr.values('DisplayName').first()['DisplayName']

        p['max_fb_id'] = max_fb.values('Match__MatchID').first()['Match__MatchID']
        p['max_fb_player'] = max_fb.values('DisplayName').first()['DisplayName']

        p['max_fd_id'] = max_fd.values('Match__MatchID').first()['Match__MatchID']
        p['max_fd_player'] = max_fd.values('DisplayName').first()['DisplayName']

    role_splits = players.values('Role').annotate(
        num_matches=Count('Match'),

        matches_won=Sum('MatchWon'),
        matches_lost=Sum('MatchLost'),
        matches_draw=Sum('MatchDraw'),

        total_kills=Sum('Kills'),
        total_deaths=Sum('Deaths'),
        total_assists=Sum('Assists'),

        total_score=Sum('CombatScore'),
        total_damage=Sum('TotalDamage'),

        first_bloods=Sum('FirstBloods'),
        first_deaths=Sum('FirstDeaths'),
        fb_fd_ratio=F('first_bloods')/Cast('first_deaths', FloatField()),

        kast_rounds=Sum('KASTRounds'),

        hs_pct=Sum(F('HS_Pct') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),
        damage_delta=Sum(F('DamageDelta') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),

        zero_kills=Sum('ZeroKillRounds'),
        one_kills=Sum('OneKillRounds'),
        two_kills=Sum('TwoKillRounds'),
        three_kills=Sum('ThreeKillRounds'),
        four_kills=Sum('FourKillRounds'),
        five_kills=Sum('FiveKillRounds'),
        six_kills=Sum('SixKillRounds'),

        attack_kills=Sum('AttackKills'),
        attack_deaths=Sum('AttackDeaths'),
        attack_damage=Sum('AttackDamage'),
        defense_kills=Sum('DefenseKills'),
        defense_deaths=Sum('DefenseDeaths'),
        defense_damage=Sum('DefenseDamage'),
        
        win_kills=Sum('WinKills'),
        win_deaths=Sum('WinDeaths'),
        win_damage=Sum('WinDamage'),
        loss_kills=Sum('LossKills'),
        loss_deaths=Sum('LossDeaths'),
        loss_damage=Sum('LossDamage'),

        attack_rounds=Sum('AttackRounds'),
        attack_wins=Sum('AttackWins'),
        attack_losses=Sum('AttackLosses'),

        defense_rounds=Sum('DefenseRounds'),
        defense_wins=Sum('DefenseWins'),
        defense_losses=Sum('DefenseLosses'),

        rounds_won=Sum('AttackWins')+Sum('DefenseWins'),
        rounds_lost=Sum('AttackLosses')+Sum('DefenseLosses'),

        rounds = Sum('RoundsPlayed'),

        kdr=F('total_kills')/Cast('total_deaths', FloatField()),
        kpr=F('total_kills')/Cast('rounds', FloatField()),
        acs=F('total_score')/Cast('rounds', FloatField()),
        adr=F('total_damage')/Cast('rounds', FloatField()),

        kast=F('kast_rounds')/Cast('rounds', FloatField()),
        k_pct=(F('rounds')-F('zero_kills'))/Cast('rounds', FloatField()),

        win_pct=(F('matches_won')+0.5*F('matches_draw'))/Cast('num_matches', FloatField()),
        round_win_pct=F('rounds_won')/Cast('rounds', FloatField()),
        attack_win_pct=F('attack_wins')/Cast('attack_rounds', FloatField()),
        defense_win_pct=F('defense_wins')/Cast('defense_rounds', FloatField()),

        kills_per_20 = (F('total_kills')/Cast('rounds', FloatField()))*20,
        deaths_per_20 = (F('total_deaths')/Cast('rounds', FloatField()))*20,
        assists_per_20 = (F('total_assists')/Cast('rounds', FloatField()))*20,

        fb_per_20 = (F('first_bloods')/Cast('rounds', FloatField()))*20,
        fd_per_20 = (F('first_deaths')/Cast('rounds', FloatField()))*20,

        attack_kdr = F('attack_kills')/Cast('attack_deaths', FloatField()), 
        attack_adr = F('attack_damage')/Cast('attack_rounds', FloatField()), 
        defense_kdr = F('defense_kills')/Cast('defense_deaths', FloatField()), 
        defense_adr = F('defense_damage')/Cast('defense_rounds', FloatField()),

        attack_kp12 = (F('attack_kills')/Cast('attack_rounds', FloatField()))*12,
        attack_dp12 = (F('attack_deaths')/Cast('attack_rounds', FloatField()))*12,
        defense_kp12 = (F('defense_kills')/Cast('defense_rounds', FloatField()))*12,
        defense_dp12 = (F('defense_deaths')/Cast('defense_rounds', FloatField()))*12,

        max_kills = Max('Kills'),
        max_deaths = Max('Deaths'),
        max_assists = Max('Assists'),
        max_kdr = Max(F('Kills') / Cast('Deaths', FloatField())),
        max_acs = Max(F('CombatScore') / F('RoundsPlayed')),
        max_adr = Max(F('TotalDamage') / Cast('RoundsPlayed', FloatField())),
        max_fb = Max('FirstBloods'),
        max_fd = Max('FirstDeaths')
    ).order_by('-num_matches')

    for p in role_splits:
        filtered_players = players.filter(Role=p['Role'])

        p['WinLossRecord'] = "{}-{}-{}".format(p['matches_won'],p['matches_lost'],p['matches_draw'])
        p['RoundRecord'] = "{}-{}".format(p["rounds_won"],p["rounds_lost"])
        p['AttackRecord'] = "{}-{}".format(p["attack_wins"],p["attack_losses"])
        p['DefenseRecord'] = "{}-{}".format(p["defense_wins"],p["defense_losses"])

        agent_counter = Counter(filtered_players.values_list('Agent', flat=True))
        if agent_counter:
            p['TopAgent'] = agent_counter.most_common(1)[0][0]
            p['AgentString'] =", ".join(f"{key} ({value})" for key, value in agent_counter.most_common())
        p['TopAgentImage'] = AgentImage(p['TopAgent'])

        max_kills = filtered_players.filter(Kills=p['max_kills']).order_by('-ACS','-KillDeathRatio')
        max_deaths = filtered_players.filter(Deaths=p['max_deaths']).order_by('Kills','ACS')
        max_assists = filtered_players.filter(Assists=p['max_assists']).order_by('-Kills','-ACS','-KillDeathRatio')
        max_kdr = filtered_players.annotate(kdr=F('Kills') / Cast('Deaths', FloatField()))\
                                    .filter(kdr=p['max_kdr']).order_by('-Kills','-ACS')
        max_acs = filtered_players.filter(ACS=p['max_acs']).order_by('-Kills','-KillDeathRatio')
        max_adr = filtered_players.annotate(adr=F('TotalDamage') / Cast('RoundsPlayed', FloatField()))\
                                    .filter(adr=p['max_adr']).order_by('-ACS','-Kills','-KillDeathRatio')
        max_fb = filtered_players.annotate(fb_pct=(Sum('FirstBloods')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                    .filter(FirstBloods=p['max_fb']).order_by('-fb_pct','FirstDeaths','-ACS','-Kills','-KillDeathRatio')
        max_fd = filtered_players.annotate(fd_pct=(Sum('FirstDeaths')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                    .filter(FirstDeaths=p['max_fd']).order_by('-fd_pct','FirstBloods','ACS','Kills','KillDeathRatio')
        

        p['max_kills_id'] = max_kills.values('Match__MatchID').first()['Match__MatchID']
        p['max_kills_player'] = max_kills.values('DisplayName').first()['DisplayName']

        p['max_deaths_id'] = max_deaths.values('Match__MatchID').first()['Match__MatchID']
        p['max_deaths_player'] = max_deaths.values('DisplayName').first()['DisplayName']

        p['max_assists_id'] = max_assists.values('Match__MatchID').first()['Match__MatchID']
        p['max_assists_player'] = max_assists.values('DisplayName').first()['DisplayName']

        p['max_kdr_id'] = max_kdr.values('Match__MatchID').first()['Match__MatchID']
        p['max_kdr_player'] = max_kdr.values('DisplayName').first()['DisplayName']

        p['max_acs_id'] = max_acs.values('Match__MatchID').first()['Match__MatchID']
        p['max_acs_player'] = max_acs.values('DisplayName').first()['DisplayName']

        p['max_adr_id'] = max_adr.values('Match__MatchID').first()['Match__MatchID']
        p['max_adr_player'] = max_adr.values('DisplayName').first()['DisplayName']

        p['max_fb_id'] = max_fb.values('Match__MatchID').first()['Match__MatchID']
        p['max_fb_player'] = max_fb.values('DisplayName').first()['DisplayName']

        p['max_fd_id'] = max_fd.values('Match__MatchID').first()['Match__MatchID']
        p['max_fd_player'] = max_fd.values('DisplayName').first()['DisplayName']

    outcome_splits = players.values('MatchWon','MatchLost','MatchDraw').annotate(
        num_matches=Count('Match')/5,

        matches_won=Sum('MatchWon'),
        matches_lost=Sum('MatchLost'),
        matches_draw=Sum('MatchDraw'),

        total_kills=Sum('Kills'),
        total_deaths=Sum('Deaths'),
        total_assists=Sum('Assists'),

        total_score=Sum('CombatScore'),
        total_damage=Sum('TotalDamage'),

        first_bloods=Sum('FirstBloods'),
        first_deaths=Sum('FirstDeaths'),
        fb_fd_ratio=F('first_bloods')/Cast('first_deaths', FloatField()),

        kast_rounds=Sum('KASTRounds'),

        hs_pct=Sum(F('HS_Pct') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),
        damage_delta=Sum(F('DamageDelta') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),

        zero_kills=Sum('ZeroKillRounds'),
        one_kills=Sum('OneKillRounds'),
        two_kills=Sum('TwoKillRounds'),
        three_kills=Sum('ThreeKillRounds'),
        four_kills=Sum('FourKillRounds'),
        five_kills=Sum('FiveKillRounds'),
        six_kills=Sum('SixKillRounds'),

        attack_kills=Sum('AttackKills'),
        attack_deaths=Sum('AttackDeaths'),
        attack_damage=Sum('AttackDamage'),
        defense_kills=Sum('DefenseKills'),
        defense_deaths=Sum('DefenseDeaths'),
        defense_damage=Sum('DefenseDamage'),
        
        win_kills=Sum('WinKills'),
        win_deaths=Sum('WinDeaths'),
        win_damage=Sum('WinDamage'),
        loss_kills=Sum('LossKills'),
        loss_deaths=Sum('LossDeaths'),
        loss_damage=Sum('LossDamage'),

        attack_rounds=Sum('AttackRounds'),
        attack_wins=Sum('AttackWins'),
        attack_losses=Sum('AttackLosses'),

        defense_rounds=Sum('DefenseRounds'),
        defense_wins=Sum('DefenseWins'),
        defense_losses=Sum('DefenseLosses'),

        rounds_won=Sum('AttackWins')+Sum('DefenseWins'),
        rounds_lost=Sum('AttackLosses')+Sum('DefenseLosses'),

        rounds = Sum('RoundsPlayed'),

        kdr=F('total_kills')/Cast('total_deaths', FloatField()),
        kpr=F('total_kills')/Cast('rounds', FloatField()),
        acs=F('total_score')/Cast('rounds', FloatField()),
        adr=F('total_damage')/Cast('rounds', FloatField()),

        kast=F('kast_rounds')/Cast('rounds', FloatField()),
        k_pct=(F('rounds')-F('zero_kills'))/Cast('rounds', FloatField()),

        win_pct=(F('matches_won')+0.5*F('matches_draw'))/Cast('num_matches', FloatField()),
        round_win_pct=F('rounds_won')/Cast('rounds', FloatField()),
        attack_win_pct=F('attack_wins')/Cast('attack_rounds', FloatField()),
        defense_win_pct=F('defense_wins')/Cast('defense_rounds', FloatField()),

        kills_per_20 = (F('total_kills')/Cast('rounds', FloatField()))*20,
        deaths_per_20 = (F('total_deaths')/Cast('rounds', FloatField()))*20,
        assists_per_20 = (F('total_assists')/Cast('rounds', FloatField()))*20,

        fb_per_20 = (F('first_bloods')/Cast('rounds', FloatField()))*20,
        fd_per_20 = (F('first_deaths')/Cast('rounds', FloatField()))*20,

        attack_kdr = F('attack_kills')/Cast('attack_deaths', FloatField()), 
        attack_adr = F('attack_damage')/Cast('attack_rounds', FloatField()), 
        defense_kdr = F('defense_kills')/Cast('defense_deaths', FloatField()), 
        defense_adr = F('defense_damage')/Cast('defense_rounds', FloatField()),

        attack_kp12 = (F('attack_kills')/Cast('attack_rounds', FloatField()))*12,
        attack_dp12 = (F('attack_deaths')/Cast('attack_rounds', FloatField()))*12,
        defense_kp12 = (F('defense_kills')/Cast('defense_rounds', FloatField()))*12,
        defense_dp12 = (F('defense_deaths')/Cast('defense_rounds', FloatField()))*12,

        max_kills = Max('Kills'),
        max_deaths = Max('Deaths'),
        max_assists = Max('Assists'),
        max_kdr = Max(F('Kills') / Cast('Deaths', FloatField())),
        max_acs = Max(F('CombatScore') / F('RoundsPlayed')),
        max_adr = Max(F('TotalDamage') / Cast('RoundsPlayed', FloatField())),
        max_fb = Max('FirstBloods'),
        max_fd = Max('FirstDeaths')
    ).order_by('-MatchWon')

    for p in outcome_splits:
        filtered_players = players.filter(MatchWon=p['MatchWon'])

        p['Outcome'] = "Win" if p['MatchWon'] == 1 else "Loss" if p['MatchLost'] == 1 else "Draw"\

        p['WinLossRecord'] = "{}-{}-{}".format(p['matches_won'],p['matches_lost'],p['matches_draw'])
        p['RoundRecord'] = "{}-{}".format(p["rounds_won"],p["rounds_lost"])
        p['AttackRecord'] = "{}-{}".format(p["attack_wins"],p["attack_losses"])
        p['DefenseRecord'] = "{}-{}".format(p["defense_wins"],p["defense_losses"])

        max_kills = filtered_players.filter(Kills=p['max_kills']).order_by('-ACS','-KillDeathRatio')
        max_deaths = filtered_players.filter(Deaths=p['max_deaths']).order_by('Kills','ACS')
        max_assists = filtered_players.filter(Assists=p['max_assists']).order_by('-Kills','-ACS','-KillDeathRatio')
        max_kdr = filtered_players.annotate(kdr=F('Kills') / Cast('Deaths', FloatField()))\
                                  .filter(kdr=p['max_kdr']).order_by('-Kills','-ACS')
        max_acs = filtered_players.filter(ACS=p['max_acs']).order_by('-Kills','-KillDeathRatio')
        max_adr = filtered_players.annotate(adr=F('TotalDamage') / Cast('RoundsPlayed', FloatField()))\
                                  .filter(adr=p['max_adr']).order_by('-ACS','-Kills','-KillDeathRatio')
        max_fb = filtered_players.annotate(fb_pct=(Sum('FirstBloods')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                 .filter(FirstBloods=p['max_fb']).order_by('-fb_pct','FirstDeaths','-ACS','-Kills','-KillDeathRatio')
        max_fd = filtered_players.annotate(fd_pct=(Sum('FirstDeaths')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                 .filter(FirstDeaths=p['max_fd']).order_by('-fd_pct','FirstBloods','ACS','Kills','KillDeathRatio')

        p['max_kills_id'] = max_kills.values('Match__MatchID').first()['Match__MatchID']
        p['max_kills_player'] = max_kills.values('DisplayName').first()['DisplayName']

        p['max_deaths_id'] = max_deaths.values('Match__MatchID').first()['Match__MatchID']
        p['max_deaths_player'] = max_deaths.values('DisplayName').first()['DisplayName']

        p['max_assists_id'] = max_assists.values('Match__MatchID').first()['Match__MatchID']
        p['max_assists_player'] = max_assists.values('DisplayName').first()['DisplayName']

        p['max_kdr_id'] = max_kdr.values('Match__MatchID').first()['Match__MatchID']
        p['max_kdr_player'] = max_kdr.values('DisplayName').first()['DisplayName']

        p['max_acs_id'] = max_acs.values('Match__MatchID').first()['Match__MatchID']
        p['max_acs_player'] = max_acs.values('DisplayName').first()['DisplayName']

        p['max_adr_id'] = max_adr.values('Match__MatchID').first()['Match__MatchID']
        p['max_adr_player'] = max_adr.values('DisplayName').first()['DisplayName']

        p['max_fb_id'] = max_fb.values('Match__MatchID').first()['Match__MatchID']
        p['max_fb_player'] = max_fb.values('DisplayName').first()['DisplayName']

        p['max_fd_id'] = max_fd.values('Match__MatchID').first()['Match__MatchID']
        p['max_fd_player'] = max_fd.values('DisplayName').first()['DisplayName']
    
    context = {
        'player_splits': player_splits,
        'role_splits': role_splits,
        'agent_splits': agent_splits,
        'outcome_splits': outcome_splits,

        'map': map,
    }

    return render(request, 'match/map/map_splits.html', context)

### RECORDS


from itertools import groupby
from operator import itemgetter

from operator import lt, gt, le, ge, eq
from datetime import timedelta
from collections import defaultdict

def BestActiveStreak(field, value, op):
    players = Player.objects.filter(Team="Team A").order_by('Username', '-Match__Date').select_related('Match')

    # Use defaultdict to group users and their matches.
    user_groups = defaultdict(list)
    for player in players:
        user_groups[player.Username].append(player)

    active_streaks = []

    for username, user_group in user_groups.items():
        streak = 0
        end_date = None
        agents = []
        for i, player in enumerate(user_group):
            if op(getattr(player,field),value):
                if streak == 0:
                    end_date = player.Match.Date
                streak += 1
                agents.append(player.Agent)

                if i == len(user_group) - 1 and streak > 0:  # end of the list
                    most_common_agent = max(set(agents), key=agents.count)
                    active_streaks.append({
                        'Username': username,
                        'DisplayName': player.DisplayName,
                        'UserTag': player.UserTag,
                        'Agent': most_common_agent,
                        'AgentImage': AgentImage(most_common_agent),
                        'Streak': streak,
                        'StartDate': player.Match.Date,
                        'EndDate': end_date,
                        'EndDateHidden': end_date + timedelta(days=1),
                        'Active': True
                    })
            else:
                if streak > 0:
                    most_common_agent = max(set(agents), key=agents.count)
                    active_streaks.append({
                        'Username': username,
                        'DisplayName': player.DisplayName,
                        'UserTag': player.UserTag,
                        'Agent': most_common_agent,
                        'AgentImage': AgentImage(most_common_agent),
                        'Streak': streak,
                        'StartDate': player.Match.Date,
                        'EndDate': end_date,
                        'EndDateHidden': end_date + timedelta(days=1),
                        'Active': True
                    })
                break

    # Sort by streak
    active_streaks.sort(key=itemgetter('Streak'), reverse=True)
    top_active_streak = active_streaks[0]['Streak'] if active_streaks else None
    top_active_streaks = [streak for streak in active_streaks if streak['Streak'] == top_active_streak]
    top_active_streaks.sort(key=itemgetter('StartDate'))

    return top_active_streaks

def BestStreak(field, value, op):
    players = Player.objects.filter(Team="Team A").order_by('Username', 'Match__Date').select_related('Match')

    # Use defaultdict to group users and their matches.
    user_groups = defaultdict(list)
    for player in players:
        user_groups[player.Username].append(player)

    all_streaks = []

    for username, user_group in user_groups.items():
        streak = 0
        start_date = None
        agents = []
        for i, player in enumerate(user_group):
            if op(getattr(player,field),value):
                if streak == 0:
                    start_date = player.Match.Date
                streak += 1
                agents.append(player.Agent)
            else:
                if streak > 0:
                    most_common_agent = max(set(agents), key=agents.count)
                    all_streaks.append({
                        'Username': username,
                        'DisplayName': player.DisplayName,
                        'UserTag': player.UserTag,
                        'Agent': most_common_agent,
                        'AgentImage': AgentImage(most_common_agent),
                        'Streak': streak,
                        'StartDate': start_date,
                        'EndDate': player.Match.Date if i > 0 else start_date,
                        'EndDateHidden': player.Match.Date - timedelta(minutes=1),
                        'Active': False
                    })
                streak = 0
                start_date = None
                agents = []

            # Handle the case when the streak is at the end of the list.
            if i == len(user_group) - 1 and streak > 0:  
                most_common_agent = max(set(agents), key=agents.count)
                all_streaks.append({
                    'Username': username,
                    'DisplayName': player.DisplayName,
                    'UserTag': player.UserTag,
                    'Agent': most_common_agent,
                    'AgentImage': AgentImage(most_common_agent),
                    'Streak': streak,
                    'StartDate': start_date,
                    'EndDate': player.Match.Date,
                    'EndDateHidden': player.Match.Date - timedelta(minutes=1),
                    'Active': True
                })

    # Sort by streak
    all_streaks.sort(key=itemgetter('Streak'), reverse=True)
    top_streak = all_streaks[0]['Streak'] if all_streaks else None
    top_streaks = [streak for streak in all_streaks if streak['Streak'] == top_streak]
    top_streaks.sort(key=itemgetter('StartDate'))

    return top_streaks

def BestGame(field,sort="desc",model="Player"):
    if model == "Player":
        if sort == "desc":
            players = Player.objects.filter(Team="Team A").order_by('-'+field)
        else:
            players = Player.objects.filter(Team="Team A").order_by(field)
        top_field = getattr(players[0],field) if players else None
        qual_players = players.filter(**{field:top_field})
        top_games = [{'Username': player.Username,
                    'Value': getattr(player, field),
                    'Date': player.Match.Date,
                    'DisplayName': player.DisplayName,
                    'UserTag': player.UserTag,
                    'Agent': player.Agent,
                    'AgentImage': player.AgentImage,
                    'MatchID': player.Match.MatchID,
                    } for player in qual_players if getattr(player, field) == top_field]
    else:
        if sort == "desc":
            matches = Match.objects.order_by('-'+field)
        else:
            matches = Match.objects.order_by(field)
        top_field = getattr(matches[0],field) if matches else None
        qual_matches = matches.filter(**{field:top_field})
        top_games = [{'MatchID': match.MatchID,
                    'Value': getattr(match, field),
                    'Date': match.Date,
                    'Map': match.Map,
                    'Score': match.Score,
                    'TeamOneScore': match.TeamOneScore,
                    'TeamTwoScore': match.TeamTwoScore,
                    'RoundsPlayed': match.RoundsPlayed,
                    'TeamOneWon': match.TeamOneWon,
                    'Players': match.Players,
                    } for match in qual_matches if getattr(match, field) == top_field]
    
    top_games = sorted(top_games, key=lambda x: x['Date'])

    return top_games

from collections import deque
def BestSpan(field, n, maximum=True):
    players = Player.objects.filter(Team="Team A").order_by('Username', 'Match__Date').select_related('Match')

    user_groups = defaultdict(list)
    for player in players:
        user_groups[player.Username].append(player)

    all_spans = []

    for username, user_group in user_groups.items():
        queue = deque(maxlen=n)
        total_field = 0
        prev_span = None
        agent_counts = defaultdict(int) # to store agent frequencies

        for i, player in enumerate(user_group):
            total_field += getattr(player, field)
            queue.append(player)
            agent_counts[player.Agent] += 1  # increment agent count

            if len(queue) == n:
                most_common_agent = max(agent_counts, key=agent_counts.get)  # get most common agent

                new_span = {
                    'Username': username,
                    'DisplayName': queue[0].DisplayName,
                    'UserTag': queue[0].UserTag,
                    'Agent': most_common_agent,  # set the most common agent
                    'AgentImage': AgentImage(most_common_agent),
                    'SpanLength': n,
                    'Span': total_field,
                    'StartDate': queue[0].Match.Date,
                    'EndDate': queue[-1].Match.Date,
                    'EndIndex': i,
                    'Active': i == len(user_group) - 1
                }

                if prev_span is None or prev_span['EndIndex'] < i - n + 1 or (maximum and new_span['Span'] > prev_span['Span']) or (not maximum and new_span['Span'] < prev_span['Span']):
                    prev_span = new_span
                    all_spans.append(prev_span)

                total_field -= getattr(queue[0], field)
                agent_counts[queue[0].Agent] -= 1  # decrement agent count for the oldest game in the queue

    all_spans.sort(key=itemgetter('Span'), reverse=maximum)
    top_span = all_spans[0]['Span'] if all_spans else None
    top_spans = [span for span in all_spans if span['Span'] == top_span]
    top_spans.sort(key=itemgetter('StartDate'))

    return top_spans

def BestSpanRatio(field1, field2, n, maximum=True):
    players = Player.objects.filter(Team="Team A").order_by('Username', 'Match__Date').select_related('Match')

    user_groups = defaultdict(list)
    for player in players:
        user_groups[player.Username].append(player)

    all_spans = []

    for username, user_group in user_groups.items():
        queue = deque(maxlen=n)
        total_field1 = 0
        total_field2 = 0
        agent_counts = defaultdict(int)  # to store agent frequencies

        for i, player in enumerate(user_group):
            total_field1 += getattr(player, field1)
            total_field2 += getattr(player, field2)
            queue.append(player)
            agent_counts[player.Agent] += 1  # increment agent count

            if len(queue) == n:
                most_common_agent = max(agent_counts, key=agent_counts.get)  # get most common agent

                span = {
                    'Username': username,
                    'DisplayName': queue[0].DisplayName,
                    'UserTag': queue[0].UserTag,
                    'Agent': most_common_agent,  # set the most common agent
                    'AgentImage': AgentImage(most_common_agent),
                    'SpanLength': n,
                    'Span': total_field1 / total_field2 if total_field2 != 0 else 0,
                    'StartDate': queue[0].Match.Date,
                    'EndDate': queue[-1].Match.Date,
                    'Active': i == len(user_group) - 1
                }
                all_spans.append(span)
                total_field1 -= getattr(queue[0], field1)
                total_field2 -= getattr(queue[0], field2)
                agent_counts[queue[0].Agent] -= 1  # decrement agent count for the oldest game in the queue

    all_spans.sort(key=itemgetter('Span'), reverse=maximum)
    top_span = all_spans[0]['Span'] if all_spans else None
    top_spans = [span for span in all_spans if span['Span'] == top_span]
    top_spans.sort(key=itemgetter('StartDate'))

    return top_spans

@cache_page(60*10)
def record_overview(request):
    BiggestWin = BestGame("ScoreDifferential",model="match")
    BiggestLoss = BestGame("ScoreDifferential",sort="asc",model="match")

    LongestGame = BestGame("RoundsPlayed",model="match")

    TotalGames = len(Match.objects.all())

    Wins = len(Match.objects.filter(TeamOneWon=1))
    Losses = len(Match.objects.filter(TeamOneLost=1))
    Draws = len(Match.objects.filter(MatchDraw=1))
    Record = "{}-{}-{}".format(Wins,Losses,Draws)

    # Who has played most / least
    UsernameCounts = Player.objects.filter(Team="Team A").values('Username').annotate(
                        Count=Count('Username')
                     ).order_by('-Count')
    
    TopPlayerUsername = UsernameCounts[0]['Username']
    TopPlayerDisplayName = TopPlayerUsername.split("#")[0]
    TopPlayerGames = UsernameCounts[0]['Count']

    UsernameCounts = UsernameCounts.order_by('Count')

    BotPlayerUsername = UsernameCounts[0]['Username']
    BotPlayerDisplayName = BotPlayerUsername.split("#")[0]
    BotPlayerGames = UsernameCounts[0]['Count']

    # Get most frequent agent of the player who played most / least
    PlayerAgentCounts = Player.objects.filter(Team="Team A",Username=TopPlayerUsername).values('Agent').annotate(
                        Count=Count('Agent')
                     ).order_by('-Count')
    TopPlayerAgent = PlayerAgentCounts[0]['Agent']
    TopPlayerAgentImage = AgentImage(TopPlayerAgent)

    PlayerAgentCounts = Player.objects.filter(Team="Team A",Username=BotPlayerUsername).values('Agent').annotate(
                        Count=Count('Agent')
                     ).order_by('-Count')
    BotPlayerAgent = PlayerAgentCounts[0]['Agent']
    BotPlayerAgentImage = AgentImage(BotPlayerAgent)

    # Get most and least played agents

    AgentCounts = []
    for x in agent_map.values():
        agent_filter = Player.objects.filter(Team="Team A",
                                             Agent=x)
        AgentCounts.append({"Agent":x, "Count":len(agent_filter)})

    AgentCounts = sorted(AgentCounts, key=lambda x: x['Count'], reverse=True)

    TopAgent = AgentCounts[0]['Agent']
    TopAgentImage = AgentImage(TopAgent)
    TopAgentCount = AgentCounts[0]['Count']

    BotAgent = AgentCounts[-1]['Agent']
    BotAgentImage = AgentImage(BotAgent)
    BotAgentCount = AgentCounts[-1]['Count']

    context = {
        "TotalGames": TotalGames,
        "Wins": Wins,
        "Losses": Losses,
        "Draws": Draws,
        "Record": Record,

        "BiggestWin": BiggestWin,
        "BiggestLoss": BiggestLoss,
        "LongestGame": LongestGame,

        "TopPlayerUsername": TopPlayerUsername,
        "TopPlayerDisplayName": TopPlayerDisplayName,
        "TopPlayerAgent": TopPlayerAgent,
        "TopPlayerAgentImage": TopPlayerAgentImage,
        "TopPlayerGames": TopPlayerGames,

        "BotPlayerUsername": BotPlayerUsername,
        "BotPlayerDisplayName": BotPlayerDisplayName,
        "BotPlayerAgent": BotPlayerAgent,
        "BotPlayerAgentImage": BotPlayerAgentImage,
        "BotPlayerGames": BotPlayerGames,

        "TopAgent": TopAgent,
        "TopAgentImage": TopAgentImage,
        "TopAgentCount": TopAgentCount,

        "BotAgent": BotAgent,
        "BotAgentImage": BotAgentImage,
        "BotAgentCount": BotAgentCount
    }

    return render(request, "match/recordbook/record_overview.html", context)

@cache_page(60*10)
def record_game(request):
    players = Player.objects.filter(Team="Team A").annotate(
        k_pct = (Sum('RoundsPlayed') - Sum('ZeroKillRounds')) / (Cast(Sum('RoundsPlayed'), FloatField())),
        fb_pct = (Sum('FirstBloods')) / (Cast(Sum('RoundsPlayed'), FloatField())),
        fd_pct = (Sum('FirstDeaths')) / (Cast(Sum('RoundsPlayed'), FloatField())),
        kpr = (Sum('Kills')) / (Cast(Sum('RoundsPlayed'), FloatField())),
    )

    MostKills = BestGame("Kills")
    LeastKills = BestGame("Kills","asc")

    players = players.order_by('-kpr')
    qual_players = players.filter(kpr=players.first().kpr)
    HighestKPR = [{'Username': players.first().Username,
                    'Value': players.first().kpr,
                    'Date': players.first().Match.Date,
                    'DisplayName': players.first().DisplayName,
                    'UserTag': players.first().UserTag,
                    'Agent': players.first().Agent,
                    'AgentImage': AgentImage(players.first().Agent),
                    'MatchID': players.first().Match.MatchID,
                    } for player in qual_players if getattr(player, "kpr") == players.first().kpr]
    qual_players = players.filter(kpr=players.last().kpr)
    LowestKPR = [{'Username': players.last().Username,
                    'Value': players.last().kpr,
                    'Date': players.last().Match.Date,
                    'DisplayName': players.last().DisplayName,
                    'UserTag': players.last().UserTag,
                    'Agent': players.last().Agent,
                    'AgentImage': AgentImage(players.last().Agent),
                    'MatchID': players.last().Match.MatchID,
                    } for player in qual_players if getattr(player, "kpr") == players.last().kpr]

    MostDeaths = BestGame("Deaths")
    LeastDeaths = BestGame("Deaths","asc")

    MostAssists = BestGame("Assists")
    LeastAssists = BestGame("Assists","asc")

    MostAssists = BestGame("Assists")
    LeastAssists = BestGame("Assists","asc")

    BestACS = BestGame("ACS")
    WorstACS = BestGame("ACS","asc")

    BestKDR = BestGame("KillDeathRatio")
    WorstKDR = BestGame("KillDeathRatio","asc")

    BestADR = BestGame("AverageDamage")
    WorstADR = BestGame("AverageDamage","asc")

    MostFB = BestGame("FirstBloods")
    MostFD = BestGame("FirstDeaths")

    players = players.order_by('-fb_pct')
    qual_players = players.filter(fb_pct=players.first().fb_pct)
    HighestFB_Pct = [{'Username': players.first().Username,
                    'Value': players.first().fb_pct,
                    'Date': players.first().Match.Date,
                    'DisplayName': players.first().DisplayName,
                    'UserTag': players.first().UserTag,
                    'Agent': players.first().Agent,
                    'AgentImage': AgentImage(players.first().Agent),
                    'MatchID': players.first().Match.MatchID,
                    } for player in qual_players if getattr(player, "fb_pct") == players.first().fb_pct]
    players = players.order_by('-fd_pct')
    qual_players = players.filter(fd_pct=players.first().fd_pct)
    HighestFD_Pct = [{'Username': players.first().Username,
                    'Value': players.first().fd_pct,
                    'Date': players.first().Match.Date,
                    'DisplayName': players.first().DisplayName,
                    'UserTag': players.first().UserTag,
                    'Agent': players.first().Agent,
                    'AgentImage': AgentImage(players.first().Agent),
                    'MatchID': players.first().Match.MatchID,
                    } for player in qual_players if getattr(player, "fd_pct") == players.first().fd_pct]

    players = players.order_by('-k_pct')
    qual_players = players.filter(k_pct=players.first().k_pct)
    HighestK_Pct = [{'Username': players.first().Username,
                    'Value': players.first().k_pct,
                    'Date': players.first().Match.Date,
                    'DisplayName': players.first().DisplayName,
                    'UserTag': players.first().UserTag,
                    'Agent': players.first().Agent,
                    'AgentImage': AgentImage(players.first().Agent),
                    'MatchID': players.first().Match.MatchID,
                    } for player in qual_players if getattr(player, "k_pct") == players.first().k_pct]
    qual_players = players.filter(k_pct=players.last().k_pct)
    LowestK_Pct = [{'Username': players.last().Username,
                    'Value': players.last().k_pct,
                    'Date': players.last().Match.Date,
                    'DisplayName': players.last().DisplayName,
                    'UserTag': players.last().UserTag,
                    'Agent': players.last().Agent,
                    'AgentImage': AgentImage(players.last().Agent),
                    'MatchID': players.last().Match.MatchID,
                    } for player in qual_players if getattr(player, "k_pct") == players.last().k_pct]

    HighestHS_Pct = BestGame("HS_Pct")
    LowestHS_Pct = BestGame("HS_Pct","asc")

    HighestDD = BestGame("DamageDelta")
    LowestDD = BestGame("DamageDelta","asc")

    context = {
        "MostKills": MostKills,
        "LeastKills": LeastKills,
        "HighestKPR": HighestKPR,
        "LowestKPR": LowestKPR,
        "MostDeaths": MostDeaths,
        "LeastDeaths": LeastDeaths,
        "MostAssists": MostAssists,
        "LeastAssists": LeastAssists,
        "BestADR": BestADR,
        "WorstADR": WorstADR,
        "BestKDR": BestKDR,
        "WorstKDR": WorstKDR,
        "BestACS": BestACS,
        "WorstACS": WorstACS,
        "MostFB": MostFB,
        "MostFD": MostFD,
        "HighestFB_Pct": HighestFB_Pct,
        "HighestFD_Pct": HighestFD_Pct,
        "HighestK_Pct": HighestK_Pct,
        "LowestK_Pct": LowestK_Pct,
        "HighestHS_Pct": HighestHS_Pct,
        "LowestHS_Pct": LowestHS_Pct,
        "HighestDD": HighestDD,
        "LowestDD": LowestDD,
    }

    return render(request, "match/recordbook/record_game.html", context)

@cache_page(60*10)
def record_streak(request):

    streaks = {
        "Kills_Gr_10_Streak": BestStreak("Kills", 10, ge),
        "Kills_Gr_15_Streak": BestStreak("Kills", 15, ge),
        "Kills_Gr_20_Streak": BestStreak("Kills", 20, ge),
        "Kills_Gr_25_Streak": BestStreak("Kills", 25, ge),
        #"Kills_Gr_30_Streak": BestStreak("Kills", 30, ge),
        "WonGameStreak": BestStreak("MatchWon", 1, ge),
        "LostGameStreak": BestStreak("MatchLost", 1, ge),
        "MVPStreak": BestStreak("MVP", 1, eq),
        "TopTwoStreak": BestStreak("ACS_Rank", 2, le),
        "TopThreeStreak": BestStreak("ACS_Rank", 3, le),
        "TopFourStreak": BestStreak("ACS_Rank", 4, le),
        "ACS_Gr_100_Streak": BestStreak("ACS", 100, ge),
        "ACS_Gr_150_Streak": BestStreak("ACS", 150, ge),
        "ACS_Gr_200_Streak": BestStreak("ACS", 200, ge),
        "ACS_Gr_250_Streak": BestStreak("ACS", 250, ge),
        "ACS_Gr_300_Streak": BestStreak("ACS", 300, ge),
        #"ACS_Gr_350_Streak": BestStreak("ACS", 350, ge),
        "ADR_Gr_100_Streak": BestStreak("ExactADR", 100, ge),
        "ADR_Gr_125_Streak": BestStreak("ExactADR", 125, ge),
        "ADR_Gr_150_Streak": BestStreak("ExactADR", 150, ge),
        "ADR_Gr_175_Streak": BestStreak("ExactADR", 175, ge),
        "ADR_Gr_200_Streak": BestStreak("ExactADR", 200, ge),
        "KDR_Greq_1_Streak": BestStreak("KillDeathRatio", 1, ge),
        "KDR_Gr_1_Streak": BestStreak("KillDeathRatio", 1, gt),
        "KDR_Gr_1d25_Streak": BestStreak("KillDeathRatio", 1.25, ge),
        "KDR_Gr_1d5_Streak": BestStreak("KillDeathRatio", 1.5, ge),
        "KDR_Gr_1d75_Streak": BestStreak("KillDeathRatio", 1.75, ge),
        "KDR_Gr_2_Streak": BestStreak("KillDeathRatio", 2.00, ge),
        "KPR_Gr_0d5_Streak": BestStreak("KillsPerRound", 0.5, ge),
        "KPR_Gr_0d75_Streak": BestStreak("KillsPerRound", 0.75, ge),
        "KPR_Greq_1_Streak": BestStreak("KillsPerRound", 1, ge),
        "KPR_Gr_1_Streak": BestStreak("KillsPerRound", 1, gt),
        "FB_Eq_0_Streak": BestStreak("FirstBloods", 1, lt),
        "FB_Gr_1_Streak": BestStreak("FirstBloods", 1, ge),
        "FB_Gr_2_Streak": BestStreak("FirstBloods", 2, ge),
        "FB_Gr_3_Streak": BestStreak("FirstBloods", 3, ge),
        "FB_Gr_4_Streak": BestStreak("FirstBloods", 4, ge),
        "FB_Gr_5_Streak": BestStreak("FirstBloods", 5, ge),
        "FD_Eq_0_Streak": BestStreak("FirstDeaths", 1, lt),
        "FD_Le_1_Streak": BestStreak("FirstDeaths", 1, le),
        "FD_Le_2_Streak": BestStreak("FirstDeaths", 2, le),
        "FD_Le_3_Streak": BestStreak("FirstDeaths", 3, le),
        "FD_Le_4_Streak": BestStreak("FirstDeaths", 4, le),
        "FD_Le_5_Streak": BestStreak("FirstDeaths", 5, le),
    }

    streaks_active = {
        "Kills_Gr_10_Streak": BestActiveStreak("Kills", 10, ge),
        "Kills_Gr_15_Streak": BestActiveStreak("Kills", 15, ge),
        "Kills_Gr_20_Streak": BestActiveStreak("Kills", 20, ge),
        "Kills_Gr_25_Streak": BestActiveStreak("Kills", 25, ge),
        #"Kills_Gr_30_Streak": BestActiveStreak("Kills", 30, ge),
        "WonGameStreak": BestActiveStreak("MatchWon", 1, ge),
        "LostGameStreak": BestActiveStreak("MatchLost", 1, ge),
        "MVPStreak": BestActiveStreak("MVP", 1, eq),
        "TopTwoStreak": BestActiveStreak("ACS_Rank", 2, le),
        "TopThreeStreak": BestActiveStreak("ACS_Rank", 3, le),
        "TopFourStreak": BestActiveStreak("ACS_Rank", 4, le),
        "ACS_Gr_100_Streak": BestActiveStreak("ACS", 100, ge),
        "ACS_Gr_150_Streak": BestActiveStreak("ACS", 150, ge),
        "ACS_Gr_200_Streak": BestActiveStreak("ACS", 200, ge),
        "ACS_Gr_250_Streak": BestActiveStreak("ACS", 250, ge),
        "ACS_Gr_300_Streak": BestActiveStreak("ACS", 300, ge),
        #"ACS_Gr_350_Streak": BestStreak("ACS", 350, ge),
        "ADR_Gr_100_Streak": BestActiveStreak("ExactADR", 100, ge),
        "ADR_Gr_125_Streak": BestActiveStreak("ExactADR", 125, ge),
        "ADR_Gr_150_Streak": BestActiveStreak("ExactADR", 150, ge),
        "ADR_Gr_175_Streak": BestActiveStreak("ExactADR", 175, ge),
        "ADR_Gr_200_Streak": BestActiveStreak("ExactADR", 200, ge),
        "KDR_Greq_1_Streak": BestActiveStreak("KillDeathRatio", 1, ge),
        "KDR_Gr_1_Streak": BestActiveStreak("KillDeathRatio", 1, gt),
        "KDR_Gr_1d25_Streak": BestActiveStreak("KillDeathRatio", 1.25, ge),
        "KDR_Gr_1d5_Streak": BestActiveStreak("KillDeathRatio", 1.5, ge),
        "KDR_Gr_1d75_Streak": BestActiveStreak("KillDeathRatio", 1.75, ge),
        "KDR_Gr_2_Streak": BestActiveStreak("KillDeathRatio", 2.00, ge),
        "KPR_Gr_0d5_Streak": BestActiveStreak("KillsPerRound", 0.5, ge),
        "KPR_Gr_0d75_Streak": BestActiveStreak("KillsPerRound", 0.75, ge),
        "KPR_Greq_1_Streak": BestActiveStreak("KillsPerRound", 1, ge),
        "KPR_Gr_1_Streak": BestActiveStreak("KillsPerRound", 1, gt),
        "FB_Eq_0_Streak": BestActiveStreak("FirstBloods", 1, lt),
        "FB_Gr_1_Streak": BestActiveStreak("FirstBloods", 1, ge),
        "FB_Gr_2_Streak": BestActiveStreak("FirstBloods", 2, ge),
        "FB_Gr_3_Streak": BestActiveStreak("FirstBloods", 3, ge),
        "FB_Gr_4_Streak": BestActiveStreak("FirstBloods", 4, ge),
        "FB_Gr_5_Streak": BestActiveStreak("FirstBloods", 5, ge),
        "FD_Eq_0_Streak": BestActiveStreak("FirstDeaths", 1, lt),
        "FD_Le_1_Streak": BestActiveStreak("FirstDeaths", 1, le),
        "FD_Le_2_Streak": BestActiveStreak("FirstDeaths", 2, le),
        "FD_Le_3_Streak": BestActiveStreak("FirstDeaths", 3, le),
        "FD_Le_4_Streak": BestActiveStreak("FirstDeaths", 4, le),
        "FD_Le_5_Streak": BestActiveStreak("FirstDeaths", 5, le),
    }

    for active_streak_name, active_streak in streaks_active.items():
        streak_name = active_streak_name.replace('Active', '')
        streak = streaks[streak_name]

        if not active_streak or not streak:
            continue

        if active_streak[0]['Streak'] == streak[0]['Streak']:
            for dic in active_streak:
                dic['BestStreak'] = True
        else:
            for dic in active_streak:
                dic['BestStreak'] = False

    context = {
        "streaks": streaks,
        "streaks_active": streaks_active,
    }

    return render(request, "match/recordbook/record_streak.html", context)

@cache_page(60*10)
def record_span(request):

    mvp = {}
    for i in range(3, 21):
        top_spans = BestSpan("MVP", i)
        for span in top_spans:
            key = (span['SpanLength'], span['Span'])
            if key not in mvp:
                mvp[key] = []
            mvp[key].append(span)

    acs = {}
    for i in range(1, 21):
        top_spans = BestSpanRatio("CombatScore", "RoundsPlayed", i)
        for span in top_spans:
            key = (span['SpanLength'], span['Span'])
            if key not in acs:
                acs[key] = []
            acs[key].append(span)

    adr = {}
    for i in range(1, 21):
        top_spans = BestSpanRatio("TotalDamage", "RoundsPlayed", i)
        for span in top_spans:
            key = (span['SpanLength'], span['Span'])
            if key not in adr:
                adr[key] = []
            adr[key].append(span)

    context = {
        'mvp': mvp,
        'acs': acs,
        'adr': adr,
    }

    return render(request, "match/recordbook/record_span.html", context)

@cache_page(60*10)
def record_span_kda(request):

    kills = {}
    for i in range(1, 21):
        top_spans = BestSpan("Kills", i)
        for span in top_spans:
            key = (span['SpanLength'], span['Span'])
            if key not in kills:
                kills[key] = []
            kills[key].append(span)

    deaths = {}
    for i in range(1, 21):
        top_spans = BestSpan("Deaths", i, 0)
        for span in top_spans:
            key = (span['SpanLength'], span['Span'])
            if key not in deaths:
                deaths[key] = []
            deaths[key].append(span)

    assists = {}
    for i in range(1, 21):
        top_spans = BestSpan("Assists", i)
        for span in top_spans:
            key = (span['SpanLength'], span['Span'])
            if key not in assists:
                assists[key] = []
            assists[key].append(span)

    kdr = {}
    for i in range(1, 21):
        top_spans = BestSpanRatio("Kills", "Deaths", i)
        for span in top_spans:
            key = (span['SpanLength'], span['Span'])
            if key not in kdr:
                kdr[key] = []
            kdr[key].append(span)

    kpr = {}
    for i in range(1, 21):
        top_spans = BestSpanRatio("Kills", "RoundsPlayed", i)
        for span in top_spans:
            key = (span['SpanLength'], span['Span'])
            if key not in kpr:
                kpr[key] = []
            kpr[key].append(span)

    kpct = {}
    for i in range(1, 21):
        top_spans = BestSpanRatio("AtLeastOneKill", "RoundsPlayed", i)
        for span in top_spans:
            key = (span['SpanLength'], span['Span'])
            if key not in kpct:
                kpct[key] = []
            kpct[key].append(span)

    dpct = {}
    for i in range(1, 21):
        top_spans = BestSpanRatio("Deaths", "RoundsPlayed", i, 0)
        for span in top_spans:
            key = (span['SpanLength'], span['Span'])
            if key not in dpct:
                dpct[key] = []
            dpct[key].append(span)

    context = {
        'kills': kills,
        'deaths': deaths,
        'assists': assists,
        'kdr': kdr,
        'kpr': kpr,
        'kpct': kpct,
        'dpct': dpct,
    }

    return render(request, "match/recordbook/record_span_kda.html", context)

@cache_page(60*10)
def record_span_fbfd(request):

    fbs = {}
    for i in range(1, 21):
        top_spans = BestSpan("FirstBloods", i)
        for span in top_spans:
            key = (span['SpanLength'], span['Span'])
            if key not in fbs:
                fbs[key] = []
            fbs[key].append(span)

    fds = {}
    for i in range(3, 21):
        top_spans = BestSpan("FirstDeaths", i, 0)
        for span in top_spans:
            key = (span['SpanLength'], span['Span'])
            if key not in fds:
                fds[key] = []
            fds[key].append(span)

    most_fds = {}
    for i in range(1, 21):
        top_spans = BestSpan("FirstDeaths", i)
        for span in top_spans:
            key = (span['SpanLength'], span['Span'])
            if key not in most_fds:
                most_fds[key] = []
            most_fds[key].append(span)

    fbfd = {}
    for i in range(1, 21):
        top_spans = BestSpanRatio("FirstBloods", "FirstDeaths", i)
        for span in top_spans:
            key = (span['SpanLength'], span['Span'])
            if key not in fbfd:
                fbfd[key] = []
            fbfd[key].append(span)

    fbpct = {}
    for i in range(1, 21):
        top_spans = BestSpanRatio("FirstBloods", "RoundsPlayed", i)
        for span in top_spans:
            key = (span['SpanLength'], span['Span'])
            if key not in fbpct:
                fbpct[key] = []
            fbpct[key].append(span)

    fdpct = {}
    for i in range(3, 21):
        top_spans = BestSpanRatio("FirstDeaths", "RoundsPlayed", i, 0)
        for span in top_spans:
            key = (span['SpanLength'], span['Span'])
            if key not in fdpct:
                fdpct[key] = []
            fdpct[key].append(span)

    context = {
        'fbs': fbs,
        'most_fds': most_fds,
        'fds': fds,
        'fbfd': fbfd,
        'fbpct': fbpct,
        'fdpct': fdpct,
    }

    return render(request, "match/recordbook/record_span_fbfd.html", context)

@cache_page(60*10)
def record_career(request):

    def GetTopBot(agg, field):
        sortedAgg = agg.order_by('-' + field)

        highest_value_Username = sortedAgg.first()['Username']
        highest_value_DisplayName = highest_value_Username.split("#")[0]
        highest_value = sortedAgg.first()[field]
        highest_Agent = most_frequent_agents[highest_value_Username]
        highest_AgentImage = AgentImage(highest_Agent)

        lowest_value_Username = sortedAgg.last()['Username']
        lowest_value_DisplayName = lowest_value_Username.split("#")[0]
        lowest_value = sortedAgg.last()[field]
        lowest_Agent = most_frequent_agents[lowest_value_Username]
        lowest_AgentImage = AgentImage(lowest_Agent)

        return {
            "Field": field,
            
            "TopUsername": highest_value_Username,
            "TopDisplayName": highest_value_DisplayName,
            "TopValue": highest_value,
            "TopAgent": highest_Agent,
            "TopAgentImage": highest_AgentImage,
            
            "BotUsername": lowest_value_Username,
            "BotDisplayName": lowest_value_DisplayName,
            "BotValue": lowest_value,
            "BotAgent": lowest_Agent,
            "BotAgentImage": lowest_AgentImage
        }

    players = Player.objects.filter(Team="Team A")

    # GetTopAgents
    agent_counts = Player.objects.filter(Team="Team A").values('Username', 'Agent').annotate(
        agent_count=Count('Agent')
    ).order_by('Username', '-agent_count')
    most_frequent_agents = {}
    for player in agent_counts:
        # If the player is not already in the dictionary, add them
        if player['Username'] not in most_frequent_agents:
            most_frequent_agents[player['Username']] = player['Agent']

    players_with_counts = players.annotate(username_count=Count('Username'))
    players_with_counts = players_with_counts.filter(username_count__gte=10)
    agg_players = players_with_counts.values('Username').annotate(
            kpr = Sum('Kills') / Cast(Sum('RoundsPlayed'), FloatField()),
            dpr = Sum('Deaths') / Cast(Sum('RoundsPlayed'), FloatField()),
            apr = Sum('Assists') / Cast(Sum('RoundsPlayed'), FloatField()),

            kdr = Sum('Kills') / Cast(Sum('Deaths'), FloatField()),
            acs = Sum('CombatScore') / Cast(Sum('RoundsPlayed'), FloatField()),
            adr = Sum('TotalDamage') / Cast(Sum('RoundsPlayed'), FloatField()),

            fb_pct = Sum('FirstBloods') / Cast(Sum('RoundsPlayed'), FloatField()),
            fd_pct = Sum('FirstDeaths') / Cast(Sum('RoundsPlayed'), FloatField()),
            fb_fd_ratio = Sum('FirstBloods') / Cast(Sum('FirstDeaths'), FloatField()),

            kast = Sum('KASTRounds') / Cast(Sum('RoundsPlayed'), FloatField()),
            k_pct = (Sum('RoundsPlayed') - Sum('ZeroKillRounds')) / Cast(Sum('RoundsPlayed'), FloatField()),

            win_pct = (Sum('MatchWon') + 0.5*Sum('MatchDraw')) / Cast(Count('Match'), FloatField()),
            round_win_pct = (Sum('AttackWins') + Sum('DefenseWins')) / Cast(Sum('RoundsPlayed'), FloatField()),
            attack_win_pct = Sum('AttackWins') / Cast((Sum('AttackWins') + Sum('AttackLosses')), FloatField()),
            defense_win_pct = Sum('DefenseWins') / Cast((Sum('DefenseWins') + Sum('DefenseLosses')), FloatField()),

            hs_pct=Sum(F('HS_Pct') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),
            damage_delta=Sum(F('DamageDelta') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),

            mvps=Sum('MVP'),
            mvp_pct=Avg('MVP'),
            adj_mvp_pct=Sum(F('MVP') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField())
        )

    context = {
        "kpr": GetTopBot(agg_players, "kpr"),
        "dpr": GetTopBot(agg_players, "dpr"),
        "apr": GetTopBot(agg_players, "apr"),
        "kdr": GetTopBot(agg_players, "kdr"),
        "acs": GetTopBot(agg_players, "acs"),
        "adr": GetTopBot(agg_players, "adr"),
        "fb_pct": GetTopBot(agg_players, "fb_pct"),
        "fd_pct": GetTopBot(agg_players, "fd_pct"),
        "fb_fd_ratio": GetTopBot(agg_players, "fb_fd_ratio"),
        "kast": GetTopBot(agg_players, "kast"),
        "k_pct": GetTopBot(agg_players, "k_pct"),
        "win_pct": GetTopBot(agg_players, "win_pct"),
        "round_win_pct": GetTopBot(agg_players, "round_win_pct"),
        "attack_win_pct": GetTopBot(agg_players, "attack_win_pct"),
        "defense_win_pct": GetTopBot(agg_players, "defense_win_pct"),
        "hs_pct": GetTopBot(agg_players, "hs_pct"),
        "damage_delta": GetTopBot(agg_players, "damage_delta"),
        "mvps": GetTopBot(agg_players, "mvps"),
        "mvp_pct": GetTopBot(agg_players, "mvp_pct"),
    }

    return render(request, "match/recordbook/record_career.html", context)

from collections import OrderedDict

@cache_page(60*10)
def record_rounds(request):

    #####

    kills_dict = {}
    max_kills_cumulative = 0
    best_performance = None

    rounds_played_values = Player.objects.values_list('RoundsPlayed', flat=True).distinct().order_by('RoundsPlayed')

    for rounds in rounds_played_values:
        players_in_round = Player.objects.filter(Team="Team A", RoundsPlayed__lte=rounds).order_by('-Kills', 'RoundsPlayed')

        if players_in_round.exists():
            top_player = players_in_round.first()

            if top_player.Kills > max_kills_cumulative or (top_player.Kills == max_kills_cumulative and top_player.RoundsPlayed < best_performance.RoundsPlayed):
                max_kills_cumulative = top_player.Kills
                best_performance = top_player

            best_players_in_round = players_in_round.filter(Team="Team A", Kills=max_kills_cumulative, RoundsPlayed=best_performance.RoundsPlayed)

            for player in best_players_in_round:
                player_dict = {
                    'Rounds': rounds,
                    'Username': player.Username,
                    'Kills': player.Kills,
                    'Date': player.Match.Date,
                    'DisplayName': player.DisplayName,
                    'UserTag': player.UserTag,
                    'Agent': player.Agent,
                    'AgentImage': player.AgentImage,
                    'MatchID': player.Match.MatchID,
                    'RoundsPlayed': player.RoundsPlayed,
                    'Score': player.Match.Score,
                    'Won': player.MatchWon,
                    'Lost': player.MatchLost,
                    'Draw': player.MatchDraw,
                }

                key = (rounds, max_kills_cumulative)

                if key not in kills_dict:
                    kills_dict[key] = []

                kills_dict[key].append(player_dict)

    #####

    assists_dict = {}
    max_kills_cumulative = 0
    best_performance = None

    rounds_played_values = Player.objects.values_list('RoundsPlayed', flat=True).distinct().order_by('RoundsPlayed')

    for rounds in rounds_played_values:
        players_in_round = Player.objects.filter(Team="Team A", RoundsPlayed__lte=rounds).order_by('-Assists', 'RoundsPlayed')

        if players_in_round.exists():
            top_player = players_in_round.first()

            if top_player.Assists > max_kills_cumulative or (top_player.Assists == max_kills_cumulative and top_player.RoundsPlayed < best_performance.RoundsPlayed):
                max_kills_cumulative = top_player.Assists
                best_performance = top_player

            best_players_in_round = players_in_round.filter(Team="Team A", Assists=max_kills_cumulative, RoundsPlayed=best_performance.RoundsPlayed)

            for player in best_players_in_round:
                player_dict = {
                    'Rounds': rounds,
                    'Username': player.Username,
                    'Assists': player.Assists,
                    'Date': player.Match.Date,
                    'DisplayName': player.DisplayName,
                    'UserTag': player.UserTag,
                    'Agent': player.Agent,
                    'AgentImage': player.AgentImage,
                    'MatchID': player.Match.MatchID,
                    'RoundsPlayed': player.RoundsPlayed,
                    'Score': player.Match.Score,
                    'Won': player.MatchWon,
                    'Lost': player.MatchLost,
                    'Draw': player.MatchDraw,
                }

                key = (rounds, max_kills_cumulative)

                if key not in assists_dict:
                    assists_dict[key] = []

                assists_dict[key].append(player_dict)

    #####

    fb_dict = {}
    max_kills_cumulative = 0
    best_performance = None

    rounds_played_values = Player.objects.values_list('RoundsPlayed', flat=True).distinct().order_by('RoundsPlayed')

    for rounds in rounds_played_values:
        players_in_round = Player.objects.filter(Team="Team A", RoundsPlayed__lte=rounds).order_by('-FirstBloods', 'RoundsPlayed')

        if players_in_round.exists():
            top_player = players_in_round.first()

            if top_player.FirstBloods > max_kills_cumulative or (top_player.FirstBloods == max_kills_cumulative and top_player.RoundsPlayed < best_performance.RoundsPlayed):
                max_kills_cumulative = top_player.FirstBloods
                best_performance = top_player

            best_players_in_round = players_in_round.filter(Team="Team A", FirstBloods=max_kills_cumulative, RoundsPlayed=best_performance.RoundsPlayed)

            for player in best_players_in_round:
                player_dict = {
                    'Rounds': rounds,
                    'Username': player.Username,
                    'FirstBloods': player.FirstBloods,
                    'Date': player.Match.Date,
                    'DisplayName': player.DisplayName,
                    'UserTag': player.UserTag,
                    'Agent': player.Agent,
                    'AgentImage': player.AgentImage,
                    'MatchID': player.Match.MatchID,
                    'RoundsPlayed': player.RoundsPlayed,
                    'Score': player.Match.Score,
                    'Won': player.MatchWon,
                    'Lost': player.MatchLost,
                    'Draw': player.MatchDraw,
                }

                key = (rounds, max_kills_cumulative)

                if key not in fb_dict:
                    fb_dict[key] = []

                fb_dict[key].append(player_dict)

    #####

    fd_dict = {}
    max_kills_cumulative = 0
    best_performance = None

    rounds_played_values = Player.objects.values_list('RoundsPlayed', flat=True).distinct().order_by('RoundsPlayed')

    for rounds in rounds_played_values:
        players_in_round = Player.objects.filter(Team="Team A", RoundsPlayed__lte=rounds).order_by('-FirstDeaths', 'RoundsPlayed')

        if players_in_round.exists():
            top_player = players_in_round.first()

            if top_player.FirstDeaths > max_kills_cumulative or (top_player.FirstDeaths == max_kills_cumulative and top_player.RoundsPlayed < best_performance.RoundsPlayed):
                max_kills_cumulative = top_player.FirstDeaths
                best_performance = top_player

            best_players_in_round = players_in_round.filter(Team="Team A", FirstDeaths=max_kills_cumulative, RoundsPlayed=best_performance.RoundsPlayed)

            for player in best_players_in_round:
                player_dict = {
                    'Rounds': rounds,
                    'Username': player.Username,
                    'FirstDeaths': player.FirstDeaths,
                    'Date': player.Match.Date,
                    'DisplayName': player.DisplayName,
                    'UserTag': player.UserTag,
                    'Agent': player.Agent,
                    'AgentImage': player.AgentImage,
                    'MatchID': player.Match.MatchID,
                    'RoundsPlayed': player.RoundsPlayed,
                    'Score': player.Match.Score,
                    'Won': player.MatchWon,
                    'Lost': player.MatchLost,
                    'Draw': player.MatchDraw,
                }

                key = (rounds, max_kills_cumulative)

                if key not in fd_dict:
                    fd_dict[key] = []

                fd_dict[key].append(player_dict)
                
    #####

    acs_dict = {}
    max_acs_cumulative = 0
    best_performance = None

    rounds_played_values = Player.objects.values_list('RoundsPlayed', flat=True).distinct().order_by('-RoundsPlayed')

    for rounds in rounds_played_values:
        players_in_round = Player.objects.filter(Team="Team A", RoundsPlayed__gte=rounds).order_by('-ACS', '-RoundsPlayed')

        if players_in_round.exists():
            top_player = players_in_round.first()

            if top_player.ACS > max_acs_cumulative or (top_player.ACS == max_acs_cumulative and top_player.RoundsPlayed > best_performance.RoundsPlayed):
                max_acs_cumulative = top_player.ACS
                best_performance = top_player

            best_players_in_round = players_in_round.filter(Team="Team A", ACS=max_acs_cumulative, RoundsPlayed=best_performance.RoundsPlayed)

            for player in best_players_in_round:
                player_dict = {
                    'Rounds': rounds,
                    'Username': player.Username,
                    'ACS': player.ACS,
                    'Date': player.Match.Date,
                    'DisplayName': player.DisplayName,
                    'UserTag': player.UserTag,
                    'Agent': player.Agent,
                    'AgentImage': player.AgentImage,
                    'MatchID': player.Match.MatchID,
                    'RoundsPlayed': player.RoundsPlayed,
                    'Score': player.Match.Score,
                    'Won': player.MatchWon,
                    'Lost': player.MatchLost,
                    'Draw': player.MatchDraw,
                }

                key = (rounds, max_acs_cumulative)

                if key not in acs_dict:
                    acs_dict[key] = []

                acs_dict[key].append(player_dict)

    acs_dict = OrderedDict(sorted(acs_dict.items()))

    #####

    adr_dict = {}
    max_acs_cumulative = 0
    best_performance = None

    rounds_played_values = Player.objects.values_list('RoundsPlayed', flat=True).distinct().order_by('-RoundsPlayed')

    for rounds in rounds_played_values:
        players_in_round = Player.objects.filter(Team="Team A", RoundsPlayed__gte=rounds).order_by('-AverageDamage', '-RoundsPlayed')

        if players_in_round.exists():
            top_player = players_in_round.first()

            if top_player.AverageDamage > max_acs_cumulative or (top_player.AverageDamage == max_acs_cumulative and top_player.RoundsPlayed > best_performance.RoundsPlayed):
                max_acs_cumulative = top_player.AverageDamage
                best_performance = top_player

            best_players_in_round = players_in_round.filter(Team="Team A", AverageDamage=max_acs_cumulative, RoundsPlayed=best_performance.RoundsPlayed)

            for player in best_players_in_round:
                player_dict = {
                    'Rounds': rounds,
                    'Username': player.Username,
                    'ADR': player.AverageDamage,
                    'Date': player.Match.Date,
                    'DisplayName': player.DisplayName,
                    'UserTag': player.UserTag,
                    'Agent': player.Agent,
                    'AgentImage': player.AgentImage,
                    'MatchID': player.Match.MatchID,
                    'RoundsPlayed': player.RoundsPlayed,
                    'Score': player.Match.Score,
                    'Won': player.MatchWon,
                    'Lost': player.MatchLost,
                    'Draw': player.MatchDraw,
                }

                key = (rounds, max_acs_cumulative)

                if key not in adr_dict:
                    adr_dict[key] = []

                adr_dict[key].append(player_dict)

    adr_dict = OrderedDict(sorted(adr_dict.items()))

    #####

    kdr_dict = {}
    max_acs_cumulative = 0
    best_performance = None

    rounds_played_values = Player.objects.values_list('RoundsPlayed', flat=True).distinct().order_by('-RoundsPlayed')

    for rounds in rounds_played_values:
        players_in_round = Player.objects.filter(Team="Team A", RoundsPlayed__gte=rounds).order_by('-KillDeathRatio', '-RoundsPlayed')

        if players_in_round.exists():
            top_player = players_in_round.first()

            if top_player.KillDeathRatio > max_acs_cumulative or (top_player.KillDeathRatio == max_acs_cumulative and top_player.RoundsPlayed > best_performance.RoundsPlayed):
                max_acs_cumulative = top_player.KillDeathRatio
                best_performance = top_player

            best_players_in_round = players_in_round.filter(Team="Team A", KillDeathRatio=max_acs_cumulative, RoundsPlayed=best_performance.RoundsPlayed)

            for player in best_players_in_round:
                player_dict = {
                    'Rounds': rounds,
                    'Username': player.Username,
                    'KDR': player.KillDeathRatio,
                    'Date': player.Match.Date,
                    'DisplayName': player.DisplayName,
                    'UserTag': player.UserTag,
                    'Agent': player.Agent,
                    'AgentImage': player.AgentImage,
                    'MatchID': player.Match.MatchID,
                    'RoundsPlayed': player.RoundsPlayed,
                    'Score': player.Match.Score,
                    'Won': player.MatchWon,
                    'Lost': player.MatchLost,
                    'Draw': player.MatchDraw,
                }

                key = (rounds, max_acs_cumulative)

                if key not in kdr_dict:
                    kdr_dict[key] = []

                kdr_dict[key].append(player_dict)

    kdr_dict = OrderedDict(sorted(kdr_dict.items()))

    #####

    kpr_dict = {}
    max_acs_cumulative = 0
    best_performance = None

    rounds_played_values = Player.objects.values_list('RoundsPlayed', flat=True).distinct().order_by('-RoundsPlayed')

    for rounds in rounds_played_values:
        players_in_round = Player.objects.filter(Team="Team A",RoundsPlayed__gte=rounds).annotate(KPR=F('Kills')/Cast(F('RoundsPlayed'),FloatField())).order_by('-KPR','-RoundsPlayed')

        if players_in_round.exists():
            top_player = players_in_round.first()

            if top_player.KPR > max_acs_cumulative or (top_player.KPR == max_acs_cumulative and top_player.RoundsPlayed > best_performance.RoundsPlayed):
                max_acs_cumulative = top_player.KPR
                best_performance = top_player

            best_players_in_round = players_in_round.filter(Team="Team A", KPR=max_acs_cumulative, RoundsPlayed=best_performance.RoundsPlayed)

            for player in best_players_in_round:
                player_dict = {
                    'Rounds': rounds,
                    'Username': player.Username,
                    'KPR': player.KPR,
                    'Date': player.Match.Date,
                    'DisplayName': player.DisplayName,
                    'UserTag': player.UserTag,
                    'Agent': player.Agent,
                    'AgentImage': player.AgentImage,
                    'MatchID': player.Match.MatchID,
                    'RoundsPlayed': player.RoundsPlayed,
                    'Score': player.Match.Score,
                    'Won': player.MatchWon,
                    'Lost': player.MatchLost,
                    'Draw': player.MatchDraw,
                }

                key = (rounds, max_acs_cumulative)

                if key not in kpr_dict:
                    kpr_dict[key] = []

                kpr_dict[key].append(player_dict)

    kpr_dict = OrderedDict(sorted(kpr_dict.items()))

    #####

    kpct_dict = {}
    max_acs_cumulative = 0
    best_performance = None

    rounds_played_values = Player.objects.values_list('RoundsPlayed', flat=True).distinct().order_by('-RoundsPlayed')

    for rounds in rounds_played_values:
        players_in_round = Player.objects.filter(Team="Team A",RoundsPlayed__gte=rounds).annotate(k_pct=(F('RoundsPlayed')-F('ZeroKillRounds'))/Cast(F('RoundsPlayed'),FloatField())).order_by('-k_pct','-RoundsPlayed')

        if players_in_round.exists():
            top_player = players_in_round.first()

            if top_player.k_pct > max_acs_cumulative or (top_player.k_pct == max_acs_cumulative and top_player.RoundsPlayed > best_performance.RoundsPlayed):
                max_acs_cumulative = top_player.k_pct
                best_performance = top_player

            best_players_in_round = players_in_round.filter(Team="Team A", k_pct=max_acs_cumulative, RoundsPlayed=best_performance.RoundsPlayed)

            for player in best_players_in_round:
                player_dict = {
                    'Rounds': rounds,
                    'Username': player.Username,
                    'K_Pct': player.k_pct,
                    'Date': player.Match.Date,
                    'DisplayName': player.DisplayName,
                    'UserTag': player.UserTag,
                    'Agent': player.Agent,
                    'AgentImage': player.AgentImage,
                    'MatchID': player.Match.MatchID,
                    'RoundsPlayed': player.RoundsPlayed,
                    'Score': player.Match.Score,
                    'Won': player.MatchWon,
                    'Lost': player.MatchLost,
                    'Draw': player.MatchDraw,
                }

                key = (rounds, max_acs_cumulative)

                if key not in kpct_dict:
                    kpct_dict[key] = []

                kpct_dict[key].append(player_dict)

    kpct_dict = OrderedDict(sorted(kpct_dict.items()))

    context = {
        'kills_dict': kills_dict,
        'assists_dict': assists_dict,
        'fb_dict': fb_dict,
        'fd_dict': fd_dict,
        'acs_dict': acs_dict,
        'adr_dict': adr_dict,
        'kdr_dict': kdr_dict,
        'kpr_dict': kpr_dict,
        'kpct_dict': kpct_dict,
    }

    return render(request, "match/recordbook/record_rounds.html", context)

### 

def player_teammates(request, username):
    players = Player.objects.filter(Team="Team A", Username=username)

    if (players.count() == 0):
        raise Http404
    
    firstRow = players.values().first()
    tagSplit = firstRow['Username'].split("#")
    displayName = tagSplit[0]
    userTag = "#"+tagSplit[1]
    agent_counter = Counter(players.values_list('Agent', flat=True))
    topAgent = agent_counter.most_common(1)[0][0]
    topAgentImage = AgentImage(topAgent)

    matching_match_ids = players.values_list('Match__MatchID', flat=True)

    AgentCounts = []
    for x in agent_map.values():
        agent_filter = Player.objects.filter(Team="Team A",
                                             Agent=x)
        AgentCounts.append({"Agent":x, "Count":len(agent_filter)})
    
    teammates = Player.objects.filter(Match__MatchID__in=matching_match_ids,
                                      Team="Team A")\
                              .exclude(Username=username)
    
    # Get teammate performances with user

    anno = teammates.values('Username').annotate(
        num_matches=Count('Match'),

        matches_won=Sum('MatchWon'),
        matches_lost=Sum('MatchLost'),
        matches_draw=Sum('MatchDraw'),

        total_kills=Sum('Kills'),
        total_deaths=Sum('Deaths'),
        total_assists=Sum('Assists'),

        total_score=Sum('CombatScore'),
        total_damage=Sum('TotalDamage'),

        first_bloods=Sum('FirstBloods'),
        first_deaths=Sum('FirstDeaths'),
        fb_fd_ratio=F('first_bloods')/Cast('first_deaths', FloatField()),

        kast_rounds=Sum('KASTRounds'),

        hs_pct=Sum(F('HS_Pct') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),
        damage_delta=Sum(F('DamageDelta') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),

        zero_kills=Sum('ZeroKillRounds'),
        one_kills=Sum('OneKillRounds'),
        two_kills=Sum('TwoKillRounds'),
        three_kills=Sum('ThreeKillRounds'),
        four_kills=Sum('FourKillRounds'),
        five_kills=Sum('FiveKillRounds'),
        six_kills=Sum('SixKillRounds'),

        attack_kills=Sum('AttackKills'),
        attack_deaths=Sum('AttackDeaths'),
        attack_damage=Sum('AttackDamage'),
        defense_kills=Sum('DefenseKills'),
        defense_deaths=Sum('DefenseDeaths'),
        defense_damage=Sum('DefenseDamage'),
        
        win_kills=Sum('WinKills'),
        win_deaths=Sum('WinDeaths'),
        win_damage=Sum('WinDamage'),
        loss_kills=Sum('LossKills'),
        loss_deaths=Sum('LossDeaths'),
        loss_damage=Sum('LossDamage'),

        attack_rounds=Sum('AttackRounds'),
        attack_wins=Sum('AttackWins'),
        attack_losses=Sum('AttackLosses'),

        defense_rounds=Sum('DefenseRounds'),
        defense_wins=Sum('DefenseWins'),
        defense_losses=Sum('DefenseLosses'),

        rounds_won=Sum('AttackWins')+Sum('DefenseWins'),
        rounds_lost=Sum('AttackLosses')+Sum('DefenseLosses'),

        rounds = Sum('RoundsPlayed'),

        kdr=F('total_kills')/Cast('total_deaths', FloatField()),
        kpr=F('total_kills')/Cast('rounds', FloatField()),
        acs=F('total_score')/Cast('rounds', FloatField()),
        adr=F('total_damage')/Cast('rounds', FloatField()),

        kast=F('kast_rounds')/Cast('rounds', FloatField()),
        k_pct=(F('rounds')-F('zero_kills'))/Cast('rounds', FloatField()),

        win_pct=(F('matches_won')+0.5*F('matches_draw'))/Cast('num_matches', FloatField()),
        round_win_pct=F('rounds_won')/Cast('rounds', FloatField()),
        attack_win_pct=F('attack_wins')/Cast('attack_rounds', FloatField()),
        defense_win_pct=F('defense_wins')/Cast('defense_rounds', FloatField()),

        kills_per_20 = (F('total_kills')/Cast('rounds', FloatField()))*20,
        deaths_per_20 = (F('total_deaths')/Cast('rounds', FloatField()))*20,
        assists_per_20 = (F('total_assists')/Cast('rounds', FloatField()))*20,

        fb_per_20 = (F('first_bloods')/Cast('rounds', FloatField()))*20,
        fd_per_20 = (F('first_deaths')/Cast('rounds', FloatField()))*20,

        attack_kdr = F('attack_kills')/Cast('attack_deaths', FloatField()), 
        attack_adr = F('attack_damage')/Cast('attack_rounds', FloatField()), 
        defense_kdr = F('defense_kills')/Cast('defense_deaths', FloatField()), 
        defense_adr = F('defense_damage')/Cast('defense_rounds', FloatField()),

        attack_kp12 = (F('attack_kills')/Cast('attack_rounds', FloatField()))*12,
        attack_dp12 = (F('attack_deaths')/Cast('attack_rounds', FloatField()))*12,
        defense_kp12 = (F('defense_kills')/Cast('defense_rounds', FloatField()))*12,
        defense_dp12 = (F('defense_deaths')/Cast('defense_rounds', FloatField()))*12,

        max_kills = Max('Kills'),
        max_deaths = Max('Deaths'),
        max_assists = Max('Assists'),
        max_kdr = Max(F('Kills') / Cast('Deaths', FloatField())),
        max_acs = Max(F('CombatScore') / F('RoundsPlayed')),
        max_adr = Max(F('TotalDamage') / Cast('RoundsPlayed', FloatField())),
        max_fb = Max('FirstBloods'),
        max_fd = Max('FirstDeaths')
    ).order_by('-num_matches')

    TeammateAgents = []

    for p in anno:
        filtered_players = teammates.filter(Username=p['Username'])

        agent_counter = Counter(filtered_players.values_list('Agent', flat=True))
        if agent_counter:
            p['TopAgent'] = agent_counter.most_common(1)[0][0]
            p['AgentString'] =", ".join(f"{key} ({value})" for key, value in agent_counter.most_common())
        p['TopAgentImage'] = AgentImage(p['TopAgent'])

        UserSplit = p['Username'].split('#')
        p['PlayerUsername'] = p['Username']
        p['PlayerDisplayName'] = UserSplit[0]
        p['PlayerUserTag'] = "#"+UserSplit[1]
        p['PlayerAgent'] = p['TopAgent']
        p['PlayerAgentImage'] = p['TopAgentImage']
        p['PlayerAgentString'] = p['AgentString']

        TeammateAgents.append({"Username":p['Username'], 
                               "TopAgent": p['TopAgent'],
                               "AgentString": p['AgentString']})

        p['WinLossRecord'] = "{}-{}-{}".format(p['matches_won'],p['matches_lost'],p['matches_draw'])
        p['RoundRecord'] = "{}-{}".format(p["rounds_won"],p["rounds_lost"])
        p['AttackRecord'] = "{}-{}".format(p["attack_wins"],p["attack_losses"])
        p['DefenseRecord'] = "{}-{}".format(p["defense_wins"],p["defense_losses"])

        max_kills = filtered_players.filter(Kills=p['max_kills']).order_by('-ACS','-KillDeathRatio')
        max_deaths = filtered_players.filter(Deaths=p['max_deaths']).order_by('Kills','ACS')
        max_assists = filtered_players.filter(Assists=p['max_assists']).order_by('-Kills','-ACS','-KillDeathRatio')
        max_kdr = filtered_players.annotate(kdr=F('Kills') / Cast('Deaths', FloatField()))\
                                  .filter(kdr=p['max_kdr']).order_by('-Kills','-ACS')
        max_acs = filtered_players.filter(ACS=p['max_acs']).order_by('-Kills','-KillDeathRatio')
        max_adr = filtered_players.annotate(adr=F('TotalDamage') / Cast('RoundsPlayed', FloatField()))\
                                  .filter(adr=p['max_adr']).order_by('-ACS','-Kills','-KillDeathRatio')
        max_fb = filtered_players.annotate(fb_pct=(Sum('FirstBloods')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                 .filter(FirstBloods=p['max_fb']).order_by('-fb_pct','FirstDeaths','-ACS','-Kills','-KillDeathRatio')
        max_fd = filtered_players.annotate(fd_pct=(Sum('FirstDeaths')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())))\
                                 .filter(FirstDeaths=p['max_fd']).order_by('-fd_pct','FirstBloods','ACS','Kills','KillDeathRatio')

        p['max_kills_id'] = max_kills.values('Match__MatchID').first()['Match__MatchID']
        p['max_kills_player'] = max_kills.values('DisplayName').first()['DisplayName']

        p['max_deaths_id'] = max_deaths.values('Match__MatchID').first()['Match__MatchID']
        p['max_deaths_player'] = max_deaths.values('DisplayName').first()['DisplayName']

        p['max_assists_id'] = max_assists.values('Match__MatchID').first()['Match__MatchID']
        p['max_assists_player'] = max_assists.values('DisplayName').first()['DisplayName']

        p['max_kdr_id'] = max_kdr.values('Match__MatchID').first()['Match__MatchID']
        p['max_kdr_player'] = max_kdr.values('DisplayName').first()['DisplayName']

        p['max_acs_id'] = max_acs.values('Match__MatchID').first()['Match__MatchID']
        p['max_acs_player'] = max_acs.values('DisplayName').first()['DisplayName']

        p['max_adr_id'] = max_adr.values('Match__MatchID').first()['Match__MatchID']
        p['max_adr_player'] = max_adr.values('DisplayName').first()['DisplayName']

        p['max_fb_id'] = max_fb.values('Match__MatchID').first()['Match__MatchID']
        p['max_fb_player'] = max_fb.values('DisplayName').first()['DisplayName']

        p['max_fd_id'] = max_fd.values('Match__MatchID').first()['Match__MatchID']
        p['max_fd_player'] = max_fd.values('DisplayName').first()['DisplayName']
    
    # Get user performances with each teammate

    UserAgents = []

    UserPerformances = []
    TeammateUsernames = teammates.values_list('Username', flat=True).distinct()
    for X in TeammateUsernames:
        teammates2 = Player.objects.filter(Team="Team A",
                                           Username=X)
        teammate_match_ids = teammates2.values_list('Match__MatchID', flat=True)
        
        user_games = Player.objects.filter(Match__MatchID__in=teammate_match_ids,
                                           Team="Team A",
                                           Username=username)
        
        user_agg = CalculateAggregates(user_games)

        user_agg['PlayerUsername'] = username
        user_agg['PlayerDisplayName'] = displayName
        user_agg['PlayerUserTag'] = userTag
        user_agg['PlayerAgent'] = user_agg['TopAgent']
        user_agg['PlayerAgentImage'] = user_agg['TopAgentImage']
        user_agg['PlayerAgentString'] = user_agg['AgentString']

        UserAgents.append({"Username":X, 
                           "TopAgent": user_agg['PlayerAgent'],
                           "AgentString": user_agg['PlayerAgentString']})
        
        tagSplit = X.split("#")
        user_agg['TeammateUsername'] = X
        user_agg['TeammateDisplayName'] = tagSplit[0]
        user_agg['TeammateUserTag'] = "#"+tagSplit[1]
        user_agg['TeammateAgent'] = next(item["TopAgent"] for item in TeammateAgents if item["Username"] == X)
        user_agg['TeammateAgentString'] = next(item["AgentString"] for item in TeammateAgents if item["Username"] == X)
        user_agg['TeammateAgentImage'] = AgentImage(user_agg['TeammateAgent'])

        UserPerformances.append(user_agg)

    for p in anno:
        p['TeammateUsername'] = username
        p['TeammateDisplayName'] = displayName
        p['TeammateUserTag'] = userTag
        p['TeammateAgent'] = next(item["TopAgent"] for item in UserAgents if item["Username"] == p['Username'])
        p['TeammateAgentString'] = next(item["AgentString"] for item in UserAgents if item["Username"] == p['Username'])
        p['TeammateAgentImage'] = AgentImage(p['TeammateAgent'])

    UserPerformances = sorted(UserPerformances, key=lambda d: d['num_matches'], reverse=True) 

    mvps = players.aggregate(
        mvps=Sum('MVP')
    )['mvps']

    context = {
        "PlayerPerformances": UserPerformances,
        "TeammatePerformances": anno,

        'username': username,
        'displayName': displayName,
        'topAgent': topAgent,
        'topAgentImage': topAgentImage,
        
        'mvps': mvps,
    }
    
    return render(request, 'match/player/player_teammates.html', context)

def lineups(request):

    players = Player.objects.filter(Team="Team A")

    matches = Match.objects.all()

    colorClasses = ["btn-danger", "btn-success", "btn-outline-dark"]
    unique_maps = sorted(list(Match.objects.values_list("Map", flat=True).distinct()))
    unique_players = sorted(list(Player.objects.filter(Team="Team A").values_list("DisplayName", flat=True).distinct()),
                            key=lambda x: x.lower())
    # Apply filters based on user input

    map_filter = request.GET.get('map')
    mp_filter = request.GET.get('minMP')
    date_filter = request.GET.get('dateRange')

    start_date = None
    end_date = None

    button_values = {}
    for player in unique_players:
        value = request.GET.get(str(player), None)
        if value is not None:
            button_values[player] = int(value)

    if date_filter:
        date_split = date_filter.split(' - ')
        start_date = date_split[0]
        end_date = date_split[1]
        start = datetime.strptime(date_split[0], '%m/%d/%Y')
        end = datetime.strptime(date_split[1], '%m/%d/%Y')

        matches = matches.filter(Date__range=(start, end))

    if map_filter:
        matches = matches.filter(Map=map_filter)

    if button_values:
        include_q_objects = Q()
        exclude_q_objects = Q()
        include_count = 0
        for player, value in button_values.items():
            if value == 1:
                # Include matches where the player with the given display name participated and the team is "Team A"
                include_q_objects |= Q(player__DisplayName=player, player__Team="Team A")
                include_count += 1
            elif value == 0:
                # Exclude matches where the player with the given display name participated and the team is "Team A"
                exclude_q_objects |= Q(player__DisplayName=player, player__Team="Team A")

        if include_count > 0:
            filtered_matches = matches.filter(include_q_objects)\
                                      .annotate(num_players=Count('player__DisplayName', distinct=True))\
                                      .filter(num_players=include_count)\
                                      .exclude(exclude_q_objects)\
                                      .distinct()
        else:
            filtered_matches = matches.exclude(exclude_q_objects).distinct()

        matching_match_ids = filtered_matches.values_list('MatchID', flat=True)
        players = Player.objects.filter(Team="Team A",
                                        Match__MatchID__in=matching_match_ids)

    lineups = players.values('Match__Players').annotate(
        num_matches=Count('Match')/5,

        matches_won=Sum('MatchWon')/5,
        matches_lost=Sum('MatchLost')/5,
        matches_draw=Sum('MatchDraw')/5,

        total_kills=Sum('Kills'),
        total_deaths=Sum('Deaths'),
        total_assists=Sum('Assists'),

        total_score=Sum('CombatScore'),
        total_damage=Sum('TotalDamage'),

        first_bloods=Sum('FirstBloods'),
        first_deaths=Sum('FirstDeaths'),
        fb_fd_ratio=Sum('FirstBloods')/Cast(Sum('FirstDeaths'), output_field=FloatField()),

        kast_rounds=Sum('KASTRounds'),

        attack_kills=Sum('AttackKills'),
        attack_deaths=Sum('AttackDeaths'),
        attack_damage=Sum('AttackDamage'),
        defense_kills=Sum('DefenseKills'),
        defense_deaths=Sum('DefenseDeaths'),
        defense_damage=Sum('DefenseDamage'),
        
        win_kills=Sum('WinKills'),
        win_deaths=Sum('WinDeaths'),
        win_damage=Sum('WinDamage'),
        loss_kills=Sum('LossKills'),
        loss_deaths=Sum('LossDeaths'),
        loss_damage=Sum('LossDamage'),

        kast=Sum('KASTRounds')/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
        k_pct=(Sum('RoundsPlayed')-Sum('ZeroKillRounds'))/Cast(Sum('RoundsPlayed'), output_field=FloatField()),

        win_pct=(Sum('MatchWon')+0.5*Sum('MatchDraw'))/Cast(Count('Match'), FloatField()),
        round_win_pct=(Sum('AttackWins')+Sum('DefenseWins'))/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
        attack_win_pct=Sum('AttackWins')/Cast(Sum('AttackRounds'), output_field=FloatField()),
        defense_win_pct=Sum('DefenseWins')/Cast(Sum('DefenseRounds'), output_field=FloatField()),

        kdr=Sum('Kills')/Cast(Sum('Deaths'), output_field=FloatField()),
        kpr=Sum('Kills')/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
        acs=Sum('CombatScore')/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
        adr=Sum('TotalDamage')/Cast(Sum('RoundsPlayed'), output_field=FloatField()),

        attack_rounds=Sum('AttackRounds')/5,
        attack_wins=Sum('AttackWins')/5,
        attack_losses=Sum('AttackLosses')/5,

        defense_rounds=Sum('DefenseRounds')/5,
        defense_wins=Sum('DefenseWins')/5,
        defense_losses=Sum('DefenseLosses')/5,

        rounds_won=(Sum('AttackWins')+Sum('DefenseWins'))/5,
        rounds_lost=(Sum('AttackLosses')+Sum('DefenseLosses'))/5,
        rounds_played=Sum('RoundsPlayed')/5,

        fb_pct=(Sum('FirstBloods')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())),
        fd_pct=(Sum('FirstDeaths')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())),

        attack_kdr=Sum('AttackKills')/Cast(Sum('AttackDeaths'), output_field=FloatField()),
        attack_adr=Sum('AttackDamage')/Cast(Sum('AttackRounds'), output_field=FloatField()),
        defense_kdr=Sum('DefenseKills')/Cast(Sum('DefenseDeaths'), output_field=FloatField()),
        defense_adr=Sum('DefenseDamage')/Cast(Sum('DefenseRounds'), output_field=FloatField()),

        max_kills = Max('Kills'),
        max_deaths = Max('Deaths'),
        max_assists = Max('Assists'),
        max_kdr = Max(F('Kills') / Cast('Deaths', FloatField())),
        max_acs = Max(F('CombatScore') / F('RoundsPlayed')),
        max_adr = Max(F('TotalDamage') / Cast('RoundsPlayed', FloatField())),
        max_fb = Max('FirstBloods'),
        max_fd = Max('FirstDeaths')
    ).order_by('-num_matches')

    max_matches = lineups.aggregate(Max('num_matches'))['num_matches__max']
    if mp_filter:
        lineups = lineups.filter(Q(num_matches__gte=mp_filter)).all()

    for m in lineups:
        
        m['WinLossRecord'] = "{}-{}-{}".format(m['matches_won'],m['matches_lost'],m['matches_draw'])
        m['RoundRecord'] = "{}-{}".format(m["rounds_won"],m["rounds_lost"])
        m['AttackRecord'] = "{}-{}".format(m["attack_wins"],m["attack_losses"])
        m['DefenseRecord'] = "{}-{}".format(m["defense_wins"],m["defense_losses"])

        MatchFilterStr = "?"
        for p in m['Match__Players'].split(", "):
            MatchFilterStr += "{}=1&".format(p)
        m['MatchFilterStr'] = MatchFilterStr.strip("&")

    context = {
        'lineups': lineups,

        'unique_maps': unique_maps,
        'unique_players': unique_players,

        'map_filter': map_filter,

        'date_filter': date_filter,
        'start_date': start_date,
        'end_date': end_date,

        'button_values': button_values,
        'colorClasses': colorClasses,

        'max_matches':max_matches,
    }

    # Render template
    return render(request, 'match/lineups.html', context)

### ANALYSIS

def solo_duelists(request):
    players = Player.objects.filter(Team="Team A",
                                    Role="Duelist",
                                    Match__N_Duelists=1)
    
    duelists = players.values('Username').annotate(
        num_matches=Count('Match'),

        matches_won=Sum('MatchWon'),
        matches_lost=Sum('MatchLost'),
        matches_draw=Sum('MatchDraw'),

        mvps=Sum('MVP'),
        mvp_pct=Avg('MVP'),

        total_kills=Sum('Kills'),
        total_deaths=Sum('Deaths'),
        total_assists=Sum('Assists'),

        total_score=Sum('CombatScore'),
        total_damage=Sum('TotalDamage'),

        first_bloods=Sum('FirstBloods'),
        first_deaths=Sum('FirstDeaths'),
        fb_fd_ratio = F('first_bloods')/Cast('first_deaths', FloatField()),

        kast_rounds=Sum('KASTRounds'),

        hs_pct=Sum(F('HS_Pct') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),
        damage_delta=Sum(F('DamageDelta') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),

        zero_kills=Sum('ZeroKillRounds'),
        one_kills=Sum('OneKillRounds'),
        two_kills=Sum('TwoKillRounds'),
        three_kills=Sum('ThreeKillRounds'),
        four_kills=Sum('FourKillRounds'),
        five_kills=Sum('FiveKillRounds'),
        six_kills=Sum('SixKillRounds'),

        attack_kills=Sum('AttackKills'),
        attack_deaths=Sum('AttackDeaths'),
        attack_damage=Sum('AttackDamage'),
        defense_kills=Sum('DefenseKills'),
        defense_deaths=Sum('DefenseDeaths'),
        defense_damage=Sum('DefenseDamage'),
        
        win_kills=Sum('WinKills'),
        win_deaths=Sum('WinDeaths'),
        win_damage=Sum('WinDamage'),
        loss_kills=Sum('LossKills'),
        loss_deaths=Sum('LossDeaths'),
        loss_damage=Sum('LossDamage'),

        attack_rounds=Sum('AttackRounds'),
        attack_wins=Sum('AttackWins'),
        attack_losses=Sum('AttackLosses'),

        defense_rounds=Sum('DefenseRounds'),
        defense_wins=Sum('DefenseWins'),
        defense_losses=Sum('DefenseLosses'),

        rounds_won=Sum('AttackWins')+Sum('DefenseWins'),
        rounds_lost=Sum('AttackLosses')+Sum('DefenseLosses'),

        rounds = Sum('RoundsPlayed'),

        kdr=F('total_kills')/Cast('total_deaths', FloatField()),
        kpr=F('total_kills')/Cast('rounds', FloatField()),
        acs=F('total_score')/Cast('rounds', FloatField()),
        adr=F('total_damage')/Cast('rounds', FloatField()),

        kast=F('kast_rounds')/Cast('rounds', FloatField()),
        k_pct=(F('rounds')-F('zero_kills'))/Cast('rounds', FloatField()),

        win_pct=(F('matches_won')+0.5*F('matches_draw'))/Cast('num_matches', FloatField()),
        round_win_pct=F('rounds_won')/Cast('rounds', FloatField()),
        attack_win_pct=F('attack_wins')/Cast('attack_rounds', FloatField()),
        defense_win_pct=F('defense_wins')/Cast('defense_rounds', FloatField()),

        kills_per_20 = (F('total_kills')/Cast('rounds', FloatField()))*20,
        deaths_per_20 = (F('total_deaths')/Cast('rounds', FloatField()))*20,
        assists_per_20 = (F('total_assists')/Cast('rounds', FloatField()))*20,

        fb_per_20 = (F('first_bloods')/Cast('rounds', FloatField()))*20,
        fd_per_20 = (F('first_deaths')/Cast('rounds', FloatField()))*20,

        attack_kdr = F('attack_kills')/Cast('attack_deaths', FloatField()), 
        attack_adr = F('attack_damage')/Cast('attack_rounds', FloatField()), 
        defense_kdr = F('defense_kills')/Cast('defense_deaths', FloatField()), 
        defense_adr = F('defense_damage')/Cast('defense_rounds', FloatField()),

        attack_kp12 = (F('attack_kills')/Cast('attack_rounds', FloatField()))*12,
        attack_dp12 = (F('attack_deaths')/Cast('attack_rounds', FloatField()))*12,
        defense_kp12 = (F('defense_kills')/Cast('defense_rounds', FloatField()))*12,
        defense_dp12 = (F('defense_deaths')/Cast('defense_rounds', FloatField()))*12,

        max_kills = Max('Kills'),
        max_deaths = Max('Deaths'),
        max_assists = Max('Assists'),
        max_kdr = Max(F('Kills') / Cast('Deaths', FloatField())),
        max_acs = Max(F('CombatScore') / F('RoundsPlayed')),
        max_adr = Max(F('TotalDamage') / Cast('RoundsPlayed', FloatField())),
        max_fb = Max('FirstBloods'),
        max_fd = Max('FirstDeaths')
    ).order_by('-num_matches')

    for p in duelists:
        filtered_players = Player.objects.filter(Team="Team A",
                                                 Role="Duelist",
                                                 Match__N_Duelists=1,
                                                 Username=p['Username'])

        tagSplit = p['Username'].split("#")

        p['DisplayName'] = tagSplit[0]
        p['UserTag'] = "#" + tagSplit[1]

        p['WinLossRecord'] = "{}-{}-{}".format(p['matches_won'],p['matches_lost'],p['matches_draw'])
        p['RoundRecord'] = "{}-{}".format(p["rounds_won"],p["rounds_lost"])
        p['AttackRecord'] = "{}-{}".format(p["attack_wins"],p["attack_losses"])
        p['DefenseRecord'] = "{}-{}".format(p["defense_wins"],p["defense_losses"])

        agent_counter = Counter(filtered_players.values_list('Agent', flat=True))
        if agent_counter:
            p['TopAgent'] = agent_counter.most_common(1)[0][0]
            p['AgentString'] =", ".join(f"{key} ({value})" for key, value in agent_counter.most_common())
        p['TopAgentImage'] = AgentImage(p['TopAgent'])

        p['max_kills_id'] = filtered_players.filter(Kills=p['max_kills']).values('Match__MatchID').first()['Match__MatchID']
        p['max_deaths_id'] = filtered_players.filter(Deaths=p['max_deaths']).values('Match__MatchID').first()['Match__MatchID']
        p['max_assists_id'] = filtered_players.filter(Assists=p['max_assists']).values('Match__MatchID').first()['Match__MatchID']
        p['max_kdr_id'] = filtered_players.annotate(kdr=F('Kills') / Cast('Deaths', FloatField()))\
                                     .filter(kdr=p['max_kdr']).values('Match__MatchID').first()['Match__MatchID']
        p['max_acs_id'] = filtered_players.filter(ACS=p['max_acs']).values('Match__MatchID').first()['Match__MatchID']
        p['max_adr_id'] = filtered_players.annotate(adr=F('TotalDamage') / Cast('RoundsPlayed', FloatField()))\
                                     .filter(adr=p['max_adr']).values('Match__MatchID').first()['Match__MatchID']
        p['max_fb_id'] = filtered_players.filter(FirstBloods=p['max_fb']).values('Match__MatchID').first()['Match__MatchID']
        p['max_fd_id'] = filtered_players.filter(FirstDeaths=p['max_fd']).values('Match__MatchID').first()['Match__MatchID']
        
    players = Player.objects.filter(Team="Team A",
                                    Role="Duelist").order_by('-Match__Date')

    if (players.count() == 0):
        raise Http404
    
    count_splits = Player.objects.filter(Team="Team A").values('Match__N_Duelists').annotate(
        num_matches=Count('Match')/5,

        matches_won=Sum('MatchWon')/5,
        matches_lost=Sum('MatchLost')/5,
        matches_draw=Sum('MatchDraw')/5,

        win_pct=(Sum('MatchWon')+0.5*Sum('MatchDraw'))/Cast(Count('Match'), FloatField()),
        round_win_pct=(Sum('AttackWins')+Sum('DefenseWins'))/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
        attack_win_pct=Sum('AttackWins')/Cast(Sum('AttackRounds'), output_field=FloatField()),
        defense_win_pct=Sum('DefenseWins')/Cast(Sum('DefenseRounds'), output_field=FloatField()),

        attack_rounds=Sum('AttackRounds')/5,
        attack_wins=Sum('AttackWins')/5,
        attack_losses=Sum('AttackLosses')/5,

        defense_rounds=Sum('DefenseRounds')/5,
        defense_wins=Sum('DefenseWins')/5,
        defense_losses=Sum('DefenseLosses')/5,

        rounds_won=(Sum('AttackWins')+Sum('DefenseWins'))/5,
        rounds_lost=(Sum('AttackLosses')+Sum('DefenseLosses'))/5,
        rounds_played=Sum('RoundsPlayed')/5,
    )

    count_splits = count_splits.order_by('Match__N_Duelists')

    for m in count_splits:
        filter_dict = {'Match__N_Duelists': m['Match__N_Duelists']}
        filtered_players = players.filter(**filter_dict)

        m['WinLossRecord'] = "{}-{}-{}".format(m['matches_won'],m['matches_lost'],m['matches_draw'])
        m['RoundRecord'] = "{}-{}".format(m["rounds_won"],m["rounds_lost"])
        m['AttackRecord'] = "{}-{}".format(m["attack_wins"],m["attack_losses"])
        m['DefenseRecord'] = "{}-{}".format(m["defense_wins"],m["defense_losses"])

        if m['Match__N_Duelists'] == 0:
            m['Count'] = "No Duelists"
        elif m['Match__N_Duelists'] == 1:
            m['Count'] = "One Duelist"
        elif m['Match__N_Duelists'] == 2:
            m['Count'] = "Two Duelists"
        elif m['Match__N_Duelists'] == 3:
            m['Count'] = "Three Duelists"
        elif m['Match__N_Duelists'] == 3:
            m['Count'] = "Four Duelists"
        elif m['Match__N_Duelists'] == 3:
            m['Count'] = "Five Duelists"

    count_splits_combat = Player.objects.filter(Team="Team A", Role="Duelist").values('Match__N_Duelists').annotate(
        num_matches=Count('Match'),

        matches_won=Sum('MatchWon'),
        matches_lost=Sum('MatchLost'),
        matches_draw=Sum('MatchDraw'),

        total_kills=Sum('Kills'),
        total_deaths=Sum('Deaths'),
        total_assists=Sum('Assists'),

        total_score=Sum('CombatScore'),
        total_damage=Sum('TotalDamage'),

        first_bloods=Sum('FirstBloods'),
        first_deaths=Sum('FirstDeaths'),
        fb_fd_ratio=Sum('FirstBloods')/Cast(Sum('FirstDeaths'), output_field=FloatField()),

        kast_rounds=Sum('KASTRounds'),

        attack_kills=Sum('AttackKills'),
        attack_deaths=Sum('AttackDeaths'),
        attack_damage=Sum('AttackDamage'),
        defense_kills=Sum('DefenseKills'),
        defense_deaths=Sum('DefenseDeaths'),
        defense_damage=Sum('DefenseDamage'),
        
        win_kills=Sum('WinKills'),
        win_deaths=Sum('WinDeaths'),
        win_damage=Sum('WinDamage'),
        loss_kills=Sum('LossKills'),
        loss_deaths=Sum('LossDeaths'),
        loss_damage=Sum('LossDamage'),

        kast=Sum('KASTRounds')/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
        k_pct=(Sum('RoundsPlayed')-Sum('ZeroKillRounds'))/Cast(Sum('RoundsPlayed'), output_field=FloatField()),

        win_pct=(Sum('MatchWon')+0.5*Sum('MatchDraw'))/Cast(Count('Match'), FloatField()),
        round_win_pct=(Sum('AttackWins')+Sum('DefenseWins'))/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
        attack_win_pct=Sum('AttackWins')/Cast(Sum('AttackRounds'), output_field=FloatField()),
        defense_win_pct=Sum('DefenseWins')/Cast(Sum('DefenseRounds'), output_field=FloatField()),

        kdr=Sum('Kills')/Cast(Sum('Deaths'), output_field=FloatField()),
        kpr=Sum('Kills')/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
        acs=Sum('CombatScore')/Cast(Sum('RoundsPlayed'), output_field=FloatField()),
        adr=Sum('TotalDamage')/Cast(Sum('RoundsPlayed'), output_field=FloatField()),

        attack_rounds=Sum('AttackRounds')/5,
        attack_wins=Sum('AttackWins')/5,
        attack_losses=Sum('AttackLosses')/5,

        defense_rounds=Sum('DefenseRounds')/5,
        defense_wins=Sum('DefenseWins')/5,
        defense_losses=Sum('DefenseLosses')/5,

        rounds_won=(Sum('AttackWins')+Sum('DefenseWins'))/5,
        rounds_lost=(Sum('AttackLosses')+Sum('DefenseLosses'))/5,
        rounds_played=Sum('RoundsPlayed')/5,

        fb_pct=(Sum('FirstBloods')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())),
        fd_pct=(Sum('FirstDeaths')/Cast(Sum('RoundsPlayed')/5, output_field=FloatField())),

        attack_kdr=Sum('AttackKills')/Cast(Sum('AttackDeaths'), output_field=FloatField()),
        attack_adr=Sum('AttackDamage')/Cast(Sum('AttackRounds'), output_field=FloatField()),
        defense_kdr=Sum('DefenseKills')/Cast(Sum('DefenseDeaths'), output_field=FloatField()),
        defense_adr=Sum('DefenseDamage')/Cast(Sum('DefenseRounds'), output_field=FloatField()),

        max_kills = Max('Kills'),
        max_deaths = Max('Deaths'),
        max_assists = Max('Assists'),
        max_kdr = Max(F('Kills') / Cast('Deaths', FloatField())),
        max_acs = Max(F('CombatScore') / F('RoundsPlayed')),
        max_adr = Max(F('TotalDamage') / Cast('RoundsPlayed', FloatField())),
        max_fb = Max('FirstBloods'),
        max_fd = Max('FirstDeaths')
    )

    for m in count_splits_combat:
        filter_dict = {'Match__N_Duelists': m['Match__N_Duelists']}
        filtered_players = players.filter(**filter_dict)

        m['WinLossRecord'] = "{}-{}-{}".format(m['matches_won'],m['matches_lost'],m['matches_draw'])
        m['RoundRecord'] = "{}-{}".format(m["rounds_won"],m["rounds_lost"])
        m['AttackRecord'] = "{}-{}".format(m["attack_wins"],m["attack_losses"])
        m['DefenseRecord'] = "{}-{}".format(m["defense_wins"],m["defense_losses"])

        if m['Match__N_Duelists'] == 0:
            m['Count'] = "No Duelists"
        elif m['Match__N_Duelists'] == 1:
            m['Count'] = "One Duelist"
        elif m['Match__N_Duelists'] == 2:
            m['Count'] = "Two Duelists"
        elif m['Match__N_Duelists'] == 3:
            m['Count'] = "Three Duelists"
        elif m['Match__N_Duelists'] == 3:
            m['Count'] = "Four Duelists"
        elif m['Match__N_Duelists'] == 3:
            m['Count'] = "Five Duelists"

    n_matches = len(Match.objects.all())
    at_least_one_d_matches = (len(Match.objects.filter(N_Duelists__gt=0))/n_matches)*100
    one_d_matches = (len(Match.objects.filter(N_Duelists=1))/n_matches)*100
    more_d_matches = (len(Match.objects.filter(N_Duelists__gt=1))/n_matches)*100

    context = {
        'duelists': duelists,
        'count_splits': count_splits,
        'count_splits_combat': count_splits_combat,

        'n_matches': n_matches,
        'at_least_one_d_matches': at_least_one_d_matches,
        'one_d_matches': one_d_matches,
        'more_d_matches': more_d_matches,
    }

    return render(request, 'match/analysis/solo_duelists.html', context)

def leaderboard_analysis(request):
    players = Player.objects.filter(Team="Team A")

    player_stats = players.values('Username').annotate(
        num_matches=Count('Match'),

        matches_won=Sum(Case(When(MatchWon=1, then=1), output_field=IntegerField())),
        matches_lost=Sum(Case(When(MatchLost=1, then=1), output_field=IntegerField())),
        matches_draw=Sum(Case(When(MatchDraw=1, then=1), output_field=IntegerField())),

        mvps=Sum('MVP'),
        mvp_pct=Avg('MVP'),
        avg_rank=Avg('ACS_Rank'),

        mvps_win=Sum(Case(When(MatchWon=1, then='MVP'), default=0, output_field=IntegerField())),
        mvp_pct_win=Avg(Case(When(MatchWon=1, then='MVP'), default=0, output_field=IntegerField())),
        avg_rank_win=Avg(Case(When(MatchWon=1, then='ACS_Rank'), default=0, output_field=IntegerField())),

        mvps_loss=Sum(Case(When(MatchLost=1, then='MVP'), default=0, output_field=IntegerField())),
        mvp_pct_loss=Avg(Case(When(MatchLost=1, then='MVP'), default=0, output_field=IntegerField())),
        avg_rank_loss=Avg(Case(When(MatchLost=1, then='ACS_Rank'), default=0, output_field=IntegerField())),
    ).order_by('-Username')


    for p in player_stats:
        filtered_players = Player.objects.filter(Team="Team A", 
                                                 Username=p['Username'])

        tagSplit = p['Username'].split("#")

        p['DisplayName'] = tagSplit[0]
        p['UserTag'] = "#" + tagSplit[1]

        p['WinLossRecord'] = "{}-{}-{}".format(p['matches_won'],p['matches_lost'],p['matches_draw'])

        agent_counter = Counter(filtered_players.values_list('Agent', flat=True))
        if agent_counter:
            p['TopAgent'] = agent_counter.most_common(1)[0][0]
        p['TopAgentImage'] = AgentImage(p['TopAgent'])

    win = players.filter(MatchWon=1).values('Username').annotate(
        num_matches=Count('Match'),

        mvps=Sum('MVP'),
        mvp_pct=Avg('MVP'),
        avg_rank=Avg('ACS_Rank'),
    ).order_by('-Username')

    loss = players.filter(MatchLost=1).values('Username').annotate(
        num_matches=Count('Match'),

        mvps=Sum('MVP'),
        mvp_pct=Avg('MVP'),
        avg_rank=Avg('ACS_Rank'),
    ).order_by('-Username')

    mvp_stats = players.filter(MVP=1).values('Username').annotate(
        num_matches=Count('Match'),

        matches_won=Sum('MatchWon'),
        matches_lost=Sum('MatchLost'),
        matches_draw=Sum('MatchDraw'),

        total_kills=Sum('Kills'),
        total_deaths=Sum('Deaths'),
        total_assists=Sum('Assists'),

        total_score=Sum('CombatScore'),
        total_damage=Sum('TotalDamage'),

        first_bloods=Sum('FirstBloods'),
        first_deaths=Sum('FirstDeaths'),
        fb_fd_ratio = F('first_bloods')/Cast('first_deaths', FloatField()),

        kast_rounds=Sum('KASTRounds'),

        hs_pct=Sum(F('HS_Pct') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),
        damage_delta=Sum(F('DamageDelta') * F('RoundsPlayed'), output_field=FloatField()) / Cast(Sum('RoundsPlayed'), FloatField()),

        zero_kills=Sum('ZeroKillRounds'),
        one_kills=Sum('OneKillRounds'),
        two_kills=Sum('TwoKillRounds'),
        three_kills=Sum('ThreeKillRounds'),
        four_kills=Sum('FourKillRounds'),
        five_kills=Sum('FiveKillRounds'),
        six_kills=Sum('SixKillRounds'),

        attack_kills=Sum('AttackKills'),
        attack_deaths=Sum('AttackDeaths'),
        attack_damage=Sum('AttackDamage'),
        defense_kills=Sum('DefenseKills'),
        defense_deaths=Sum('DefenseDeaths'),
        defense_damage=Sum('DefenseDamage'),
        
        win_kills=Sum('WinKills'),
        win_deaths=Sum('WinDeaths'),
        win_damage=Sum('WinDamage'),
        loss_kills=Sum('LossKills'),
        loss_deaths=Sum('LossDeaths'),
        loss_damage=Sum('LossDamage'),

        attack_rounds=Sum('AttackRounds'),
        attack_wins=Sum('AttackWins'),
        attack_losses=Sum('AttackLosses'),

        defense_rounds=Sum('DefenseRounds'),
        defense_wins=Sum('DefenseWins'),
        defense_losses=Sum('DefenseLosses'),

        rounds_won=Sum('AttackWins')+Sum('DefenseWins'),
        rounds_lost=Sum('AttackLosses')+Sum('DefenseLosses'),

        rounds = Sum('RoundsPlayed'),

        kdr=F('total_kills')/Cast('total_deaths', FloatField()),
        kpr=F('total_kills')/Cast('rounds', FloatField()),
        acs=F('total_score')/Cast('rounds', FloatField()),
        adr=F('total_damage')/Cast('rounds', FloatField()),

        kast=F('kast_rounds')/Cast('rounds', FloatField()),
        k_pct=(F('rounds')-F('zero_kills'))/Cast('rounds', FloatField()),

        win_pct=(F('matches_won')+0.5*F('matches_draw'))/Cast('num_matches', FloatField()),
        round_win_pct=F('rounds_won')/Cast('rounds', FloatField()),
        attack_win_pct=F('attack_wins')/Cast('attack_rounds', FloatField()),
        defense_win_pct=F('defense_wins')/Cast('defense_rounds', FloatField()),

        kills_per_20 = (F('total_kills')/Cast('rounds', FloatField()))*20,
        deaths_per_20 = (F('total_deaths')/Cast('rounds', FloatField()))*20,
        assists_per_20 = (F('total_assists')/Cast('rounds', FloatField()))*20,

        fb_per_20 = (F('first_bloods')/Cast('rounds', FloatField()))*20,
        fd_per_20 = (F('first_deaths')/Cast('rounds', FloatField()))*20,

        attack_kdr = F('attack_kills')/Cast('attack_deaths', FloatField()), 
        attack_adr = F('attack_damage')/Cast('attack_rounds', FloatField()), 
        defense_kdr = F('defense_kills')/Cast('defense_deaths', FloatField()), 
        defense_adr = F('defense_damage')/Cast('defense_rounds', FloatField()),

        attack_kp12 = (F('attack_kills')/Cast('attack_rounds', FloatField()))*12,
        attack_dp12 = (F('attack_deaths')/Cast('attack_rounds', FloatField()))*12,
        defense_kp12 = (F('defense_kills')/Cast('defense_rounds', FloatField()))*12,
        defense_dp12 = (F('defense_deaths')/Cast('defense_rounds', FloatField()))*12,

        max_kills = Max('Kills'),
        max_deaths = Max('Deaths'),
        max_assists = Max('Assists'),
        max_kdr = Max(F('Kills') / Cast('Deaths', FloatField())),
        max_acs = Max(F('CombatScore') / F('RoundsPlayed')),
        max_adr = Max(F('TotalDamage') / Cast('RoundsPlayed', FloatField())),
        max_fb = Max('FirstBloods'),
        max_fd = Max('FirstDeaths')
    )

    mvp_stats = mvp_stats.order_by('-num_matches')

    for p in mvp_stats:
        filtered_players = Player.objects.filter(Team="Team A", 
                                                 Username=p['Username'],
                                                 MVP=1)

        tagSplit = p['Username'].split("#")

        p['DisplayName'] = tagSplit[0]
        p['UserTag'] = "#" + tagSplit[1]

        p['WinLossRecord'] = "{}-{}-{}".format(p['matches_won'],p['matches_lost'],p['matches_draw'])
        p['RoundRecord'] = "{}-{}".format(p["rounds_won"],p["rounds_lost"])
        p['AttackRecord'] = "{}-{}".format(p["attack_wins"],p["attack_losses"])
        p['DefenseRecord'] = "{}-{}".format(p["defense_wins"],p["defense_losses"])

        agent_counter = Counter(filtered_players.values_list('Agent', flat=True))
        if agent_counter:
            p['TopAgent'] = agent_counter.most_common(1)[0][0]
        p['TopAgentImage'] = AgentImage(p['TopAgent'])

        p['max_kills_id'] = filtered_players.filter(Kills=p['max_kills']).values('Match__MatchID').first()['Match__MatchID']
        p['max_deaths_id'] = filtered_players.filter(Deaths=p['max_deaths']).values('Match__MatchID').first()['Match__MatchID']
        p['max_assists_id'] = filtered_players.filter(Assists=p['max_assists']).values('Match__MatchID').first()['Match__MatchID']
        p['max_kdr_id'] = filtered_players.annotate(kdr=F('Kills') / Cast('Deaths', FloatField()))\
                                     .filter(kdr=p['max_kdr']).values('Match__MatchID').first()['Match__MatchID']
        p['max_acs_id'] = filtered_players.filter(ACS=p['max_acs']).values('Match__MatchID').first()['Match__MatchID']
        p['max_adr_id'] = filtered_players.annotate(adr=F('TotalDamage') / Cast('RoundsPlayed', FloatField()))\
                                     .filter(adr=p['max_adr']).values('Match__MatchID').first()['Match__MatchID']
        p['max_fb_id'] = filtered_players.filter(FirstBloods=p['max_fb']).values('Match__MatchID').first()['Match__MatchID']
        p['max_fd_id'] = filtered_players.filter(FirstDeaths=p['max_fd']).values('Match__MatchID').first()['Match__MatchID']

    context = {
        'player_stats': player_stats,
        'win': win,
        'loss': loss,

        'mvp_stats': mvp_stats
    }
    
    return render(request, 'match/analysis/leaderboard_analysis.html', context)

from django.db.models.functions import ExtractHour

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import urllib
import io
from matplotlib.ticker import MaxNLocator

def time_of_day(request):

    # Format x-axis labels to display in 12-hour format.
    def format_hour(value, tick_number):
        # Convert to int because the value might be a float.
        hour = int(value)
        return f'{((hour % 12) or 12)} {"AM" if hour < 12 else "PM"}'

    hourly_data = Match.objects.annotate(
            hour=ExtractHour('Date')
        ).values('hour').annotate(
            num_matches=Count('MatchID'),
            won=Sum('TeamOneWon'),
            lost=Sum('TeamOneLost'),
            draw=Sum('MatchDraw'),
            win_pct=(Sum('TeamOneWon')+0.5*Sum('MatchDraw'))/Count('MatchID'),
            round_win_pct=(Sum('TeamOneScore'))/Cast(Sum('RoundsPlayed'), FloatField()),
        ).order_by('hour')
    
    for h in hourly_data:
        h['hour_24'] = h['hour']
        h['hour'] = format_hour(h['hour'], None)
        h['MatchRecord'] = "{}-{}-{}".format(h['won'],h['lost'],h['draw'])
    
    hours = ['12 AM', '1 AM', '2 AM', '3 AM', '4 AM', '5 AM', '6 AM', '7 AM',
             '8 AM', '9 AM', '10 AM', '11 AM', '12 PM', '1 PM', '2 PM', '3 PM',
             '4 PM', '5 PM', '6 PM', '7 PM', '8 PM', '9 PM', '10 PM', '11 PM']

    # Extract hours and counts from the QuerySet.
    won_counts = [0]*24
    lost_counts = [0]*24
    draw_counts = [0]*24

    for data in hourly_data:
        index = hours.index(data['hour'])
        won_counts[index] = data['won']
        lost_counts[index] = data['lost']
        draw_counts[index] = data['draw']

    # Plot the histogram.
    plt.bar(hours, won_counts, color='#7ab378', label="Win", edgecolor="black", linewidth=0.5)
    plt.bar(hours, lost_counts, bottom=won_counts, color='#f79ea6', label="Loss", edgecolor="black", linewidth=0.5)
    plt.bar(hours, draw_counts, bottom=[i+j for i, j in zip(won_counts, lost_counts)], color='grey', label="Draw", edgecolor="black", linewidth=0.5)
    plt.ylim(0,max([a+b+c for a,b,c in zip(won_counts,lost_counts,draw_counts)])+5)

    plt.xlabel('Hour')
    plt.ylabel('Count')
    plt.title('Games Played Per Hour')

    # Apply the formatter to the x-axis.
    plt.gca().xaxis.set_major_formatter(ticker.FuncFormatter(format_hour))
    
    plt.legend(title="Match Outcome", loc='best')

    tick_hours = ['12 AM', '3 AM', '12 PM', '6 PM', "11 PM"]
    tick_indices = [hours.index(hour) for hour in tick_hours]
    plt.xticks(tick_indices, tick_hours)

    plt.tight_layout()

    # Save the figure to a BytesIO object.
    buf = io.BytesIO()
    plt.savefig(buf, format='svg')
    plt.close()

    svg = buf.getvalue().decode()
    buf.close()
    uri = urllib.parse.quote(svg)

    #############################################################
    #############################################################

    sub_qs = Player.objects.filter(Team="Team A").values('Match').annotate(min_id=Min('id')).values('min_id')
    queryset = Player.objects.filter(id__in=Subquery(sub_qs)).annotate(
        hour=ExtractHour('Match__Date'),
        time_category=Case(
            When(Q(hour__gte=12) & Q(hour__lt=20), then=Value('Pre-Night (12 PM to 8 PM)')),
            When(Q(hour__gte=20) & Q(hour__lt=24), then=Value('Early Night (8 PM to 12 AM)')),
            default=Value('Late Night (12 AM to 4 AM)'),
            output_field=models.CharField(),
        )
    )

    categorized = queryset.values('time_category').annotate(
        num_matches=Count('Match'),
        matches_won=Sum('MatchWon'),
        matches_lost=Sum('MatchLost'),
        matches_draw=Sum('MatchDraw'),

        rounds_played=Sum('RoundsPlayed'),
        rounds_won=Sum('AttackWins') + Sum('DefenseWins'),
        rounds_lost=Sum('AttackLosses') + Sum('DefenseLosses'),

        attack_rounds=Sum('AttackRounds'),
        attack_wins=Sum('AttackWins'),
        attack_losses=Sum('AttackLosses'),

        defense_rounds=Sum('DefenseRounds'),
        defense_wins=Sum('DefenseWins'),
        defense_losses=Sum('DefenseLosses'),
    ).annotate(
        win_pct=(F('matches_won') + 0.5 * F('matches_draw')) / Cast(F('num_matches'), FloatField()),
        round_win_pct=F('rounds_won') / Cast(F('rounds_played'), FloatField()),
        attack_win_pct=F('attack_wins') / Cast(F('attack_rounds'), FloatField()),
        defense_win_pct=F('defense_wins') / Cast(F('defense_rounds'), FloatField())
    ).annotate(
    ordering=Case(
        When(time_category__contains='Pre-Night', then=Value(1)),
        When(time_category__contains='Early Night', then=Value(2)),
        When(time_category__contains='Late Night', then=Value(3)),
        output_field=IntegerField(),
    )
    ).order_by('ordering')

    for m in categorized:
        m['WinLossRecord'] = "{}-{}-{}".format(m['matches_won'],m['matches_lost'],m['matches_draw'])
        m['RoundRecord'] = "{}-{}".format(m["rounds_won"],m["rounds_lost"])
        m['AttackRecord'] = "{}-{}".format(m["attack_wins"],m["attack_losses"])
        m['DefenseRecord'] = "{}-{}".format(m["defense_wins"],m["defense_losses"])

    #############################################################
    #############################################################

    queryset = Player.objects.filter(Team="Team A").annotate(
        hour=ExtractHour('Match__Date'),
        time_category=Case(
            When(Q(hour__gte=12) & Q(hour__lt=20), then=Value('Pre-Night')),
            When(Q(hour__gte=20) & Q(hour__lt=24), then=Value('Early Night')),
            default=Value('Late Night'),
            output_field=models.CharField(),
        )
    )

    player_stats = queryset.values('time_category', 'Username').annotate(
        total_matches=Count('Match'),

        matches_won=Sum('MatchWon'),
        matches_lost=Sum('MatchLost'),
        matches_draw=Sum('MatchDraw'),

        rounds_played=Sum('RoundsPlayed'),
        rounds_won=Sum('AttackWins') + Sum('DefenseWins'),
        rounds_lost=Sum('AttackLosses') + Sum('DefenseLosses'),

        kdr = Sum('Kills')/Cast(Sum('Deaths'), FloatField()),
        kpr = Sum('Kills')/Cast(Sum('RoundsPlayed'), FloatField()),
        acs = Sum('CombatScore')/Cast(Sum('RoundsPlayed'), FloatField()),
    ).annotate(
        win_pct=(F('matches_won') + 0.5 * F('matches_draw')) / F('total_matches'),
        round_win_pct=F('rounds_won') / F('rounds_played'),
    )

    for p in player_stats:
        p['WinLossRecord'] = "{}-{}-{}".format(p['matches_won'],p['matches_lost'],p['matches_draw'])

    def restructure_queryset(queryset):
        result = {}
        for record in queryset:
            username = record['Username']
            category = record['time_category']
            if username not in result:
                result[username] = {}
            result[username][category] = record
        return result

    player_stats = restructure_queryset(player_stats)

    #############################################################
    #############################################################

    context = {
        'uri': uri,
        'hourly_data':hourly_data,
        'categorized':categorized,
        'player_stats': player_stats,
        'categories': ['Pre-Night', 'Early Night', 'Late Night'],
    }

    return render(request, 'match/analysis/time_of_day.html', context)

import numpy as np

def versatility(request):

    player_data = Player.objects.filter(Team="Team A").annotate(
        acs=Sum('CombatScore') / Sum('RoundsPlayed')).values('Username', 'Agent', 'Role', 'acs')

    # Create a pandas DataFrame from the QuerySet
    df = pd.DataFrame.from_records(player_data)

    # Calculate the sum of average_combat_score for each agent and role
    grouped = df.groupby(['Username', 'Agent', 'Role']).mean().reset_index()

    agent_counts = df.groupby(['Username', 'Agent']).size().reset_index(name='counts')
    role_counts = df.groupby(['Username', 'Role']).size().reset_index(name='counts')

    agent_counts['prob'] = agent_counts.groupby('Username')['counts'].transform(lambda x: x / x.sum())
    role_counts['prob'] = role_counts.groupby('Username')['counts'].transform(lambda x: x / x.sum())

    agent_counts['naive_entropy'] = -agent_counts['prob'] * np.log2(agent_counts['prob'])
    role_counts['naive_entropy'] = -role_counts['prob'] * np.log2(role_counts['prob'])

    # Get the total naive entropies per user
    naive_agent_entropy = agent_counts.groupby('Username')['naive_entropy'].sum().reset_index()
    naive_role_entropy = role_counts.groupby('Username')['naive_entropy'].sum().reset_index()

    # Merge the naive and weighted entropies into the final dataframe
    final_df = pd.merge(naive_agent_entropy, naive_role_entropy, on='Username', suffixes=('_naive_agent', '_naive_role'))

    def process_row(row):
        N_ROLES = 4

        filtered = Player.objects.filter(Team="Team A", Username=row['Username'])
        tag_split = row['Username'].split("#")
        row['DisplayName'] = tag_split[0]
        row['UserTag'] = "#" + tag_split[1]
        agents = filtered.values_list('Agent', flat=True)
        row['MP'] = len(agents)
        agent_counter = Counter(agents)
        agents_played = len(agent_counter)
        roles_played = len(filtered.values_list('Role', flat=True).distinct())
        row['AgentPct'] = len(agent_counter)/len(agent_map)
        row['AgentStr'] = "{}/{}".format(agents_played,len(agent_map))
        row['RolePct'] = roles_played/N_ROLES
        row['RoleStr'] = "{}/{}".format(roles_played,N_ROLES)
        row['TopAgent'] = agent_counter.most_common(1)[0][0] if agent_counter else None
        row['TopAgentImage'] = AgentImage(row['TopAgent']) if row['TopAgent'] else None
        return row

    final_df = final_df.apply(process_row, axis=1).sort_values(by="MP",ascending=False).reset_index(drop=True)

    context = {
        "player_stats": final_df.to_dict('records'),
        "playable_agents": len(agent_map),
    }

    return render(request, 'match/analysis/versatility.html', context)