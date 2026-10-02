"""Shared-control execution boundary. No implicit API client or model loading."""
import copy
import hashlib
import io
import json
from pathlib import Path

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

class ReplayMissing(RuntimeError):
    pass

class StrictReplay:
    def __init__(self, records):
        self.records = list(records)

    def call(self, provider, payload):
        if not self.records:
            raise ReplayMissing('replay exhausted; live fallback is forbidden')
        record = self.records[0]
        if record['provider'] != provider or record['payload_sha256'] != canonical(payload):
            raise ReplayMissing('replay request identity mismatch')
        self.records.pop(0)
        if record.get('error'):
            raise ReplayMissing('recorded failure: '+record['error'])
        return record['content']

    def finish(self):
        if self.records:
            raise ReplayMissing('unconsumed replay records')

class ControlStore:
    def __init__(self, root, manifest):
        self.root = Path(root).resolve()
        self.manifest = manifest

    def verified(self, relative):
        path = (self.root / relative).resolve()
        if self.root not in path.parents or path.is_symlink():
            raise ValueError('control path escapes root')
        if sha(path) != self.manifest['files'][relative]:
            raise ValueError('control hash drift: '+relative)
        return path

    def load(self, key):
        row = json.loads(self.verified('rows/A/'+key+'.json').read_text())
        mask = self.verified(row['mask_path'])
        return row, mask

def original_image(image_bytes):
    from PIL import Image
    return Image.open(io.BytesIO(image_bytes)).convert('RGB')

def assert_mask_shape(mask, image):
    if mask is None or tuple(mask.shape) != (image.height, image.width):
        raise ValueError('mask does not match original RGB spatial shape')

def execute_case(key, arm, selection, controls, *, image_bytes=None, changed_predict=None):
    """Unchanged route shares the EXACT frozen A outcome, including failures.

    changed_predict(image, selection) owns explicitly configured downstream
    execution. It is never called for control rows and no retry is implicit.
    No GT, score, subset, or historical difficulty enters this callback.
    """
    base, mask_path = controls.load(key)
    same = selection['selected_route'] == base['selected_route']
    if arm == 'A' or same:
        return {'reasoning': copy.deepcopy(base['reasoning']),
                'mask_source': str(mask_path), 'mask_sha256': sha(mask_path),
                'source': 'shared_frozen_A', 'external_calls': 0,
                'selected_route': base['selected_route'], 'case': base['case']}
    if image_bytes is None or changed_predict is None:
        raise ReplayMissing('changed route requires original RGB and explicit prediction adapter')
    image = original_image(image_bytes)
    outcome = changed_predict(image, copy.deepcopy(selection))
    assert_mask_shape(outcome.get('mask'), image)
    if not isinstance(outcome.get('reasoning'), dict):
        raise ValueError('prediction missing reasoning record')
    return outcome

def save_mask(path, mask, image):
    import numpy as np
    assert_mask_shape(mask, image)
    path = Path(path)
    with path.open('xb') as handle:
        np.savez_compressed(handle, mask=np.asarray(mask, dtype=bool))
    return sha(path)

def save_segmentation_cache(path, masks, boxes, phrases, logits):
    """Save the full cache schema, not a single-mask file under a masks key."""
    import numpy as np
    path = Path(path)
    with path.open('xb') as handle:
        np.savez_compressed(handle, masks=np.asarray(masks), boxes=np.asarray(boxes),
                            logits=np.asarray(logits), phrases=np.asarray(phrases,dtype=str))
    return sha(path)

def load_segmentation_cache(path, expected_hash):
    import numpy as np
    if sha(path) != expected_hash:
        raise ValueError('segmentation cache hash drift')
    with np.load(path, allow_pickle=False) as data:
        if set(data.files) != {'masks','boxes','logits','phrases'}:
            raise ValueError('segmentation cache schema mismatch')
        masks, boxes, logits, phrases = (data[k].copy() for k in ('masks','boxes','logits','phrases'))
    if not (len(masks) == len(boxes) == len(logits) == len(phrases)):
        raise ValueError('segmentation cache count mismatch')
    return masks, boxes, phrases.tolist(), logits

def load_original_images(repo, cases):
    """Read RGB and row join fields only; never request GT/difficulty columns."""
    import pandas as pd
    wanted = {(int(c['scene']), int(c['object'])-1, c['annotation']) for c in cases}
    images = {}
    for name in ('train-00000-of-00002.parquet','train-00001-of-00002.parquet'):
        frame = pd.read_parquet(Path(repo)/'data'/name,
                                columns=['sceneId','queryObjId','annotation','image'])
        for _, row in frame.iterrows():
            key = (int(row['sceneId']),int(row['queryObjId']),row['annotation'])
            if key in wanted:
                value = row['image']['bytes']
                if key in images and images[key] != value:
                    raise ValueError('ambiguous original image identity')
                images[key] = value
    if set(images) != wanted:
        raise ValueError('missing original images')
    return images

def verify_derived(root, seal):
    """Validate all row/mask bytes against the derived seal, not old hashes."""
    root = Path(root).resolve()
    if seal.get('status') != 'complete':
        raise ValueError('derived outputs are not complete')
    for rel, expected in seal['files'].items():
        path = (root/rel).resolve()
        if root not in path.parents or sha(path) != expected:
            raise ValueError('derived output hash mismatch: '+rel)
    for arm in 'ADE':
        rows = set(p.stem for p in (root/'rows'/arm).glob('*.json'))
        masks = set(p.stem for p in (root/'predictions'/arm).glob('*.npz'))
        expected = set(seal['case_ids'])
        if rows != expected or masks != expected:
            raise ValueError('derived coverage mismatch: '+arm)
        for k in rows:
            if 'rows/'+arm+'/'+k+'.json' not in seal['files'] or 'predictions/'+arm+'/'+k+'.npz' not in seal['files']:
                raise ValueError('unsealed derived output')
    return True
