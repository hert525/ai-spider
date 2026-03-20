"""Simple test to verify the new architecture."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_basic():
    """Test basic imports and structure."""
    try:
        from src.core.config import settings
        from src.core.models import Project, Task, Worker
        from src.engine.nodes import FetchNode, ParseNode, GenerateNode, ValidateNode
        from src.engine.graphs import SmartScraperGraph, CodeGeneratorGraph
        from src.scheduler.task_manager import task_manager
        from src.scheduler.worker import worker_manager
        
        print("✅ All imports successful")
        print(f"  - Settings: {settings.llm_model}")
        print(f"  - Models: Project, Task, Worker")
        print(f"  - Nodes: FetchNode, ParseNode, GenerateNode, ValidateNode")
        print(f"  - Graphs: SmartScraperGraph, CodeGeneratorGraph")
        print(f"  - Scheduler: task_manager, worker_manager")
        
        # Test model instantiation
        p = Project(name="Test", description="Test project")
        t = Task(project_id=p.id, name="Test task")
        w = Worker(id="test-worker", hostname="test")
        
        print(f"✅ Models instantiated: {p.id}, {t.id}, {w.id}")
        
        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_basic())
