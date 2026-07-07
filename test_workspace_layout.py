from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_workspace_layout_elements():
    response = client.get("/workspace")
    assert response.status_code == 200
    html = response.text
    
    # 3-column classes and structures
    assert "Column 1: Email Templates" in html
    assert "Column 2: Alert Center" in html
    assert "Column 3: Reminders & Notes" in html
    
    # Key interactive elements
    assert 'id="shiftToggle"' in html
    assert 'id="volumeSlider"' in html
    assert 'id="btnTestAlarm"' in html
    assert 'id="alertQueue"' in html
    
    # Modal & overlay elements
    assert 'id="settingsModal"' in html
    assert 'id="alarmOverlay"' in html
    assert 'id="btnSilence"' in html
    
    # Scripts
    assert "AudioContext" in html
    assert "OscillatorNode" in html or "createOscillator" in html
    assert "connectWebSocket" in html
