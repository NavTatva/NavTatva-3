from types import SimpleNamespace


def test_retired_scene_cannot_reappear_from_index_or_disk(monkeypatch):
    from app import scenes
    retired = SimpleNamespace(id='caspian_baku_seeps', selftest=False)
    active = SimpleNamespace(id='gom_mc20_chronic_slick', selftest=False)
    monkeypatch.setattr(scenes, 'load_index', lambda: [retired, active])
    monkeypatch.setattr(scenes, 'scan_disk', lambda: [retired])
    assert [s.id for s in scenes.all_scenes()] == [active.id]
    assert scenes.get(retired.id) is None
