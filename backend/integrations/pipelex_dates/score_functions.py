"""Optional Pipelex library, discovered only when DATE_SCORING_BACKEND=pipelex."""
import json
from pipelex.core.memory.working_memory import WorkingMemory
from pipelex.core.stuffs.text_content import TextContent
from pipelex.system.registries.func_registry import pipe_func
from backend.streams.E_orchestrator.date_composer import score_candidates


@pipe_func()
def chandelle_date_score(working_memory: WorkingMemory) -> TextContent:
    payload=json.loads(working_memory.get_stuff_as_str('score_request'))
    return TextContent(text=json.dumps(score_candidates(payload['rows'],payload['budget'],payload['distance_scale_km'])))
