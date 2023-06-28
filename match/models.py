from django.db import models

agent_map = {"41fb69c1-4189-7b37-f117-bcaf1e96f1bf":"Astra",
             "5f8d3a7f-467b-97f3-062c-13acf203c006":"Breach",
             "9f0d8ba9-4140-b941-57d3-a7ad57c6b417":"Brimstone",
             "22697a3d-45bf-8dd7-4fec-84a9e28c69d7":"Chamber",
             "117ed9e3-49f3-6512-3ccf-0cada7e3823b":"Cypher",
             "cc8b64c8-4b25-4ff9-6e7f-37b4da43d235":"Deadlock",
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

class Match(models.Model):
    MatchID = models.CharField(max_length=200, unique=True)
    Map = models.CharField(max_length=200)
    Date = models.DateTimeField()
    Score = models.CharField(max_length=200)
    TeamOneScore = models.IntegerField()
    TeamTwoScore = models.IntegerField()
    ScoreDifferential = models.IntegerField()
    TeamOneWon = models.IntegerField()
    TeamOneLost = models.IntegerField()
    MatchDraw = models.IntegerField()
    RoundsPlayed = models.IntegerField()
    Players = models.CharField(max_length=500)
    MVP = models.CharField(max_length=200)
    MVP_ACS = models.IntegerField()
    TopKiller = models.CharField(max_length=200)
    MostKills = models.IntegerField()
    TopKDR = models.CharField(max_length=200)
    TopKDRValue = models.FloatField()
    N_Duelists = models.IntegerField()
    N_Sentinels = models.IntegerField()
    N_Initiators = models.IntegerField()
    N_Controllers = models.IntegerField()
    
    def __str__(self):
        return ', '.join(f'{field.name}={getattr(self, field.name)}' for field in self._meta.fields)
    
    @property
    def Outcome(self):
        if self.TeamOneWon:
            return "Win"
        elif self.TeamOneLost:
            return "Loss"
        elif self.MatchDraw:
            return "Draw"

class Player(models.Model):
    Match = models.ForeignKey(Match, on_delete=models.CASCADE)

    Username = models.CharField(max_length=200)
    DisplayName = models.CharField(max_length=200)

    Team = models.CharField(max_length=200)

    Rank = models.CharField(max_length=200)
    Agent = models.CharField(max_length=200)
    Role = models.CharField(max_length=200)

    MVP = models.IntegerField()
    ACS_Rank = models.IntegerField()

    TRS = models.IntegerField()
    ACS = models.IntegerField()
    CombatScore = models.IntegerField()

    AverageDamage = models.FloatField()
    TotalDamage = models.IntegerField()

    Kills = models.IntegerField()
    Deaths = models.IntegerField()
    Assists = models.IntegerField()

    KillDifferential = models.IntegerField()
    KillDeathRatio = models.FloatField()

    DamageDelta = models.IntegerField()
    HS_Pct = models.FloatField()
    KAST = models.FloatField()
    KASTRounds = models.IntegerField()

    FirstBloods = models.IntegerField()
    FirstDeaths = models.IntegerField()
    MultiKills = models.IntegerField()
    
    AttackKills = models.IntegerField()
    AttackDeaths = models.IntegerField()
    AttackAssists = models.IntegerField()
    AttackKillDeathRatio = models.FloatField()

    DefenseKills = models.IntegerField()
    DefenseDeaths = models.IntegerField()
    DefenseAssists = models.IntegerField()
    DefenseKillDeathRatio = models.FloatField()

    WinKills = models.IntegerField()
    WinDeaths = models.IntegerField()
    WinKillDeathRatio = models.FloatField()

    LossKills = models.IntegerField()
    LossDeaths = models.IntegerField()
    LossKillDeathRatio = models.FloatField()

    AttackRounds = models.IntegerField()
    AttackDamage = models.IntegerField()
    AttackAverageDamage = models.FloatField()

    DefenseRounds = models.IntegerField()
    DefenseDamage = models.IntegerField()
    DefenseAverageDamage = models.FloatField()

    WinDamage = models.IntegerField()
    WinAverageDamage = models.FloatField()
    LossDamage = models.IntegerField()
    LossAverageDamage = models.FloatField()

    ZeroKillRounds = models.IntegerField()
    OneKillRounds = models.IntegerField()
    TwoKillRounds = models.IntegerField()
    ThreeKillRounds = models.IntegerField()
    FourKillRounds = models.IntegerField()
    FiveKillRounds = models.IntegerField()
    SixKillRounds = models.IntegerField()

    AttackWins = models.IntegerField()
    AttackLosses = models.IntegerField()
    DefenseWins = models.IntegerField()
    DefenseLosses = models.IntegerField()

    MatchWon = models.IntegerField()
    MatchLost = models.IntegerField()
    MatchDraw = models.IntegerField()
    RoundsPlayed = models.IntegerField()

    def __str__(self):
        return ', '.join(f'{field.name}={getattr(self, field.name)}' for field in self._meta.fields)
    
    @property
    def RoundsWon(self):
        return self.AttackWins+self.DefenseWins
    
    @property
    def WeightWins(self):
        return self.MatchWon+0.5*self.MatchDraw
    
    @property
    def ExactADR(self):
        return self.TotalDamage/(self.Match.RoundsPlayed)
    
    @property
    def RankImage(self):
        ranks = ["Iron", "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Ascendant", "Immortal"]
        try:
            tier, number = self.Rank.split()
            number = int(number)
            if tier not in ranks or number < 1 or number > 3:
                raise ValueError
        except ValueError:
            return "https://trackercdn.com/cdn/tracker.gg/valorant/icons/tiersv2/0.png"
        else:
            tier_number = ranks.index(tier) * 3 + number + 2
            return f"https://trackercdn.com/cdn/tracker.gg/valorant/icons/tiersv2/{tier_number}.png"
        
    @property
    def AgentImage(self):
        agent_id = None
        for k, v in agent_map.items():
            if v == self.Agent:
                agent_id = k
                break
        if agent_id:
            return f"https://titles.trackercdn.com/valorant-api/agents/{agent_id}/displayicon.png"
        return None
    
    @property
    def AttackScore(self):
        return str(self.AttackWins)+"-"+str(self.AttackLosses)
    
    @property
    def AttackWinPct(self):
        return self.AttackWins/self.AttackRounds
    
    @property
    def DefenseScore(self):
        return str(self.DefenseWins)+"-"+str(self.DefenseLosses)
    
    @property
    def DefenseWinPct(self):
        return self.DefenseWins/self.DefenseRounds
    
    @property 
    def TotalWinPct(self):
        return (self.AttackWins+self.DefenseWins) / self.RoundsPlayed
    
    @property
    def KillsPerRound(self):
        return self.Kills/self.Match.RoundsPlayed
    
    @property
    def K_Pct(self):
        return (self.Match.RoundsPlayed-self.ZeroKillRounds)/self.Match.RoundsPlayed
    
    @property
    def AtLeastZeroKills(self):
        return self.ZeroKillRounds+self.OneKillRounds+self.TwoKillRounds+self.ThreeKillRounds+self.FourKillRounds+self.FiveKillRounds+self.SixKillRounds
    
    @property
    def AtLeastOneKill(self):
        return self.OneKillRounds+self.TwoKillRounds+self.ThreeKillRounds+self.FourKillRounds+self.FiveKillRounds+self.SixKillRounds
    
    @property
    def AtLeastTwoKills(self):
        return self.TwoKillRounds+self.ThreeKillRounds+self.FourKillRounds+self.FiveKillRounds+self.SixKillRounds
    
    @property
    def AtLeastThreeKills(self):
        return self.ThreeKillRounds+self.FourKillRounds+self.FiveKillRounds+self.SixKillRounds
    
    @property
    def AtLeastFourKills(self):
        return self.FourKillRounds+self.FiveKillRounds+self.SixKillRounds
    
    @property
    def AtLeastFiveKills(self):
        return self.FiveKillRounds+self.SixKillRounds
    
    @property
    def AtLeastSixKills(self):
        return self.SixKillRounds
    
    @property
    def UserTag(self):
        return "#"+self.Username.split("#")[1]
        
    @property
    def FB_Pct(self):
        return self.FirstBloods/(self.RoundsPlayed)
    
    @property
    def FD_Pct(self):
        return self.FirstDeaths/(self.RoundsPlayed)
    
    @property
    def FBFDRatio(self):
        if self.FirstDeaths == 0:
            return self.FirstBloods
        return self.FirstBloods/self.FirstDeaths