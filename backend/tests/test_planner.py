"""Behavioral and persistence regressions for the application planner (providers mocked)."""
from copy import deepcopy
from datetime import timedelta
import pytest
from sqlmodel import Session, select
from app.config import get_settings
from app.db import engine
from app.models import (PlannerSession, ListeningBatch, PlannerApproval, Message, Trip, OptionGeneration,
                        VenueRecommendation, PrivatePrefs)
from app.logic import planner_service as svc
from app.logic.listening import new_template, safe_updates, missing_fields, effective_attendance, semantic_signature
from app.privacy.crypto import encrypt_json


def headers(uid='alice'):
    return {'X-Test-User':uid}


def create(client,world,topic='Dining'):
    response=client.post('/chats/test-chat/planners',headers=headers(),json={
        'title':'Weekend together','topic':topic,'location':'Austin','timezone':'America/Chicago'})
    assert response.status_code==201,response.text
    return response.json()


def edit(client,p,field,value,user='alice'):
    response=client.patch(f"/trips/{p['tripId']}/planner",headers=headers(user),json={
        'revision':p['revision'],'field':field,'value':value})
    assert response.status_code==200,response.text
    return response.json()


def ready(client,p):
    p=edit(client,p,'attendance','going')
    return edit(client,p,'when.flexibility',None)


def vote(client,p,user='alice',approve=True):
    return client.post(f"/trips/{p['tripId']}/planner/approve",headers=headers(user),json={
        'revision':p['approvalRevision'],'approve':approve})


@pytest.fixture(autouse=True)
def mocked_providers(monkeypatch):
    # No automated test can make a paid request, including background tasks.
    from app.integrations import muse_group
    from app.integrations.serpapi_client import SerpApiClient
    monkeypatch.setattr(muse_group,'listen_planner',lambda ctx:{'updates':[]})
    monkeypatch.setattr(muse_group,'predict_planner',lambda ctx:{'suggestions':{}})
    monkeypatch.setattr(SerpApiClient,'search',lambda self,params:{'local_results':[
        {'title':'Local venue','place_id':'place-one','rating':4.8,'address':'Austin','price':'$$'}]})


def test_dynamic_attendance_flexibility_and_optional_fields():
    t=new_template('Dinner','Dining',members=('a','b','c'))
    assert all(e['status']=='conditional' for e in effective_attendance(t).values())
    t['spoke']=['a']
    assert effective_attendance(t)['a']=={'status':'going','condition':None,'inferred':True}
    t,_=safe_updates(t,[{'field':'when.flexibility','value':None,'user_id':'a','source_message_id':'m'},
                        {'field':'where.search_area','value':'Austin','source_message_id':'m'}],[{'id':'m','user_id':'a'}])
    assert not missing_fields(t) and not t['cluster']
    t['spoke'].append('b')
    assert 'b' in missing_fields(t)[0]
    t['when']['agreed']={'label':'Friday','date':None}
    assert not missing_fields(t)


def test_attribution_corrections_and_empty_availability():
    t=new_template('Trip','Travel',members=('alice','bob'))
    messages=[{'id':'m','user_id':'alice'}]
    t,decisions=safe_updates(t,[{'field':'when.flexibility','value':[],'user_id':'alice','source_message_id':'m'},
        {'field':'preferences','value':['beach'],'user_id':'bob','source_message_id':'m'},
        {'field':'trip_type','value':'flight','source_message_id':'context'}],messages)
    assert not any(d['accepted'] for d in decisions)
    t,decisions=safe_updates(t,[{'field':'attendance','value':'not_going','user_id':'alice','source_message_id':'m'}],messages)
    assert t['attendance']['alice']['status']=='not_going'
    t,_=safe_updates(t,[{'field':'attendance','value':'going','user_id':'alice','source_message_id':'m'}],messages)
    assert t['attendance']['alice']['status']=='going'


def test_manual_edits_win_against_old_source_and_budget_is_not_public():
    t=new_template('Dinner','Dining',members=('a',))
    t['cluster']['meal_type']='dinner'
    result,_=safe_updates(t,[{'field':'meal_type','value':'lunch','source_message_id':'m'},
        {'field':'budget','value':500,'source_message_id':'m','user_id':'a'},
        {'field':'preferences','value':['budget 500'],'source_message_id':'m','user_id':'a'}],
        [{'id':'m','user_id':'a'}],field_versions={'meal_type:group':3},source_revisions={'m':1})
    assert result==t and 'budget' not in result


def test_authorization_and_contract(client,world):
    assert client.post('/chats/test-chat/planners',headers=headers('dan'),json={'title':'x','topic':'Dining'}).status_code==404
    p=create(client,world)
    assert client.get(f"/trips/{p['tripId']}/planner",headers=headers('dan')).status_code==404
    assert client.get('/chats/test-chat/planner',headers=headers()).json()['tripId']==p['tripId']
    assert client.post('/chats/test-chat/planners',headers=headers(),json={'title':'x','topic':'Dining'}).status_code==409
    assert client.post('/chats/test-chat/planners',headers=headers(),json={'title':'x','topic':'Other'}).status_code==422
    for key in ('internal','notes','tokens','decisions','prompts','budget'):
        assert key not in p
    assert not p['poll']['ready'] and p['poll']['eligible']==['alice','bob','cara']


def test_no_vote_is_not_decline_and_meaningful_edits_reset_votes(client,world):
    p=ready(client,create(client,world))
    response=vote(client,p,approve=False)
    assert response.status_code==200,response.text
    p=response.json()
    assert p['poll']['changes']==['alice'] and p['attendance']['alice']['status']=='going'
    revision=p['approvalRevision']
    p=edit(client,p,'cuisine',['Italian'])
    assert p['approvalRevision']>revision and p['poll']['changes']==[]
    response=client.patch(f"/trips/{p['tripId']}/planner",headers=headers(),json={'revision':0,'field':'meal_type','value':'dinner'})
    assert response.status_code==409


@pytest.mark.parametrize('threshold,required',[(.4,2),(.5,2),(.6,2)])
def test_configurable_vote_threshold(client,world,threshold,required):
    p=ready(client,create(client,world))
    p=edit(client,p,'threshold',threshold)
    assert p['poll']['required']==required
    p=vote(client,p).json()
    assert p['status']=='collecting'
    p=vote(client,p,'bob').json()
    assert p['status']=='approved' and p['pricedMembers']==['alice']
    assert p['generation']['status']=='resolving'
    current=client.get(f"/trips/{p['tripId']}/planner",headers=headers()).json()
    assert len(current['recommendations']['venues'])==1
    assert current['recommendations']['venues'][0]['priceLevel']=='$$'
    assert 'groupTotal' not in current['recommendations']['venues'][0]


@pytest.mark.parametrize('topic',['Dining','Entertainment'])
def test_venue_flow_pick_and_reapprove(client,world,topic):
    p=ready(client,create(client,world,topic))
    p=vote(client,p).json()
    p=vote(client,p,'bob').json()
    p=client.get(f"/trips/{p['tripId']}/planner",headers=headers()).json()
    venue=p['recommendations']['venues'][0]
    r=client.post(f"/trips/{p['tripId']}/planner/pick",headers=headers(),json={'optionId':venue['id']})
    assert r.status_code==200,r.text
    assert r.json()['status']=='picked'
    assert client.post(f"/trips/{p['tripId']}/planner/retry",headers=headers()).status_code==409
    r=client.post(f"/trips/{p['tripId']}/planner/revise",headers=headers())
    assert r.status_code==200 and r.json()['poll']['approvals']==[]
    assert r.json()['recommendations']['venues']==[]
    assert client.post(f"/trips/{p['tripId']}/planner/pick",headers=headers(),json={'optionId':venue['id']}).status_code==409


def test_flexible_travel_approval_then_requires_exact_pricing(client,world):
    p=ready(client,create(client,world,'Travel'))
    p=vote(client,p).json()
    p=vote(client,p,'bob').json()
    current=client.get(f"/trips/{p['tripId']}/planner",headers=headers()).json()
    assert current['status']=='approved' and current['pricedMembers']==['alice']
    assert current['generation']['status']=='needs_input'
    assert set(current['generation']['missing'])=={'destinations','checkin','checkout','origin:alice'}
    assert client.post(f"/trips/{p['tripId']}/options/generate",headers=headers()).status_code==409


def test_durable_batches_context_and_recovery(client,world,monkeypatch):
    monkeypatch.setattr(get_settings(),'listener_debounce_seconds',0)
    p=create(client,world)
    for i in range(8):
        r=client.post('/chats/test-chat/messages',headers=headers(),json={'text':f'Dinner idea {i}'})
        assert r.status_code==201
    with Session(engine) as session:
        batch_id,lease=svc.claim_batch(session)
        batch=session.get(ListeningBatch,batch_id)
        assert len(batch.message_ids)==6
        planner=session.get(PlannerSession,p['tripId'])
        ctx,messages=svc.listener_context(session,planner,batch)
        assert len(ctx.listener['after'])==2 and len(ctx.listener['before'])<=4
        assert 'origins' not in str(ctx.listener['template'])
        batch.started_at=svc.now()-timedelta(seconds=100)
        session.add(batch);session.commit()
        claimed=svc.claim_batch(session)
        assert claimed and claimed[1]!=lease
        assert len(session.get(ListeningBatch,claimed[0]).message_ids)<=6


def test_failed_listener_retry_and_manual_during_inference(client,world,monkeypatch):
    monkeypatch.setattr(get_settings(),'listener_debounce_seconds',0)
    p=create(client,world)
    client.post('/chats/test-chat/messages',headers=headers(),json={'text':'Lunch please'})
    with Session(engine) as session:
        batch_id,lease=svc.claim_batch(session)
    svc.process_batch(engine,batch_id,lease) # missing key is an honest failure
    p=client.get(f"/trips/{p['tripId']}/planner",headers=headers()).json()
    assert p['listening']=='failed'
    assert client.post(f"/trips/{p['tripId']}/planner/retry",headers=headers()).status_code==202
    monkeypatch.setattr(get_settings(),'muse_api_key','test-only-key')
    def infer(ctx):
        current=client.get(f"/trips/{p['tripId']}/planner",headers=headers()).json()
        edit(client,current,'meal_type','dinner')
        return {'updates':[{'field':'meal_type','value':'lunch','source_message_id':ctx.listener['batch'][0]['id']}]}
    monkeypatch.setattr('app.integrations.muse_group.listen_planner',infer)
    with Session(engine) as session:
        batch_id,lease=svc.claim_batch(session)
    svc.process_batch(engine,batch_id,lease)
    p=client.get(f"/trips/{p['tripId']}/planner",headers=headers()).json()
    assert p['template']['cluster']['meal_type']=='dinner' and p['listening']=='idle'


def test_unknown_hard_requirements_and_private_boundary(client,world):
    p=ready(client,create(client,world))
    with Session(engine) as session:
        session.add(PrivatePrefs(trip_id=p['tripId'],user_id='bob',data_encrypted=encrypt_json({'budget_cap':8765,'no_gos':'SECRET-PRIVATE'})))
        session.commit()
    p=edit(client,p,'hard_constraints',['Wheelchair accessible'])
    p=vote(client,p).json();p=vote(client,p,'bob').json()
    p=client.get(f"/trips/{p['tripId']}/planner",headers=headers()).json()
    venue=p['recommendations']['venues'][0]
    assert not venue['pickEligible'] and 'SECRET-PRIVATE' not in str(p) and '8765' not in str(p)
    assert client.post(f"/trips/{p['tripId']}/planner/pick",headers=headers(),json={'optionId':venue['id']}).status_code==409


def test_precise_origin_owner_only_and_not_in_model(client,world):
    p=create(client,world)
    r=client.put(f"/trips/{p['tripId']}/me/origin",headers=headers(),json={'latitude':30.123456,'longitude':-97.654321,'label':'Austin'})
    assert r.status_code==200,r.text
    p=client.get(f"/trips/{p['tripId']}/planner",headers=headers()).json()
    assert p['template']['where']['origins']=={'alice':'Austin'}
    assert '30.123456' not in str(p) and '-97.654321' not in str(p)
    owner=client.get(f"/trips/{p['tripId']}/me/private",headers=headers()).json()
    assert owner['originLocation']['latitude']==30.123456
    assert client.get(f"/trips/{p['tripId']}/me/private",headers=headers('bob')).json()['originLocation'] is None
    assert client.patch(f"/trips/{p['tripId']}/planner",headers=headers(),json={'revision':p['revision'],'field':'where.origins','value':'30.123,-97.456'}).status_code==422


def test_provider_failure_preserves_published_venues_and_empty_search_is_distinct(client,world,monkeypatch):
    p=ready(client,create(client,world))
    p=vote(client,p).json();p=vote(client,p,'bob').json()
    with Session(engine) as session:
        before=session.exec(select(VenueRecommendation)).all()[0].id
    def fail(*args,**kwargs):
        raise RuntimeError('SECRET-PROVIDER-KEY')
    monkeypatch.setattr('app.integrations.serpapi_client.SerpApiClient.search',fail)
    assert client.post(f"/trips/{p['tripId']}/planner/retry",headers=headers()).status_code==202
    current=client.get(f"/trips/{p['tripId']}/planner",headers=headers()).json()
    assert current['generation']['status']=='failed' and 'SECRET' not in str(current)
    assert current['recommendations']['venues'][0]['id']==before
    monkeypatch.setattr('app.integrations.serpapi_client.SerpApiClient.search',lambda *a,**k:{'local_results':[]})
    client.post(f"/trips/{p['tripId']}/planner/retry",headers=headers())
    current=client.get(f"/trips/{p['tripId']}/planner",headers=headers()).json()
    assert current['generation']['status']=='ready' and current['recommendations']['venues']==[]


def test_stale_generation_and_stale_listener_never_publish(client,world,monkeypatch):
    p=ready(client,create(client,world))
    p=vote(client,p).json();p=vote(client,p,'bob').json()
    with Session(engine) as session:
        previous=session.exec(select(VenueRecommendation)).all()[0].id
    def revise_during_fetch(*args,**kwargs):
        client.post(f"/trips/{p['tripId']}/planner/revise",headers=headers())
        return {'local_results':[{'title':'Stale venue','place_id':'stale'}]}
    monkeypatch.setattr('app.integrations.serpapi_client.SerpApiClient.search',revise_during_fetch)
    client.post(f"/trips/{p['tripId']}/planner/retry",headers=headers())
    with Session(engine) as session:
        assert session.exec(select(VenueRecommendation)).all()[0].id==previous
    monkeypatch.setattr(get_settings(),'listener_debounce_seconds',0)
    monkeypatch.setattr(get_settings(),'muse_api_key','test-only')
    client.post('/chats/test-chat/messages',headers=headers(),json={'text':'Lunch'})
    with Session(engine) as session:
        batch_id,lease=svc.claim_batch(session)
    def revise_during_inference(ctx):
        client.post(f"/trips/{p['tripId']}/planner/revise",headers=headers())
        return {'updates':[{'field':'meal_type','value':'lunch','source_message_id':ctx.listener['batch'][0]['id']}]}
    monkeypatch.setattr('app.integrations.muse_group.listen_planner',revise_during_inference)
    svc.process_batch(engine,batch_id,lease)
    current=client.get(f"/trips/{p['tripId']}/planner",headers=headers()).json()
    assert current['template']['cluster']=={} and current['listening']=='idle'


def test_recovered_six_message_batch_does_not_drop_remaining_messages(client,world,monkeypatch):
    monkeypatch.setattr(get_settings(),'listener_debounce_seconds',0)
    monkeypatch.setattr(get_settings(),'muse_api_key','test-only')
    p=create(client,world)
    ids=[]
    for i in range(8):
        ids.append(client.post('/chats/test-chat/messages',headers=headers(),json={'text':f'message {i}'}).json()['id'])
    with Session(engine) as session:
        batch_id,lease=svc.claim_batch(session)
        batch=session.get(ListeningBatch,batch_id)
        batch.started_at=svc.now()-timedelta(seconds=100)
        session.add(batch);session.commit()
        recovered,recovered_lease=svc.claim_batch(session)
    svc.process_batch(engine,recovered,recovered_lease)
    with Session(engine) as session:
        second,second_lease=svc.claim_batch(session)
        assert len(session.get(ListeningBatch,second).message_ids)==2
        all_ids=[mid for row in session.exec(select(ListeningBatch)).all() for mid in row.message_ids]
        assert sorted(all_ids)==sorted(ids)


def test_prediction_is_optional_empty_only_and_explicit_wins(client,world,monkeypatch):
    monkeypatch.setattr(get_settings(),'listener_debounce_seconds',0)
    monkeypatch.setattr(get_settings(),'muse_api_key','test-only')
    p=create(client,world)
    p=edit(client,p,'meal_type','dinner')
    calls=[]
    def prediction(ctx):
        calls.append(ctx)
        return {'suggestions':{'meal_type':'lunch','cuisine':['Italian'],'budget':500}}
    monkeypatch.setattr('app.integrations.muse_group.predict_planner',prediction)
    for i in range(2):
        client.post('/chats/test-chat/messages',headers=headers(),json={'text':f'Hello {i}'})
        with Session(engine) as session:
            batch_id,lease=svc.claim_batch(session)
        svc.process_batch(engine,batch_id,lease)
    p=client.get(f"/trips/{p['tripId']}/planner",headers=headers()).json()
    assert p['template']['cluster']=={'meal_type':'dinner','cuisine':['Italian']}
    assert p['template']['sources']['cuisine:group']=='suggested'
    assert len(calls)<=2
    p=edit(client,p,'cuisine',['Thai'])
    assert p['template']['sources']['cuisine:group']=='manual'


def test_membership_changes_require_new_approval(client,world):
    from app.models import ChatMember
    p=ready(client,create(client,world))
    p=vote(client,p).json();p=vote(client,p,'bob').json()
    with Session(engine) as session:
        session.add(ChatMember(chat_id='test-chat',user_id='dan'));session.commit()
    p=client.get(f"/trips/{p['tripId']}/planner",headers=headers()).json()
    assert p['status']=='collecting' and p['poll']['approvals']==[] and 'dan' in p['poll']['eligible']
    assert p['attendance']['dan']['status']=='conditional'


def test_exact_place_is_human_confirmed_and_not_replaced(client,world,monkeypatch):
    p=ready(client,create(client,world))
    assert client.post(f"/trips/{p['tripId']}/planner/places",headers=headers(),json={'query':'Cafe','sessionToken':'abcdefghijklmnop'}).status_code==503
    monkeypatch.setattr('app.integrations.places.details',lambda *a,**k:{'id':'exact','name':'Exact Cafe','address':'Austin','url':None,'kind':'venue'})
    r=client.post(f"/trips/{p['tripId']}/planner/destination",headers=headers(),json={'revision':p['revision'],'placeId':'exact','sessionToken':'abcdefghijklmnop'})
    assert r.status_code==200,r.text
    p=r.json();p=vote(client,p).json();p=vote(client,p,'bob').json()
    p=client.get(f"/trips/{p['tripId']}/planner",headers=headers()).json()
    # The mocked provider returns another venue. It must not replace the approved target.
    assert p['recommendations']['venues']==[]
