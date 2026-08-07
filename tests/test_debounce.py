import asyncio

from bot.album import AlbumBuffer


async def test_album_fires_once_with_all_items():
    fired: list[tuple[str, list]] = []

    async def callback(group_id, items):
        fired.append((group_id, items))

    buf = AlbumBuffer(callback, delay=0.05)
    buf.add("g1", "foto1")
    await asyncio.sleep(0.01)
    buf.add("g1", "foto2")
    await asyncio.sleep(0.01)
    buf.add("g1", "foto3")
    await asyncio.sleep(0.15)

    assert fired == [("g1", ["foto1", "foto2", "foto3"])]


async def test_timer_resets_on_new_photo():
    fired = []

    async def callback(group_id, items):
        fired.append(items)

    buf = AlbumBuffer(callback, delay=0.08)
    buf.add("g1", "a")
    await asyncio.sleep(0.05)  # < delay: Timer läuft noch
    buf.add("g1", "b")
    await asyncio.sleep(0.05)  # erster Timer wäre jetzt abgelaufen — wurde aber resettet
    assert fired == []
    await asyncio.sleep(0.06)
    assert fired == [["a", "b"]]


async def test_groups_are_independent():
    fired = {}

    async def callback(group_id, items):
        fired[group_id] = items

    buf = AlbumBuffer(callback, delay=0.03)
    buf.add("g1", "a")
    buf.add("g2", "x")
    buf.add("g1", "b")
    await asyncio.sleep(0.1)

    assert fired == {"g1": ["a", "b"], "g2": ["x"]}
