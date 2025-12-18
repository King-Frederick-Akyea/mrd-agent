"""
Example: Generate MRD for Triumph-like app in European market.
"""

import asyncio
import json
from datetime import datetime

from src.main import AutonomousProductAgent

async def main():
    """Generate MRD for European skill-gaming app"""
    
    user_prompt = (
        "I want to build a skill-based gambling app targeting young men, "
        "similar to Triumph but for the European market"
    )
    
    print("=" * 60)
    print("AUTONOMOUS MRD AGENT DEMO")
    print("=" * 60)
    print(f"Prompt: {user_prompt}")
    print("-" * 60)
    
    agent = AutonomousProductAgent()
    
    print("🚀 Starting MRD generation...")
    print("📋 Creating research plan...")
    print("🔍 Executing research tasks...")
    
    start_time = datetime.now()
    mrd = await agent.generate_mrd(user_prompt)
    processing_time = (datetime.now() - start_time).total_seconds()
    
    print("✅ MRD Generation Complete!")
    print("-" * 60)
    
    print("📊 MRD SUMMARY:")
    try:
        print(f"   ID: {mrd.id}")
        print(f"   Vertical: {mrd.vertical}")
        print(f"   Confidence Score: {mrd.confidence_score:.2%}")
        print(f"   Processing Time: {processing_time:.2f}s")
        print(f"   Competitors Analyzed: {len(mrd.competitor_analysis)}")
        print(f"   Features Recommended: {len(mrd.feature_recommendations)}")
    except Exception:
        print("   (partial or error MRD returned)")
    
    output_file = f"mrd_triumph_europe_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(mrd.model_dump_json(indent=2))
    except Exception:
        import json
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(json.dumps(mrd if isinstance(mrd, dict) else {}, indent=2))
    
    print(f"\n💾 Saved to: {output_file}")

    print("\n🎯 TOP FEATURE RECOMMENDATIONS:")
    try:
        for i, feature in enumerate(mrd.feature_recommendations[:3], 1):
            print(f"   {i}. {feature.name} ({feature.priority})")
            print(f"      Impact: {feature.estimated_impact:.0%}")
            print(f"      Effort: {feature.development_effort.upper()}")
    except Exception:
        pass
    
    print("\n" + "=" * 60)
    print("DEMO COMPLETE - Structured MRD ready for product team")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
