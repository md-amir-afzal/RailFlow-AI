from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
from app.core.data import STATIONS, EDGES
from app.core.database import RailFlowRepository
from app.schemas.train import TrainCreate, ScenarioRequest, OptimizeRequest, DelayFeedback
from app.railway_network.graph import GRAPH, route_options
from app.prediction.model import MODEL
from app.optimization.scheduler import optimize
from app.optimization.conflicts import detect_conflicts
from app.simulation.engine import run_scenario
from fastapi import Body

app=FastAPI(title='RailFlow AI API',version='1.0.0',description='Simulation and decision-support platform. Synthetic demo data; not connected to live railway operations.')
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5173','http://127.0.0.1:5173'],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
repository = RailFlowRepository()
trains = repository.list_trains(); last_scenario = None
@app.get('/api/health')
def health(): return {'status':'ok','service':'RailFlow AI','timestamp':datetime.now(timezone.utc).isoformat(),'data_mode':'SYNTHETIC_DEMO','storage':'SQLite'}
@app.get('/api/overview')
def overview():
    delayed=sum(t['delay_min']>5 for t in trains); total=sum(t['delay_min'] for t in trains)
    return {'total_trains':len(trains),'active_trains':len(trains),'delayed_trains':delayed,'on_time_trains':len(trains)-delayed,'average_delay_min':round(total/max(len(trains),1),1),'stations':len(STATIONS),'track_sections':len(EDGES),'track_utilization_pct':round(min(96,22+len(trains)*7.3),1),'data_mode':'SYNTHETIC DEMO','updated_at':datetime.now(timezone.utc).isoformat()}
@app.get('/api/trains')
def get_trains(): return trains
@app.post('/api/trains')
def add_train(t:TrainCreate):
    if any(x['id']==t.id for x in trains): raise HTTPException(409,'Train ID already exists')
    if t.origin not in GRAPH or t.destination not in GRAPH: raise HTTPException(400,'Unknown origin or destination station')
    if t.route[0]!=t.origin or t.route[-1]!=t.destination: raise HTTPException(400,'Route endpoints must match origin and destination')
    if any(a not in GRAPH or b not in GRAPH or not GRAPH.has_edge(a,b) for a,b in zip(t.route,t.route[1:])): raise HTTPException(400,'Route contains a non-existent track section')
    row=t.model_dump(); row['status']='Delayed' if row['delay_min']>5 else 'On time'; repository.save_train(row); trains.append(row); return row
@app.patch('/api/trains/{train_id}')
def update_train(train_id:str, payload:dict):
    t=next((x for x in trains if x['id']==train_id),None)
    if not t: raise HTTPException(404,'Train not found')
    for k in ('priority','delay_min','speed_kmph','scheduled_departure'):
        if k in payload: t[k]=payload[k]
    t['status']='Delayed' if t['delay_min']>5 else 'On time'; repository.save_train(t); return t
@app.delete('/api/trains/{train_id}')
def delete_train(train_id:str):
    global trains
    if not repository.delete_train(train_id): raise HTTPException(404,'Train not found')
    trains = repository.list_trains()
    return {'deleted':train_id}
@app.get('/api/stations')
def stations(): return STATIONS
@app.get('/api/network')
def network(): return {'stations':STATIONS,'sections':[{'from':a,'to':b,'distance_km':km,'tracks':tracks,'capacity_trains_per_hour':tracks*4,'congestion':'Moderate' if tracks==1 else 'Low'} for a,b,km,tracks in EDGES],'data_mode':'Illustrative corridor sample'}
@app.get('/api/routes')
def routes(origin:str,destination:str):
    try: return route_options(origin,destination)
    except (ValueError, Exception) as e: raise HTTPException(400,str(e))
@app.get('/api/predictions')
def predictions():
    out=[]
    for t in trains:
        pred=MODEL.predict(t,0.25+min(t['delay_min']/100,0.5))
        out.append({'train_id':t['id'],'train_name':t['name'],'current_delay_min':t['delay_min'],'predicted_delay_min':pred,'risk':'Critical' if pred>=35 else 'High' if pred>=22 else 'Moderate' if pred>=10 else 'Low','confidence':'Model estimate; not calibrated probability','top_factors':['Current delay','Synthetic congestion index','Train category']})
    return {'model':MODEL.best_name,'metrics':MODEL.metrics[MODEL.best_name],'all_model_metrics':MODEL.metrics,'dataset':MODEL.dataset_label,'predictions':out}

@app.get('/api/learning')
def learning_status():
    return {'verified_outcomes':repository.count_delay_feedback(),'dataset':MODEL.dataset_label,'model':MODEL.best_name,'auto_retrain_every':20,'note':'Only operator-verified arrival outcomes are used for learning.'}

@app.post('/api/learning/feedback')
def record_delay_feedback(feedback: DelayFeedback):
    train=next((item for item in trains if item['id']==feedback.train_id),None)
    if not train: raise HTTPException(404,'Train not found')
    features=MODEL.build_features(train,0.25+min(train['delay_min']/100,0.5))[0].tolist()
    repository.save_delay_feedback(features,feedback.actual_delay_min,feedback.source)
    count=repository.count_delay_feedback()
    if count >= 20 and count % 20 == 0:
        MODEL.learn_from_feedback(repository.list_delay_feedback())
    return {'saved':True,'verified_outcomes':count,'auto_retrained':count >= 20 and count % 20 == 0}

@app.post('/api/learning/retrain')
def retrain_delay_model():
    feedback=repository.list_delay_feedback()
    if len(feedback)<10: raise HTTPException(400,'Add at least 10 verified arrival outcomes before retraining.')
    MODEL.learn_from_feedback(feedback)
    return {'model':MODEL.best_name,'dataset':MODEL.dataset_label,'verified_outcomes':len(feedback),'metrics':MODEL.metrics[MODEL.best_name]}
@app.post('/api/optimize')
def schedule(req: OptimizeRequest = Body(default=OptimizeRequest())):
    try: return optimize(trains, req.headway_min, req.horizon_hours)
    except ValueError as e: raise HTTPException(400, str(e))

@app.get('/api/congestion')
def congestion_forecast():
    section_rows=[]
    for a,b,km,tracks in EDGES:
        users=[t for t in trains if any({x,y}=={a,b} for x,y in zip(t['route'],t['route'][1:]))]
        density=len(users); capacity=max(1,tracks*4)
        utilization=min(100, round(density/capacity*100,1))
        level='Critical' if utilization>=90 else 'High' if utilization>=65 else 'Moderate' if utilization>=35 else 'Low'
        section_rows.append({'from':a,'to':b,'distance_km':km,'tracks':tracks,'capacity_trains_per_hour':capacity,'scheduled_train_count':density,'utilization_pct':utilization,'forecast_horizon_min':60,'congestion':level,'data_mode':'SYNTHETIC DEMO'})
    return {'forecast_horizon_min':60,'sections':section_rows,'method':'Route-overlap density proxy; not a live occupancy forecast','data_mode':'SYNTHETIC DEMO'}

@app.get('/api/recommendations')
def recommendations():
    items=[]
    for t in trains:
        if t['delay_min']>=15:
            items.append({'type':'DELAY_REVIEW','severity':'High' if t['delay_min']>=30 else 'Moderate','affected_trains':[t['id']],'problem':f"{t['name']} has {t['delay_min']} minutes of simulated delay",'recommendation':'Review sequencing and downstream section availability before proposing a revised dispatch time.','reason':'Current synthetic delay exceeds the 15-minute review threshold.','expected_impact':'Potential reduction in avoidable waiting; quantify with the scheduler before adoption.','feasibility':'Requires section-level validation and authorized railway review.'})
    if not items: items.append({'type':'MONITOR','severity':'Info','affected_trains':[],'problem':'No train currently exceeds the demo delay review threshold.','recommendation':'Continue monitoring the simulated corridor and rerun forecasts after disruptions.','reason':'All current delays are below 15 minutes.','expected_impact':'No quantified impact claimed.','feasibility':'Monitoring only.'})
    return {'recommendations':items,'data_mode':'SYNTHETIC DEMO'}
@app.post('/api/simulate')
def simulate(req:ScenarioRequest):
    global last_scenario
    last_scenario=run_scenario(trains,req.scenario,req.seed,req.intensity)
    last_scenario['run_id'] = repository.save_scenario(last_scenario)
    return last_scenario
@app.get('/api/assistant')
def assistant(q:str):
    ql=q.lower()
    if 'delay' in ql: answer=f"{sum(t['delay_min']>5 for t in trains)} of {len(trains)} simulated trains are delayed by more than 5 minutes. Total accumulated delay is {sum(t['delay_min'] for t in trains)} minutes."
    elif 'congest' in ql: answer='The demo network flags single-track corridors as higher sensitivity. Current congestion is illustrative and derived from the sample corridor model, not live occupancy.'
    elif 'optimiz' in ql: answer='Run Smart Scheduling to calculate a priority-aware headway plan. The result is a heuristic proposal and must be validated by railway operations experts.'
    else: answer=f"RailFlow AI currently contains {len(trains)} simulated trains and {len(STATIONS)} sample stations. Ask about delays, congestion, or schedule optimization."
    return {'answer':answer,'source':'Current SQLite-backed demo application state','data_mode':'SYNTHETIC DEMO'}

@app.get('/api/scenarios')
def scenario_history(limit: int = 20):
    return {'runs': repository.list_scenarios(limit), 'data_mode': 'SYNTHETIC DEMO'}


@app.get('/api/conflicts')
def train_conflicts(headway_min: int = 8):
    if not 1 <= headway_min <= 60:
        raise HTTPException(400, 'headway_min must be between 1 and 60 minutes')
    try:
        return detect_conflicts(trains, headway_min)
    except (ValueError, KeyError) as e:
        raise HTTPException(400, str(e))
