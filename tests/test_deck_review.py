from __future__ import annotations
import sys
from pathlib import Path
S=Path(__file__).resolve().parents[1]/"scripts";sys.path.insert(0,str(S))
from deck_review import apply,make_package,rhythm  # noqa:E402

def plan(): return {"pages":[{"page_id":"p1","sequence":1,"section":"x","page_role":"strategy","narrative_function":"problem","primary_message":"a","content_ids":["a"],"candidate_route":"element_asset_hybrid","candidate_archetype":None,"design_intent_status":"approved","estimated_content_density":"low","continuity_group":"x","status":"runtime_ready","human_review_status":"pending","runtime_manifest":"x","locked":True},{"page_id":"p2","sequence":2,"section":"x","page_role":"strategy","narrative_function":"proof","primary_message":"b","content_ids":["b"],"candidate_route":"element_asset_hybrid","candidate_archetype":None,"design_intent_status":"pending","estimated_content_density":"high","continuity_group":"x","status":"unresolved","human_review_status":"pending","runtime_manifest":None,"locked":False},{"page_id":"p3","sequence":3,"section":"x","page_role":"strategy","narrative_function":"proof","primary_message":"c","content_ids":["c"],"candidate_route":"element_asset_hybrid","candidate_archetype":None,"design_intent_status":"pending","estimated_content_density":"high","continuity_group":"x","status":"unresolved","human_review_status":"pending","runtime_manifest":None,"locked":False}]}
def package(): return make_package(plan(),{}, {"content_units":[{"content_id":"a","content_status":"sourced"},{"content_id":"b","content_status":"unresolved"},{"content_id":"c","content_status":"unresolved"}]},{},None,"r1")
def test_package_rhythm_and_decisions():
 p=package(); assert p["visual_rhythm"]["warnings"]
 stale=apply(p,plan(),{"base_review_id":"old","reviewer":"synthetic","reviewer_type":"synthetic_test","decisions":[]});assert stale["status"]=="stale"
 conflict=apply(p,plan(),{"base_review_id":p["review_id"],"reviewer":"synthetic","reviewer_type":"synthetic_test","decisions":[{"scope":"page","action":"change_route","target_ids":["p1"],"value":"pure_native_safety"}]});assert conflict["status"]=="conflict"
 ok=apply(p,plan(),{"base_review_id":p["review_id"],"reviewer":"synthetic","reviewer_type":"synthetic_test","decisions":[{"scope":"page","action":"change_route","target_ids":["p1"],"value":"pure_native_safety","override_lock":True},{"scope":"page","action":"mark_source_unresolved","target_ids":["p2"]}]});assert ok["status"]=="applied" and "p1" in ok["runtime_rebuild_scope"]
def test_dry_run_does_not_return_revision():
 p=package(); r=apply(p,plan(),{"base_review_id":p["review_id"],"reviewer":"synthetic","reviewer_type":"synthetic_test","decisions":[{"scope":"page","action":"reorder_page","target_ids":["p2"],"value":1}]},True);assert r["revised_plan"] is None

def test_more_decision_actions():
 p=package(); d={"base_review_id":p["review_id"],"reviewer":"synthetic","reviewer_type":"synthetic_test","decisions":[{"scope":"page","action":"unlock_page","target_ids":["p1"]},{"scope":"page","action":"exclude_from_runtime","target_ids":["p2"]},{"scope":"page","action":"approve_page","target_ids":["p1"]},{"scope":"page","action":"request_new_design_intent","target_ids":["p3"]}]}; r=apply(p,plan(),d);assert r["status"]=="applied"

def test_approved_source_page_without_runtime_stays_source_ready():
 p=package(); r=apply(p,plan(),{"base_review_id":p["review_id"],"reviewer":"human_reviewer","reviewer_type":"human","decisions":[{"scope":"page","action":"approve_page","target_ids":["p2"]}]}); assert r["revised_plan"]["pages"][1]["status"]=="source_ready"
