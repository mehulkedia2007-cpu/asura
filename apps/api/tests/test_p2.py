"""P2 acceptance tests through public API endpoints."""

from fastapi.testclient import TestClient

from daari.main import app

client = TestClient(app)


def test_catalog_and_shared_persona_engine():
    catalog = client.get('/engine/catalog').json()
    assert len(catalog['skills']) == 24
    assert len(catalog['roles']) == 2
    assert len(catalog['tools']) == 5
    assert all(t['parameters']['type'] == 'object' for t in catalog['tools'])
    payload = {'goal': 'data_analyst', 'held': {'ms_excel_basic': 2}}
    student = client.post('/engine/roadmap', json={**payload, 'persona': 'student'}).json()
    rural = client.post('/engine/roadmap', json={**payload, 'persona': 'rural'}).json()
    assert student == rural
    assert student['steps']


def test_before_after_vector_and_market_shock():
    learn = client.post('/engine/simulate-skill-update', json={
        'goal': 'data_analyst', 'held': {'ms_excel_basic': 2},
        'skill': 'sql_querying', 'level': 5,
    }).json()
    assert learn['after']['total_hours'] <= learn['before']['total_hours']
    assert 'sql_querying' in learn['diff']['removed']
    assert learn['profile_vector']['before_version'] != learn['profile_vector']['after_version']
    assert learn['profile_vector']['cosine_shift'] is not None

    shock = client.post('/engine/market-shock', json={
        'goal': 'data_analyst', 'skill': 'data_visualization_powerbi',
        'added_listings': 50,
    }).json()
    before = [s['skill'] for s in shock['before']['steps']]
    after = [s['skill'] for s in shock['after']['steps']]
    assert after.index('data_visualization_powerbi') <= before.index('data_visualization_powerbi')
    assert shock['demand_after']['data_visualization_powerbi'] > 1


def test_match_components_and_validation():
    result = client.post('/engine/match', json={
        'goal': 'data_analyst', 'held': {'sql_querying': 3},
    }).json()
    assert set(result['components']) == {
        'coverage', 'gap_cost', 'vector_sim', 'constraint_fit', 'demand_bonus'
    }
    assert result['components']['vector_sim'] > 0
    assert client.post('/engine/roadmap', json={'goal': 'unknown'}).status_code == 422
    assert client.post('/engine/roadmap', json={
        'goal': 'data_analyst', 'held': {'invented': 4},
    }).status_code == 422


def test_cat_terminates_and_uncertainty_shrinks():
    state = {}
    previous_se = float('inf')
    answer = None
    for _ in range(6):
        payload = {'skill': 'sql_querying', **state}
        item = client.post('/engine/assess/next', json=payload).json()['item']
        assert item is not None
        answer = client.post('/engine/assess/answer', json={
            **payload, 'item_id': item['id'], 'answer': 'SELECT',
        }).json()
        state = answer['state']
        assert state['se'] <= previous_se
        previous_se = state['se']
    assert answer is not None and answer['done'] is True
    assert client.post('/engine/assess/next', json={
        'skill': 'sql_querying', **state,
    }).json()['item'] is None


def test_assessment_prompts_follow_the_selected_locale():
    te = client.post('/engine/assess/next', json={
        'skill': 'sql_querying', 'locale': 'te',
    }).json()
    hi = client.post('/engine/assess/next', json={
        'skill': 'sql_querying', 'locale': 'hi',
    }).json()
    assert te['item']['display_language'] == 'te'
    assert '\u0c00' <= te['item']['text'][0] <= '\u0c7f'
    assert hi['item']['display_language'] == 'hi'
    assert '\u0900' <= hi['item']['text'][0] <= '\u097f'

    scored = client.post('/engine/assess/answer', json={
        'skill': 'sql_querying', 'locale': 'te', **te['state'],
        'item_id': te['item']['id'], 'answer': 'ORDER BY ... DESC',
    })
    assert scored.status_code == 200
    assert scored.json()['correct'] is True
