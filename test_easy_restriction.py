#!/usr/bin/env python3
"""
Test script to verify the one EASY prop per player restriction
"""

from ml_prop_generator import MLPropGenerator

def test_easy_restriction():
    print("🧪 Testing one EASY prop per player restriction...")
    
    generator = MLPropGenerator()
    props = generator.generate_today_props()
    
    print(f"📊 Generated {len(props)} total props")
    
    # Count EASY props
    easy_props = [p for p in props if p['difficulty'] == 'EASY']
    print(f"🎯 EASY props: {len(easy_props)}")
    
    # Check if each player has only one EASY prop
    player_easy_counts = {}
    for prop in easy_props:
        player = prop['player_name']
        if player not in player_easy_counts:
            player_easy_counts[player] = 0
        player_easy_counts[player] += 1
    
    # Find violations
    violations = []
    for player, count in player_easy_counts.items():
        if count > 1:
            violations.append((player, count))
    
    if violations:
        print(f"❌ VIOLATIONS FOUND: {len(violations)} players have multiple EASY props:")
        for player, count in violations:
            print(f"   • {player}: {count} EASY props")
    else:
        print("✅ SUCCESS: All players have exactly one EASY prop!")
    
    # Show sample props
    if easy_props:
        print("\n📋 Sample EASY props:")
        for prop in easy_props[:5]:
            print(f"   • {prop['player_name']} - {prop['prop_type']} {prop['line_value']} ({prop['team']})")
    
    return len(violations) == 0

if __name__ == "__main__":
    success = test_easy_restriction()
    if success:
        print("\n🎉 Restriction working correctly!")
    else:
        print("\n⚠️ Restriction needs fixing!") 