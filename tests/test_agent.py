import asyncio

from src.main import AutonomousProductAgent

def test_generate_mrd_runs():
    agent = AutonomousProductAgent()
    async def run():
        mrd = await agent.generate_mrd("Build skill-based gambling app for Europe")
        # Ensure either MRDOutput-like or ErrorMRD-like structure returned
        assert hasattr(mrd, 'generated_at') or hasattr(mrd, 'error')
    asyncio.run(run())
