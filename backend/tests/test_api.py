from fastapi.testclient import TestClient
from app.main import app
client=TestClient(app)

def test_health_and_overview():
    assert client.get('/api/health').status_code==200
    data=client.get('/api/overview').json(); assert data['total_trains']>=1 and data['data_mode']=='SYNTHETIC DEMO'

def test_trains_predictions_and_schedule():
    assert len(client.get('/api/trains').json())>=1
    p=client.get('/api/predictions').json(); assert p['predictions'] and p['model']
    assert client.post('/api/optimize').json()['status']=='FEASIBLE_HEURISTIC'

def test_routes_and_simulation():
    r=client.get('/api/routes?origin=NDLS&destination=CSMT'); assert r.status_code==200 and r.json()
    s=client.post('/api/simulate',json={'scenario':'heavy_traffic','seed':7,'intensity':20}); assert s.status_code==200
    assert s.json()['scenario']=='heavy_traffic'

def test_rejects_invalid_train_route():
    payload={'id':'99999','name':'Bad route','category':'Express','origin':'NDLS','destination':'CSMT','route':['NDLS','CSMT'],'priority':3,'scheduled_departure':'2026-11-09T10:00:00','delay_min':0,'speed_kmph':80}
    assert client.post('/api/trains',json=payload).status_code==400

def test_constraint_scheduler_respects_shared_single_track_headway():
    from app.optimization.scheduler import optimize
    sample=[
      {'id':'A1','name':'A','route':['KOTA','ADI'],'scheduled_departure':'2026-11-09T10:00:00','delay_min':0,'priority':3,'speed_kmph':80},
      {'id':'A2','name':'B','route':['KOTA','ADI'],'scheduled_departure':'2026-11-09T10:00:00','delay_min':0,'priority':2,'speed_kmph':80},
    ]
    result=optimize(sample,headway=10)
    first,second=result['trains']
    from datetime import datetime
    d1=datetime.fromisoformat(first['optimized_departure']); d2=datetime.fromisoformat(second['optimized_departure'])
    assert (d2-d1).total_seconds() >= 600
    assert result['status']=='FEASIBLE_HEURISTIC'


def test_congestion_and_recommendation_endpoints():
    c=client.get('/api/congestion'); assert c.status_code==200 and c.json()['sections']
    assert all('utilization_pct' in x and x['data_mode']=='SYNTHETIC DEMO' for x in c.json()['sections'])
    r=client.get('/api/recommendations'); assert r.status_code==200 and r.json()['recommendations']


def test_simulation_is_reproducible_and_reports_occupancy():
    payload={'scenario':'heavy_traffic','seed':17,'intensity':25}
    a=client.post('/api/simulate',json=payload).json()
    b=client.post('/api/simulate',json=payload).json()
    assert [x['delay_min'] for x in a['trains']]==[x['delay_min'] for x in b['trains']]
    assert a['section_occupancy'] and a['events']


def test_optimizer_rejects_invalid_headway():
    r=client.post('/api/optimize',json={'headway_min':0})
    assert r.status_code==422

def test_scenario_runs_are_saved_and_listed():
    run = client.post('/api/simulate', json={'scenario':'normal','seed':91,'intensity':0})
    assert run.status_code == 200
    assert isinstance(run.json().get('run_id'), int)
    history = client.get('/api/scenarios?limit=5')
    assert history.status_code == 200
    assert history.json()['runs']
    assert history.json()['runs'][0]['seed'] == 91


def test_sqlite_repository_persists_train_and_scenario_across_instances(tmp_path):
    from app.core.database import RailFlowRepository
    path = tmp_path / 'railflow-test.sqlite3'
    first = RailFlowRepository(path, seed_trains=False)
    train = {
        'id':'T900','name':'Persistence test','route':['NDLS','JP'],
        'origin':'NDLS','destination':'JP','priority':2,
        'scheduled_departure':'2026-11-10T10:00:00','delay_min':4,
        'speed_kmph':80,'status':'On time'
    }
    first.save_train(train)
    first.save_scenario({'scenario':'normal','seed':5,'trains':[]})

    reopened = RailFlowRepository(path, seed_trains=False)
    assert reopened.get_train('T900')['name'] == 'Persistence test'
    assert reopened.list_scenarios()[0]['seed'] == 5
    assert reopened.delete_train('T900') is True
    assert reopened.get_train('T900') is None

def test_train_crud_writes_through_to_sqlite():
    from app.main import repository
    payload = {
        'id':'T999','name':'SQLite CRUD Demo','category':'Express',
        'origin':'NDLS','destination':'JP','route':['NDLS','JP'],
        'priority':3,'scheduled_departure':'2026-11-10T11:00:00',
        'delay_min':0,'speed_kmph':85
    }
    created = client.post('/api/trains', json=payload)
    assert created.status_code == 200
    assert repository.get_train('T999')['name'] == 'SQLite CRUD Demo'
    updated = client.patch('/api/trains/T999', json={'delay_min':22})
    assert updated.status_code == 200
    assert repository.get_train('T999')['delay_min'] == 22
    deleted = client.delete('/api/trains/T999')
    assert deleted.status_code == 200
    assert repository.get_train('T999') is None


def test_conflict_detector_flags_single_track_headway_and_overlap():
    from app.optimization.conflicts import detect_conflicts
    sample = [
        {'id':'C1','route':['KOTA','ADI'],'scheduled_departure':'2026-11-10T10:00:00','delay_min':0,'speed_kmph':80},
        {'id':'C2','route':['KOTA','ADI'],'scheduled_departure':'2026-11-10T10:03:00','delay_min':0,'speed_kmph':80},
    ]
    result = detect_conflicts(sample, headway_min=8)
    assert result['conflict_count'] == 1
    assert result['conflicts'][0]['conflict_type'] == 'SECTION_OVERLAP'
    assert result['conflicts'][0]['severity'] == 'Critical'


def test_conflicts_endpoint_and_headway_validation():
    result = client.get('/api/conflicts?headway_min=8')
    assert result.status_code == 200
    assert 'conflict_count' in result.json()
    assert result.json()['data_mode'] == 'SYNTHETIC DEMO'
    assert client.get('/api/conflicts?headway_min=0').status_code == 400


def test_conflict_detector_flags_single_track_overlap_and_headway():
    from app.optimization.conflicts import detect_conflicts
    trains = [
        {'id':'C1','name':'Conflict One','route':['KOTA','ADI'],
         'scheduled_departure':'2026-11-10T10:00:00','delay_min':0,'speed_kmph':80},
        {'id':'C2','name':'Conflict Two','route':['KOTA','ADI'],
         'scheduled_departure':'2026-11-10T10:01:00','delay_min':0,'speed_kmph':80},
    ]
    result = detect_conflicts(trains, headway_min=8)
    assert result['conflict_count'] == 1
    conflict = result['conflicts'][0]
    assert conflict['conflict_type'] == 'SECTION_OVERLAP'
    assert conflict['severity'] == 'Critical'
    assert conflict['overlap_min'] > 0
    assert conflict['train_ids'] == ['C1', 'C2']


def test_conflict_detector_respects_parallel_track_capacity():
    from app.optimization.conflicts import detect_conflicts
    trains = [
        {'id':f'D{i}','route':['NDLS','AGC'],
         'scheduled_departure':'2026-11-10T10:00:00','delay_min':0,'speed_kmph':80}
        for i in range(2)
    ]
    result = detect_conflicts(trains, headway_min=8)
    assert result['conflict_count'] == 0


def test_conflicts_api_and_headway_validation():
    assert client.get('/api/conflicts').status_code == 200
    response = client.get('/api/conflicts?headway_min=0')
    assert response.status_code == 400


def test_conflict_detector_flags_multi_track_capacity_overrun():
    from app.optimization.conflicts import detect_conflicts
    trains = [
        {'id':f'CAP{i}','route':['NDLS','AGC'],
         'scheduled_departure':'2026-11-10T10:00:00','delay_min':0,'speed_kmph':80}
        for i in range(3)
    ]
    result = detect_conflicts(trains, headway_min=8)
    assert result['conflict_count'] == 1
    assert result['conflicts'][0]['conflict_type'] == 'TRACK_CAPACITY_EXCEEDED'
    assert result['conflicts'][0]['severity'] == 'Critical'
    assert len(result['conflicts'][0]['train_ids']) == 3


def test_dashboard_api_contracts_for_frontend_views():
    """Keep the API response shapes consumed by the React dashboard stable."""
    overview = client.get('/api/overview').json()
    assert {'total_trains', 'delayed_trains', 'average_delay_min', 'stations', 'track_sections'} <= overview.keys()

    predictions = client.get('/api/predictions').json()
    assert {'model', 'metrics', 'predictions'} <= predictions.keys()
    assert predictions['predictions']
    assert {'train_id', 'train_name', 'predicted_delay_min', 'risk'} <= predictions['predictions'][0].keys()

    network = client.get('/api/network').json()
    assert {'stations', 'sections'} <= network.keys()
    assert network['stations'] and network['sections']
    assert {'from', 'to', 'tracks'} <= network['sections'][0].keys()

    congestion = client.get('/api/congestion').json()
    assert congestion['sections']
    assert {'from', 'to', 'utilization_pct', 'congestion'} <= congestion['sections'][0].keys()

    conflicts = client.get('/api/conflicts').json()
    assert {'conflict_count', 'critical_count', 'conflicts', 'safety_note'} <= conflicts.keys()

    scenarios = client.get('/api/scenarios?limit=5').json()
    assert 'runs' in scenarios

    routes = client.get('/api/routes?origin=NDLS&destination=CSMT')
    assert routes.status_code == 200 and routes.json()
    assert {'stations', 'travel_minutes', 'score'} <= routes.json()[0].keys()

    assert 'recommendations' in client.get('/api/recommendations').json()
    assert 'answer' in client.get('/api/assistant?q=Which%20trains%20are%20delayed').json()


def test_verified_delay_feedback_and_retrain_threshold(monkeypatch):
    import app.main as main

    class MemoryRepository:
        def __init__(self):
            self.feedback = []

        def save_delay_feedback(self, features, actual_delay_min, source):
            self.feedback.append({"features": features, "actual_delay_min": actual_delay_min})

        def count_delay_feedback(self):
            return len(self.feedback)

        def list_delay_feedback(self):
            return self.feedback

    memory = MemoryRepository()
    monkeypatch.setattr(main, "repository", memory)
    learned = []
    monkeypatch.setattr(main.MODEL, "learn_from_feedback", lambda rows: learned.append(rows))

    train = client.get('/api/trains').json()[0]
    response = client.post('/api/learning/feedback', json={
        'train_id': train['id'], 'actual_delay_min': 12
    })
    assert response.status_code == 200
    assert response.json()['verified_outcomes'] == 1
    assert memory.feedback[0]['actual_delay_min'] == 12
    assert client.post('/api/learning/retrain').status_code == 400

    memory.feedback.extend([
        {"features": [0.0] * 12, "actual_delay_min": 10.0} for _ in range(9)
    ])
    retrained = client.post('/api/learning/retrain')
    assert retrained.status_code == 200
    assert retrained.json()['verified_outcomes'] == 10
    assert len(learned) == 1 and len(learned[0]) == 10
