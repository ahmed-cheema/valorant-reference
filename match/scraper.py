from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium import webdriver
from datetime import datetime
import pandas as pd
import numpy as np
import bs4 as bs
import json
import time

import undetected_chromedriver as uc

from .models import Match, Player, User

def printError(msg,match_id):
    print("\n=== ERROR ===\nMATCH ID: {}".format(match_id))
    raise SystemExit("-> " + msg)

def str2num(value):
    if "%" in value:
        return float(value.strip("%")) / 100
    elif "." in value:
        return float(value)
    elif "," in value:
        return int(value.replace(",",""))
    else:
        return int(value)
    
def safe_kdr(k,d):
    if d != 0:
        return k/d
    else:
        return k
    
def map_rank(url):
    number = int(url.split("tiersv2/")[1].split(".png")[0])
    if number == 0 or number == 1 or number == 2:
        return "N/A"
    elif number == 27:
        return "Radiant"
    else:
        tier = (number - 3) // 3
        rank = (number - 3) % 3 + 1
        if tier == 0:
            return f"Iron {rank}"
        elif tier == 1:
            return f"Bronze {rank}"
        elif tier == 2:
            return f"Silver {rank}"
        elif tier == 3:
            return f"Gold {rank}"
        elif tier == 4:
            return f"Platinum {rank}"
        elif tier == 5:
            return f"Diamond {rank}"
        elif tier == 6:
            return f"Ascendant {rank}"
        elif tier == 7:
            return f"Immortal {rank}"
        
def xpath_soup(element):
    """
    Generate xpath of soup element
    :param element: bs4 text or node
    :return: xpath as string
    """
    components = []
    child = element if element.name else element.parent
    for parent in child.parents:
        """
        @type parent: bs4.element.Tag
        """
        children_list = list(parent.children)
        previous = children_list[:parent.contents.index(child)]
        xpath_tag = child.name
        xpath_index = sum(1 for i in previous if i.name == xpath_tag) + 1
        components.append(xpath_tag if xpath_index == 1 else '%s[%d]' % (xpath_tag, xpath_index))
        child = parent
    components.reverse()
    return '/%s' % '/'.join(components)

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

role_map = {"Astra":"Controller",
            "Breach":"Initiator",
            "Brimstone":"Controller",
            "Chamber":"Sentinel",
            "Cypher":"Sentinel",
            "Deadlock":"Sentinel",
            "Fade":"Initiator",
            "Gekko":"Initiator",
            "Harbor":"Controller",
            "Jett":"Duelist",
            "KAY/O":"Initiator",
            "Killjoy":"Sentinel",
            "Neon":"Duelist",
            "Omen":"Controller",
            "Phoenix":"Duelist",
            "Raze":"Duelist",
            "Reyna":"Duelist",
            "Sage":"Sentinel",
            "Skye":"Initiator",
            "Sova":"Initiator",
            "Viper":"Controller",
            "Yoru":"Duelist"}

InvalidMatches = ["6fa64508-aa14-4600-9a0c-969d6d580398", # Competitive: Xanns played on Noel's acc
                  "ee175228-811f-4905-af0e-ce922d1b4788", # Premier: Xanns played on Noel's acc
                  "7062b7bd-89fa-40ac-a832-89a8c2613573", # Premier: Xanns played on Noel's acc
                 ]

with open('match/squad.json', 'r') as f:
    squad = json.load(f)

def GetNewMatches(username):

    url = "https://tracker.gg/valorant/profile/riot/{}/matches".format(username.replace("#","%23"))

    options = Options()
    options.add_argument("Window-size=1920,1080")

    s = Service(executable_path='C:/Users/cheem/chromedriver.exe')

    browser = webdriver.Chrome(service=s, options=options)

    while(True):
        soup = bs.BeautifulSoup(browser.page_source)
        if len(soup.find_all("div",{"class": "trn-match-row"})) == 0:
            continue
        else:
            break

    match_rows = browser.find_elements(By.CLASS_NAME, "trn-match-row")

    match_ids = []

    for match in match_rows:
        match.click()
        
        while(True):
            soupMatch = bs.BeautifulSoup(browser.page_source)
            if len(soupMatch.find_all("a",{"class": "trn-button trn-button--transparent"})) == 0:
                continue
            else:
                break

        match_id = soupMatch.find("a",{"class": "trn-button trn-button--transparent"})["href"].split("match/")[1]

        if Match.objects.filter(MatchID=match_id).exists():
            print("Obtained {} new Match IDs prior to last match in database".format(len(match_ids)))
            browser.quit()
            break

        match_ids.append(match_id)

        browser.find_element(By.CLASS_NAME, "trn-button-close").click()

    return match_ids

def ScrapeMatch(match_id):

    if Match.objects.filter(MatchID=match_id).exists():
        printError("Match with this ID already exists",match_id)

    if match_id in InvalidMatches:
        printError("Match is in pre-determined list of invalid matches",match_id)

    url = "https://tracker.gg/valorant/match/{}".format(match_id)

    options = Options()
    #options.add_argument("--headless")
    options.add_argument("Window-size=1920,1080")
    #options.add_extension("C:/Users/cheem/cors_unblock.crx")

    s = Service(executable_path="C:/Users/cheem/chromedriver.exe")

    browser = uc.Chrome(service=s, options=options)
    browser.get(url)

    while(True):
        soup = bs.BeautifulSoup(browser.page_source, features="html.parser")
        body_class = soup.body.get('class')
        if body_class and 'skin-takeover' in body_class:
            break
        else:
            if (len(soup.find_all("span", {"class": "trn-ign"})) == 0) or \
            ((len(soup.find_all("div", {"id": "closeIconHit"})) == 0) and \
            (len(soup.find_all("div", {"id": "cpmstarvideosliderclose"})) == 0)):
                continue
            else:
                break

    time.sleep(0.5)

    if len(soup.find_all("div", {"id": "closeIconHit"})) != 0:
        closeVideo = soup.select("div[id='closeIconHit']")[0]
        browser.find_element(by=By.XPATH, value=xpath_soup(closeVideo)).click()
    elif len(soup.find_all("div", {"id": "cpmstarvideosliderclose"})):
        closeVideo = soup.select("div[id='cpmstarvideosliderclose']")[0]
        browser.find_element(by=By.XPATH, value=xpath_soup(closeVideo)).click()

    mapName = soup.find("div", {"class": "trn-match-drawer__header-value"}).text
    datetime_object = datetime.strptime([x.text.strip() for x in soup.select("div.trn-match-drawer__header-label") if ", " in x.text][0],
                                        "%m/%d/%y, %I:%M %p")

    teamOneScore = int(soup.find("div", {"class": "trn-match-drawer__header-value valorant-color-team-1"}).text)
    teamTwoScore = int(soup.find("div", {"class": "trn-match-drawer__header-value valorant-color-team-2"}).text)

    usernames = [x.text.strip().replace("  #","#") for x in soup.find_all("span", {"class": "trn-ign"})]
    displayNames = [x.split("#")[0] for x in usernames]
    agents = [agent_map.get(x["src"].split("agents/")[1].split("/displayicon.png")[0]) for x in soup.find_all("img", {"data-v-f2f6dd5e": True, "data-v-2a2d68ed": True, }) if ("displayicon" in x["src"])]
    roles = [role_map.get(x) for x in agents]

    TeamChunks = soup.find_all("div",{"class": "st__item st-header__item st-header__item--sortable st__item--sticky st__item--wide"})
    if "Avg. Rank:" in str(TeamChunks[0]) and "Avg. Rank:" in str(TeamChunks[1]):
        ranks = [map_rank(e) for i, e in enumerate([x["src"] for x in soup.find_all("img", {"data-v-f2f6dd5e": True, "data-v-2a2d68ed": True, }) if ("tiersv2" in x["src"])]) if i not in [0,6]]
    elif "Avg. Rank:" in str(TeamChunks[0]):
        ranks = [map_rank(e) for i, e in enumerate([x["src"] for x in soup.find_all("img", {"data-v-f2f6dd5e": True, "data-v-2a2d68ed": True, }) if ("tiersv2" in x["src"])]) if i not in [0]]
    elif "Avg. Rank:" in str(TeamChunks[1]):
        ranks = [map_rank(e) for i, e in enumerate([x["src"] for x in soup.find_all("img", {"data-v-f2f6dd5e": True, "data-v-2a2d68ed": True, }) if ("tiersv2" in x["src"])]) if i not in [5]]
    else:
        ranks = [map_rank(e) for i, e in enumerate([x["src"] for x in soup.find_all("img", {"data-v-f2f6dd5e": True, "data-v-2a2d68ed": True, }) if ("tiersv2" in x["src"])])]

    won = ([int(teamOneScore > teamTwoScore)] * 5) + ([int(teamTwoScore > teamOneScore)] * 5)

    rounds = [teamOneScore+teamTwoScore] * 10
    roundsWon = ([teamOneScore] * 5) + ([teamTwoScore] * 5)
    roundsLost = ([teamTwoScore] * 5) + ([teamOneScore] * 5)

    if (sum(e in squad for e in usernames[0:5]) > 1) & (sum(e in squad for e in usernames[0:5]) < 5):
        not_in_squad = ", ".join([e for e in usernames[0:5] if e not in squad])
        printError("Five queue not detected: {} not in squad".format(not_in_squad),match_id)
    elif sum(e in squad for e in usernames[0:5]) == 5:
        teams = (["Team A"] * 5) + (["Team B"] * 5)
    elif (sum(e in squad for e in usernames[5:10]) > 1) & (sum(e in squad for e in usernames[5:10]) < 5):
        not_in_squad = ", ".join([e for e in usernames[5:10] if e not in squad])
        printError("Five queue not detected: {} not in squad".format(not_in_squad),match_id)
    elif sum(e in squad for e in usernames[5:10]) == 5:
        teams = (["Team B"] * 5) + (["Team A"] * 5)
    else:
        printError("Five queue not detected",match_id)

    values = [str2num(x.text) for x in soup.find_all("div", {"data-v-2a2d68ed": True, "class": "value"})]

    data = {"GameID": [match_id] * 10,
            "Map": [mapName] * 10,
            "Date": [datetime_object.strftime("%Y-%m-%d %H:%M:%S")] * 10,
            "DisplayName": displayNames,
            "Username": usernames,
            "Team": teams,
            "Rounds":rounds,
            "RoundsWon":roundsWon,
            "RoundsLost":roundsLost,
            "GameWon":won,
            "Rank": ranks,
            "Agent": agents,
            "Role": roles}

    tracker_columns = ["TRS","ACS","Kills","Deaths","Assists","KillDifferential","KillDeathRatio","DamageDelta","AverageDamage","HS_Pct","KAST","FirstBloods","FirstDeaths","MultiKills"]
    for i, col in enumerate(tracker_columns):
        data[col] = values[i::14]

    df = pd.DataFrame(data)

    df["CombatScore"] = df.ACS*df.Rounds
    df["KASTRounds"] = (df.KAST*df.Rounds).round()
    df["MatchWon"] = (df.RoundsWon > df.RoundsLost).astype(int)
    df["MatchLost"] = (df.RoundsWon < df.RoundsLost).astype(int)
    df["MatchDraw"] = (df.RoundsWon == df.RoundsLost).astype(int)
    df["RoundsPlayed"] = df.RoundsWon + df.RoundsLost

    df.KillDeathRatio = [safe_kdr(x,y) for x,y in zip(df.Kills,df.Deaths)]

    performanceButton = [x for x in soup.find_all("div",{"class":"trn-match-drawer__tabs-tab"}) if "Performance" in x.text][0]
    browser.find_element(by=By.XPATH, value=xpath_soup(performanceButton)).click()

    row_list = []
    for i in range(0,10):
        perfSoup = bs.BeautifulSoup(browser.page_source, features="html.parser")

        playerTeammates = list(df[df.Team == df.Team[i]].Username)

        active_player = perfSoup.find("div", {"class": "player--active"})
        next_player = active_player.find_next_sibling("div", {"class": "player"})

        username = (perfSoup.find("span", {"class": "trn-ign__username"}).text+perfSoup.find("span", {"class": "trn-ign__discriminator"}).text).strip().replace("  #","#")
        hs_pct = np.round(float(perfSoup.select('div.stat > div.label:-soup-contains("HS%") + div.value')[0].text.strip().replace("%",""))/100,3)

        rounds = perfSoup.select("div[class='round']")

        WK, WD, WDMG, LK, LD, LDMG, ADMG, ARds, DDMG, DRds, k0, k1, k2, k3, k4, k5, k6, AW, AL, DW, DL = [0] * 21
        for r in rounds:
            outcome = r.find("div", {"class": "outcome"})["class"][1].split("--")[1]

            nKills = len(r.select("div[class='kill']"))
            nDeaths = len(r.select("div[class='death']"))

            if outcome == "win":
                WK += nKills
                WD += nDeaths
            if outcome == "loss":
                LK += nKills
                LD += nDeaths

            if nKills == 0:
                k0 += 1
            elif nKills == 1:
                k1 += 1
            elif nKills == 2:
                k2 += 1
            elif nKills == 3:
                k3 += 1
            elif nKills == 4:
                k4 += 1
            elif nKills == 5:
                k5 += 1
            elif nKills == 6:
                k6 += 1

            browser.find_element(by=By.XPATH, value=xpath_soup(r)).click()
            
            roundSoup = bs.BeautifulSoup(browser.page_source, features="html.parser")

            roundSide = roundSoup.select("div[class='side']")[0].text.strip().split(" ")[0]

            dmg = 0
            dmg_rows = roundSoup.find_all("div", {"class": "st-content__item"})
            for dr in dmg_rows:
                try:
                    dmgPlayerUsername = dr.select("span.trn-ign")[0].text.strip().replace("  #","#")
                    if dmgPlayerUsername not in playerTeammates:
                        dmg += int(dr.find_all("div", {"class": "st__item st-content__item-value st__item--align-center"})[1].text)
                except:
                    break

            if roundSide == "Attack":
                ADMG += dmg
                ARds += 1
            elif roundSide == "Defense":
                DDMG += dmg
                DRds += 1

            if outcome == "win":
                WDMG += dmg
                if roundSide == "Attack":
                    AW += 1
                else:
                    DW += 1
            elif outcome == "loss":
                LDMG += dmg
                if roundSide == "Attack":
                    AL += 1
                else:
                    DL += 1

        AK, AA, AD, AKD = [pd.to_numeric(x.text) for x in perfSoup.select('div.side-header:-soup-contains("Attack")')[0].select("div.value")]
        DK, DA, DD, DKD = [pd.to_numeric(x.text) for x in perfSoup.select('div.side-header:-soup-contains("Defense")')[0].select("div.value")]

        row_list.append({
            "Username":username,
            "HS_Pct":hs_pct,
            "AttackKills":AK,
            "AttackAssists":AA,
            "AttackDeaths":AD,
            "AttackKillDeathRatio":safe_kdr(AK,AD),
            "DefenseKills":DK,
            "DefenseAssists":DA,
            "DefenseDeaths":DD,
            "DefenseKillDeathRatio":safe_kdr(DK,DD),
            "WinKills":WK,
            "WinDeaths":WD,
            "WinKillDeathRatio":safe_kdr(WK,WD),
            "LossKills":LK,
            "LossDeaths":LD,
            "LossKillDeathRatio":safe_kdr(LK,LD),
            "TotalDamage":ADMG+DDMG,
            "AttackRounds":ARds,
            "AttackDamage":ADMG,
            "DefenseRounds":DRds,
            "DefenseDamage":DDMG,
            "WinDamage":WDMG,
            "LossDamage":LDMG,
            "AttackAverageDamage":safe_kdr(ADMG,ARds),
            "DefenseAverageDamage":safe_kdr(DDMG,DRds),
            "ZeroKillRounds":k0,
            "OneKillRounds":k1,
            "TwoKillRounds":k2,
            "ThreeKillRounds":k3,
            "FourKillRounds":k4,
            "FiveKillRounds":k5,
            "SixKillRounds":k6,
            "AttackWins":AW,
            "AttackLosses":AL,
            "DefenseWins":DW,
            "DefenseLosses":DL
        })
        
        if i != 9:
            browser.find_element(by=By.XPATH,value=xpath_soup(next_player.find("div", {"class": "image"}))).click()

        browser.find_element(by=By.XPATH, value=xpath_soup(r)).click()

    pf = pd.DataFrame(row_list)

    df.HS_Pct = pf.HS_Pct

    db = pd.merge(df,pf)

    db["WinAverageDamage"] = np.vectorize(safe_kdr)(db.WinDamage,db.RoundsWon)
    db["LossAverageDamage"] = np.vectorize(safe_kdr)(db.LossDamage,db.RoundsLost)

    browser.quit()

    teamA_df = db[db.Team == "Team A"].reset_index(drop=True)
    role_vc = teamA_df.Role.value_counts()
    
    teamA_score = teamA_df.RoundsWon.max()
    teamB_score = db[db.Team == "Team B"].RoundsWon.max()

    sorted_players = sorted(teamA_df['DisplayName'], key=lambda x: x.lower())
    players = ", ".join(sorted_players)

    ACS_Leaders = teamA_df.sort_values(by=["ACS","Kills","KillDeathRatio"], ascending=False).reset_index(drop=True)
    K_Leaders = teamA_df.sort_values(by=["Kills","ACS","KillDeathRatio"], ascending=False).reset_index(drop=True)
    KDR_Leaders = teamA_df.sort_values(by=["KillDeathRatio","Kills","ACS"], ascending=False).reset_index(drop=True)

    match = Match(MatchID = db["GameID"][0],
                  Map = db["Map"][0],
                  Date = db["Date"][0],
                  Score = str(teamA_score)+"-"+str(teamB_score),
                  TeamOneScore = teamA_score,
                  TeamTwoScore = teamB_score,
                  TeamOneWon = int(teamA_score > teamB_score),
                  TeamOneLost = int(teamA_score < teamB_score),
                  ScoreDifferential = teamA_score - teamB_score,
                  MatchDraw = int(teamA_score == teamB_score),
                  RoundsPlayed = teamA_score+teamB_score,
                  Players = players,
                  MVP = ACS_Leaders.DisplayName[0],
                  MVP_ACS = ACS_Leaders.ACS[0],
                  TopKiller = K_Leaders.DisplayName[0],
                  MostKills = K_Leaders.Kills[0],
                  TopKDR = KDR_Leaders.DisplayName[0],
                  TopKDRValue = KDR_Leaders.KillDeathRatio[0],
                  N_Duelists = role_vc.get("Duelist",0),
                  N_Sentinels = role_vc.get("Sentinel",0),
                  N_Initiators = role_vc.get("Initiator",0),
                  N_Controllers = role_vc.get("Controller",0))
    match.save()

    for idx, row in db.iterrows():
        if row["Team"] == "Team A":
            if not User.objects.filter(Username=row["Username"]).exists():
                user = User(Username = row["Username"],
                            DisplayName = row["DisplayName"],
                            UserTag = row["Username"].split("#")[1])
                user.save()
            player = Player(Match = match,
                            Username = row["Username"],
                            DisplayName = row["DisplayName"],
                            Team = row["Team"],
                            Rank = row["Rank"],
                            Agent = row["Agent"],
                            Role = row["Role"],
                            TRS = row["TRS"],
                            ACS = row["ACS"],
                            CombatScore = row["CombatScore"],
                            AverageDamage = row["AverageDamage"],
                            TotalDamage = row["TotalDamage"],
                            Kills = row["Kills"],
                            Deaths = row["Deaths"],
                            Assists = row["Assists"],
                            KillDifferential = row["KillDifferential"],
                            KillDeathRatio = row["KillDeathRatio"],
                            DamageDelta = row["DamageDelta"],
                            HS_Pct = row["HS_Pct"],
                            KAST = row["KAST"],
                            KASTRounds = row["KASTRounds"],
                            FirstBloods = row["FirstBloods"],
                            FirstDeaths = row["FirstDeaths"],
                            MultiKills = row["MultiKills"],
                            AttackKills = row["AttackKills"],
                            AttackDeaths = row["AttackDeaths"],
                            AttackAssists = row["AttackAssists"],
                            AttackKillDeathRatio = row["AttackKillDeathRatio"],
                            DefenseKills = row["DefenseKills"],
                            DefenseDeaths = row["DefenseDeaths"],
                            DefenseAssists = row["DefenseAssists"],
                            DefenseKillDeathRatio = row["DefenseKillDeathRatio"],
                            WinKills = row["WinKills"],
                            WinDeaths = row["WinDeaths"],
                            WinKillDeathRatio = row["WinKillDeathRatio"],
                            LossKills = row["LossKills"],
                            LossDeaths = row["LossDeaths"],
                            LossKillDeathRatio = row["LossKillDeathRatio"],
                            AttackRounds = row["AttackRounds"],
                            AttackDamage = row["AttackDamage"],
                            AttackAverageDamage = row["AttackAverageDamage"],
                            DefenseRounds = row["DefenseRounds"],
                            DefenseDamage = row["DefenseDamage"],
                            DefenseAverageDamage = row["DefenseAverageDamage"],
                            WinDamage = row["WinDamage"],
                            WinAverageDamage = row["WinAverageDamage"],
                            LossDamage = row["LossDamage"],
                            LossAverageDamage = row["LossAverageDamage"],
                            ZeroKillRounds = row["ZeroKillRounds"],
                            OneKillRounds = row["OneKillRounds"],
                            TwoKillRounds = row["TwoKillRounds"],
                            ThreeKillRounds = row["ThreeKillRounds"],
                            FourKillRounds = row["FourKillRounds"],
                            FiveKillRounds = row["FiveKillRounds"],
                            SixKillRounds = row["SixKillRounds"],
                            AttackWins = row["AttackWins"],
                            AttackLosses = row["AttackLosses"],
                            DefenseWins = row["DefenseWins"],
                            DefenseLosses = row["DefenseLosses"],
                            MatchWon = row["MatchWon"],
                            MatchLost = row["MatchLost"],
                            MatchDraw = row["MatchDraw"],
                            RoundsPlayed = row["RoundsPlayed"],
                            MVP=int(ACS_Leaders.Username[0] == row["Username"]),
                            ACS_Rank=ACS_Leaders[ACS_Leaders.Username == row["Username"]].index.item()+1)
            player.save()
        else:
            player = Player(Match = match,
                            Username = row["Username"],
                            DisplayName = row["DisplayName"],
                            Team = row["Team"],
                            Rank = row["Rank"],
                            Agent = row["Agent"],
                            Role = row["Role"],
                            TRS = row["TRS"],
                            ACS = row["ACS"],
                            CombatScore = row["CombatScore"],
                            AverageDamage = row["AverageDamage"],
                            TotalDamage = row["TotalDamage"],
                            Kills = row["Kills"],
                            Deaths = row["Deaths"],
                            Assists = row["Assists"],
                            KillDifferential = row["KillDifferential"],
                            KillDeathRatio = row["KillDeathRatio"],
                            DamageDelta = row["DamageDelta"],
                            HS_Pct = row["HS_Pct"],
                            KAST = row["KAST"],
                            KASTRounds = row["KASTRounds"],
                            FirstBloods = row["FirstBloods"],
                            FirstDeaths = row["FirstDeaths"],
                            MultiKills = row["MultiKills"],
                            AttackKills = row["AttackKills"],
                            AttackDeaths = row["AttackDeaths"],
                            AttackAssists = row["AttackAssists"],
                            AttackKillDeathRatio = row["AttackKillDeathRatio"],
                            DefenseKills = row["DefenseKills"],
                            DefenseDeaths = row["DefenseDeaths"],
                            DefenseAssists = row["DefenseAssists"],
                            DefenseKillDeathRatio = row["DefenseKillDeathRatio"],
                            WinKills = row["WinKills"],
                            WinDeaths = row["WinDeaths"],
                            WinKillDeathRatio = row["WinKillDeathRatio"],
                            LossKills = row["LossKills"],
                            LossDeaths = row["LossDeaths"],
                            LossKillDeathRatio = row["LossKillDeathRatio"],
                            AttackRounds = row["AttackRounds"],
                            AttackDamage = row["AttackDamage"],
                            AttackAverageDamage = row["AttackAverageDamage"],
                            DefenseRounds = row["DefenseRounds"],
                            DefenseDamage = row["DefenseDamage"],
                            DefenseAverageDamage = row["DefenseAverageDamage"],
                            WinDamage = row["WinDamage"],
                            WinAverageDamage = row["WinAverageDamage"],
                            LossDamage = row["LossDamage"],
                            LossAverageDamage = row["LossAverageDamage"],
                            ZeroKillRounds = row["ZeroKillRounds"],
                            OneKillRounds = row["OneKillRounds"],
                            TwoKillRounds = row["TwoKillRounds"],
                            ThreeKillRounds = row["ThreeKillRounds"],
                            FourKillRounds = row["FourKillRounds"],
                            FiveKillRounds = row["FiveKillRounds"],
                            SixKillRounds = row["SixKillRounds"],
                            AttackWins = row["AttackWins"],
                            AttackLosses = row["AttackLosses"],
                            DefenseWins = row["DefenseWins"],
                            DefenseLosses = row["DefenseLosses"],
                            MatchWon = row["MatchWon"],
                            MatchLost = row["MatchLost"],
                            MatchDraw = row["MatchDraw"],
                            RoundsPlayed = row["RoundsPlayed"],
                            MVP=-1,
                            ACS_Rank=-1)
            player.save()