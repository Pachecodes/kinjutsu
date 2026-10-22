"""Local deterministic form-to-prompt preview. No agents, models or render submission."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

ROOT = Path(__file__).resolve().parents[4]
PROMPTING = ROOT / 'prompting'
_spec = importlib.util.spec_from_file_location('kinjutsu_offline_prompts', PROMPTING / 'renderer.py')
_renderer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_renderer)
router = APIRouter(prefix='/prompting', tags=['offline prompt templates'])


class BuildPromptRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    template: Literal['character-swap-aligned', 'motion-ref2va', 't2va', 'i2va', 'fl2va', 'l2va']
    input: dict[str, Any]


@router.get('/catalog')
def catalog():
    return json.loads((PROMPTING / 'catalog.json').read_text(encoding='utf-8'))


@router.post('/build')
def build(body: BuildPromptRequest):
    if len(json.dumps(body.input, ensure_ascii=False)) > 65536:
        raise HTTPException(422, 'Formulario demasiado grande; máximo 64 KiB de texto.')
    try:
        prompt = _renderer.render_prompt(body.template, body.input)
    except _renderer.PromptValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {'template':body.template, 'prompt':prompt, 'requires_agent':False, 'submits_render':False}
