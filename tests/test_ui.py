"""Optional UI check in a separate process: core imports stay Qt-free."""

import importlib.util
import os
import subprocess
import sys

import pytest


@pytest.mark.skipif(importlib.util.find_spec("PySide6") is None,reason="optional GUI extra not installed")
def test_offscreen_editor_calculation_and_stop():
    script='''
from PySide6.QtWidgets import QApplication
from astral_town.ui.app import MainWindow
from astral_town.scenario import from_scenario
app=QApplication([])
w=MainWindow('examples/artificial.json')
w.show();app.processEvents()
w.inputs['wallet'].setValue(123)
assert from_scenario(w.collect())[1].wallet==123
w.inputs['wallet'].setValue(20)
w.start_calculation()
while w.worker.isRunning():app.processEvents()
app.processEvents()
assert '期待スコア: 24' in w.results.toPlainText()
w.exact.setChecked(False);w.iterations.setValue(100000)
w.start_calculation();w.cancel()
while w.worker.isRunning():app.processEvents()
app.processEvents()
assert w.calculate.isEnabled()
w.close()
'''
    result=subprocess.run([sys.executable,"-c",script],env={**os.environ,"QT_QPA_PLATFORM":"offscreen"},capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr


@pytest.mark.skipif(importlib.util.find_spec("PySide6") is None,reason="optional GUI extra not installed")
def test_offscreen_playable_mode_warning_confidence_and_results():
    script='''
from PySide6.QtWidgets import QApplication
from astral_town.ui.app import MainWindow
from astral_town.scenario import from_scenario
app=QApplication([])
w=MainWindow('examples/playable_defaults.json')
w.show();app.processEvents()
w.horizon.setValue(1);w.depth.setValue(0)
w.rule_mode.setCurrentIndex(w.rule_mode.findData('strict'))
w.start_calculation()
while w.worker.isRunning():app.processEvents()
app.processEvents()
assert 'unresolved' in w.results.toPlainText()
assert 'card_distribution' in w.results.toPlainText()
w.rule_mode.setCurrentIndex(w.rule_mode.findData('playable'))
assert w.profile_warning.isVisible()
assert '一様分布' in w.profile_warning.text()
data=w.collect()
assert data['profile']=='playable-defaults'
assert from_scenario(data)[0].registry.values['card_distribution'].confidence.value=='unknown'
w.start_calculation()
while w.worker.isRunning():app.processEvents()
app.processEvents()
assert 'assumption-based' in w.results.toPlainText()
assert 'uniform_eligible_buildings' in w.results.toPlainText()
w.rule_mode.setCurrentIndex(w.rule_mode.findData('strict'))
assert 'profile' not in w.collect()
assert not w.profile_warning.isVisible()
w.close()
'''
    result=subprocess.run([sys.executable,"-c",script],env={**os.environ,"QT_QPA_PLATFORM":"offscreen"},capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
