from logoskittens.persistence import Store


def test_session_survives_reopen(tmp_path):
    path = tmp_path / "logos.db"
    store = Store(path)
    store.create_session("sess-1", "nb_greeting_practice", {"medium": "virtual_screen"})
    store.add_turn(
        turn_id="turn-1",
        session_id="sess-1",
        user_text="Hei",
        assessment={"form_ok": True, "new_words": ["hei"], "error_tags": []},
        actor_states=[("state-1", "actor_tutor_01", "EMOTION_NEUTRAL", "Hei.")],
        errors=[("err-1", "register", "too informal")],
        words=[("word-1", "hei")],
    )
    assert store.journal_mode() == "wal"

    reopened = Store(path)
    snapshot = reopened.read_session("sess-1")
    assert snapshot is not None
    assert snapshot["turns"][0]["user_text"] == "Hei"
    assert snapshot["vocabulary"] == ["hei"]
    assert snapshot["errors"][0]["tag"] == "register"
    assert snapshot["actor_state"][0]["last_emotion"] == "EMOTION_NEUTRAL"
    assert reopened.get_session_row("sess-1").personality_id == "peter"
