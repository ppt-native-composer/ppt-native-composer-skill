#!/usr/bin/env python3
"""Planning-layer compiler. It is advisory until it emits runtime-ready pages for Phase 6-A."""
from __future__ import annotations
import argparse, hashlib, json, sys
from collections import Counter, defaultdict, deque
from copy import deepcopy
from pathlib import Path
from typing import Any
from jsonschema import Draft202012Validator

ROOT=Path(__file__).resolve().parent.parent
ROLES={"cover","section_opener","strategy","concept","evidence","execution","summary","closing","custom"}
ROUTES={"element_asset_hybrid","full_substrate_hybrid","visual_reference_mode","template_native_plus_skin","pure_native_safety"}
NODES={"context","problem","insight","proposition","proof","mechanism","concept","experience","execution","transition","summary","call_to_action"}

def load(path:Path)->dict[str,Any]:
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict): raise ValueError(f"JSON object required: {path}")
    return value
def dump(path:Path,value:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def digest(path:Path)->str: return hashlib.sha256(path.read_bytes()).hexdigest()
def validate(value:dict[str,Any],schema:str)->list[str]:
    return [f"{e.json_path}: {e.message}" for e in Draft202012Validator(load(ROOT/"schemas"/schema)).iter_errors(value)]
def graph_issues(graph:dict[str,Any])->list[str]:
    nodes={n["node_id"]:n for n in graph["nodes"]}; errors=[]; incoming=defaultdict(int); outgoing=defaultdict(int)
    for edge in graph["edges"]:
        if edge["from"] not in nodes or edge["to"] not in nodes: errors.append("edge references unknown node"); continue
        incoming[edge["to"]]+=1; outgoing[edge["from"]]+=1
    pending={n:set() for n in nodes}
    for edge in graph["edges"]:
        if edge["from"] in nodes and edge["to"] in nodes: pending[edge["to"]].add(edge["from"])
    done=set()
    while len(done)<len(nodes):
        ready=[n for n,d in pending.items() if not d and n not in done]
        if not ready: errors.append("narrative cycle detected"); break
        done.update(ready)
        for deps in pending.values(): deps.difference_update(ready)
    for n in nodes:
        if len(nodes)>1 and not incoming[n] and not outgoing[n]: errors.append(f"disconnected node: {n}")
    messages=[" ".join(n["message"].lower().split()) for n in nodes.values()]
    errors += ["repeated narrative message"] if any(v>1 for v in Counter(messages).values()) else []
    return errors

def build(input_data:dict[str,Any], base:Path)->dict[str,Any]:
    errors=validate(input_data,"planning_input.schema.json")
    if errors: raise ValueError("planning input invalid: "+"; ".join(errors))
    source_map={}
    for source in input_data["source_documents"]:
        p=Path(source["path"]); p=p if p.is_absolute() else base/p
        source_map[source["source_id"]]={"path":str(p),"sha256":digest(p) if p.exists() else None,"available":p.exists()}
    units=deepcopy(input_data["content_units"]); unit_map={u["content_id"]:u for u in units}
    trace=[]
    for u in units:
        source=source_map.get(u.get("source_id")); status=u["status"]
        trace.append({"content_id":u["content_id"],"exact_text":u["text"],"content_status":status,"source_id":u.get("source_id"),"source":source,"transformation_note":"input-preserved","approval_status":"not_requested" if status in {"inferred","proposed","unresolved","placeholder"} else "source_available"})
    type_by_role={"cover":"context","strategy":"problem","concept":"concept","evidence":"proof","execution":"execution","summary":"summary","closing":"call_to_action"}
    nodes=[]
    for i,u in enumerate(units,1):
        role=u.get("candidate_role") or "custom"; node_type=type_by_role.get(role,"transition")
        nodes.append({"node_id":u.get("candidate_node") or f"n{i:02d}","node_type":node_type,"message":u["text"],"content_ids":[u["content_id"]],"required_evidence":[u["content_id"]] if u["status"] in {"sourced","approved_copy"} else [],"confidence":"unresolved" if u["status"] in {"unresolved","placeholder"} else "high" if u["status"] in {"sourced","approved_copy"} else "medium","candidate_page_role":role,"human_approval_status":"pending"})
    edges=[{"from":nodes[i]["node_id"],"to":nodes[i+1]["node_id"]} for i in range(len(nodes)-1)]
    graph={"nodes":nodes,"edges":edges}; issues=graph_issues(graph)
    pages=[]
    for i,node in enumerate(nodes,1):
        u=unit_map[node["content_ids"][0]]; status="runtime_ready" if u.get("runtime_manifest") and u["status"] in {"sourced","approved_copy"} else "unresolved" if u["status"] in {"unresolved","placeholder"} else "needs_human_decision"
        if u.get("source_id") and not source_map.get(u["source_id"],{}).get("available"):
            status="unresolved"
        pages.append({"page_id":f"page_{i:02d}","section":"core","sequence":i,"page_role":node["candidate_page_role"] if node["candidate_page_role"] in ROLES else "custom","narrative_function":node["node_type"],"primary_message":node["message"],"supporting_messages":[],"content_ids":node["content_ids"],"source_references":[u.get("source_id")],"mandatory_copy":[u["text"]] if u.get("mandatory") else [],"optional_copy":[],"prohibited_copy":input_data.get("prohibited_content",[]),"proof_requirement":node["required_evidence"],"visual_job":"requires Design Intent and approved visual direction","intended_audience_effect":"pending human review","candidate_route":u.get("route"),"candidate_archetype":None,"design_intent_status":"approved" if status=="runtime_ready" else "pending","dependencies":[pages[-1]["page_id"]] if pages else [],"continuity_group":"planned_core","estimated_content_density":"low","status":status,"human_review_status":"locked" if u.get("locked") else "pending","runtime_manifest":u.get("runtime_manifest"),"locked":bool(u.get("locked"))})
    overrides=[]
    for directive in input_data.get("human_directives",[]):
        action=directive["action"]; target=next((p for p in pages if p["page_id"]==directive.get("page_id")),None)
        if action=="lock_page" and target: target["locked"]=True; target["human_review_status"]="human_locked"
        elif action=="reorder_page" and target and "sequence" in directive: target["sequence"]=directive["sequence"]
        elif action=="replace_role" and target and directive.get("page_role") in ROLES: target["page_role"]=directive["page_role"]
        elif action=="change_route" and target and directive.get("route") in ROUTES: target["candidate_route"]=directive["route"]
        elif action=="mark_unresolved" and target: target["status"]="unresolved"; target["runtime_manifest"]=None
        elif action=="remove_optional_page" and target and not directive.get("required",False): pages.remove(target)
        elif action=="add_mandatory_page": pages.append({"page_id":directive.get("new_page_id",f"manual_{len(pages)+1}"),"section":"manual","sequence":directive.get("sequence",len(pages)+1),"page_role":directive.get("page_role","custom"),"narrative_function":"transition","primary_message":directive.get("message","Human-required page"),"supporting_messages":[],"content_ids":[],"source_references":[],"mandatory_copy":[],"optional_copy":[],"prohibited_copy":[],"proof_requirement":[],"visual_job":"human-defined","intended_audience_effect":"human-defined","candidate_route":None,"candidate_archetype":None,"design_intent_status":"pending","dependencies":[],"continuity_group":"manual","estimated_content_density":"unknown","status":"needs_human_decision","human_review_status":"human_added","runtime_manifest":None,"locked":True})
        overrides.append({"directive":directive,"applied":True})
    pages.sort(key=lambda p:p["sequence"])
    used=Counter(cid for p in pages for cid in p["content_ids"])
    mandatory=[u["content_id"] for u in units if u.get("mandatory")]
    omissions=[cid for cid in mandatory if not used[cid]]
    unresolved=[p["page_id"] for p in pages if p["status"] in {"unresolved","needs_human_decision","design_intent_pending","blocked"}]
    strategy={"communication_problem":input_data.get("communication_objective"),"audience_state":input_data.get("audience",[]),"desired_audience_shift":input_data.get("desired_action"),"central_proposition":input_data.get("key_message"),"narrative_logic":"source-backed nodes progress in declared planning order; unresolved nodes remain non-executable","emotional_progression":"manual_required","evidence_strategy":"only sourced or approved_copy units may support runtime-ready pages","visual_progression":"Visual Bible and per-page Design Intent remain canonical","opening_strategy":"context/cover when source-backed","closing_strategy":"only if source-backed or human-approved","page_count_rationale":{"target":input_data["page_count"],"planned":len(pages)},"risk_and_uncertainty":["planner inferences are not source facts","unresolved pages cannot compile"],"human_decisions_required":unresolved}
    continuity={"section_rhythm":"manual_required","information_density_rhythm":"manual_required","visual_intensity_rhythm":"manual_required","text_visual_balance":"manual_required","page_role_repetition_limit":{"status":"warn" if max(Counter(p["page_role"] for p in pages).values())>3 else "pass"},"route_repetition_limit":"manual_required","title_hierarchy":"manual_required","page_number_strategy":"manifest_order","recurring_motif":"visual_bible referenced","repeated_asset_policy":"asset registry required at runtime","transition_page_policy":"manual_required","opening_closing_relationship":"manual_required","color_progression":"manual_required","typography_continuity":"manual_required","intentional_variation_points":"manual_required"}
    return {"deck_strategy":strategy,"narrative_graph":graph,"narrative_issues":issues,"page_plan":{"pages":pages,"execution_readiness":{"runtime_ready_pages":[p["page_id"] for p in pages if p["status"]=="runtime_ready"],"blocked_pages":unresolved,"mandatory_omissions":omissions,"duplicate_allocations":[cid for cid,n in used.items() if n>1]}},"source_traceability":{"sources":source_map,"content_units":trace},"continuity_contract":continuity,"human_override_record":overrides}

def compile_manifest(plan:dict[str,Any], input_data:dict[str,Any], output_root:str)->dict[str,Any]:
    pages=[]
    for p in plan["page_plan"]["pages"]:
        if p["status"]!="runtime_ready": continue
        pages.append({"page_id":p["page_id"],"order":len(pages)+1,"section":p["section"],"page_role":p["page_role"],"page_runtime_manifest":p["runtime_manifest"],"dependencies":[d for d in p["dependencies"] if any(x["page_id"]==d and x["status"]=="runtime_ready" for x in plan["page_plan"]["pages"])],"required":True,"continuity_group":p["continuity_group"],"route":p["candidate_route"]})
    return {"manifest_version":"1.0","deck_id":input_data["project_id"]+"_planned_acceptance","deck_title":input_data["project_title"],"source_provenance":{"planning_input":input_data["project_id"],"planning_note":"compiled only from runtime_ready source-backed pages"},"theme_strategy":{"visual_bible":input_data.get("visual_bible")},"page_numbering":{"policy":"preserve_page_runtime"},"failure_policy":"strict","pages":pages,"output":{"root":output_root},"runtime_options":{"resume":True,"jobs":2,"preview_dpi":96}}

def replan_delta(previous:dict[str,Any], current:dict[str,Any])->dict[str,Any]:
    previous_plan=previous.get("page_plan",previous); current_plan=current.get("page_plan",current)
    old={p["page_id"]:p for p in previous_plan["pages"]}; new={p["page_id"]:p for p in current_plan["pages"]}
    changed=[pid for pid,p in new.items() if pid not in old or any(p.get(k)!=old[pid].get(k) for k in ("primary_message","content_ids","sequence","status","candidate_route"))]
    removed=sorted(set(old)-set(new)); locked_unchanged=[pid for pid,p in new.items() if p.get("locked") and pid in old and pid not in changed]
    return {"affected_pages":changed,"removed_pages":removed,"unchanged_locked_pages":locked_unchanged,"pages_requiring_human_approval":[pid for pid in changed if new[pid]["status"]!="runtime_ready"],"pages_requiring_runtime_rebuild":[pid for pid in changed if new[pid]["status"]=="runtime_ready"],"deck_level_change":bool(changed or removed)}

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--input',required=True); ap.add_argument('--outdir',required=True); ap.add_argument('--compile-root'); ap.add_argument('--previous-plan'); args=ap.parse_args()
    inp=load(Path(args.input)); result=build(inp,Path(args.input).parent); out=Path(args.outdir)
    for key,value in result.items(): dump(out/f"{key}.json",value)
    if args.compile_root: dump(out/'deck_manifest.json',compile_manifest(result,inp,args.compile_root))
    if args.previous_plan: dump(out/'incremental_replanning.json',replan_delta(load(Path(args.previous_plan)),result))
    return 0
if __name__=='__main__': raise SystemExit(main())
