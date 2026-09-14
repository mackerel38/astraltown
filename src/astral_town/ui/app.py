"""PySide6 state editor. All transitions/search stay in the core layers."""

import json
import math
import sys
from dataclasses import fields,replace
from fractions import Fraction
from pathlib import Path
from threading import Event as StopEvent

from PySide6.QtCore import Qt,QThread,Signal
from PySide6.QtGui import QColor,QBrush,QPen,QFont,QFontMetricsF
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QTabWidget,
    QLineEdit,QSpinBox,QDoubleSpinBox,QCheckBox,QComboBox,QPushButton,QLabel,QPlainTextEdit,QTableWidget,QTableWidgetItem,
    QHeaderView,QGraphicsView,QGraphicsScene,QFileDialog,QSplitter,QScrollArea)

from astral_town.data.loader import load_file
from astral_town.model.building import BuildingInstance,ShopOffer
from astral_town.model.stand import StandInstance
from astral_town.model.enums import BuildingType,StandType,Pack
from astral_town.model.serialization import encode
from astral_town.scenario import from_scenario,to_plain
from astral_town.solver.expectimax import Expectimax
from astral_town.solver.rollout import rollout,PRESETS


class Worker(QThread):
    result_ready=Signal(object)
    failed=Signal(str)

    def __init__(self,data,settings):
        super().__init__()
        self.data,self.settings=data,settings
        self.stopped=StopEvent()

    def run(self):
        try:
            game,state=from_scenario(self.data)
            options=dict(objective=self.settings["objective"],clear_threshold=Fraction(str(self.settings["threshold"])),
                         risk_lambda=Fraction(str(self.settings["risk"])),allowed_actions=self.data.get("allowed_actions"),cancel=self.stopped.is_set)
            if self.settings["exact"]:
                result=Expectimax(game,horizon=self.settings["horizon"],management_depth=self.settings["depth"],node_budget=self.settings["nodes"],**options).solve(state)
            else:result=rollout(game,state,iterations=self.settings["iterations"],seed=self.settings["seed"],**options)
            self.result_ready.emit(to_plain(result))
        except Exception as exc:self.failed.emit(f"{type(exc).__name__}: {exc}")


class ObjectTable(QWidget):
    """Editable scalar instance fields; internal counters use JSON arrays."""

    def __init__(self,cls,enum_fields):
        super().__init__()
        self.cls,self.enum_fields=cls,enum_fields
        self.names=[f.name for f in fields(cls)]
        layout=QVBoxLayout(self)
        self.table=QTableWidget(0,len(self.names))
        self.table.setHorizontalHeaderLabels(self.names)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)
        buttons=QHBoxLayout()
        add=QPushButton("行を追加")
        remove=QPushButton("選択行を削除")
        add.clicked.connect(lambda:self.table.insertRow(self.table.rowCount()))
        remove.clicked.connect(lambda:self.table.removeRow(self.table.currentRow()) if self.table.currentRow()>=0 else None)
        buttons.addWidget(add);buttons.addWidget(remove);buttons.addStretch()
        layout.addLayout(buttons)

    def set_objects(self,objects):
        self.table.setRowCount(len(objects))
        for i,obj in enumerate(objects):
            for j,name in enumerate(self.names):
                value=getattr(obj,name)
                text=str(value.value) if name in self.enum_fields else json.dumps(value,ensure_ascii=False)
                self.table.setItem(i,j,QTableWidgetItem(text))

    def objects(self):
        result=[]
        for i in range(self.table.rowCount()):
            data={}
            for j,name in enumerate(self.names):
                item=self.table.item(i,j)
                if item is None or not item.text().strip():raise ValueError(f"行{i+1}の{name}を入力してください")
                text=item.text().strip()
                if name in self.enum_fields:data[name]=self.enum_fields[name](text)
                else:data[name]=json.loads(text)
                if name=="custom_counters":data[name]=tuple(tuple(p) for p in data[name])
            result.append(self.cls(**data))
        return tuple(result)


class MainWindow(QMainWindow):
    def __init__(self,path,*,profile=None,mode=None):
        super().__init__()
        self.worker=None
        self.setWindowTitle("Astral Town Optimizer — ルールと仮定を明示して比較")
        self.resize(1250,900)
        self.data=load_file(path)
        if profile:self.data.update(profile=profile,rule_mode="playable")
        if mode:self.data["rule_mode"]=mode
        root=QWidget();self.setCentralWidget(root)
        layout=QVBoxLayout(root)
        top=QHBoxLayout()
        title=QLabel("Astral Town  /  状態と行動の比較")
        title.setStyleSheet("font-size:22px;font-weight:600")
        top.addWidget(title);top.addStretch()
        for label,callback in (("開く",self.open_file),("保存",self.save_file),("盤面を更新",self.refresh_board)):
            button=QPushButton(label);button.clicked.connect(callback);top.addWidget(button)
        layout.addLayout(top)
        self.description=QLabel();self.description.setWordWrap(True);layout.addWidget(self.description)
        split=QSplitter(Qt.Orientation.Horizontal);layout.addWidget(split,1)
        tabs=self.tabs=QTabWidget();split.addWidget(tabs)
        self.general=QWidget();form=QFormLayout(self.general)
        self.inputs={}
        for name,label in (("difficulty_id","難易度"),("stage_index","ステージ index（0開始）"),("turns_remaining","残りターン"),
                           ("wallet","所持金"),("stage_progress","ステージ進捗"),("player_position","現在位置"),("progress_score","獲得済み進行点"),
                           ("next_dice_count","次のサイコロ数"),("shop_refresh_count","更新回数"),("roll_id","ロール ID")):
            widget=QLineEdit() if name=="difficulty_id" else QSpinBox()
            if isinstance(widget,QSpinBox):widget.setRange(0,1000000000)
            self.inputs[name]=widget;form.addRow(label,widget)
        for name,label in (("unlocked_lots","解放土地 ID（JSON）"),("forced_die_effects","強制出目（JSON）"),("stand_offers","屋台候補（JSON）"),
                           ("last_roll","直前の出目（JSON）"),("movement_remaining","残り移動量（JSON）"),("forced_stop","強制停止中（true/false）"),("rule_version","ルール版（JSON文字列）")):
            widget=QLineEdit();self.inputs[name]=widget;form.addRow(label,widget)
        self.packs={pack:QCheckBox(pack.value) for pack in Pack}
        packrow=QWidget();packlayout=QHBoxLayout(packrow)
        for checkbox in self.packs.values():packlayout.addWidget(checkbox)
        form.addRow("選択パック",packrow)
        self.phase=QComboBox();self.phase.addItems(["management","roll","stand_selection","terminal"])
        self.status=QComboBox();self.status.addItems(["playing","cleared","failed"])
        form.addRow("フェーズ",self.phase);form.addRow("状態",self.status)
        general_scroll=QScrollArea();general_scroll.setWidgetResizable(True);general_scroll.setWidget(self.general)
        tabs.addTab(general_scroll,"ゲーム状態")
        self.scene=QGraphicsScene();self.board_view=QGraphicsView(self.scene);tabs.addTab(self.board_view,"盤面")
        self.placed=ObjectTable(BuildingInstance,{"building_type":BuildingType});tabs.addTab(self.placed,"配置建物")
        self.inventory=ObjectTable(BuildingInstance,{"building_type":BuildingType});tabs.addTab(self.inventory,"倉庫")
        self.stands=ObjectTable(StandInstance,{"stand_type":StandType});tabs.addTab(self.stands,"屋台")
        self.shop=QPlainTextEdit();tabs.addTab(self.shop,"ショップ（JSON）")
        self.configuration=QPlainTextEdit();tabs.addTab(self.configuration,"盤面・ルール・仮定（JSON）")
        self.rules=QTableWidget(0,4);self.rules.setHorizontalHeaderLabels(["ルール ID","信頼度","値","出典"])
        self.rules.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers);tabs.addTab(self.rules,"ルール信頼度")
        side=QWidget();side_layout=QVBoxLayout(side);split.addWidget(side);split.setSizes([820,430])
        controls=QFormLayout();side_layout.addLayout(controls)
        self.objective=QComboBox();self.objective.addItems(["EXPECTED_SCORE","CLEAR_PROBABILITY","EXPECTED_SCORE_WITH_CLEAR_CONSTRAINT","RISK_ADJUSTED_SCORE"])
        controls.addRow("目的",self.objective)
        self.threshold=QDoubleSpinBox();self.threshold.setRange(0,1);self.threshold.setSingleStep(.05);controls.addRow("最低クリア確率",self.threshold)
        self.risk=QDoubleSpinBox();self.risk.setRange(0,1000000);self.risk.setValue(1);controls.addRow("失敗ペナルティ λ",self.risk)
        self.rule_mode=QComboBox()
        for label,value in (("Strict（既定仮定なし）","strict"),("Playable defaults","playable"),("Custom assumptions","custom"),("Empirical / 観測分布","empirical")):
            self.rule_mode.addItem(label,value)
        controls.addRow("ルールモード",self.rule_mode)
        self.profile_warning=QLabel("⚠ 未確認ルールを仮定して計算します。\n確率分布は主に一様分布を使用します。\nゲーム真値ではなく、結果は assumption-based です。")
        self.profile_warning.setWordWrap(True);controls.addRow(self.profile_warning)
        self.rule_mode.currentIndexChanged.connect(lambda:self.profile_warning.setVisible(self.rule_mode.currentData()=="playable"))
        self.exact=QCheckBox("確率列挙（外すとロールアウト）");self.exact.setChecked(True);controls.addRow(self.exact)
        self.horizon=QSpinBox();self.horizon.setRange(1,100);self.horizon.setValue(2);controls.addRow("先読みロール数",self.horizon)
        self.depth=QSpinBox();self.depth.setRange(0,20);self.depth.setValue(1);controls.addRow("管理行動の深さ",self.depth)
        self.nodes=QSpinBox();self.nodes.setRange(1,10000000);self.nodes.setValue(100000);controls.addRow("探索ノード上限",self.nodes)
        self.preset=QComboBox();self.preset.addItems(PRESETS);controls.addRow("試行数プリセット",self.preset)
        self.iterations=QSpinBox();self.iterations.setRange(1,1000000);self.iterations.setValue(PRESETS["NORMAL"]);controls.addRow("試行数 / 初手",self.iterations)
        self.preset.currentTextChanged.connect(lambda key:self.iterations.setValue(PRESETS[key]));self.preset.setCurrentText("NORMAL")
        self.seed=QSpinBox();self.seed.setRange(0,2147483647);controls.addRow("乱数シード",self.seed)
        buttons=QHBoxLayout();self.calculate=QPushButton("計算");self.stop=QPushButton("停止");self.stop.setEnabled(False)
        buttons.addWidget(self.calculate);buttons.addWidget(self.stop);side_layout.addLayout(buttons)
        self.calculate.clicked.connect(self.start_calculation);self.stop.clicked.connect(self.cancel)
        self.results=QPlainTextEdit();self.results.setReadOnly(True);side_layout.addWidget(self.results,1)
        self.status_label=QLabel("未計算");self.status_label.setWordWrap(True);side_layout.addWidget(self.status_label)
        self.populate()

    def populate(self):
        game,state=from_scenario(self.data)
        self.rule_mode.setCurrentIndex(self.rule_mode.findData(self.data.get("rule_mode", "playable" if self.data.get("profile") else "custom")))
        self.profile_warning.setVisible(self.rule_mode.currentData()=="playable")
        self.description.setText(self.data.get("description","手動入力状態。未確定ルールは設定画面で明示します。"))
        for name,widget in self.inputs.items():
            value=getattr(state,name)
            if isinstance(widget,QSpinBox):widget.setValue(value)
            elif name=="difficulty_id":widget.setText(value)
            elif name=="unlocked_lots":widget.setText(json.dumps(sorted(value)))
            else:widget.setText(json.dumps(to_plain(value)))
        for pack,widget in self.packs.items():widget.setChecked(pack in state.selected_packs)
        self.phase.setCurrentText(state.phase);self.status.setCurrentText(state.status)
        self.placed.set_objects(state.buildings);self.inventory.set_objects(state.inventory);self.stands.set_objects(state.stands)
        self.shop.setPlainText(json.dumps(to_plain(state.shop_offers),indent=2))
        self.configuration.setPlainText(json.dumps({k:v for k,v in self.data.items() if k!="state"},ensure_ascii=False,indent=2))
        self.rules.setRowCount(len(game.registry.values))
        for row,(key,value) in enumerate(game.registry.values.items()):
            for col,text in enumerate((key,value.confidence.value,str(value.value),value.source)):
                self.rules.setItem(row,col,QTableWidgetItem(text))
        self.rules.resizeColumnsToContents()
        self.draw_board(game,state)

    def collect(self):
        from astral_town.model.state import ForcedDieEffect
        game,state=from_scenario(self.data)
        changes={name:widget.value() if isinstance(widget,QSpinBox) else widget.text() for name,widget in self.inputs.items()}
        changes["unlocked_lots"]=frozenset(json.loads(changes["unlocked_lots"]))
        changes["forced_die_effects"]=tuple(ForcedDieEffect(**row) for row in json.loads(changes["forced_die_effects"]))
        changes["stand_offers"]=tuple(StandType(value) for value in json.loads(changes["stand_offers"]))
        changes["last_roll"]=tuple(json.loads(changes["last_roll"]))
        for key in ("movement_remaining","forced_stop","rule_version"):changes[key]=json.loads(changes[key])
        changes.update(buildings=self.placed.objects(),inventory=self.inventory.objects(),stands=self.stands.objects(),
                       selected_packs=frozenset(pack for pack,widget in self.packs.items() if widget.isChecked()),
                       phase=self.phase.currentText(),status=self.status.currentText())
        shop=[]
        for row in json.loads(self.shop.toPlainText()):
            b=dict(row["building"]);b["building_type"]=BuildingType(b["building_type"]);b["custom_counters"]=tuple(tuple(p) for p in b.get("custom_counters",()))
            shop.append(ShopOffer(row["offer_id"],BuildingInstance(**b),row["price"]))
        changes["shop_offers"]=tuple(shop)
        state=replace(state,**changes)
        data=json.loads(self.configuration.toPlainText());data["state"]=encode(state)
        data["rule_mode"]=self.rule_mode.currentData()
        if data["rule_mode"]=="playable":data["profile"]="playable-defaults"
        else:data.pop("profile",None)
        from_scenario(data) # Validate before submission.
        return data

    def draw_board(self,game,state):
        self.scene.clear()
        for i,space in enumerate(game.board.spaces):
            angle=2*math.pi*i/len(game.board.spaces)-math.pi/2
            x,y=260*math.cos(angle),260*math.sin(angle)
            color={"START":"#93c5fd","COIN":"#fde68a","CARD":"#86efac"}.get(space.type.value,"#e2e8f0")
            self.scene.addRect(x-43,y-30,86,60,QPen(QColor("#475569")),QBrush(QColor(color)))
            b=next((b for b in state.buildings if b.location==space.lot_id),None)
            label=f"{space.id} {space.type.value}"
            font=QFont();font.setPointSize(9)
            if b:
                short=QFontMetricsF(font).elidedText(f"#{b.instance_id} {b.building_type.value}",Qt.TextElideMode.ElideRight,76)
                label+=f"\n{short}\nLv{b.level} XP{b.xp}"
            elif space.lot_id is not None:label+=f"\nlot {space.lot_id}"
            item=self.scene.addText(label,font);item.setPos(x-40,y-28)
            if b:item.setToolTip(f"{b.building_type.value} #{b.instance_id}\nLv{b.level} XP{b.xp}\ndice +{b.dice_coin_bonus} / pass +{b.pass_coin_bonus} / stay +{b.stay_coin_bonus}")
            if space.id==state.player_position:
                self.scene.addEllipse(x-9,y-47,18,18,QPen(QColor("#be123c")),QBrush(QColor("#e11d48")))
        self.scene.setSceneRect(-330,-330,660,660)
        self.board_view.fitInView(self.scene.sceneRect(),Qt.AspectRatioMode.KeepAspectRatio)

    def refresh_board(self):
        try:
            self.data=self.collect();game,state=from_scenario(self.data);self.draw_board(game,state);self.status_label.setText("入力を反映しました")
        except Exception as exc:self.status_label.setText(str(exc))

    def open_file(self):
        path,_=QFileDialog.getOpenFileName(self,"シナリオを開く","","JSON / YAML (*.json *.yaml *.yml)")
        if path:
            try:self.data=load_file(path);self.populate()
            except Exception as exc:self.status_label.setText(str(exc))

    def save_file(self):
        try:data=self.collect()
        except Exception as exc:self.status_label.setText(str(exc));return
        path,_=QFileDialog.getSaveFileName(self,"シナリオを保存","scenario.json","JSON (*.json)")
        if path:Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    def start_calculation(self):
        try:data=self.collect()
        except Exception as exc:self.status_label.setText(str(exc));return
        settings=dict(objective=self.objective.currentText(),threshold=self.threshold.value(),risk=self.risk.value(),exact=self.exact.isChecked(),
                      horizon=self.horizon.value(),depth=self.depth.value(),nodes=self.nodes.value(),iterations=self.iterations.value(),seed=self.seed.value())
        self.worker=Worker(data,settings)
        self.worker.result_ready.connect(self.show_result);self.worker.failed.connect(self.status_label.setText)
        self.worker.finished.connect(self.finished)
        self.calculate.setEnabled(False);self.stop.setEnabled(True);self.status_label.setText("計算中…")
        self.worker.start()

    def show_result(self,result):
        lines=[result.get("exactness",""),f"profile: {result.get('profile') or 'none'}",""]
        if result.get("assumptions_used"):lines.extend(["参照した仮定:",*result["assumptions_used"],""])
        if result.get("assumption_values"):lines.append(json.dumps(result["assumption_values"],ensure_ascii=False,indent=2))
        if result.get("profile_assumptions_used"):lines.extend(["playable-defaults から参照:",*result["profile_assumptions_used"],""])
        labels={"PLACE":"配置","MOVE_BUILDING":"移動","SELL":"売却","BUY":"購入","MERGE":"合成","UNPLACE":"倉庫へ戻す",
                "UNLOCK_LAND":"土地解放","REFRESH_SHOP":"ショップ更新","SELECT_STAND":"屋台選択","END_MANAGEMENT_AND_ROLL":"ロール"}
        for i,recommendation in enumerate(result.get("recommendations",[]),1):
            actions=recommendation.get("actions",[recommendation.get("action")])
            names=[]
            for action in actions:
                label=labels.get(action["kind"],action["kind"])
                if action.get("source_id") is not None:label+=f" #{action['source_id']}"
                if action.get("target") is not None:label+=f" → {action['target']}"
                names.append(label)
            metrics=recommendation["metrics"]
            lines.extend([f"候補 {i}  {' → '.join(names)}",f"期待スコア: {metrics['expected_score']}",
                          f"クリア確率: {float(Fraction(metrics['clear_probability'])):.1%}",
                          f"最終所持金: {metrics['expected_wallet']}",
                          f"建物点: {metrics['expected_building_score']} / 進行点: {metrics['expected_progress_score']}"])
            if recommendation.get("score_interval_95") is not None:lines.append(f"95%区間: {recommendation['score_interval_95']}（{recommendation['samples']}試行）")
            lines.append("")
        if result.get("next_best_gap") is not None:lines.append(f"次点との差: {result['next_best_gap']}")
        lines.extend(result.get("limitations",[]))
        if result.get("missing_rule_ids"):lines.extend(["必要な未確定ルール:",*result["missing_rule_ids"]])
        self.results.setPlainText("\n".join(lines))
        missing=result.get("missing_rule_ids",[])
        self.status_label.setText("未確定ルール: "+", ".join(missing) if missing else result.get("exactness",""))

    def finished(self):
        self.calculate.setEnabled(True);self.stop.setEnabled(False)

    def cancel(self):
        if self.worker:self.worker.stopped.set();self.status_label.setText("停止要求を送信しました")

    def closeEvent(self,event):
        if self.worker and self.worker.isRunning():
            self.cancel();event.ignore();self.worker.finished.connect(self.close)
        else:event.accept()


def run(path,*,profile=None,mode=None):
    app=QApplication.instance() or QApplication(sys.argv)
    window=MainWindow(path,profile=profile,mode=mode);window.show()
    app.exec()
