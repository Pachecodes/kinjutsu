"""Offline UI/API parity checks; optional read-only live schema checks.
Run: python -m unittest discover -s tests -p test_workflow_ui.py -v
Set KINJUTSU_COMFY_URL=http://127.0.0.1:8218 for live socket validation.
"""
import json
import os
from pathlib import Path
import unittest
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


class WorkflowUITests(unittest.TestCase):
    def test_importable_gui_roundtrip_matches_api(self):
        path = ROOT / 'workflows/character-swap-turbo8-ui.json'
        self.assertTrue(path.is_file(), 'Complete GUI workflow must exist')
        ui = json.loads(path.read_text(encoding='utf-8'))
        api = json.loads((path.parent / 'character-swap-turbo8-api.json').read_text(encoding='utf-8'))
        self.assertEqual(ui['version'], 0.4)
        self.assertEqual(ui['extra']['workflow_name'], 'Pachecodes : Kinjutsu')
        nodes = {str(n['id']): n for n in ui['nodes']}
        self.assertEqual(set(nodes), set(api))
        links = {link[0]: link for link in ui['links']}
        self.assertEqual(len(links), len(ui['links']))
        reverse = {}
        used_links = set()
        for nid, node in nodes.items():
            self.assertEqual(len(node['properties']['kinjutsu_widget_names']),
                             len(node.get('widgets_values', [])))
            inputs = dict(zip(node['properties']['kinjutsu_widget_names'], node.get('widgets_values', [])))
            # Frontend-only upload/seed controls must never become API inputs.
            inputs = {k: v for k, v in inputs.items() if k in api[nid]['inputs']}
            for slot, inp in enumerate(node.get('inputs', [])):
                if inp.get('link') is None:
                    continue
                lid, origin, outslot, target, inslot, typ = links[inp['link']]
                self.assertEqual((str(target), inslot), (nid, slot))
                used_links.add(lid)
                source = nodes[str(origin)]['outputs'][outslot]
                self.assertIn(lid, source['links'])
                self.assertEqual(source['type'], inp['type'])
                self.assertEqual(typ, inp['type'])
                inputs[inp['name']] = [str(origin), outslot]
            reverse[nid] = {'class_type': node['type'], 'inputs': inputs}
        self.assertEqual(used_links, set(links), 'No dangling graph links')
        for nid, node in nodes.items():
            for slot, output in enumerate(node.get('outputs', [])):
                for lid in output.get('links') or []:
                    self.assertEqual((str(links[lid][1]), links[lid][2]), (nid, slot))
        self.assertEqual(reverse, api)
        self.assertNotIn('ModelPreviewOverrideKJ', {n['type'] for n in nodes.values()})

    def test_dynamic_upload_and_seed_controls_are_frontend_native(self):
        ui = json.loads((ROOT / 'workflows/character-swap-turbo8-ui.json').read_text(encoding='utf-8'))
        nodes = {str(n['id']): n for n in ui['nodes']}
        ref = nodes['5']
        refs = [i for i in ref['inputs'] if i['name'].startswith('ref_images.')]
        self.assertEqual([i['name'] for i in refs],
                         ['ref_images.ref_image_0', 'ref_images.ref_image_1'])
        self.assertIsNotNone(refs[0]['link'])
        self.assertIsNone(refs[1]['link'], 'Native autogrow keeps an empty next socket')
        self.assertEqual(nodes['7']['widgets_values'], [20261021, 'fixed'])
        self.assertEqual(nodes['15']['widgets_values'][0], 'reference-person.png')
        self.assertEqual(nodes['16']['widgets_values'][0], 'guide-aligned.mp4')
        for nid in ['15', '16']:
            self.assertIn('upload', nodes[nid]['properties']['kinjutsu_widget_names'])
        text = json.dumps(ui)
        for private_fragment in ['D:/', 'C:/', 'D:\\\\', 'C:\\\\', 'data:image', 'http://']:
            self.assertNotIn(private_fragment, text)

    @unittest.skipUnless(os.environ.get('KINJUTSU_COMFY_URL'), 'Set KINJUTSU_COMFY_URL for read-only live schema checks')
    def test_live_object_info_socket_indices_and_dynamic_schema(self):
        base = os.environ['KINJUTSU_COMFY_URL'].rstrip('/')
        with urllib.request.urlopen(base + '/object_info', timeout=30) as response:
            catalog = json.load(response)
        ui = json.loads((ROOT / 'workflows/character-swap-turbo8-ui.json').read_text(encoding='utf-8'))
        for node in ui['nodes']:
            definition = catalog[node['type']]
            self.assertEqual([o['type'] for o in node.get('outputs', [])], definition['output'])
            schema = {k: v for group in ['required', 'optional']
                      for k, v in definition['input'].get(group, {}).items()}
            for inp in node.get('inputs', []):
                if inp['name'] == 'upload':
                    continue  # Frontend upload button, not an inference input.
                if '.' in inp['name']:
                    group, child = inp['name'].split('.', 1)
                    kind, options = schema[group]
                    self.assertEqual(kind, 'COMFY_AUTOGROW_V3')
                    template = options['template']
                    self.assertTrue(child.startswith(template['prefix']))
                    index = int(child[len(template['prefix']):])
                    self.assertLess(index, template['max'])
                    expected = next(iter(template['input']['required'].values()))[0]
                else:
                    expected = schema[inp['name']][0]
                    if isinstance(expected, list):
                        expected = 'COMBO'
                self.assertEqual(inp['type'], expected, (node['id'], inp['name']))


if __name__ == '__main__':
    unittest.main()
