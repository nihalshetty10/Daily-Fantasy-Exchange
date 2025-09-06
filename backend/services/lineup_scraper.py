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
	- Rotowire daily lineups (primary for MLB)
	- NFL.com and Rotowire for NFL lineups
	Returns mappings keyed by team name variants → list[str player full names]
	Variants include the visible full name (when available) and nickname (last word),
	and records like "(78-45)" are stripped.
	Also returns per-team game time in ET when available.
	"""

	ROTOWIRE_MLB_URL = "https://www.rotowire.com/baseball/daily-lineups.php"
	ROTOWIRE_NFL_URL = "https://www.rotowire.com/football/lineups.php"
	MLB_STARTING_LINEUPS_URL = "https://www.mlb.com/starting-lineups"

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
			resp = hs.get(self.ROTOWIRE_MLB_URL, headers=self.session.headers, timeout=30)
			resp.html.render(timeout=30, sleep=1)
			return resp.html.html
		except Exception:
			# Fallback to plain requests
			resp = self.session.get(self.ROTOWIRE_MLB_URL, timeout=30)
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
			
			# Enhanced parsing for MLB.com structure
			# Look for game cards/containers
			game_containers = soup.find_all(['div', 'section'], class_=lambda x: x and any(word in x.lower() for word in ['game', 'lineup', 'card', 'matchup']))
			
			for container in game_containers:
				container_text = container.get_text(' ', strip=True)
				
				# Check if this container has both teams
				away_team_lower = away_team.lower()
				home_team_lower = home_team.lower()
				
				# More flexible team matching
				away_match = any(word in container_text.lower() for word in away_team_lower.split()) or away_team_lower in container_text.lower()
				home_match = any(word in container_text.lower() for word in home_team_lower.split()) or home_team_lower in container_text.lower()
				
				if away_match and home_match:
					print(f"       🎯 Found game container for {away_team} vs {home_team}")
					
					# Look for pitcher names and stats
					# Pattern: "Jake Irvin R (8-10 5.42 ERA) 102 SO"
					pitcher_pattern = r'([A-Za-z\s]+)\s+[LR]\s+\([0-9-]+\s+[0-9.]+ ERA\)'
					pitcher_matches = re.findall(pitcher_pattern, container_text)
					
					# Also look for pitcher names in specific elements
					pitcher_elements = container.find_all(['div', 'span', 'p', 'h3', 'h4'], string=lambda x: x and len(x.strip()) > 2)
					
					for element in pitcher_elements:
						text = element.get_text(' ', strip=True)
						
						# Look for pitcher name patterns
						if re.search(r'[A-Z][a-z]+\s+[A-Z][a-z]+', text) and ('ERA' in text or 'SO' in text or 'RHP' in text or 'LHP' in text):
							# Extract just the name (before stats)
							name_match = re.match(r'([A-Z][a-z]+\s+[A-Z][a-z]+)', text)
							if name_match:
								pitcher_name = name_match.group(1).strip()
								
								# Determine which team this pitcher belongs to
								# Look at surrounding context
								parent_text = element.parent.get_text(' ', strip=True) if element.parent else text
								
								if away_team_lower in parent_text.lower() or any(word in parent_text.lower() for word in away_team_lower.split()):
									if not away_pitcher:  # Only set if not already found
										away_pitcher = pitcher_name
										print(f"       🎯 Found away pitcher: {pitcher_name}")
								elif home_team_lower in parent_text.lower() or any(word in parent_text.lower() for word in home_team_lower.split()):
									if not home_pitcher:  # Only set if not already found
										home_pitcher = pitcher_name
										print(f"       🎯 Found home pitcher: {pitcher_name}")
			
			if away_pitcher or home_pitcher:
				print(f"       ✅ MLB.com pitchers: {away_pitcher} vs {home_pitcher}")
			else:
				print(f"       ⚠️ No pitchers found on MLB.com for {away_team} vs {home_team}")
			
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
		"""Return Rotowire lineups with MLB.com fallback for pitchers."""
		# Get primary data from Rotowire
		rotowire_lineups, rotowire_times = self.fetch_rotowire()
		
		# Check if we need MLB.com fallback for any missing pitchers
		teams_needing_pitchers = []
		for team, players in rotowire_lineups.items():
			# Check if this team has any pitchers (P position)
			has_pitcher = any('P' in str(player) for player in players)
			# Since Rotowire typically only gives hitters, we need pitchers for all teams
			if not has_pitcher and len(players) > 0:  # Has hitters but no pitcher
				teams_needing_pitchers.append(team)
		
		# If no teams were detected as needing pitchers, add all teams that have players
		if not teams_needing_pitchers:
			teams_needing_pitchers = list(rotowire_lineups.keys())
			print(f"       🔄 Adding pitchers to all {len(teams_needing_pitchers)} teams with lineups")
		
		if teams_needing_pitchers:
			print(f"       🔄 Using MLB.com fallback for pitchers: {teams_needing_pitchers}")
			
			# Get today's games to find pitcher matchups
			mlb_cards = self.get_mlb_lineup_cards()
			
			# Team name mapping from full names to abbreviations
			team_mapping = {
				'Philadelphia Phillies': 'PHI',
				'Milwaukee Brewers': 'MIL', 
				'Los Angeles Dodgers': 'LAD',
				'Pittsburgh Pirates': 'PIT',
				'Cleveland Guardians': 'CLE',
				'Tampa Bay Rays': 'TB',
				'Los Angeles Angels': 'LAA',
				'Kansas City Royals': 'KC',
				'Chicago White Sox': 'CWS',
				'Minnesota Twins': 'MIN',
				'New York Yankees': 'NYY',
				'Houston Astros': 'HOU',
				'Washington Nationals': 'WSH',
				'Chicago Cubs': 'CHC',
				'New York Mets': 'NYM',
				'Cincinnati Reds': 'CIN',
				'Detroit Tigers': 'DET',
				'Baltimore Orioles': 'BAL',
				'Toronto Blue Jays': 'TOR',
				'Miami Marlins': 'MIA',
				'Seattle Mariners': 'SEA',
				'Atlanta Braves': 'ATL',
				'San Francisco Giants': 'SF',
				'St. Louis Cardinals': 'STL',
				'San Diego Padres': 'SD',
				'Colorado Rockies': 'COL',
				'Athletics': 'OAK',
				'Boston Red Sox': 'BOS',
				'Arizona Diamondbacks': 'ARI'
			}
			
			for card in mlb_cards:
				away_team_full = card.get('away_label', '')
				home_team_full = card.get('home_label', '')
				away_pitcher = card.get('away_pitcher', '')
				home_pitcher = card.get('home_pitcher', '')
				
				# Convert full names to abbreviations
				away_team = team_mapping.get(away_team_full, away_team_full)
				home_team = team_mapping.get(home_team_full, home_team_full)
				
				# Add pitchers to lineups if teams match and we have pitcher data
				if away_team in teams_needing_pitchers and away_pitcher:
					if away_team not in rotowire_lineups:
						rotowire_lineups[away_team] = []
					# Add pitcher to the lineup
					rotowire_lineups[away_team].append(away_pitcher)
					print(f"       ✅ Added pitcher {away_pitcher} to {away_team}")
				
				if home_team in teams_needing_pitchers and home_pitcher:
					if home_team not in rotowire_lineups:
						rotowire_lineups[home_team] = []
					# Add pitcher to the lineup
					rotowire_lineups[home_team].append(home_pitcher)
					print(f"       ✅ Added pitcher {home_pitcher} to {home_team}")
		
		return rotowire_lineups, rotowire_times

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
			
			# Add team abbreviation mappings for Rotowire vs MLB.com matching
			team_abbrevs = {
				'TOR': 'Toronto Blue Jays', 'TORONTO': 'Toronto Blue Jays',
				'PIT': 'Pittsburgh Pirates', 'PITTSBURGH': 'Pittsburgh Pirates',
				'SEA': 'Seattle Mariners', 'SEATTLE': 'Seattle Mariners',
				'PHI': 'Philadelphia Phillies', 'PHILADELPHIA': 'Philadelphia Phillies',
				'HOU': 'Houston Astros', 'HOUSTON': 'Houston Astros',
				'DET': 'Detroit Tigers', 'DETROIT': 'Detroit Tigers',
				'CLE': 'Cleveland Guardians', 'CLEVELAND': 'Cleveland Guardians',
				'ARI': 'Arizona Diamondbacks', 'ARIZONA': 'Arizona Diamondbacks',
				'STL': 'St. Louis Cardinals', 'ST. LOUIS': 'St. Louis Cardinals',
				'MIA': 'Miami Marlins', 'MIAMI': 'Miami Marlins',
				'NYM': 'New York Mets', 'NEW YORK METS': 'New York Mets',
				'WAS': 'Washington Nationals', 'WASHINGTON': 'Washington Nationals',
				'CWS': 'Chicago White Sox', 'CHICAGO WHITE SOX': 'Chicago White Sox',
				'ATL': 'Atlanta Braves', 'ATLANTA': 'Atlanta Braves',
				'NYY': 'New York Yankees', 'NEW YORK YANKEES': 'New York Yankees',
				'TB': 'Tampa Bay Rays', 'TAMPA BAY': 'Tampa Bay Rays',
				'TEX': 'Texas Rangers', 'TEXAS': 'Texas Rangers',
				'KC': 'Kansas City Royals', 'KANSAS CITY': 'Kansas City Royals',
				'OAK': 'Athletics', 'ATHLETICS': 'Athletics',
				'MIN': 'Minnesota Twins', 'MINNESOTA': 'Minnesota Twins',
				'MIL': 'Milwaukee Brewers', 'MILWAUKEE': 'Milwaukee Brewers',
				'CHC': 'Chicago Cubs', 'CHICAGO CUBS': 'Chicago Cubs',
				'LAD': 'Los Angeles Dodgers', 'LOS ANGELES DODGERS': 'Los Angeles Dodgers',
				'COL': 'Colorado Rockies', 'COLORADO': 'Colorado Rockies',
				'CIN': 'Cincinnati Reds', 'CINCINNATI': 'Cincinnati Reds',
				'LAA': 'Los Angeles Angels', 'LOS ANGELES ANGELS': 'Los Angeles Angels',
				'SF': 'San Francisco Giants', 'SAN FRANCISCO': 'San Francisco Giants',
				'SD': 'San Diego Padres', 'SAN DIEGO': 'San Diego Padres'
			}
			
			# Add abbreviation mappings
			for abbrev, full_name in team_abbrevs.items():
				if base.upper() == abbrev or base.upper() == full_name.upper():
					keys.add(full_name)
					keys.add(abbrev)
			
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
		
		# Build a team -> hitters map from the best matching Rotowire cards
		rot_team_hitters: Dict[str, List[str]] = {}
		for rc in rot:
			away_team = self._clean_team_label(rc.get('away_label',''))
			home_team = self._clean_team_label(rc.get('home_label',''))
			if away_team and rc.get('away_hitters'):
				rot_team_hitters[away_team] = rc.get('away_hitters', [])
			if home_team and rc.get('home_hitters'):
				rot_team_hitters[home_team] = rc.get('home_hitters', [])
		
		# Also create a fuzzy team name mapping for better matching
		fuzzy_team_map = {}
		for team_name in rot_team_hitters.keys():
			# Create multiple variations of the team name for fuzzy matching
			variations = [team_name]
			parts = team_name.split()
			if len(parts) > 1:
				variations.append(parts[-1])  # Last word (e.g., "Jays", "Pirates")
				variations.append(parts[-1].upper())  # Uppercase last word
				variations.append(' '.join(parts[:-1]))  # Everything except last word
			for variation in variations:
				fuzzy_team_map[variation] = team_name
		
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
			
			away_k = team_keys(away_team)
			home_k = team_keys(home_team)
			best = None
			best_score = -1
			for rc in rot_index:
				score = 0
				if away_k & rc['away_keys'] and home_k & rc['home_keys']:
					score = 2
				elif away_k & rc['home_keys'] and home_k & rc['away_keys']:
					score = 2
				# small bonus if times match
				if rc['time'] and time_et and rc['time'] == time_et:
					score += 1
				if score > best_score:
					best_score = score
					best = rc
			
			# Prefer hitters from the best Rotowire card if we found one; otherwise fall back to team-based hitters
			away_hitters = (best['away_hitters'] if best else []) or rot_team_hitters.get(away_team, []) or rot_team_hitters.get(fuzzy_team_map.get(away_team, ''), [])
			home_hitters = (best['home_hitters'] if best else []) or rot_team_hitters.get(home_team, []) or rot_team_hitters.get(fuzzy_team_map.get(home_team, ''), [])
			
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

	# ==================== NFL METHODS ====================
	
	def get_nfl_lineups(self) -> Tuple[Dict[str, List[Dict]], Dict[str, str]]:
		"""Get NFL lineups using card-based approach like MLB"""
		try:
			response = self.session.get(self.ROTOWIRE_NFL_URL, timeout=20)
			response.raise_for_status()
			soup = BeautifulSoup(response.text, 'html.parser')
			
			team_to_players: Dict[str, List[Dict]] = {}
			team_to_time: Dict[str, str] = {}
			
			# Look for NFL lineup cards similar to MLB
			cards = soup.select('div.lineup.is-nfl') or soup.select('.lineup.is-nfl')
			if not cards:
				# Fallback to any lineup cards
				cards = [c for c in soup.select('.lineup') if 'football' in c.get('class', []) or 'nfl' in c.get('class', [])]
			
			# If no specific NFL cards, try broader search
			if not cards:
				cards = soup.select('.lineup')
			
			def extract_team_labels(card) -> List[str]:
				labels: List[str] = []
				# Look for team names in various selectors
				for sel in [".lineup__team .lineup__abbr", ".lineup__team a", ".lineup__team", ".is-home .lineup__team", ".is-visit .lineup__team"]:
					for el in card.select(sel):
						txt = el.get_text(" ", strip=True)
						if txt and 1 <= len(txt) < 50:
							labels.append(txt)
				# Dedupe and keep first two
				labels = list(dict.fromkeys(labels))
				return labels[:2]
			
			def extract_time_et(card) -> str:
				text = card.get_text(" ", strip=True)
				m = re.search(r"(\d{1,2}:\d{2}\s*[AP]M\s*ET)", text)
				return m.group(1).strip() if m else 'TBD'
			
			# NFL position patterns
			POS_RE = re.compile(r"^(QB|RB|WR|TE)\b")
			NAME_OK_RE = re.compile(r"^[A-Z]\.??\s*[A-Za-z\-'\s.]+$|^[A-Z][a-z\s.]+\s+[A-Z][a-z\-']+$")
			
			def extract_col_players(ul) -> List[Dict]:
				players: List[Dict] = []
				for li in ul.select('li.lineup__player'):
					pos_el = li.select_one('.lineup__pos')
					a = li.select_one('a')
					if not pos_el or not a:
						continue
					
					pos = pos_el.get_text(strip=True)
					if pos not in ['QB', 'RB', 'WR', 'TE']:
						continue
					
					full_name = a.get_text(' ', strip=True)
					if not NAME_OK_RE.match(full_name):
						continue
					
					# Check for injury designation (Q=Questionable, D=Doubtful, O=Out)
					injury = ''
					if full_name.endswith(' Q'):
						full_name = full_name[:-2].strip()
						injury = 'Q'
					elif full_name.endswith(' D'):
						full_name = full_name[:-2].strip()
						injury = 'D'
					elif full_name.endswith(' O'):
						full_name = full_name[:-2].strip()
						injury = 'O'
					
					players.append({
						'name': full_name,
						'position': pos,
						'injury': injury
					})
				
				return players
			
			# Process each card
			for card in cards:
				team_labels = extract_team_labels(card)
				if len(team_labels) < 2:
					continue
				
				away_team = team_labels[0]
				home_team = team_labels[1]
				game_time = extract_time_et(card)
				
				# Extract players from both columns
				away_ul = card.select_one('ul.lineup__list.is-visit')
				home_ul = card.select_one('ul.lineup__list.is-home')
				
				away_players = extract_col_players(away_ul) if away_ul else []
				home_players = extract_col_players(home_ul) if home_ul else []
				
				# Limit to 6 players per team (1 QB, 1 RB, 3 WR, 1 TE)
				def limit_players(players):
					limited = []
					pos_counts = {'QB': 0, 'RB': 0, 'WR': 0, 'TE': 0}
					for p in players:
						pos = p['position']
						if pos_counts[pos] < (1 if pos in ['QB', 'RB', 'TE'] else 3):
							limited.append(p)
							pos_counts[pos] += 1
					return limited
				
				away_players = limit_players(away_players)
				home_players = limit_players(home_players)
				
				team_to_players[away_team] = away_players
				team_to_players[home_team] = home_players
				team_to_time[away_team] = game_time
				team_to_time[home_team] = game_time
				
				print(f"✅ NFL {away_team}: {len(away_players)} players, {home_team}: {len(home_players)} players")
			
			return team_to_players, team_to_time
			
		except Exception as e:
			print(f"❌ Error getting NFL lineups: {e}")
			return {}, {}
	
	def _get_nfl_games(self) -> List[Dict]:
		"""Get today's NFL games from Rotowire lineups page"""
		try:
			url = self.ROTOWIRE_NFL_URL
			response = self.session.get(url, timeout=15)
			response.raise_for_status()
			
			soup = BeautifulSoup(response.text, 'html.parser')
			games = []
			
			# Get page text for pattern matching
			page_text = soup.get_text(' ', strip=True)
			
			# Determine today's weekday abbreviation in Eastern Time
			try:
				et = pytz.timezone('US/Eastern')
				today_et = datetime.now(et)
				weekday = today_et.strftime('%a').upper()  # e.g., 'SUN'
			except Exception:
				weekday = datetime.utcnow().strftime('%a').upper()
			
			# Define valid NFL team names to filter out false matches
			valid_teams = [
				'Chiefs', 'Chargers', 'Buccaneers', 'Falcons', 'Bills', 'Dolphins', 'Patriots', 'Jets',
				'Ravens', 'Bengals', 'Browns', 'Steelers', 'Texans', 'Colts', 'Jaguars', 'Titans',
				'Broncos', 'Raiders', 'Rams', '49ers', 'Cardinals', 'Seahawks', 'Bears', 'Lions',
				'Packers', 'Vikings', 'Cowboys', 'Giants', 'Eagles', 'Commanders', 'Panthers', 'Saints'
			]
			
			# Pattern to match the actual format: "KC LAC Chiefs (0-0) Chargers (0-0)"
			# This matches: ABBREV1 ABBREV2 Team1 (record) Team2 (record)
			# More precise pattern to avoid capturing extra text
			game_pattern = r'([A-Z]{2,4})\s+([A-Z]{2,4})\s+([A-Za-z\s]+?)\s+\([0-9-]+\)\s+([A-Za-z\s]+?)\s+\([0-9-]+\)'
			
			matches = re.finditer(game_pattern, page_text)
			for match in matches:
				away_abbrev_raw = match.group(1).strip()
				home_abbrev_raw = match.group(2).strip()
				away_team = match.group(3).strip()
				home_team = match.group(4).strip()
				
				# Clean abbreviations (remove unwanted text)
				away_abbrev = re.sub(r'[^A-Z]', '', away_abbrev_raw)
				home_abbrev = re.sub(r'[^A-Z]', '', home_abbrev_raw)
				
				# Clean team names (remove extra spaces and unwanted text)
				away_team = re.sub(r'\s+', ' ', away_team).strip()
				home_team = re.sub(r'\s+', ' ', home_team).strip()
				
				# Remove common unwanted prefixes/suffixes
				away_team = re.sub(r'^(Tickets|Alerts|PM|ET)\s+', '', away_team).strip()
				home_team = re.sub(r'^(Tickets|Alerts|PM|ET)\s+', '', home_team).strip()
				away_team = re.sub(r'\s+(PM|ET)$', '', away_team).strip()
				home_team = re.sub(r'\s+(PM|ET)$', '', home_team).strip()
				
				# Extract just the team name (last word before any extra text)
				away_team = away_team.split()[-1] if away_team else ''
				home_team = home_team.split()[-1] if home_team else ''
				
				# Check if these are valid NFL team names
				away_valid = any(team in away_team for team in valid_teams)
				home_valid = any(team in home_team for team in valid_teams)
				
				if away_valid and home_valid and len(away_team) < 50 and len(home_team) < 50:
					# Try to find game time near this match
					start_pos = match.start()
					context = page_text[max(0, start_pos-200):start_pos+200]
					time_match = re.search(r'([A-Za-z]{3}\s+\d{1,2}:\d{2}\s+[AP]M\s+ET)', context)
					game_time = time_match.group(1) if time_match else 'TBD'
					
					games.append({
						'away_team': away_team,
						'home_team': home_team,
						'away_abbrev': away_abbrev,
						'home_abbrev': home_abbrev,
						'game_time': game_time
					})
			
			# Remove duplicates
			unique_games = []
			seen = set()
			for game in games:
				key = (game['away_team'], game['home_team'])
				if key not in seen:
					seen.add(key)
					unique_games.append(game)
			
			# Filter to today's weekday only (e.g., only SUN games on Sunday)
			def is_today_game(gt: str) -> bool:
				if not gt or gt == 'TBD':
					return False
				return gt.upper().startswith(weekday)
			unique_games = [g for g in unique_games if is_today_game(g.get('game_time',''))]
			
			print(f"Found {len(unique_games)} NFL games for today")
			return unique_games
			
		except Exception as e:
			print(f"❌ Error getting NFL games: {e}")
			return []
	
	def _get_nfl_team_abbrev(self, team_name: str) -> str:
		"""Get NFL team abbreviation from full name"""
		team_mapping = {
			'Kansas City Chiefs': 'KC',
			'Los Angeles Chargers': 'LAC',
			'Tampa Bay Buccaneers': 'TB',
			'Atlanta Falcons': 'ATL',
			'Buffalo Bills': 'BUF',
			'Miami Dolphins': 'MIA',
			'New England Patriots': 'NE',
			'New York Jets': 'NYJ',
			'Baltimore Ravens': 'BAL',
			'Cincinnati Bengals': 'CIN',
			'Cleveland Browns': 'CLE',
			'Pittsburgh Steelers': 'PIT',
			'Houston Texans': 'HOU',
			'Indianapolis Colts': 'IND',
			'Jacksonville Jaguars': 'JAX',
			'Tennessee Titans': 'TEN',
			'Denver Broncos': 'DEN',
			'Las Vegas Raiders': 'LV',
			'Los Angeles Rams': 'LAR',
			'San Francisco 49ers': 'SF',
			'Arizona Cardinals': 'ARI',
			'Seattle Seahawks': 'SEA',
			'Chicago Bears': 'CHI',
			'Detroit Lions': 'DET',
			'Green Bay Packers': 'GB',
			'Minnesota Vikings': 'MIN',
			'Dallas Cowboys': 'DAL',
			'New York Giants': 'NYG',
			'Philadelphia Eagles': 'PHI',
			'Washington Commanders': 'WSH',
			'Carolina Panthers': 'CAR',
			'New Orleans Saints': 'NO'
		}
		return team_mapping.get(team_name, team_name[:3].upper())
	
	def _get_nfl_team_lineup(self, team_name: str, team_abbrev: str) -> List[Dict]:
		"""Get NFL team lineup with 6 players (1 QB, 1 RB, 3 WR, 1 TE) from Rotowire"""
		try:
			url = self.ROTOWIRE_NFL_URL
			response = self.session.get(url, timeout=15)
			response.raise_for_status()
			
			soup = BeautifulSoup(response.text, 'html.parser')
			players = []
			# Build a locked team block: from "TeamName (record)" to the next team header
			page_text = soup.get_text(' ', strip=True)
			team_header_pattern = rf'\b{re.escape(team_name)}\s+\([0-9-]+\)'
			header_match = re.search(team_header_pattern, page_text)
			if not header_match:
				print(f"⚠️ Team header not found for {team_name}")
				return []
			start_idx = header_match.start()
			# Compile next-team pattern from valid short names seen on the page
			valid_teams = [
				'Chiefs','Chargers','Buccaneers','Falcons','Bills','Dolphins','Patriots','Jets',
				'Ravens','Bengals','Browns','Steelers','Texans','Colts','Jaguars','Titans',
				'Broncos','Raiders','Rams','49ers','Cardinals','Seahawks','Bears','Lions',
				'Packers','Vikings','Cowboys','Giants','Eagles','Commanders','Panthers','Saints'
			]
			next_teams_regex = r'\b(' + '|'.join(map(re.escape, valid_teams)) + r')\s+\([0-9-]+\)'
			next_match = re.search(next_teams_regex, page_text[start_idx + 1:])
			end_idx = (start_idx + 1 + next_match.start()) if next_match else min(len(page_text), start_idx + 600)
			block = page_text[start_idx:end_idx]
			# Within the block, extract positions strictly in order and limited per spec
			pos_pattern = re.compile(r'\b(QB|RB|WR|TE)\s+([^QDRK][^QBWRTEK]{0,60}?)(?=\s+(?:QB|RB|WR|TE|K|$))')
			counts = {'QB': 0, 'RB': 0, 'WR': 0, 'TE': 0}
			for m in pos_pattern.finditer(block):
				pos = m.group(1)
				name_raw = re.sub(r'\s+', ' ', m.group(2)).strip()
				# Injury tag capture at end of token list (e.g., "Name Q" / "Name D" / "Name O")
				injury = ''
				if name_raw.endswith(' Q'):
					name_raw = name_raw[:-2].strip()
					injury = 'Q'
				elif name_raw.endswith(' D'):
					name_raw = name_raw[:-2].strip()
					injury = 'D'
				elif name_raw.endswith(' O'):
					name_raw = name_raw[:-2].strip()
					injury = 'O'
				# Enforce limits: QB 1, RB 1, WR 3, TE 1
				limit = 3 if pos == 'WR' else 1
				if counts[pos] >= limit:
					continue
				# Skip kickers entirely per requirements
				players.append({'name': name_raw, 'position': pos, 'injury': injury})
				counts[pos] += 1
				if len(players) >= 6 and counts['QB'] >= 1 and counts['RB'] >= 1 and counts['TE'] >= 1 and counts['WR'] >= 2:
					break
			print(f"Found {len(players)} players for {team_name} ({team_abbrev})")
			return players[:6]
			
		except Exception as e:
			print(f"❌ Error getting NFL lineup for {team_name}: {e}")
			return []
	
	def get_nfl_combined_cards(self) -> List[Dict]:
		"""Get NFL lineup cards similar to MLB format"""
		try:
			team_lineups, team_times = self.get_nfl_lineups()
			cards = []
			
			# Group teams into games (assuming we have pairs)
			teams = list(team_lineups.keys())
			for i in range(0, len(teams), 2):
				if i + 1 < len(teams):
					away_team = teams[i]
					home_team = teams[i + 1]
					
					away_players = team_lineups.get(away_team, [])
					home_players = team_lineups.get(home_team, [])
					game_time = team_times.get(away_team, 'TBD')
					
					# Separate players by position
					away_qb = [p for p in away_players if p['position'] == 'QB']
					away_rb = [p for p in away_players if p['position'] == 'RB']
					away_wr = [p for p in away_players if p['position'] == 'WR']
					away_te = [p for p in away_players if p['position'] == 'TE']
					
					home_qb = [p for p in home_players if p['position'] == 'QB']
					home_rb = [p for p in home_players if p['position'] == 'RB']
					home_wr = [p for p in home_players if p['position'] == 'WR']
					home_te = [p for p in home_players if p['position'] == 'TE']
					
					cards.append({
						'away_label': away_team,
						'home_label': home_team,
						'time_et': game_time,
						'away_qb': away_qb[0]['name'] if away_qb else '',
						'away_rb': away_rb[0]['name'] if away_rb else '',
						'away_wr': [p['name'] for p in away_wr[:3]],  # Top 3 WRs
						'away_te': away_te[0]['name'] if away_te else '',
						'home_qb': home_qb[0]['name'] if home_qb else '',
						'home_rb': home_rb[0]['name'] if home_rb else '',
						'home_wr': [p['name'] for p in home_wr[:3]],  # Top 3 WRs
						'home_te': home_te[0]['name'] if home_te else '',
						'away_players': away_players,  # Full player list with positions
						'home_players': home_players   # Full player list with positions
					})
			
			print(f"🎯 NFL cards created: {len(cards)} games")
			return cards
			
		except Exception as e:
			print(f"❌ Error creating NFL cards: {e}")
			return [] 

	def get_nfl_players_today(self) -> List[Dict]:
		"""Return a flat list of NFL players (QB/RB/WR/TE) scheduled for TODAY (ET).
		Each item: {name, position, injury, team?, game_time_et}. Ignores K and away/home.
		"""
		try:
			resp = self.session.get(self.ROTOWIRE_NFL_URL, timeout=20)
			resp.raise_for_status()
			soup = BeautifulSoup(resp.text, 'html.parser')
			
			# Weekday in ET
			try:
				et = pytz.timezone('US/Eastern')
				today = datetime.now(et)
				weekday = today.strftime('%a').upper()
			except Exception:
				weekday = datetime.utcnow().strftime('%a').upper()
			
			players: List[Dict] = []
			
			# Look for game cards/containers
			game_containers = soup.select('.lineup, .game-card, .matchup')
			if not game_containers:
				# Fallback: look for any div containing team names and players
				game_containers = soup.select('div')
			
			for container in game_containers:
				container_text = container.get_text(' ', strip=True)
				
				# Check if this container has today's games
				if weekday not in container_text or 'ET' not in container_text:
					continue
				
				# Extract game time
				time_match = re.search(rf'{weekday}\s+\d{{1,2}}:\d{{2}}\s+[AP]M\s+ET', container_text)
				if not time_match:
					continue
				game_time = time_match.group(0)
				
				# Extract team names - look for patterns like "Team Name (record)"
				team_patterns = [
					r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*\(\d+-\d+\)',  # Team Name (record)
					r'([A-Z]{2,4})\s+[A-Z][a-z]+',  # Abbreviation + City
					r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+[A-Z][a-z]+',  # City + Team
				]
				
				teams = []
				for pattern in team_patterns:
					matches = re.findall(pattern, container_text)
					if matches:
						teams.extend(matches[:2])  # Take first 2 teams
						break
				
				# If no teams found, try to extract from common NFL team patterns
				if not teams:
					team_abbrevs = ['KC', 'LAC', 'TB', 'ATL', 'BUF', 'MIA', 'NE', 'NYJ', 'BAL', 'CIN', 'CLE', 'PIT', 
									'HOU', 'IND', 'JAX', 'TEN', 'DEN', 'LV', 'DAL', 'NYG', 'PHI', 'WAS', 'CHI', 'DET', 
									'GB', 'MIN', 'NO', 'CAR', 'ARI', 'LAR', 'SF', 'SEA']
					for abbrev in team_abbrevs:
						if abbrev in container_text:
							teams.append(abbrev)
							if len(teams) >= 2:
								break
				
				# Extract players with positions
				player_patterns = [
					r'\b(QB|RB|WR|TE)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z\.]+)*)',
					r'\b(QB|RB|WR|TE)\s+([A-Z]\.\s*[A-Z][a-z]+(?:\s+[A-Z][a-z\.]+)*)',
				]
				
				for pattern in player_patterns:
					for match in re.finditer(pattern, container_text):
						pos = match.group(1)
						name = match.group(2).strip()
						
						# Clean up name
						name = re.sub(r'\s+', ' ', name)
						
						# Check for injury status
						injury = ''
						if name.endswith(' Q'):
							name = name[:-2].strip()
							injury = 'Q'
						elif name.endswith(' D'):
							name = name[:-2].strip()
							injury = 'D'
						elif name.endswith(' O'):
							name = name[:-2].strip()
							injury = 'O'
						
						# Assign team (alternate between teams if we have 2)
						team = teams[0] if teams else 'Unknown'
						if len(teams) == 2:
							# Simple alternating logic - could be improved
							team = teams[0] if len(players) % 2 == 0 else teams[1]
						
						players.append({
							'name': name,
							'position': pos,
							'injury': injury,
							'team': team,
							'game_time_et': game_time
						})
			
			# Deduplicate by (name, position, time)
			seen = set()
			uniq: List[Dict] = []
			for p in players:
				key = (p['name'], p['position'], p['game_time_et'])
				if key in seen:
					continue
				seen.add(key)
				uniq.append(p)
			
			return uniq
		except Exception as e:
			print(f"❌ Error getting NFL players for today: {e}")
			return []