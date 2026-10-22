import copy
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from prompting.renderer import BASE_SECTIONS, REF_SECTIONS, PromptValidationError, render_prompt


def example(template='t2va'):
    return json.loads((ROOT / f'prompting/examples/{template}.json').read_text(encoding='utf-8'))


class RendererTests(unittest.TestCase):
    def test_all_examples_deterministic_and_not_mutated(self):
        for name in ('character-swap-aligned', 'motion-ref2va', 't2va', 'i2va', 'fl2va', 'l2va'):
            with self.subTest(name=name):
                data = example(name)
                before = copy.deepcopy(data)
                self.assertEqual(render_prompt(name, data), render_prompt(name, data))
                self.assertEqual(data, before)

    def test_section_order(self):
        for name, expected in [('motion-ref2va', REF_SECTIONS), ('t2va', BASE_SECTIONS), ('i2va', BASE_SECTIONS), ('fl2va', BASE_SECTIONS), ('l2va', BASE_SECTIONS)]:
            prompt = render_prompt(name, example(name))
            sections = [line.split(':', 1)[0] for line in prompt.splitlines() if any(line.startswith(s + ':') for s in BASE_SECTIONS + REF_SECTIONS)]
            self.assertEqual(sections, list(expected))

    def test_aligned_ownership(self):
        result = render_prompt('character-swap-aligned', example('character-swap-aligned'))
        self.assertTrue(result.startswith('body_swap:'))
        self.assertIn('<Picture 1>', result)
        self.assertNotIn('<Video', result)
        self.assertIn('lighting and timing', result)
        self.assertIn('6.25 seconds', result)
        self.assertIn('intrinsic skin complexion', result)
        self.assertIn(example('character-swap-aligned')['identity'], result)
        self.assertNotIn('sunglasses', result)
        self.assertNotIn('couch', result)

    def test_motion_is_not_aligned(self):
        result = render_prompt('motion-ref2va', example('motion-ref2va'))
        self.assertIn('<Video 1>', result)
        self.assertIn('[reference generation]', result)
        self.assertNotIn('body_swap:', result)
        self.assertNotIn('<Audio', result)

    def test_multiple_images_category_numbering(self):
        data = example('motion-ref2va')
        data['assets'].append({'kind':'image','role':'scene','token':'<Picture 2>','description':'A plain empty rehearsal room'})
        data['assets'].append({'kind':'image','role':'costume','token':'<Picture 3>','description':'A plain grey rehearsal jacket'})
        result = render_prompt('motion-ref2va', data)
        for token in ('<Picture 1>', '<Picture 2>', '<Picture 3>', '<Subject 1>', '<Subject 2>', '<Subject 3>', '<Video 1>'):
            self.assertIn(token, result)
        self.assertNotIn('<Picture 4>', result)
        self.assertNotIn('<Video 2>', result)

    def test_identity_need_not_be_picture_one_in_motion(self):
        data=example('motion-ref2va')
        data['assets'][0]['token']='<Picture 2>'
        data['assets'].insert(0, {'kind':'image','role':'scene','token':'<Picture 1>','description':'A room with a plain wall'})
        result=render_prompt('motion-ref2va',data)
        self.assertIn('using <Picture 2> for identity',result)

    def test_keyframe_instructions_dynamic_final_shot(self):
        for name in ('fl2va', 'l2va'):
            data=example(name)
            data['duration_seconds']=8.75
            shot=copy.deepcopy(data['shots'][0]); shot['start_seconds']=3.125
            data['shots'].append(shot)
            result=render_prompt(name,data)
            self.assertIn('8.75-second mark',result)
            self.assertIn('Shot 2',result.splitlines()[0])
            self.assertIn('[Shot 2] At 00:03.125, the camera cuts to',result)
            self.assertNotIn('[Shot 1] At',result)

    def test_dialogue_language_and_verbatim(self):
        data=example()
        data['dialogue']=[{'shot':1,'start_seconds':1,'end_seconds':2,'speaker':'The adult performer with a low measured voice','language':'Spanish','text':'¡Mira, aquí estoy!','delivery':'speaking at a measured pace'}]
        result=render_prompt('t2va',data)
        self.assertIn('<d>[Spanish] ¡Mira, aquí estoy!</d>',result)
        self.assertIn('(S1)',result)
        data['dialogue'][0]['voiceover']=True
        self.assertIn('says in an off-screen voiceover',render_prompt('t2va',data))
        self.assertIn('lips remain completely closed',render_prompt('t2va',data))

    def test_speaker_ids_stable_in_actual_order(self):
        data=example()
        data['dialogue']=[{'shot':1,'start_seconds':i,'end_seconds':i+0.5,'speaker':who,'language':'Spanish','text':'Sí.','delivery':'quietly'} for i,who in enumerate(('The performer','An off-screen narrator','The performer'))]
        result=render_prompt('t2va',data)
        self.assertEqual(result.count('The performer (S1)'),2)
        self.assertIn('An off-screen narrator (S2)',result)

    def test_invalid_durations_and_cut_times(self):
        for value in (0,-1,'NaN','Infinity',True,'6.2511',3601):
            data=example(); data['duration_seconds']=value
            with self.subTest(value=value),self.assertRaises(PromptValidationError): render_prompt('t2va',data)
        for value in (0,6.25,7,-1,'NaN',True):
            data=example(); shot=copy.deepcopy(data['shots'][0]);shot['start_seconds']=value;data['shots'].append(shot)
            with self.subTest(cut=value),self.assertRaises(PromptValidationError): render_prompt('t2va',data)

    def test_missing_essentials(self):
        for field in ('identity','duration_seconds','style','shots','audio','assets'):
            data=example();del data[field]
            with self.assertRaises(PromptValidationError):render_prompt('t2va',data)
        for field in ('scene','performance','camera','lighting','sound'):
            data=example();data['shots'][0][field]=''
            with self.assertRaises(PromptValidationError):render_prompt('t2va',data)

    def test_token_mismatch_and_unresolved_labels(self):
        for token in ('<Picture 2>','<Picture1>','Picture 1','<Video 1>'):
            data=example('i2va');data['assets'][0]['token']=token
            with self.assertRaises(PromptValidationError):render_prompt('i2va',data)
        for fragment in ('Use <Picture 9>', 'Use <Video 1>', '{{scene}}', '[Shot N]', 'TODO', '<Picture 01>', '<Subject 1>'):
            data=example();data['shots'][0]['scene']=fragment
            with self.assertRaises(PromptValidationError):render_prompt('t2va',data)

    def test_no_extra_references_and_no_guide_token(self):
        data=example('character-swap-aligned');data['assets'][1]['token']='<Video 1>'
        with self.assertRaises(PromptValidationError):render_prompt('character-swap-aligned',data)
        data=example('character-swap-aligned');data['assets'].append({'kind':'image','role':'scene','token':'<Picture 2>','description':'An extra image'})
        with self.assertRaises(PromptValidationError):render_prompt('character-swap-aligned',data)
        data=example('motion-ref2va');data['assets'][1]['kind']='aligned_guide'
        with self.assertRaises(PromptValidationError):render_prompt('motion-ref2va',data)

    def test_silence_must_be_explicit(self):
        data=example();data['audio']['soundscape']='N/A'
        with self.assertRaises(PromptValidationError):render_prompt('t2va',data)
        data['audio']['silent']=True;data['shots'][0]['sound']='N/A'
        self.assertIn('overall_soundscape: N/A',render_prompt('t2va',data))

    def test_dialogue_overflow_and_unknown_recipe_fields(self):
        data=example();data['dialogue']=[{'shot':1,'start_seconds':6,'end_seconds':7,'speaker':'The performer','language':'Spanish','text':'Sí.','delivery':'quietly'}]
        with self.assertRaises(PromptValidationError):render_prompt('t2va',data)
        data=example();data['lora_chain']=[]
        with self.assertRaises(PromptValidationError):render_prompt('t2va',data)

    def test_no_network_subprocess_or_environment_dependency(self):
        with patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden')),patch.object(subprocess,'run',side_effect=AssertionError('process forbidden')),patch.dict('os.environ',{},clear=True):
            self.assertIn('integrated_multimodal_description:',render_prompt('t2va',example()))

    def test_motion_speech_subject_binding(self):
        data=example('motion-ref2va')
        data['dialogue']=[{'shot':1,'start_seconds':1,'end_seconds':2,'speaker':'The adult performer with a low measured voice','language':'Spanish','text':'Aquí.','delivery':'quietly','subject':1}]
        self.assertIn('<Subject 1> (S1)',render_prompt('motion-ref2va',data))
        data['dialogue'][0]['subject']=2
        with self.assertRaises(PromptValidationError):render_prompt('motion-ref2va',data)

    def test_output_asset_references_exactly_equal_attached(self):
        import re
        for name in ('character-swap-aligned','motion-ref2va','t2va','i2va','fl2va','l2va'):
            data=example(name)
            result=render_prompt(name,data)
            expected={a['token'] for a in data['assets'] if 'token' in a}
            found=set(re.findall(r'<(?:Picture|Video|Audio) [0-9]+>',result))
            self.assertEqual(found,expected)
        data=example();data['shots'][0]['scene']='Use Picture 9'
        with self.assertRaises(PromptValidationError):render_prompt('t2va',data)

    def test_standalone_file_import(self):
        spec=importlib.util.spec_from_file_location('standalone_h3_renderer',ROOT/'prompting/renderer.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertEqual(render_prompt('t2va',example()),module.render_prompt('t2va',example()))

    def test_schema_and_catalog_valid_json(self):
        catalog=json.loads((ROOT/'prompting/catalog.json').read_text(encoding='utf-8'))
        self.assertFalse(catalog['requires_agent'])
        self.assertEqual(len(catalog['templates']),6)
        schema=json.loads((ROOT/'prompting/request.schema.json').read_text(encoding='utf-8'))
        self.assertFalse(schema['additionalProperties'])

    def test_cli_all_modes_and_error(self):
        import tempfile
        # All fixtures are synthetic prose; no human media, services or GPU.
        with tempfile.TemporaryDirectory(dir=ROOT/'prompting/tests') as temp:
            for name in ('character-swap-aligned','motion-ref2va','t2va','i2va','fl2va','l2va'):
                output=Path(temp)/f'{name}.txt'
                result=subprocess.run([sys.executable,str(ROOT/'scripts/build_prompt.py'),'--template',name,'--input',str(ROOT/f'prompting/examples/{name}.json'),'--output',str(output)],capture_output=True)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(output.read_text(encoding='utf-8'),render_prompt(name,example(name)))
            invalid=Path(temp)/'invalid.json';invalid.write_text('{}',encoding='utf-8')
            result=subprocess.run([sys.executable,str(ROOT/'scripts/build_prompt.py'),'--template','t2va','--input',str(invalid)],capture_output=True)
            self.assertEqual(result.returncode,2)
            self.assertIn(b'missing required fields',result.stderr)
        for flag in ('--help','--list'):
            result=subprocess.run([sys.executable,str(ROOT/'scripts/build_prompt.py'),flag],capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)


if __name__ == '__main__':
    unittest.main()
