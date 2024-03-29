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
from bs4 import Tag
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

def average_rank(ranks, number=True):
    rank_mapping = {
        "Iron 1": 0, "Iron 2": 1, "Iron 3": 2,
        "Bronze 1": 3, "Bronze 2": 4, "Bronze 3": 5,
        "Silver 1": 6, "Silver 2": 7, "Silver 3": 8,
        "Gold 1": 9, "Gold 2": 10, "Gold 3": 11,
        "Platinum 1": 12, "Platinum 2": 13, "Platinum 3": 14,
        "Diamond 1": 15, "Diamond 2": 16, "Diamond 3": 17,
        "Ascendant 1": 18, "Ascendant 2": 19, "Ascendant 3": 20,
        "Immortal 1": 21, "Immortal 2": 22, "Immortal 3": 23,
        "Radiant": 24
    }

    reverse_mapping = {v: k for k, v in rank_mapping.items()}

    valid_ranks = [rank for rank in ranks if rank != "N/A"]

    if not valid_ranks:
        return "None"

    rank_numbers = [rank_mapping[rank] for rank in valid_ranks]
    average_rank_number = round(sum(rank_numbers) / len(valid_ranks))

    if number:
        return reverse_mapping[average_rank_number]
    else:
        return reverse_mapping[average_rank_number][0:-2]

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
                  "739ef85a-1c23-4b4d-a5cc-f258f04725f0", # Competitive: Lan played on Jake's acc
                 ]

with open('match/squad.json', 'r', encoding='utf8') as f:
    squad = json.load(f)

from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

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

    browser = uc.Chrome(driver_executable_path=ChromeDriverManager().install(),options=options)
    browser.get(url)

    i = 0
    while(i <= 100):
        soup = bs.BeautifulSoup(browser.page_source, features="html.parser")
        body_class = soup.body.get('class')
        if body_class and 'skin-takeover' in body_class:
            break
        else:
            if (len(soup.find_all("span", {"class": "trn-ign"})) == 0) or \
            ((len(soup.find_all("div", {"id": "closeIconHit"})) == 0) and \
            (len(soup.find_all("div", {"id": "cpmstarvideosliderclose"})) == 0) and \
            (len(soup.find_all("div", {"class": "cpmsoutstreamclose"})) == 0)):
                i += 1
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
    elif len(soup.find_all("div", {"class": "cpmsoutstreamclose"})):
        time.sleep(1)
        browser.find_element(by=By.XPATH, value="/html/body/div[2]/div/div[4]").click()

    mapName = soup.find("div", {"class": "trn-match-drawer__header-value"}).text
    datetime_object = datetime.strptime([x.text.strip() for x in soup.select("div.trn-match-drawer__header-label") if ", " in x.text][0],
                                        "%m/%d/%y, %I:%M %p")

    teamOneScore = int(soup.find("div", {"class": "trn-match-drawer__header-value valorant-color-team-1"}).text)
    teamTwoScore = int(soup.find("div", {"class": "trn-match-drawer__header-value valorant-color-team-2"}).text)

    usernames = [x.text.strip().replace("  #","#") for x in soup.find_all("span", {"class": "trn-ign"})]
    displayNames = [x.split("#")[0] for x in usernames]
    agents = [agent_map.get(x["src"].split("agents/")[1].split("/displayicon.png")[0]) for x in soup.find_all("img", {"data-v-4ff6b405": True, "data-v-0c313880": True, }) if ("displayicon" in x["src"])]
    roles = [role_map.get(x) for x in agents]

    TeamChunks = soup.find_all("div",{"class": "st__item st-header__item st-header__item--sortable st__item--sticky st__item--wide"})
    if "Avg. Rank:" in str(TeamChunks[0]) and "Avg. Rank:" in str(TeamChunks[1]):
        ranks = [map_rank(e) for i, e in enumerate([x["src"] for x in soup.find_all("img", {"data-v-4ff6b405": True, "data-v-0c313880": True, }) if ("tiersv2" in x["src"])]) if i not in [0,6]]
    elif "Avg. Rank:" in str(TeamChunks[0]):
        ranks = [map_rank(e) for i, e in enumerate([x["src"] for x in soup.find_all("img", {"data-v-4ff6b405": True, "data-v-0c313880": True, }) if ("tiersv2" in x["src"])]) if i not in [0]]
    elif "Avg. Rank:" in str(TeamChunks[1]):
        ranks = [map_rank(e) for i, e in enumerate([x["src"] for x in soup.find_all("img", {"data-v-4ff6b405": True, "data-v-0c313880": True, }) if ("tiersv2" in x["src"])]) if i not in [5]]
    else:
        ranks = [map_rank(e) for i, e in enumerate([x["src"] for x in soup.find_all("img", {"data-v-4ff6b405": True, "data-v-0c313880": True, }) if ("tiersv2" in x["src"])])]

    won = ([int(teamOneScore > teamTwoScore)] * 5) + ([int(teamTwoScore > teamOneScore)] * 5)

    surrender = False
    surrender_image = 'https://trackercdn.com/cdn/tracker.gg/valorant/icons/earlysurrender-flag.png'

    if len(soup.find_all("img", src=surrender_image)) > 0:

        surrender = True

        entries = soup.find_all('div', class_='entry')

        team_a_wins = 0
        team_b_wins = 0
        surrenders = 0
        surrender_wins_team_a = 0
        surrender_wins_team_b = 0

        for entry in entries:
            # Find all children within the entry
            children = entry.findChildren(recursive=False)

            # Flag to keep track of whether the round was a surrender
            is_surrender = any(isinstance(child, Tag) and child.name == 'img' and child['src'] == surrender_image for child in children)

            for i in range(len(children)):
                child = children[i]

                if isinstance(child, Tag) and child.name == 'div' and child.text == '•':
                    if i == 0: 
                        team_b_wins += 1 if not is_surrender else 0
                        surrender_wins_team_b += 1 if is_surrender else 0
                    elif i == 1:
                        team_a_wins += 1 if not is_surrender else 0
                        surrender_wins_team_a += 1 if is_surrender else 0

            surrenders += is_surrender

        teamOneScore = team_a_wins
        teamTwoScore = team_b_wins

        if surrender_wins_team_a > 0:
            won = [1,1,1,1,1,0,0,0,0,0]
        else:
            won = [0,0,0,0,0,1,1,1,1,1]

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

    values = [str2num(x.text) for x in soup.find_all("div", {"data-v-0c313880": True, "class": "value"})]

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

        if surrender:
            rounds = rounds[:(teamOneScore+teamTwoScore)]

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
    teamB_df = db[db.Team == "Team B"].reset_index(drop=True)
    role_vc = teamA_df.Role.value_counts()
    
    teamA_score = teamA_df.RoundsWon.max()
    teamB_score = db[db.Team == "Team B"].RoundsWon.max()

    sorted_players = sorted(teamA_df['DisplayName'], key=lambda x: x.lower())
    players = ", ".join(sorted_players)

    ACS_Leaders = teamA_df.sort_values(by=["ACS","Kills","KillDeathRatio"], ascending=False).reset_index(drop=True)
    K_Leaders = teamA_df.sort_values(by=["Kills","ACS","KillDeathRatio"], ascending=False).reset_index(drop=True)
    KDR_Leaders = teamA_df.sort_values(by=["KillDeathRatio","Kills","ACS"], ascending=False).reset_index(drop=True)

    AvgTeamRank = average_rank(list(teamA_df.Rank), number=True)
    AvgOppRank = average_rank(list(teamB_df.Rank), number=True)
    AvgTeamRankSimple = average_rank(list(teamA_df.Rank), number=False)
    AvgOppRankSimple = average_rank(list(teamB_df.Rank), number=False)

    match = Match(MatchID = db["GameID"][0],
                  Map = db["Map"][0],
                  Date = db["Date"][0],
                  Score = str(teamA_score)+"-"+str(teamB_score),
                  TeamOneScore = teamA_score,
                  TeamTwoScore = teamB_score,
                  TeamOneWon = teamA_df.GameWon.max(),
                  TeamOneLost = teamB_df.GameWon.max(),
                  ScoreDifferential = teamA_score - teamB_score,
                  MatchDraw = int(teamA_df.GameWon.max() == teamB_df.GameWon.max()),
                  Surrender = int(surrender),
                  RoundsPlayed = teamA_score+teamB_score,
                  Players = players,
                  MVP = teamA_df.DisplayName[0],
                  MVP_ACS = teamA_df.ACS[0],
                  TopKiller = K_Leaders.DisplayName[0],
                  MostKills = K_Leaders.Kills[0],
                  TopKDR = KDR_Leaders.DisplayName[0],
                  TopKDRValue = KDR_Leaders.KillDeathRatio[0],
                  N_Duelists = role_vc.get("Duelist",0),
                  N_Sentinels = role_vc.get("Sentinel",0),
                  N_Initiators = role_vc.get("Initiator",0),
                  N_Controllers = role_vc.get("Controller",0),
                  AverageRank = AvgTeamRank,
                  AverageOppRank = AvgOppRank,
                  AverageRankSimple = AvgTeamRankSimple,
                  AverageOppRankSimple = AvgOppRankSimple)
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