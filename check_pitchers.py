import json

# Load the data
with open('mlb_props.json', 'r') as f:
    data = json.load(f)

print("Keys in data:", list(data.keys()))

if 'cards' in data:
    print(f"Cards found: {len(data['cards'])}")
    for i, card in enumerate(data['cards'][:3]):
        print(f"Card {i}: {card.get('away_pitcher', 'No away pitcher')} vs {card.get('home_pitcher', 'No home pitcher')}")
else:
    print("No cards found in data")

if 'games' in data:
    print(f"Games found: {len(data['games'])}")
    for i, game in enumerate(data['games'][:3]):
        print(f"Game {i}: {game.get('away_team', 'No away team')} @ {game.get('home_team', 'No home team')}")

if 'props' in data:
    print(f"Props found: {len(data['props'])}")
    # Check first few props for pitcher positions
    pitcher_count = 0
    for prop_id, prop_data in list(data['props'].items())[:10]:
        if prop_data['player_info']['position'] == 'P':
            pitcher_count += 1
            print(f"Pitcher prop found: {prop_data['player_info']['name']} - {prop_data['player_info']['team_name']}")
    
    print(f"Total pitcher props found: {pitcher_count}") 