"""Memory contract tests exercise real SQLite and strict viewer scoping."""
import json
import pytest

from backend.db.database import Database
from backend.streams.B_memory.v2 import MemoryServiceV2, LocalSemanticBackend


@pytest.fixture
def memory(tmp_path):
    db = Database(tmp_path / "v2.sqlite")
    with db.connect() as conn:
        conn.execute("INSERT INTO v2_couples(id,created_at,onboarding_status) VALUES('c','2026-01-01','completed')")
        for uid, role in (("a","A"),("b","B")):
            conn.execute("INSERT INTO v2_users(id,name,token_hash) VALUES(?,?,?)",(uid,uid,uid))
            conn.execute("INSERT INTO v2_memberships(couple_id,user_id,role,status) VALUES('c',?,?,'completed')",(uid,role))
    return MemoryServiceV2(db)


def fact(memory, user="a", value=None, privacy="PRIVATE", key="interest", category="interests", **kwargs):
    return memory.ingest("c","PERSON",user,user,category,key,value if value is not None else {"values":["culture"]},privacy,**kwargs)


@pytest.mark.parametrize("owner,other",[("a","b"),("b","a")])
def test_private_person_isolation_and_no_planning_leak(memory, owner, other):
    secret = "private-secret-" + owner
    item = fact(memory,owner,{"values":[secret]})
    assert secret in json.dumps(memory.list_facts("c","PERSON",owner,owner))
    for operation in (lambda: memory.list_facts("c","PERSON",owner,other),
                      lambda: memory.search("c","PERSON",owner,other,secret),
                      lambda: memory.profile("c","PERSON",owner,other),
                      lambda: memory.export_entity("c","PERSON",owner,other),
                      lambda: memory.provenance(item["id"],other)):
        with pytest.raises(PermissionError):
            operation()
    assert secret not in json.dumps(memory.planning_context("c"))
    assert secret not in json.dumps(memory.profile("c","COUPLE","c",other))
    assert memory.list_facts("c","PERSON",other,other) == []


def test_ingest_cannot_write_other_person_or_couple(memory):
    with pytest.raises(PermissionError):
        memory.ingest("c","PERSON","b","a","interests","x","secret")
    with pytest.raises(PermissionError):
        memory.ingest("unknown","PERSON","a","a","interests","x","secret")
    with pytest.raises(ValueError):
        memory.ingest("c","COUPLE","c","a","interests","x","secret","PRIVATE")


def test_recommendation_consent_affects_only_structured_planning(memory):
    fact(memory,"a",{"values":["food","culture"]},"COUPLE_RECOMMENDATION")
    fact(memory,"b",{"values":["food","sport"]},"COUPLE_RECOMMENDATION")
    fact(memory,"a",{"text":"private prose should never appear"},"COUPLE_RECOMMENDATION",key="experience",category="experience")
    context = memory.planning_context("c")
    assert context["person_a"]["interests"] == ["culture","food"]
    assert context["person_b"]["interests"] == ["food","sport"]
    public = memory.profile("c","COUPLE","c","b")
    assert public["interests"] == ["food"]
    assert "culture" not in json.dumps(public)
    assert "private prose" not in json.dumps(context)
    assert memory.list_facts("c","COUPLE","c","b") == []


def test_share_revoke_and_unauthorized_mutation(memory):
    item = fact(memory,value={"values":["cinema"]})
    for operation in (lambda: memory.update(item["id"],"b",value="changed"), lambda: memory.delete(item["id"],"b"), lambda: memory.share(item["id"],"b")):
        with pytest.raises(PermissionError):
            operation()
    memory.share(item["id"],"a","SHARED")
    assert memory.profile("c","COUPLE","c","b")["interests"] == ["cinema"]
    assert [f["id"] for f in memory.list_facts("c","COUPLE","c","b")] == [item["id"]]
    version = memory.profile("c","COUPLE","c","a")["version"]
    memory.revoke(item["id"],"a")
    assert memory.list_facts("c","COUPLE","c","b") == []
    assert memory.profile("c","COUPLE","c","b")["interests"] == []
    assert memory.profile("c","COUPLE","c","b")["version"] > version
    assert [e["kind"] for e in memory.provenance(item["id"],"a")] == ["created","consent_changed","consent_changed"]


def test_onboarding_idempotent_resume_correction_and_scope(memory):
    original = memory.ingest_onboarding("c","a",2,{"values":["culture"]},idempotency_key="answer-2")
    retry = memory.ingest_onboarding("c","a",2,{"values":["culture"]},idempotency_key="answer-2")
    assert retry["id"] == original["id"]
    assert retry["reinforcement_count"] == 1
    reopened = MemoryServiceV2(Database(memory.db.path))
    assert reopened.profile("c","PERSON","a","a")["interests"] == ["culture"]
    corrected = reopened.ingest_onboarding("c","a",2,{"values":["sport"]},idempotency_key="answer-2-edit")
    assert corrected["supersedes"] == original["id"]
    assert reopened.profile("c","PERSON","a","a")["interests"] == ["sport"]
    assert reopened.profile("c","PERSON","b","b")["interests"] == []
    assert [e["kind"] for e in reopened.provenance(original["id"],"a")] == ["created","superseded"]


def test_idempotency_namespaced_by_owner(memory):
    a = fact(memory,"a",idempotency_key="same")
    b = fact(memory,"b",idempotency_key="same")
    assert a["id"] != b["id"]
    assert b["owner_id"] == "b"


def test_duplicate_reinforces_conflict_coexists_correction_supersedes(memory):
    a = fact(memory,value={"max":40},category="budget",key="usual")
    duplicate = fact(memory,value={"max":40},category="budget",key="usual")
    assert a["id"] == duplicate["id"]
    assert duplicate["reinforcement_count"] == 2
    conflicting = fact(memory,value={"max":80},category="budget",key="usual")
    assert len(memory.list_facts("c","PERSON","a","a")) == 2
    profile = memory.profile("c","PERSON","a","a")
    assert profile["unresolved_conflicts"][0]["contradicted_by"] == conflicting["id"]
    assert profile["budget"]["max"] == 80
    corrected = memory.update(conflicting["id"],"a",value={"max":60})
    assert corrected["supersedes"] == conflicting["id"]
    assert memory.profile("c","PERSON","a","a")["budget"]["max"] == 60
    assert memory.repository.get(conflicting["id"])["valid_to"]


def test_retrieval_fusion_and_access_metadata(memory):
    irrelevant = fact(memory,value={"values":["sport"]},key="sport",salience=1.0)
    target = fact(memory,value={"values":["pottery workshops"]},key="creative",tags=["pottery"],entities=["pottery"])
    matches = memory.search("c","PERSON","a","a","pottery")
    assert matches[0]["id"] == target["id"]
    assert matches[0]["retrieval_score"] > matches[1]["retrieval_score"]
    assert matches[0]["retrieval_signals"]["lexical"] > 0
    assert matches[0]["retrieval_signals"]["entity_overlap"] > 0
    assert set(matches[0]["retrieval_signals"]) == {"lexical","semantic","entity_overlap","recency","confidence","salience","reinforcement","decay"}
    assert memory.repository.get(target["id"])["last_accessed_at"]
    assert memory.repository.get(irrelevant["id"])["last_accessed_at"]


def test_profile_budget_style_constraints_and_snapshot_reopen(memory):
    fact(memory,"a",{"min":40,"max":100,"unit":"couple"},"COUPLE_RECOMMENDATION",key="budget",category="budget")
    fact(memory,"b",{"max":60,"unit":"person"},"COUPLE_RECOMMENDATION",key="budget",category="budget")
    fact(memory,"a",{"novelty":.8,"energy":.3},"COUPLE_RECOMMENDATION",key="style",category="style")
    fact(memory,"b",{"novelty":.2},"COUPLE_RECOMMENDATION",key="style",category="style")
    fact(memory,"a",{"days":["Saturday"],"travel_minutes":30,"accessibility":["step_free"],"dietary":["vegan"]},"COUPLE_RECOMMENDATION",key="practical",category="practical")
    context = memory.planning_context("c")
    assert context["couple"]["budget"]["max"] == 50
    assert context["couple"]["novelty"] == .5
    assert context["person_a"]["constraints"]["travel_minutes"] == 30
    assert context["person_a"]["constraints"]["accessibility"] == ["step_free"]
    assert "vegan" not in json.dumps(context["couple"])
    reopened = MemoryServiceV2(Database(memory.db.path))
    assert reopened.profile("c","COUPLE","c","b") == memory.profile("c","COUPLE","c","a")


def test_incomplete_onboarding_never_derives_public_profile(memory):
    with memory.db.connect() as conn:
        conn.execute("UPDATE v2_memberships SET status='in_progress' WHERE user_id='b'")
    fact(memory,"a",{"values":["food"]},"SHARED")
    pending = memory.derive_couple("c")
    assert pending["awaiting_onboarding"] is True
    assert pending["interests"] == []
    assert pending["version"] == 0
    with memory.db.connect() as conn:
        conn.execute("UPDATE v2_memberships SET status='completed' WHERE user_id='b'")
    assert memory.derive_couple("c")["interests"] == ["food"]


def test_deletion_removes_retrieval_keeps_audit_and_entity_erasure(memory):
    item = fact(memory,privacy="SHARED")
    second = fact(memory,value={"values":["food"]},key="food",privacy="SHARED")
    memory.delete(item["id"],"a")
    assert all(f["id"] != item["id"] for f in memory.search("c","PERSON","a","a","culture"))
    with memory.db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM v2_events WHERE fact_id=?",(item["id"],)).fetchone()[0] == 2
    memory.delete_entity("c","PERSON","a","a")
    assert memory.list_facts("c","PERSON","a","a") == []
    assert memory.derive_couple("c")["interests"] == []
    with memory.db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM v2_events WHERE entity_id='a'").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM v2_embeddings WHERE fact_id=?",(second["id"],)).fetchone()[0] == 0


def test_session_and_date_memories_do_not_cross_owners(memory):
    for scope in ("SESSION","DATE"):
        item = memory.ingest("c",scope,"date-123","a","history","note",{"text":"my private evening"})
        assert memory.list_facts("c",scope,"date-123","b") == []
        assert memory.list_facts("c",scope,"date-123","a")[0]["id"] == item["id"]


def test_conversation_and_feedback_seed_correct_person(memory):
    extracted = memory.ingest_conversation("c","a","I love culture and cinema. I hate nightlife.")
    assert len(extracted) == 2
    assert memory.profile("c","PERSON","a","a")["interests"] == ["cinema","culture"]
    assert memory.profile("c","PERSON","a","a")["dislikes"] == ["nightlife"]
    memory.ingest_feedback("c","b","date1",4,repeat=["food"],avoid=["sport"],text="private review")
    assert memory.profile("c","PERSON","b","b")["interests"] == ["food"]
    assert "private review" not in json.dumps(memory.planning_context("c"))
    assert memory.profile("c","PERSON","a","a")["dislikes"] == ["nightlife"]


def test_local_semantic_is_stable_and_sql_remains_authoritative(memory):
    local = LocalSemanticBackend()
    assert local.embed("culture cinema") == LocalSemanticBackend().embed("cinema culture")
    item = fact(memory)
    with memory.db.connect() as conn:
        conn.execute("DELETE FROM v2_embeddings")
    assert memory.search("c","PERSON","a","a","culture")[0]["id"] == item["id"]


def test_malformed_manual_structures_cannot_poison_profile(memory):
    fact(memory,value={"values":None})
    fact(memory,value={"max":"not a number","unit":None},category="budget",key="budget")
    fact(memory,value={"dietary":None,"days":"secret","travel_minutes":-10},category="practical",key="practical")
    profile = memory.profile("c","PERSON","a","a")
    assert profile["interests"] == []
    assert "max" not in profile["budget"]
    assert profile["constraints"]["days"] == []
    assert "travel_minutes" not in profile["constraints"]


def test_flexible_budget_never_becomes_derived_hard_cap(memory):
    fact(memory,"a",{"max":20,"unit":"person","flexible":True},"COUPLE_RECOMMENDATION",key="budget",category="budget")
    # The other member has no budget yet: only a soft preference exists.
    assert memory.derive_couple("c")["budget"] == {"max":20,"unit":"person","flexible":True}
    fact(memory,"b",{"max":200,"unit":"couple","flexible":False},"COUPLE_RECOMMENDATION",key="budget",category="budget")
    assert memory.derive_couple("c")["budget"] == {"max":100,"unit":"person","flexible":False}


def test_nonshared_experience_prose_never_appears_in_couple_payload(memory):
    for owner in ('a','b'):
        fact(memory,owner,{"text":f"private experience {owner}"},"PRIVATE",key="onboarding:7",category="experience")
        fact(memory,owner,{"text":f"recommendation experience {owner}"},"COUPLE_RECOMMENDATION",key="other-experience",category="experience")
    public = json.dumps({"profile":memory.derive_couple("c"),"facts":memory.list_facts("c","COUPLE","c","b"),"context":memory.planning_context("c")})
    assert 'private experience' not in public
    assert 'recommendation experience' not in public


def test_onboarding_service_edit_back_to_previous_answer_keeps_profile_consistent(memory):
    from backend.domain.onboarding import OnboardingService, Answer
    onboarding = OnboardingService(memory.db,memory)
    viewer = {"id":"a","couple_id":"c"}
    for interest in ('culture','food','culture'):
        onboarding.answer('c','a',viewer,Answer(step=2,value={"values":[interest]}))
    assert onboarding.member('c','a',viewer)['answers'][0]['value'] == {"values":["culture"]}
    assert memory.profile('c','PERSON','a','a')['interests'] == ['culture']
