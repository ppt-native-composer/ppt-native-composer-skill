#!/usr/bin/env python3
"""Immutable human review packages and safe planning-revision application."""
from __future__ import annotations
import argparse,json,hashlib,uuid
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
from jsonschema import Draft202012Validator
from deck_planner import ROOT,compile_manifest,load,dump,validate

def now(): return datetime.now(timezone.utc).isoformat()
def sha(v): return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:12]
def rhythm(pages:list[dict])->dict[str,Any]:
    warnings=[]; routes=[p.get("candidate_route") for p in pages]; roles=[p.get("page_role") for p in pages]
    for i in range(2,len(pages)):
        if roles[i]==roles[i-1]==roles[i-2]: warnings.append({"rule":"role_repetition","pages":[pages[i-2]["page_id"],pages[i-1]["page_id"],pages[i]["page_id"]],"status":"warn"})
        if routes[i] and routes[i]==routes[i-1]==routes[i-2]: warnings.append({"rule":"route_repetition","pages":[pages[i-2]["page_id"],pages[i-1]["page_id"],pages[i]["page_id"]],"status":"warn"})
    high=[p["page_id"] for p in pages if p.get("visual_intensity","medium")=="high"]
    return {"status":"manual_required","pages":[{"page_id":p["page_id"],"text_density":p.get("estimated_content_density","unknown"),"visual_density":p.get("visual_intensity","manual_required"),"information_load":p.get("estimated_content_density","unknown"),"emotional_intensity":"manual_required","visual_intensity":p.get("visual_intensity","manual_required"),"whitespace_intent":"manual_required","dominant_composition_type":p.get("candidate_archetype") or "manual_required","dominant_color_family":"visual_bible/manual_required","title_scale_class":p.get("title_scale","manual_required"),"visual_asset_prominence":p.get("asset_prominence","manual_required"),"transition_function":p.get("narrative_function"),"similarity_previous":"manual_required","similarity_next":"manual_required"} for p in pages],"warnings":warnings,"high_intensity_pages":high}
def make_package(plan:dict,strategy:dict,trace:dict,continuity:dict,preview:str|None,revision:str)->dict:
    pages=plan["pages"]; rid="review-" + sha({"revision":revision,"pages":pages})
    return {"review_id":rid,"created_at":now(),"planning_revision":revision,"strategy_summary":strategy,"narrative_arc":"see Phase 6-B narrative graph","pages":[{"page_id":p["page_id"],"sequence":p["sequence"],"section":p["section"],"page_role":p["page_role"],"narrative_function":p["narrative_function"],"primary_message":p["primary_message"],"source_status":[x["content_status"] for x in trace["content_units"] if x["content_id"] in p["content_ids"]],"route":p.get("candidate_route"),"archetype":p.get("candidate_archetype"),"design_intent_status":p.get("design_intent_status"),"content_density":p.get("estimated_content_density"),"visual_intensity":p.get("visual_intensity","manual_required"),"continuity_group":p.get("continuity_group"),"runtime_readiness":p["status"],"unresolved_decisions":[] if p["status"]=="runtime_ready" else [p["status"]],"human_decision_status":p.get("human_review_status"),"preview":preview if p["status"]=="runtime_ready" else None} for p in pages],"visual_rhythm":rhythm(pages),"continuity_review":continuity,"contact_sheet":preview,"scope":"human review only; no L3/client-grade claim"}
def apply(package:dict,plan:dict,decision:dict,dry:bool=False)->dict:
    if decision["base_review_id"]!=package["review_id"]: return {"status":"stale","reason":"base review package differs","applied":[],"affected_pages":[]}
    if decision["reviewer_type"]!="human" and decision["reviewer_type"]!="synthetic_test": return {"status":"rejected","reason":"reviewer type missing","applied":[],"affected_pages":[]}
    pages=deepcopy(plan["pages"]); by={p["page_id"]:p for p in pages}; applied=[]; conflicts=[]; touched=set(); seen=set()
    field={"reorder_page":"sequence","replace_role":"page_role","change_route":"candidate_route","change_archetype":"candidate_archetype","change_visual_intensity":"visual_intensity","change_text_density":"estimated_content_density","change_asset_prominence":"asset_prominence","change_title_scale":"title_scale","revise_primary_message":"primary_message"}
    for item in decision["decisions"]:
        targets=item.get("target_ids",list(by) if item["scope"] in {"deck","batch","section"} else [])
        for pid in targets:
            p=by.get(pid)
            if not p: conflicts.append({"target":pid,"status":"needs_manual_resolution","reason":"page missing"}); continue
            key=(pid,item["action"])
            if key in seen: conflicts.append({"target":pid,"status":"conflict","reason":"same field modified twice"}); continue
            seen.add(key)
            if p.get("locked") and item["action"] not in {"unlock_page","lock_page"} and not item.get("override_lock"): conflicts.append({"target":pid,"status":"conflict","reason":"page locked"}); continue
            before=deepcopy(p)
            if item["action"]=="lock_page": p["locked"]=True; p["human_review_status"]="human_locked"
            elif item["action"]=="unlock_page": p["locked"]=False; p["human_review_status"]="pending"
            elif item["action"]=="exclude_from_runtime": p["status"]="blocked"; p["runtime_manifest"]=None
            elif item["action"]=="mark_source_unresolved": p["status"]="unresolved"; p["runtime_manifest"]=None
            elif item["action"] in {"approve_page","approve_for_runtime"}:
                p["human_review_status"]="human_approved"
                p["status"]="runtime_ready" if p.get("runtime_manifest") else "source_ready"
            elif item["action"] in field: p[field[item["action"]]]=item.get("value"); p["review_rebuild_required"]=p.get("status")=="runtime_ready"
            elif item["action"] in {"request_new_design_intent","hold_for_client_input","reject_page"}: p["status"]="needs_human_decision"; p["human_review_status"]=item["action"]
            else: continue
            applied.append({"target":pid,"action":item["action"],"previous":before,"new":deepcopy(p),"reviewer":decision["reviewer"]}); touched.add(pid)
    status="conflict" if conflicts and not applied else "partially_applied" if conflicts else "applied"
    return {"status":status,"dry_run":dry,"applied":applied,"conflicts":conflicts,"affected_pages":sorted(touched),"revised_plan":{"pages":sorted(pages,key=lambda x:x["sequence"])} if not dry else None,"runtime_rebuild_scope":[pid for pid in touched if by[pid].get("status")=="runtime_ready"]}
def main():  # pragma: no cover - CLI composition is covered by integration evidence.
    a=argparse.ArgumentParser();a.add_argument('--plan',required=True);a.add_argument('--strategy',required=True);a.add_argument('--trace',required=True);a.add_argument('--continuity',required=True);a.add_argument('--outdir',required=True);a.add_argument('--preview');a.add_argument('--revision',default='r1');a.add_argument('--decision');a.add_argument('--dry-run',action='store_true');a.add_argument('--planning-input');a.add_argument('--compile-root');x=a.parse_args();out=Path(x.outdir)
    pkg=make_package(load(Path(x.plan)),load(Path(x.strategy)),load(Path(x.trace)),load(Path(x.continuity)),x.preview,x.revision); errs=validate(pkg,'review_package.schema.json');
    if errs: raise SystemExit('; '.join(errs))
    dump(out/'review_package.json',pkg); (out/'review_report.md').write_text('# Deck Review\n\n'+ '\n'.join(f"- {p['page_id']}: `{p['runtime_readiness']}` / `{p['page_role']}`" for p in pkg['pages'])+'\n',encoding='utf-8')
    if x.decision:
        d=load(Path(x.decision)); errs=validate(d,'human_review_decision.schema.json');
        if errs: raise SystemExit('; '.join(errs))
        result=apply(pkg,load(Path(x.plan)),d,x.dry_run); dump(out/'decision_application.json',result)
        if result.get('revised_plan') and not x.dry_run:
            dump(out/'planning_revision.json',result['revised_plan']); dump(out/'revision_lineage.json',{"parent_revision":x.revision,"decision_id":d['decision_id'],"review_id":pkg['review_id'],"created_at":now()})
            if x.planning_input and x.compile_root:
                inp=load(Path(x.planning_input)); dump(out/'deck_manifest.json',compile_manifest({"page_plan":result['revised_plan']},inp,x.compile_root))
if __name__=='__main__': main()
