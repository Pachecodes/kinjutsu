"""Deterministic, standard-library-only H3 form renderer. No media or network I/O.

Public API: render_prompt(template: str, data: dict) -> str
Raises PromptValidationError for invalid form data. Does not mutate data.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re

TEMPLATES = ("character-swap-aligned", "motion-ref2va", "t2va", "i2va", "fl2va", "l2va")
BASE_SECTIONS = ("integrated_multimodal_description", "overall_soundscape", "non_diegetic_music")
REF_SECTIONS = ("subject_definitions", "summary", "retention_analysis", "detailed_description", "overall_soundscape", "non_diegetic_music")
TOKEN = re.compile(r"<(Picture|Video|Audio|Subject) ([1-9][0-9]*)>")


class PromptValidationError(ValueError):
    """Actionable invalid-input error; safe to display as a form error."""


def fail(message):
    raise PromptValidationError(message)


def obj(value, required, optional=(), path="input"):
    if not isinstance(value, dict):
        fail(f"{path}: expected an object")
    missing = set(required) - value.keys()
    extra = value.keys() - set(required) - set(optional)
    if missing:
        fail(f"{path}: missing required fields: {', '.join(sorted(missing))}")
    if extra:
        fail(f"{path}: unsupported fields: {', '.join(sorted(extra))}")


def text(value, path, allowed):
    if not isinstance(value, str) or not value.strip():
        fail(f"{path}: nonempty text required; describe it explicitly, do not infer from media")
    if '\n' in value or '\r' in value:
        fail(f"{path}: use one paragraph, not additional prompt sections")
    if re.search(r"\{\{|\}\}|\b(?:TODO|TBD)\b|\[(?:Shot|Subject|Picture|Video|Audio|INSERT|REPLACE|PLACEHOLDER)\b", value, re.I):
        fail(f"{path}: unresolved labels/placeholders are not allowed")
    for match in TOKEN.finditer(value):
        if match.group() not in allowed:
            fail(f"{path}: reference {match.group()} is not attached/allowed")
    remainder = TOKEN.sub('', value)
    if re.search(r'\b(?:Picture|Video|Audio|Subject)\s+[0-9]+\b', remainder):
        fail(f"{path}: reference labels must use exact attached angle-bracket tokens")
    if '<' in remainder or '>' in remainder:
        fail(f"{path}: malformed reference or markup; use exact attached tokens")
    return value.strip()


def number(value, path, places=3):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        fail(f"{path}: expected finite decimal seconds")
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or result > 3600:
            fail(f"{path}: must be finite and between 0 and 3600 seconds")
        if result != result.quantize(Decimal(10) ** -places):
            fail(f"{path}: maximum {places} decimal places")
        return result
    except InvalidOperation:
        fail(f"{path}: expected finite decimal seconds")


def timestamp(seconds):
    ms = int(seconds * 1000)
    return f"{ms // 60000:02d}:{(ms // 1000) % 60:02d}.{ms % 1000:03d}"


def render_prompt(template: str, data: dict) -> str:
    """Render only text. Caller owns attachment mapping and runtime compatibility."""
    if template not in TEMPLATES:
        fail(f"template: choose one of {', '.join(TEMPLATES)}")
    obj(data, ("duration_seconds", "identity", "style", "assets", "shots", "audio"), ("dialogue",))
    duration = number(data['duration_seconds'], 'duration_seconds', 3)
    if duration <= 0:
        fail('duration_seconds: must be greater than zero')
    assets = data['assets']
    if not isinstance(assets, list):
        fail('assets: expected ordered array')
    allowed = set()
    counts = {'image': 0, 'video': 0, 'audio': 0}
    roles = []
    clean_assets = []
    for i, asset in enumerate(assets):
        path = f'assets[{i}]'
        obj(asset, ('kind', 'role', 'description'), ('token',), path)
        kind, role = asset['kind'], asset['role']
        if not isinstance(kind, str) or not isinstance(role, str):
            fail(f'{path}: kind and role must be strings')
        if kind == 'aligned_guide':
            if role != 'aligned_guide' or 'token' in asset:
                fail(f'{path}: aligned guide must have role aligned_guide and NO token')
            token = None
        elif kind in counts:
            counts[kind] += 1
            token = f"<{ {'image': 'Picture', 'video': 'Video', 'audio': 'Audio'}[kind]} {counts[kind]}>"
            if asset.get('token') != token:
                fail(f'{path}.token: expected exact attached token {token} in category attachment order')
            allowed.add(token)
        else:
            fail(f'{path}.kind: unsupported asset kind')
        roles.append(role)
        clean_assets.append((kind, role, token, asset['description']))
    if template == 'character-swap-aligned':
        if [(a[0], a[1]) for a in clean_assets] != [('image', 'identity'), ('aligned_guide', 'aligned_guide')]:
            fail('assets: aligned swap requires ONLY Picture 1 identity followed by one tokenless aligned_guide')
    elif template == 'motion-ref2va':
        if counts['video'] != 1 or counts['audio'] or 'aligned_guide' in roles or counts['image'] < 1 or roles.count('identity') != 1:
            fail('assets: Motion requires identity image(s) with exactly one identity role and exactly one ordinary Motion Video 1; no audio or aligned guide')
        for kind, role, token, _ in clean_assets:
            if (kind == 'image' and role not in ('identity', 'scene', 'costume', 'style')) or (kind == 'video' and role != 'motion'):
                fail('assets: Motion image roles are identity/scene/costume/style; video role is motion')
    else:
        expected = {'t2va': [], 'i2va': [('image', 'first_frame')], 'fl2va': [('image', 'first_frame'), ('image', 'last_frame')], 'l2va': [('image', 'last_frame')]}[template]
        if [(a[0], a[1]) for a in clean_assets] != expected:
            fail(f'assets: {template} requires ordered roles {expected}, with no extra references')
    identity = text(data['identity'], 'identity', allowed)
    style = text(data['style'], 'style', allowed)
    for i, a in enumerate(clean_assets):
        text(a[3], f'assets[{i}].description', allowed)
    shots = data['shots']
    if not isinstance(shots, list) or not shots:
        fail('shots: at least one explicitly described shot required')
    if template == 'character-swap-aligned' and len(shots) != 1:
        fail('shots: approved aligned swap preserves guide timing; exactly one continuous shot, no added cuts')
    starts = []
    for i, shot in enumerate(shots):
        obj(shot, ('start_seconds', 'scene', 'performance', 'camera', 'lighting', 'sound'), path=f'shots[{i}]')
        start = number(shot['start_seconds'], f'shots[{i}].start_seconds')
        if (i == 0 and start != 0) or (i > 0 and start <= starts[-1]) or start >= duration:
            fail(f'shots[{i}].start_seconds: first must be 0; later cuts strictly increase and stay before duration')
        starts.append(start)
        for field in ('scene', 'performance', 'camera', 'lighting', 'sound'):
            text(shot[field], f'shots[{i}].{field}', allowed)
    audio = data['audio']
    obj(audio, ('soundscape', 'music', 'silent'), path='audio')
    if type(audio['silent']) is not bool:
        fail('audio.silent: expected boolean')
    soundscape = text(audio['soundscape'], 'audio.soundscape', allowed)
    music = text(audio['music'], 'audio.music', allowed)
    if (soundscape == 'N/A') != audio['silent']:
        fail('audio.soundscape: N/A is reserved for explicitly complete silence; silent=true requires N/A')
    lines = data.get('dialogue', [])
    if not isinstance(lines, list):
        fail('dialogue: expected array')
    if audio['silent'] and (music != 'N/A' or lines or any(s['sound'] != 'N/A' for s in shots)):
        fail('audio: complete silence requires music and shot sound N/A, and no dialogue')
    if template == 'character-swap-aligned' and (lines or music != 'N/A'):
        fail('audio: approved aligned template has no narration, dialogue, singing or music')
    speakers = {}
    utterances = [[] for _ in shots]
    previous_end = Decimal(0)
    for i, line in enumerate(lines):
        path = f'dialogue[{i}]'
        obj(line, ('shot', 'start_seconds', 'end_seconds', 'speaker', 'language', 'text', 'delivery'), ('voiceover', 'subject'), path)
        index = line['shot']
        if type(index) is not int or not 1 <= index <= len(shots):
            fail(f'{path}.shot: must reference an existing shot number')
        start = number(line['start_seconds'], path + '.start_seconds')
        end = number(line['end_seconds'], path + '.end_seconds')
        boundary = starts[index] if index < len(starts) else duration
        if not starts[index-1] <= start < end <= boundary or start < previous_end:
            fail(f'{path}: dialogue must be chronological, nonoverlapping, and fit wholly inside its shot and duration; split cross-cut lines explicitly')
        previous_end = end
        speaker = text(line['speaker'], path + '.speaker', allowed)
        lang = text(line['language'], path + '.language', set())
        if '[' in lang or ']' in lang:
            fail(f'{path}.language: plain language name required')
        words = text(line['text'], path + '.text', set())
        # Preserve the actual spoken string verbatim, including user punctuation.
        words = line['text']
        delivery = text(line['delivery'], path + '.delivery', allowed)
        voiceover = line.get('voiceover', False)
        if type(voiceover) is not bool:
            fail(path + '.voiceover: expected boolean')
        subject = line.get('subject')
        if subject is not None and (template != 'motion-ref2va' or type(subject) is not int or subject != 1):
            fail(path + '.subject: only subject=1 (the identity performer) is supported in Motion; omit for independent/off-screen voices')
        speaker_key = ('subject', subject) if subject is not None else ('voice', speaker)
        sid = speakers.setdefault(speaker_key, len(speakers) + 1)
        speaker_label = f'<Subject 1> (S{sid}), {speaker}' if subject is not None else f'{speaker} (S{sid})'
        phrase = 'says in an off-screen voiceover' if voiceover else 'says'
        close = ' while the corresponding on-screen character\'s lips remain completely closed.' if voiceover else ''
        utterances[index-1].append(f'Between {start:.3f} and {end:.3f} seconds, {speaker_label}, {delivery}, {phrase}: <d>[{lang}] {words}</d>{close}')
    refmode = template == 'motion-ref2va'
    shot_text = []
    for i, shot in enumerate(shots):
        lead = f'[Shot {i+1}] ' + (f'At {timestamp(starts[i])}, the camera cuts to ' if i else '')
        if not i and not refmode:
            lead += style + '. ' + identity + '. '
        anchor = ''
        if template in ('i2va', 'fl2va') and i == 0:
            anchor += 'Begin from <Picture 1>, preserving the supplied first-frame identity, clothing, composition and spatial relationships. '
        if template in ('fl2va', 'l2va') and i == len(shots)-1:
            token = '<Picture 2>' if template == 'fl2va' else '<Picture 1>'
            anchor += f'Continuously converge to the exact pose, object states and composition of {token} at {duration.normalize():f} seconds. '
        if refmode:
            subject_phrase = f'<Subject 1>, {identity},' if i == 0 else '<Subject 1>'
            anchor += f'Keep {subject_phrase} visible; use <Video 1> for the explicitly described motion, camera and timing, not its identity. '
            for n, a in enumerate([a for a in clean_assets if a[0] == 'image' and a[1] != 'identity'], 2):
                anchor += f'Apply <Subject {n}> as the {a[1]} guidance here. '
        body = ' '.join(f'{key.capitalize()}: {shot[key]}.' for key in ('scene', 'performance', 'camera', 'lighting', 'sound'))
        shot_text.append(lead + anchor + body + ' ' + ' '.join(utterances[i]))
    timeline = ' '.join(x.strip() for x in shot_text)
    if not refmode and template != 'character-swap-aligned':
        descriptions = ' '.join(f'{a[2]} establishes the {a[1]}: {a[3]}.' for a in clean_assets)
        if descriptions:
            timeline += ' ' + descriptions
    if template == 'character-swap-aligned':
        return (
            'body_swap: Replace the single adult person in the aligned guide with the character in <Picture 1>. '
            "Picture 1 owns the entire person's identity: facial proportions, hair, and consistent intrinsic skin complexion across face, neck, both arms, both hands and every finger, allowing natural local lighting and shadows. "
            'The aligned guide owns only performance, expressions, mouth movements, pose, clothing, accessories, props, environment, framing, camera motion, lighting and timing, not the original person\'s identity or complexion. '
            'Preserve guide clothing, scene and local lighting. Follow the original hand trajectories and gestures precisely without inventing actions. Keep the same coherent reference face throughout. '
            'Exactly one coherent adult character, anatomically plausible separated fingers and stable scene geometry throughout. No added people, cuts, text, captions, watermark or collage. '
            f'Target duration: {duration.normalize():f} seconds; keep the aligned guide timing across the full target. '
            f'Identity description: {identity}. Identity portrait notes: {clean_assets[0][3]}. Guide description: {clean_assets[1][3]}. '
            f'User-described guide timeline (preserve; do not replace with invented staging): {timeline}\n\n'
            f'overall_soundscape: {soundscape}\n\nnon_diegetic_music: {music}\n'
        )
    if refmode:
        identity_asset = next(a for a in clean_assets if a[1] == 'identity')
        definitions = [f'<Subject 1> is {identity}, using {identity_asset[2]} for identity: {identity_asset[3]}.']
        retention = [f'<Subject 1> (appears in {", ".join(f"[Shot {i+1}]" for i in range(len(shots)))}): fully_preserved - retain the explicitly described identity.']
        for n, a in enumerate([a for a in clean_assets if a[0] == 'image' and a[1] != 'identity'], 2):
            definitions.append(f'<Subject {n}> is the {a[1]} guidance from {a[2]}: {a[3]}.')
            retention.append(f'<Subject {n}> (appears in all target shots): attribute_transfer - transfer the described {a[1]} characteristics.')
        motion = next(a for a in clean_assets if a[0] == 'video')
        definitions.append(f'<Video 1> provides whole-video motion, camera and temporal guidance: {motion[3]}. Its audio is not enabled or reused.')
        retention.append('<Video 1> (motion, camera and temporal structure): weak_reference - guide the explicitly described target actions without copying identity or audio; this is ordinary reference generation, not an aligned guide.')
        sections = [('subject_definitions', '\n'.join(definitions)), ('summary', f'[reference generation] Generate a {duration.normalize():f}-second target featuring <Subject 1>, guided by <Video 1> and the image-derived subjects defined above. Do not edit or continue the source file or copy its soundtrack.'), ('retention_analysis', '\n'.join(retention)), ('detailed_description', f'The target video uses this user-specified style: {style}.\n{timeline}'), ('overall_soundscape', soundscape), ('non_diegetic_music', music)]
        return '\n\n'.join(f'{name}:\n{value}' for name, value in sections) + '\n'
    instruction = ''
    if template == 'i2va':
        instruction = 'For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.\n\n'
    elif template == 'fl2va':
        instruction = f'How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot {len(shots)}) aligns with the {duration.normalize():f}-second mark of the target video.\n\n'
    elif template == 'l2va':
        instruction = f'How the reference pictures align with the target video — <Picture 1> (from [Shot {len(shots)}]) aligns with the {duration.normalize():f}-second mark of the target video.\n\n'
    return instruction + f'integrated_multimodal_description: {timeline} The target ends at {duration.normalize():f} seconds.\n\noverall_soundscape: {soundscape}\n\nnon_diegetic_music: {music}\n'
