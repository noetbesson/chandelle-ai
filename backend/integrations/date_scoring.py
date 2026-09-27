"""Local score by default; optional Pipelex runtime executes the identical pure function."""
import asyncio
import json
import logging
import os
from pathlib import Path
from threading import RLock
from backend.streams.E_orchestrator.date_composer import score_candidates

LOCK=RLock()


def _pipelex(rows,budget,distance):
    from pipelex.pipelex import Pipelex
    from pipelex.pipeline.runner import PipelexMTHDSProtocol
    directory=Path(__file__).with_name('pipelex_dates')
    # Dedicated library: it contains only a PipeFunc, no LLM/provider call or account key.
    Pipelex.make(library_dirs=[str(directory)])
    async def run():
        runner=PipelexMTHDSProtocol(library_dirs=[str(directory)])
        response=await runner.execute(pipe_code='score_candidates',inputs={
            'score_request':json.dumps({'rows':rows,'budget':budget,'distance_scale_km':distance})})
        return json.loads(response.pipe_output.main_stuff.content.text)
    return asyncio.run(run())


def score(rows,budget,distance):
    expected=score_candidates(rows,budget,distance)
    if os.getenv('DATE_SCORING_BACKEND','local')!='pipelex':return expected,'local_deterministic',None
    try:
        with LOCK:output=_pipelex(rows,budget,distance)
        if output!=expected:raise ValueError('Non deterministic scoring output')
        return output,'pipelex_local',None
    except Exception:
        logging.getLogger(__name__).warning('date_scoring fallback=local reason=pipelex_unavailable_or_invalid')
        return expected,'local_deterministic','pipelex_unavailable_or_invalid'
