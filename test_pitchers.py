from backend.services.lineup_scraper import LineupScraper

scraper = LineupScraper()
cards = scraper.get_combined_cards()

print(f'Total cards: {len(cards)}')

for i, card in enumerate(cards[:3]):
    print(f'Card {i}: Away pitcher: {card.get("away_pitcher", "None")}, Home pitcher: {card.get("home_pitcher", "None")}')

# Check if any cards have pitcher data
pitcher_cards = [card for card in cards if card.get('away_pitcher') or card.get('home_pitcher')]
print(f'Cards with pitcher data: {len(pitcher_cards)}') 