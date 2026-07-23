from __future__ import annotations
import json, sys
from pathlib import Path
import pytest
S=Path(__file__).resolve().parents[1]/"scripts"; sys.path.insert(0,str(S))
import deck_planner  # noqa:E402
from deck_planner import build, compile_manifest, graph_issues, replan_delta, validate  # noqa:E402
from runtime_test_support import create_runtime_case  # noqa:E402

def payload(tmp_path:Path)->dict:
    source=tmp_path/"source.md"; source.write_text("Fact A\nFact B",encoding="utf-8")
    _, runtime=create_runtime_case(tmp_path/"runtime",case_id="planning")
    return {"planning_version":"1.0","project_id":"p","project_title":"P","presentation_type":"proposal","source_documents":[{"source_id":"s", "path":str(source)}],"page_count":{"min":2,"max":4},"language":"zh-CN","aspect_ratio":"16:9","content_units":[{"content_id":"a","text":"Fact A","status":"sourced","source_id":"s","candidate_role":"strategy","runtime_manifest":str(runtime),"route":"element_asset_hybrid","locked":True},{"content_id":"b","text":"Needs source","status":"unresolved","candidate_role":"evidence","mandatory":True}],"human_directives":[{"action":"lock_page","page_id":"page_01"}]}

def test_planning_traceability_compile_and_unresolved_block(tmp_path:Path)->None:
    data=payload(tmp_path); result=build(data,tmp_path)
    assert result["page_plan"]["pages"][0]["status"]=="runtime_ready"
    assert result["page_plan"]["pages"][0]["locked"] is True
    assert result["page_plan"]["pages"][1]["status"]=="unresolved"
    manifest=compile_manifest(result,data,str(tmp_path/"deck"))
    assert len(manifest["pages"])==1 and manifest["pages"][0]["route"]=="element_asset_hybrid"
    assert result["source_traceability"]["content_units"][0]["source"]["sha256"]

def test_graph_and_incremental_contracts(tmp_path:Path)->None:
    data=payload(tmp_path); first=build(data,tmp_path)
    assert "narrative cycle detected" in graph_issues({"nodes":[{"node_id":"a","message":"a"},{"node_id":"b","message":"b"}],"edges":[{"from":"a","to":"b"},{"from":"b","to":"a"}]})
    changed=json.loads(json.dumps(data)); changed["content_units"][0]["text"]="Fact A revised"
    second=build(changed,tmp_path); delta=replan_delta(first,second)
    assert delta["pages_requiring_runtime_rebuild"]==["page_01"]
    assert delta["deck_level_change"] is True
    assert validate(data,"planning_input.schema.json")==[]

def test_missing_source_and_invalid_contract_are_not_ready(tmp_path:Path)->None:
    data=payload(tmp_path); data["source_documents"][0]["path"]="missing.md"
    result=build(data,tmp_path)
    assert result["page_plan"]["pages"][0]["status"]=="unresolved"
    data.pop("language")
    assert validate(data,"planning_input.schema.json")

def test_override_variants_and_cli_outputs(tmp_path:Path, monkeypatch:pytest.MonkeyPatch)->None:
    data=payload(tmp_path)
    data["human_directives"]=[
        {"action":"replace_role","page_id":"page_01","page_role":"concept"},
        {"action":"change_route","page_id":"page_01","route":"full_substrate_hybrid"},
        {"action":"mark_unresolved","page_id":"page_02"},
        {"action":"add_mandatory_page","new_page_id":"manual","page_role":"summary"},
        {"action":"remove_optional_page","page_id":"manual"},
    ]
    result=build(data,tmp_path)
    first=result["page_plan"]["pages"][0]
    assert first["page_role"]=="concept" and first["candidate_route"]=="full_substrate_hybrid"
    assert result["page_plan"]["pages"][1]["status"]=="unresolved"
    source=tmp_path/"input.json"; source.write_text(json.dumps(data),encoding="utf-8")
    out=tmp_path/"out"
    monkeypatch.setattr(sys,"argv",["deck_planner.py","--input",str(source),"--outdir",str(out),"--compile-root",str(tmp_path/"deck")])
    assert deck_planner.main()==0
    assert (out/"deck_manifest.json").exists()
