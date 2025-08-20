import requests
import json
import re
import time
from datetime import datetime
from bs4 import BeautifulSoup
from typing import Dict, List, Tuple, Iterable
import pytz


class LineupScraper:
	"""Scrape starting lineups from public websites.
	- Rotowire daily lineups (primary)
	Returns mappings keyed by team name variants → list[str player full names]
	Variants include the visible full name (when available) and nickname (last word),
	and records like "(78-45)" are stripped.
	Also returns per-team game time in ET when available.
	"""

	ROTOWIRE_URL = "https://www.rotowire.com/baseball/daily-lineups.php"

	def __init__(self):
		self.session = requests.Session()
		self.session.headers.update({
			"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
		})

	@staticmethod
	def _clean_team_label(label: str) -> str:
		# Remove standings/records in parentheses
		base = re.sub(r"\s*\(.*?\)\s*", "", label).strip()
		return base

	@staticmethod
	def _team_keys(label: str) -> Iterable[str]:
		base = LineupScraper._clean_team_label(label)
		if not base:
			return []
		tokens = base.split()
		keys = {base}
		if tokens:
			keys.add(tokens[-1])  # nickname like "Padres"
		return keys

	@staticmethod
	def _norm_name(name: str) -> str:
		return re.sub(r"[^a-z]", "", name.lower())

	def _assign_team_mapping(self, mapping: Dict[str, List[str]], team_label: str, value: List[str]):
		for k in self._team_keys(team_label):
			mapping[k] = value

	def _assign_time_mapping(self, mapping: Dict[str, str], team_label: str, value: str):
		for k in self._team_keys(team_label):
			mapping[k] = value

	def _get_rotowire_html(self) -> str:
		"""Fetch Rotowire HTML; try JS-render if available for full content."""
		try:
			# Try requests_html for JS rendering (optional dependency)
			from requests_html import HTMLSession
			hs = HTMLSession()
			resp = hs.get(self.ROTOWIRE_URL, headers=self.session.headers, timeout=30)
			resp.html.render(timeout=30, sleep=1)
			return resp.html.html
		except Exception:
			# Fallback to plain requests
			resp = self.session.get(self.ROTOWIRE_URL, timeout=30)
			resp.raise_for_status()
			return resp.text

	def fetch_rotowire(self) -> Tuple[Dict[str, List[str]], Dict[str, str]]:
		"""Scrape Rotowire daily lineups. Returns (team_to_players, team_to_time_et)."""
		html = self._get_rotowire_html()
		soup = BeautifulSoup(html, "html.parser")

		team_to_players: Dict[str, List[str]] = {}
		team_to_time: Dict[str, str] = {}

		# Capture lineup cards by class and extract two UL columns (visit/home)
		cards = soup.select('div.lineup.is-mlb') or soup.select('.lineup.is-mlb')
		if not cards:
			# broader fallback
			cards = [c for c in soup.select('.lineup') if c.select('ul.lineup__list.is-visit') and c.select('ul.lineup__list.is-home')]

		def extract_team_labels(card) -> List[str]:
			labels: List[str] = []
			# Prefer compact abbr or team block
			for sel in [".lineup__team .lineup__abbr", ".lineup__team a", ".lineup__team", ".is-home .lineup__team", ".is-visit .lineup__team"]:
				for el in card.select(sel):
					txt = el.get_text(" ", strip=True)
					if txt and 1 <= len(txt) < 50:
						labels.append(txt)
			# If not found, look for data-nickname/data-team buttons inside card
			if len(labels) < 2:
				for btn in card.select('button[data-team][data-nickname]'):
					nick = btn.get('data-nickname') or ''
					team = btn.get('data-team') or ''
					if nick:
						labels.append(nick)
			# Dedupe and keep first two
			labels = list(dict.fromkeys(labels))
			return labels[:2]

		def extract_time_et(card) -> str:
			text = card.get_text(" ", strip=True)
			m = re.search(r"(\d{1,2}:\d{2}\s*[AP]M\s*ET)", text)
			return m.group(1).strip() if m else None

		POS_RE = re.compile(r"^(RF|LF|CF|SS|2B|3B|1B|DH|C)\b")
		NAME_OK_RE = re.compile(r"^[A-Z]\.??\s*[A-Za-z\-']+$|^[A-Z][a-z]+\s+[A-Z][a-z\-']+$")

		def extract_col_players(ul) -> List[str]:
			out: List[str] = []
			for li in ul.select('li.lineup__player'):
				pos = li.select_one('.lineup__pos')
				a = li.select_one('a')
				if not pos or not a:
					continue
				if pos.get_text(strip=True) not in ['C','1B','2B','SS','3B','LF','CF','RF','DH']:
					continue
				
				# Get the player link URL
				player_url = a.get('href')
				full_name = a.get_text(' ', strip=True)
				
				# Try to get full name from player detail page
				if player_url and player_url.startswith('/'):
					try:
						# Construct full URL
						full_url = f"https://www.rotowire.com{player_url}"
						player_resp = self.session.get(full_url, timeout=10)
						if player_resp.status_code == 200:
							player_soup = BeautifulSoup(player_resp.text, "html.parser")
							# Look for full name in various selectors
							name_selectors = [
								'h1.player-name',
								'.player-header h1',
								'.player-info h1',
								'h1',
								'.player-name'
							]
							for selector in name_selectors:
								name_el = player_soup.select_one(selector)
								if name_el:
									extracted_name = name_el.get_text(' ', strip=True)
									if extracted_name and len(extracted_name) > len(full_name):
										full_name = extracted_name
										break
					except Exception as e:
						# If we can't get full name, use the link text
						pass
				
				full_name = re.sub(r"\s+[LRS]$", "", full_name)
				out.append(full_name)
				if len(out) == 9:
					break
			return out

		for card in cards:
			try:
				ul_visit = card.select_one('ul.lineup__list.is-visit')
				ul_home = card.select_one('ul.lineup__list.is-home')
				if not ul_visit or not ul_home:
					continue
				players_visit = extract_col_players(ul_visit)
				players_home = extract_col_players(ul_home)
				# Accept partial lineups; do not require 9
				labels = extract_team_labels(card)
				if len(labels) < 2:
					continue
				team_a, team_b = labels[0], labels[1]
				game_time_et = extract_time_et(card)
				self._assign_team_mapping(team_to_players, team_a, players_visit[:9])
				self._assign_team_mapping(team_to_players, team_b, players_home[:9])
				if game_time_et:
					self._assign_time_mapping(team_to_time, team_a, game_time_et)
					self._assign_time_mapping(team_to_time, team_b, game_time_et)
			except Exception:
				continue

		return team_to_players, team_to_time

	def get_lineup_cards(self) -> List[Dict]:
		"""Return per-game lineup entries to support doubleheaders.
		Each entry: {
		  'home_label': str,
		  'away_label': str,
		  'time_et': Optional[str],
		  'home_hitters': List[str],
		  'away_hitters': List[str]
		}
		"""
		html = self._get_rotowire_html()
		soup = BeautifulSoup(html, "html.parser")
		cards = soup.select('div.lineup.is-mlb') or soup.select('.lineup.is-mlb')
		if not cards:
			cards = [c for c in soup.select('.lineup') if c.select('ul.lineup__list.is-visit') and c.select('ul.lineup__list.is-home')]

		def extract_time_et(card) -> str:
			text = card.get_text(" ", strip=True)
			m = re.search(r"(\d{1,2}:\d{2}\s*[AP]M\s*ET)", text)
			return m.group(1).strip() if m else None

		def extract_team_labels(card) -> List[str]:
			labels: List[str] = []
			for sel in [".lineup__team .lineup__abbr", ".lineup__team a", ".lineup__team", ".is-home .lineup__team", ".is-visit .lineup__team"]:
				for el in card.select(sel):
					txt = el.get_text(" ", strip=True)
					if txt and 1 <= len(txt) < 50:
						labels.append(txt)
			if len(labels) < 2:
				for btn in card.select('button[data-team][data-nickname]'):
					nick = btn.get('data-nickname') or ''
					if nick:
						labels.append(nick)
			labels = list(dict.fromkeys(labels))
			return labels[:2]

		def extract_col_players(ul) -> List[str]:
			out: List[str] = []
			for li in ul.select('li.lineup__player'):
				pos = li.select_one('.lineup__pos')
				a = li.select_one('a')
				if not pos or not a:
					continue
				if pos.get_text(strip=True) not in ['C','1B','2B','SS','3B','LF','CF','RF','DH']:
					continue
				
				# Get the player link URL
				player_url = a.get('href')
				full_name = a.get_text(' ', strip=True)
				
				# Try to get full name from player detail page
				if player_url and player_url.startswith('/'):
					try:
						# Construct full URL
						full_url = f"https://www.rotowire.com{player_url}"
						player_resp = self.session.get(full_url, timeout=10)
						if player_resp.status_code == 200:
							player_soup = BeautifulSoup(player_resp.text, "html.parser")
							# Look for full name in various selectors
							name_selectors = [
								'h1.player-name',
								'.player-header h1',
								'.player-info h1',
								'h1',
								'.player-name'
							]
							for selector in name_selectors:
								name_el = player_soup.select_one(selector)
								if name_el:
									extracted_name = name_el.get_text(' ', strip=True)
									if extracted_name and len(extracted_name) > len(full_name):
										full_name = extracted_name
										break
					except Exception as e:
						# If we can't get full name, use the link text
						pass
				
				full_name = re.sub(r"\s+[LRS]$", "", full_name)
				out.append(full_name)
				if len(out) == 9:
					break
			return out

		def extract_pitchers(card) -> Tuple[str, str]:
			"""Find two pitcher names from Rotowire card header area (above hitter lists).
			Rule: anchors not inside any ul.lineup__list and with '/baseball/player/' in href.
			Return (away_pitcher, home_pitcher) if found, else empty strings.
			"""
			try:
				def inside_lineup_list(node) -> bool:
					p = node
					while p and p is not card:
						if getattr(p, 'name', None) == 'ul' and 'class' in p.attrs and p.get('class') and 'lineup__list' in p.get('class'):
							return True
						p = p.parent
					return False
				
				def get_full_pitcher_name(a) -> str:
					"""Get full pitcher name by following the player link."""
					player_url = a.get('href')
					full_name = a.get_text(' ', strip=True)
					
					# Try to get full name from player detail page
					if player_url and player_url.startswith('/'):
						try:
							# Construct full URL
							full_url = f"https://www.rotowire.com{player_url}"
							player_resp = self.session.get(full_url, timeout=10)
							if player_resp.status_code == 200:
								player_soup = BeautifulSoup(player_resp.text, "html.parser")
								# Look for full name in various selectors
								name_selectors = [
									'h1.player-name',
									'.player-header h1',
									'.player-info h1',
									'h1',
									'.player-name'
								]
								for selector in name_selectors:
									name_el = player_soup.select_one(selector)
									if name_el:
										extracted_name = name_el.get_text(' ', strip=True)
										if extracted_name and len(extracted_name) > len(full_name):
											full_name = extracted_name
											break
						except Exception as e:
							# If we can't get full name, use the link text
							pass
					
					return full_name
				
				pitch_names: List[str] = []
				for a in card.find_all('a', href=True):
					href = a.get('href','')
					if '/baseball/player/' not in href:
						continue
					if inside_lineup_list(a):
						continue
					full_name = get_full_pitcher_name(a)
					if not full_name or len(full_name) > 40 or ' ' not in full_name:
						continue
					if full_name not in pitch_names:
						pitch_names.append(full_name)
					if len(pitch_names) == 2:
						break
				away_p = pitch_names[0] if len(pitch_names) > 0 else ''
				home_p = pitch_names[1] if len(pitch_names) > 1 else ''
				return away_p, home_p
			except Exception:
				return '', ''

		out_cards: List[Dict] = []
		for card in cards:
			try:
				ul_visit = card.select_one('ul.lineup__list.is-visit')
				ul_home = card.select_one('ul.lineup__list.is-home')
				if not ul_visit or not ul_home:
					continue
				players_visit = extract_col_players(ul_visit)
				players_home = extract_col_players(ul_home)
				away_p, home_p = extract_pitchers(card)
				labels = extract_team_labels(card)
				if len(labels) < 2:
					continue
				team_a, team_b = labels[0], labels[1]
				out_cards.append({
					'home_label': team_b,  # Rotowire marks is-home on UL, not necessarily in label order; map by UL classes
					'away_label': team_a,
					'time_et': extract_time_et(card),
					'home_hitters': players_home,
					'away_hitters': players_visit,
					'home_pitcher': home_p,
					'away_pitcher': away_p,
				})
			except Exception:
				continue
		return out_cards

	def get_mlb_lineup_cards(self) -> List[Dict]:
		"""Get starting lineups and probable pitchers directly from MLB API. Returns same shape as get_lineup_cards."""
		try:
			# Get today's date in YYYY-MM-DD format
			today = datetime.now().strftime('%Y-%m-%d')
			
			# MLB API endpoint for today's games
			url = f"https://statsapi.mlb.com/api/v1/schedule"
			params = {
				'sportId': 1,  # MLB
				'date': today
			}
			
			response = self.session.get(url, params=params, timeout=30)
			response.raise_for_status()
			data = response.json()
			
			print(f"🔍 MLB API returned {len(data.get('dates', []))} date(s)")
			
			cards = []
			
			for date_data in data.get('dates', []):
				games = date_data.get('games', [])
				print(f"   Found {len(games)} games for {date_data.get('date', 'Unknown')}")
				
				for game in games:
					game_id = str(game['gamePk'])
					
					# Get team names from the teams object
					teams = game.get('teams', {})
					home_team = teams.get('home', {}).get('team', {}).get('name', '')
					away_team = teams.get('away', {}).get('team', {}).get('name', '')
					
					if not home_team or not away_team:
						print(f"       ⚠️ Skipping game {game_id} - missing team names")
						continue
					
					print(f"     Game: {away_team} @ {home_team}")
					
					# Get game time
					game_time = game.get('gameDate', '')
					time_et = ''
					if game_time:
						# Convert UTC to Eastern Time
						utc_time = datetime.fromisoformat(game_time.replace('Z', '+00:00'))
						et_time = utc_time.astimezone(pytz.timezone('America/New_York'))
						time_et = et_time.strftime('%I:%M %p ET')
					
					# Get real pitcher data
					away_pitcher, home_pitcher = self._get_real_pitchers(game_id, away_team, home_team)
					
					# Create card
					card = {
						'away_label': away_team,
						'home_label': home_team,
						'time_et': time_et,
						'away_hitters': [],  # Will be filled by Rotowire
						'home_hitters': [],  # Will be filled by Rotowire
						'away_pitcher': away_pitcher,
						'home_pitcher': home_pitcher,
					}
					
					cards.append(card)
					print(f"       ✅ Created card: {away_team} @ {home_team} - {time_et}")
			
			print(f"🎯 Total MLB API cards created: {len(cards)}")
			return cards
			
		except requests.exceptions.RequestException as e:
			print(f"❌ MLB API request failed: {e}")
			return []
		except Exception as e:
			print(f"❌ Error in MLB API scraper: {e}")
			return []
	
	def _get_real_pitchers(self, game_id: str, away_team: str, home_team: str) -> Tuple[str, str]:
		"""Get real pitcher data from MLB sources without artificial fallbacks.
		Order: MLB.com starting-lineups → MLB API (hydrated/boxscore). If not found, return empty.
		"""
		try:
			# 1) Scrape MLB.com starting-lineups first (source of truth for pregame)
			away_pitcher, home_pitcher = self._scrape_mlb_starting_lineups(game_id, away_team, home_team)
			
			# 2) If still missing, try MLB API hydrated endpoints
			if not away_pitcher or not home_pitcher:
				ap, hp = self._get_mlb_probable_pitchers(game_id, away_team, home_team)
				away_pitcher = away_pitcher or ap
				home_pitcher = home_pitcher or hp
			
			# 3) Return whatever we found (may be empty if not yet announced). Do NOT use fallbacks.
			return away_pitcher or '', home_pitcher or ''
		
		except Exception as e:
			print(f"       ⚠️ Error getting real pitchers: {e}")
			return '', ''
	
	def _get_mlb_probable_pitchers(self, game_id: str, away_team: str, home_team: str) -> Tuple[str, str]:
		"""Try to get probable pitchers from MLB API using hydrated schedule by gamePk"""
		try:
			away_pitcher = ''
			home_pitcher = ''
			# Use schedule endpoint with hydrate probablePitcher
			url = f"https://statsapi.mlb.com/api/v1/schedule?gamePk={game_id}&hydrate=probablePitcher"
			resp = self.session.get(url, timeout=10)
			if resp.status_code == 200:
				data = resp.json() or {}
				dates = data.get('dates', [])
				if dates and dates[0].get('games'):
					g = dates[0]['games'][0]
					teams = g.get('teams', {})
					away = teams.get('away', {})
					home = teams.get('home', {})
					ap = (away.get('probablePitcher') or {}).get('fullName')
					hp = (home.get('probablePitcher') or {}).get('fullName')
					if ap:
						away_pitcher = ap
					if hp:
						home_pitcher = hp
					if away_pitcher or home_pitcher:
						print(f"       🎯 Found probable pitchers (hydrated): {away_pitcher} vs {home_pitcher}")
						return away_pitcher, home_pitcher
			# Fallback: try game endpoint with boxscore hydration
			alt = f"https://statsapi.mlb.com/api/v1/game/{game_id}/boxscore"
			resp2 = self.session.get(alt, timeout=10)
			if resp2.status_code == 200:
				data2 = resp2.json() or {}
				teams = data2.get('teams', {})
				away = (teams.get('away') or {}).get('players') or {}
				home = (teams.get('home') or {}).get('players') or {}
				# Heuristic: pick starting pitcher by position code '1'
				def find_sp(players):
					for p in players.values():
						pos = ((p.get('position') or {}).get('code') or '').strip()
						is_sp = pos == '1' or (p.get('isStarter') is True and pos == '1')
						if is_sp:
							name = ((p.get('person') or {}).get('fullName') or '').strip()
							if name:
								return name
					return ''
				ap = find_sp(away)
				hp = find_sp(home)
				if ap:
					away_pitcher = ap
				if hp:
					home_pitcher = hp
				if away_pitcher or home_pitcher:
					print(f"       🎯 Found probable pitchers (boxscore): {away_pitcher} vs {home_pitcher}")
					return away_pitcher, home_pitcher
			return '', ''
		except Exception as e:
			print(f"       ⚠️ Error getting probable pitchers: {e}")
			return '', ''
	
	def _scrape_mlb_starting_lineups(self, game_id: str, away_team: str, home_team: str) -> Tuple[str, str]:
		"""Scrape starting lineups from MLB.com starting-lineups page"""
		try:
			# Scrape from the main starting lineups page
			lineups_url = "https://www.mlb.com/starting-lineups"
			response = self.session.get(lineups_url, timeout=15)
			
			if response.status_code != 200:
				print(f"       ⚠️ Failed to get starting lineups page: {response.status_code}")
				return '', ''
			
			soup = BeautifulSoup(response.text, 'html.parser')
			
			# Look for the specific game by team names
			away_pitcher = ''
			home_pitcher = ''
			
			# Try to find game sections that contain our teams
			game_sections = soup.find_all(['div', 'section'], class_=lambda x: x and any(word in x.lower() for word in ['game', 'lineup', 'team']))
			
			for section in game_sections:
				section_text = section.get_text(' ', strip=True)
				
				# Check if this section contains both teams
				if away_team.lower() in section_text.lower() and home_team.lower() in section_text.lower():
					# Look for pitcher information in this section
					pitcher_elements = section.find_all(['div', 'span', 'p'], string=lambda x: x and any(word in x.lower() for word in ['sp', 'pitcher', 'starting']))
					
					for element in pitcher_elements:
						text = element.get_text(' ', strip=True)
						if text and len(text) > 3:
							# Try to determine which team this pitcher belongs to
							if away_team.lower() in text.lower() or any(word in text.lower() for word in away_team.lower().split()):
								away_pitcher = text
							elif home_team.lower() in text.lower() or any(word in text.lower() for word in home_team.lower().split()):
								home_pitcher = text
			
			if away_pitcher or home_pitcher:
				print(f"       🎯 Scraped pitchers from starting-lineups: {away_pitcher} vs {home_pitcher}")
			
			return away_pitcher, home_pitcher
			
		except Exception as e:
			print(f"       ⚠️ Error scraping MLB starting lineups: {e}")
			return '', ''
	
	def _get_pitchers_from_depth_charts(self, away_team: str, home_team: str) -> Tuple[str, str]:
		"""Get pitchers from team depth charts (fallback method)"""
		try:
			# This would require scraping team depth charts
			# For now, return empty strings
			return '', ''
			
		except Exception as e:
			print(f"       ⚠️ Error getting depth chart pitchers: {e}")
			return '', ''
	
	def _get_team_ace(self, team_name: str) -> str:
		"""Get the team's ace pitcher as a final fallback"""
		# Known team aces (this could be expanded)
		team_aces = {
			'Milwaukee Brewers': 'Corbin Burnes',
			'Chicago Cubs': 'Marcus Stroman',
			'Houston Astros': 'Justin Verlander',
			'Detroit Tigers': 'Eduardo Rodriguez',
			'Toronto Blue Jays': 'Alek Manoah',
			'Pittsburgh Pirates': 'Mitch Keller',
			'St. Louis Cardinals': 'Adam Wainwright',
			'Miami Marlins': 'Sandy Alcantara',
			'Seattle Mariners': 'Luis Castillo',
			'Philadelphia Phillies': 'Aaron Nola',
			'Baltimore Orioles': 'Kyle Gibson',
			'Boston Red Sox': 'Chris Sale',
			'Chicago White Sox': 'Dylan Cease',
			'Atlanta Braves': 'Max Fried',
			'Texas Rangers': 'Nathan Eovaldi',
			'Kansas City Royals': 'Brady Singer',
			'Los Angeles Dodgers': 'Clayton Kershaw',
			'Colorado Rockies': 'German Marquez',
			'Cincinnati Reds': 'Hunter Greene',
			'Los Angeles Angels': 'Shohei Ohtani',
			'Cleveland Guardians': 'Shane Bieber',
			'Arizona Diamondbacks': 'Zac Gallen',
			'San Francisco Giants': 'Logan Webb',
			'San Diego Padres': 'Yu Darvish'
		}
		
		return team_aces.get(team_name, f"{team_name} SP")
	
	def _get_team_id(self, team_name: str) -> int:
		"""Get MLB team ID from team name"""
		team_ids = {
			'Milwaukee Brewers': 158,
			'Chicago Cubs': 112,
			'Houston Astros': 117,
			'Detroit Tigers': 116,
			'Toronto Blue Jays': 141,
			'Pittsburgh Pirates': 134,
			'St. Louis Cardinals': 138,
			'Miami Marlins': 146,
			'Seattle Mariners': 136,
			'Philadelphia Phillies': 121,
			'Baltimore Orioles': 110,
			'Boston Red Sox': 111,
			'Chicago White Sox': 145,
			'Atlanta Braves': 144,
			'Texas Rangers': 140,
			'Kansas City Royals': 118,
			'Los Angeles Dodgers': 119,
			'Colorado Rockies': 115,
			'Cincinnati Reds': 113,
			'Los Angeles Angels': 108,
			'Cleveland Guardians': 114,
			'Arizona Diamondbacks': 109,
			'San Francisco Giants': 137,
			'San Diego Padres': 135
		}
		
		return team_ids.get(team_name, 0)

	def get_lineups(self) -> Tuple[Dict[str, List[str]], Dict[str, str]]:
		"""Return only Rotowire lineups and ET times."""
		return self.fetch_rotowire()

	def _canon_team(self, name: str) -> str:
		name = (name or '').strip()
		name = re.sub(r"\s*\(.*?\)\s*", "", name)
		return name

	def get_combined_cards(self) -> List[Dict]:
		"""Merge Rotowire hitters with MLB.com pitchers into per-game cards.
		Return entries with: away_label, home_label, time_et, away_hitters, home_hitters, away_pitcher, home_pitcher
		"""
		rot = self.get_lineup_cards()
		mlb = self.get_mlb_lineup_cards()
		
		# Index rot cards by fuzzy team key sets for robust matching
		def team_keys(label: str) -> set:
			base = self._clean_team_label(label)
			parts = base.split()
			keys = {base}
			if parts:
				keys.add(parts[-1])
				keys.add(parts[-1].upper())
			return keys
		
		rot_index = []
		for rc in rot:
			rot_index.append({
				'away': rc.get('away_label',''),
				'home': rc.get('home_label',''),
				'time': rc.get('time_et',''),
				'away_keys': team_keys(rc.get('away_label','')),
				'home_keys': team_keys(rc.get('home_label','')),
				'away_hitters': rc.get('away_hitters',[]),
				'home_hitters': rc.get('home_hitters',[]),
			})
		
		processed_games = set()
		out: List[Dict] = []
		
		for mc in mlb:
			away_team = mc.get('away_label','')
			home_team = mc.get('home_label','')
			time_et = mc.get('time_et','')
			game_key = f"{away_team}@{home_team}@{time_et}"
			if game_key in processed_games:
				continue
			processed_games.add(game_key)
			
			away_keys = team_keys(away_team)
			home_keys = team_keys(home_team)
			best = None
			best_score = -1
			for rc in rot_index:
				score = 0
				if away_keys & rc['away_keys'] and home_keys & rc['home_keys']:
					score = 2
				elif away_keys & rc['home_keys'] and home_keys & rc['away_keys']:
					score = 2
				# small bonus if times match
				if rc['time'] and time_et and rc['time'] == time_et:
					score += 1
				if score > best_score:
					best_score = score
					best = rc
			
			away_hitters = best['away_hitters'] if best else []
			home_hitters = best['home_hitters'] if best else []
			
			out.append({
				'away_label': away_team,
				'home_label': home_team,
				'time_et': time_et,
				'away_hitters': away_hitters,
				'home_hitters': home_hitters,
				'away_pitcher': mc.get('away_pitcher',''),
				'home_pitcher': mc.get('home_pitcher',''),
			})
		
		# Sort by game time
		out.sort(key=lambda x: x.get('time_et',''))
		print(f"🎯 Combined cards created: {len(out)} unique games")
		return out 