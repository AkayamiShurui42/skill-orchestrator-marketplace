from pathlib import Path
import runpy
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from orchestrator import main
sys.argv=[str(Path(__file__).resolve().parents[1]/'scripts'/'orchestrator.py'),'hook-prompt']
main()
