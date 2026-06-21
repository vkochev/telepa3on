from telepa3on.poller import next_update_offset


def test_next_update_offset_advances_after_handled_updates():
    offset = None
    offset = next_update_offset(offset, {"update_id": 10})
    offset = next_update_offset(offset, {"update_id": 11})

    assert offset == 12
