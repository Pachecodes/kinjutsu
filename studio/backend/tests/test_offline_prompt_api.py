import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]


def test_offline_prompt_catalog_and_build(client):
    r=client.get('/api/prompting/catalog')
    assert r.status_code==200
    assert len(r.json()['templates'])==6
    form=json.loads((ROOT/'prompting/examples/character-swap-aligned.json').read_text(encoding='utf8'))
    form['duration_seconds']=10.125
    r=client.post('/api/prompting/build',json={'template':'character-swap-aligned','input':form})
    assert r.status_code==200, r.text
    body=r.json()
    assert body['requires_agent'] is False and body['submits_render'] is False
    assert body['prompt'].startswith('body_swap:')
    assert '<Picture 1>' in body['prompt'] and '<Video 1>' not in body['prompt']


def test_prompt_form_errors_and_unknown_fields_do_not_generate(client):
    assert client.post('/api/prompting/build',json={'template':'t2va','input':{}}).status_code==422
    assert client.post('/api/prompting/build',json={'template':'t2va','input':{},'submit':True}).status_code==422


def test_prompt_preview_does_not_submit_jobs(client):
    before=client.get('/api/jobs').json()
    form=json.loads((ROOT/'prompting/examples/t2va.json').read_text(encoding='utf8'))
    r=client.post('/api/prompting/build',json={'template':'t2va','input':form})
    assert r.status_code==200,r.text
    assert client.get('/api/jobs').json()==before
