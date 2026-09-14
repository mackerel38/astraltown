# Astral Town Optimizer

Python 3.12+。仕様の基準は `SPEC.md`、`RULE_STATUS.md`、`TARGETS.md` です。
strict mode は未知の現行値を補完しません。動作優先の `playable-defaults` は明示選択する仮定プロファイルです。

## セットアップと実行

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
pytest
python -m astral_town
```

GUI はオプション依存で、コアの実行・テストには不要です。

```bash
python -m pip install -e '.[gui,test]'
python -m astral_town gui --scenario examples/artificial.json
```

Linux の画面がない環境で GUI を検証する場合は `QT_QPA_PLATFORM=offscreen` を指定します。
通常利用時はデスクトップ環境で起動してください。

## CLI

```bash
# ルールの値・信頼度を表示
python -m astral_town config

# 決定論的なイベント例
python -m astral_town trace
python examples/scripted_effects.py

# 人工状態の上位3候補。配置/売却/ロールを比較
python -m astral_town solve --scenario examples/artificial.json --horizon 1 --management-depth 1

# 建物8個・屋台4個の人工状態を比較
python -m astral_town solve --scenario examples/populated_comparison.json --horizon 1 --management-depth 1

# 2ロールの厳密な確率列挙（行動をロールに限定した人工状態）
python -m astral_town solve --scenario examples/populated_assumptions.json --horizon 2 --management-depth 0

# 1ターンのシード固定トレース
python -m astral_town simulate --scenario examples/populated_assumptions.json --seed 42

# 初期状態と全イベントの前後状態を、再生可能な JSON に保存
python -m astral_town simulate --scenario examples/populated_assumptions.json --seed 42 --trace-output /tmp/turn-trace.json

# 長期の方策評価。初手ごとに200試行
python -m astral_town rollout --scenario examples/populated_comparison.json --iterations 200 --seed 42
```

目的は `--objective` で切り替えます。

| 値 | 目的 |
|---|---|
| `EXPECTED_SCORE` | 最終スコア期待値 |
| `CLEAR_PROBABILITY` | クリア確率 |
| `EXPECTED_SCORE_WITH_CLEAR_CONSTRAINT` | `--clear-threshold 0.8` などの制約下で期待値を最大化 |
| `RISK_ADJUSTED_SCORE` | 期待値 − `--risk-lambda 10` × 失敗確率 |

Expectimax のクリア制約は、将来の分岐ごとにスコアとクリア確率のトレードオフを保持します。
制約付きの結果は初手を表示し、その後の方策は分岐に依存します。
通常の決定論的な管理手順は、ロールに至る行動列を表示します。
ロールアウトは初手を比較し、既定の継続方策は「ロール／屋台候補の先頭を選択」です。
ロールアウトを MCTS や全方策の厳密最適化として表示しません。

## シナリオとルール設定

`examples/*.json` はすべて**人工状態と明示的な仮定**です。
実ゲームの初期所持金、土地配置、ノルマ、確率を確定した資料ではありません。

シナリオには次の項目を保存します。

- `state`: 型タグ付き `GameState`。ID、建物・屋台の内部値、ショップ、強制出目も保存します。
- `board`: 周回順のマスと土地・隣接関係・対応タイル。未知の現行配置は同梱していません。
- `assumptions`: 利用者が明示的に選ぶ仮定。元のルール信頼度を変更しません。
- `accept_topology_assumption`: 人工・未確認の盤面を計算に使う明示フラグ。
- `allowed_actions`: 省略すると利用可能な管理行動を検討。指定時はその行動集合内の結果になります。
- `rules`: 任意の完全なルールレジストリ。省略時は `src/astral_town/data/rules.json`。
- `empirical_assumptions`: 観測から取り込んだ分布と出典・標本数・適用文脈。

GUI では状態・配置建物・倉庫・屋台を編集できます。
ショップ、盤面、全ルール、仮定は JSON 編集欄から変更できます。
盤面更新・保存時にもモデルの整合性を検証します。計算中は「停止」で中断できます。
建物欄の XP は現在のレベル内の残余 XP、`stage_index` は0開始です。
`management` 状態はそのターンの `TURN_START` 効果を処理済みとして入力します。

ルール値の例:

```json
{
  "value": null,
  "confidence": "unknown",
  "source": "RULE_STATUS.md §14"
}
```

分布は `probability` に `"1/3"` などの文字列を使い、合計が正確に1になる必要があります。
生成建物はタイプだけでなくレベル・XP・各ボーナス・カウンターを含む完全なテンプレートが必要です。
ショップ・カード・狐・三つ葉・豚・大袋は、それぞれ独立した設定を使います。
`random_target_distribution: "uniform"` は個別指定、または `playable-defaults` の明示選択時だけ使う仮定です。

`confirmed_legacy` は通常モードで参照できません。
独自 `rules` に旧版値を用意し、シナリオで `legacy: true` とした場合のみ利用でき、結果は旧版モデルとして表示します。
これは旧版の全ゲームを再現するプロファイルではありません。旧版の丸めと現行の効果を組み合わせる場合も、
その組み合わせを利用者が明示する必要があります。

## 結果の読み方

- `exact`: 参照したルールと探索範囲に未解決・仮定・打ち切りがない場合。
- `assumption-based`: 実際に参照した明示的仮定、または人工盤面がある場合。
- `bounded-search`: 管理行動数、許可行動集合、ヒューリスティックなどの探索制限がある場合。
- `simulation-estimated`: シード付きロールアウトの推定。95%スコア区間は正規近似、クリア確率区間は Wilson 法です。
- `budget-exhausted`: 探索ノード予算／ロールアウトの総ロール上限などに到達。ゲームルール不足ではありません。
- `unresolved`: 必要なルールが未確定。`missing_rule_ids` を確認してください。

結果にはスコア期待値、クリア確率、最終所持金、建物点・進行点、次点との差、
使用した仮定・観測分布の ID を含めます。
未解決の候補を捨て、残りだけを全体の最適解と呼ぶことはしません。
先読みが終端に届かず、Python API でカットオフ評価関数を渡していない場合は `cutoff_heuristic` を返します。
GUI の「確率列挙」を外すとロールアウトになります。ルールモードとは独立した選択です。

## Playable default assumptions

**`playable-defaults` はゲーム真値ではありません。** 未確認の確率を原則一様として計算を動かすための、明示的な default assumptions です。
元の `rules.json` の証拠・confidence は変更しません。ショップの価格・更新料金などには明示的な legacy/default assumptions を使います。
このプロファイルの項目を1つでも参照した結果は、確率を全列挙していても必ず **`assumption-based`** です。

```bash
# 同じ人工状態: strict は card_distribution 未確定で unresolved
python -m astral_town solve --scenario examples/playable_defaults.json --mode strict --horizon 1 --management-depth 0

# 明示選択すると計算可能。盤面・ノルマ・効果順序などはシナリオ内の個別仮定
python -m astral_town solve --scenario examples/playable_defaults.json --profile playable-defaults --horizon 1 --management-depth 0

python -m astral_town rollout --scenario examples/playable_defaults.json --profile playable-defaults --iterations 1000 --seed 42 --max-rolls 1
python -m astral_town gui --scenario examples/playable_defaults.json --profile playable-defaults
```

CLI の `--mode` と GUI のルールモードは次のとおりです。

| モード | 自動のデフォルト仮定 | 明示入力 |
|---|---|---|
| `strict` / Strict | なし。シナリオの profile 指定も無効化 | 従来互換で `assumptions` の個別仮定は使用可能。観測分布は無効 |
| `playable` / Playable defaults | `playable-defaults` を使用 | 個別仮定・観測分布で置換可能 |
| `custom` / Custom assumptions | なし | シナリオの個別仮定・明示的な観測分布。既存 CLI の互換動作 |
| `empirical` / Empirical | なし | 観測分布を使用。未観測の結果を一様で追加しない |

`--profile playable-defaults` は playable mode を選択します。`--mode strict` と同時指定すると入力エラーです。
シナリオに `profile: "playable-defaults"` / `rule_mode: "playable"` を保存することもできます。
Strict の個別仮定を使った結果も `exact` にはなりません。仮定を一切許容しない計算では `assumptions` と `legacy` を指定しないでください。
GUI の Playable defaults には「未確認・主に一様分布・assumption-based」の説明を表示し、Rule Status は元の confidence を表示します。

採用する仮定の全一覧（定義は `src/astral_town/data/assumptions_playable.json`）:

| 項目 | デフォルト仮定 |
|---|---|
| `random_target_distribution` | 既存条件を満たす対象 N 個から各 `1/N`。Rabbit Inn 自身除外などを維持 |
| `multi_target_sampling` | `without_replacement`。1効果内の対象を重複選択しない |
| `card_distribution` | 選択パックで eligible な全建物 type から一様 |
| `THREE_LEAF.distribution` | eligible な Luck 建物 type から一様。ハイブリッドは必要パックすべて必須 |
| `fox_generation_distribution` | Piggy Bank / Piglet Bank 各 `1/2` |
| `cannon_reward_distribution` | Treasure を確率1で生成 |
| `generated_building_state` | 上記報酬・ショップは fresh Lv1、XP 0、全永久ボーナス 0、全カウンター 0（Treasure decay も0）、未配置 |
| `big_bag_distribution` | 現在配置されている建物インスタンスから一様 |
| `big_bag_copy_state`, `big_bag_template` | `template`。同じ type の fresh Lv1、XP・全ボーナス・全カウンター0、未配置。既存の `full` 指定も使用可能 |
| `stand_offers` | パック条件を満たす屋台から3種類を重複なしで抽選。各 unordered subset が `1 / C(N,3)`、3未満なら全種類。3提示は legacy/default assumption |
| `shop_distribution` | 3枠を独立抽選。各枠は eligible な建物 type から一様、同じ type の重複可。旧rarity分布は使用しない |
| `purchase_prices` | Green 8 / Blue 16 / Purple 30 / Gold 50 の明示 legacy assumption |
| `refresh_prices` | `min(5 * (shop_refresh_count + 1), 50)`。有限配列でなく上限50の legacy assumption |
| `shop_refill` | `none`。購入した枠を補充しない |
| `palunan_sale_scope` | `total`。固有売却ボーナスを含む総額へ倍率適用 |

`palunan_sale_scope = base_only` では基礎売値に倍率を掛け、固有ボーナスを後から加えます。
Palunan の倍率・丸めは別途入力が必要で、最終建物点への作用 `score_palunan` も独立設定です。
屋台の所有重複可否、空／不足ターゲット時の処理、倉庫容量・満杯時処理も独立した未確定ルールです。
**このプロファイルは未確定の非確率ルールすべてを埋めるものではありません。** 実盤面・ノルマ・残りロール数・採点・処理順など必要な値は利用者が入力してください。

動的な `uniform_eligible_buildings` / `uniform_eligible_stands` 戦略は状態の `selected_packs` を参照します。
分布は保存済みの巨大な組合せ JSON ではなく実行時に生成し、全確率を `Fraction` で保持します。
ショップは順序付き3枠の積分布、屋台は組合せのみを列挙します。
既存の明示分布リスト、`{"strategy":"explicit","outcomes":[...]}`、文脈付き経験分布も使用できます。
個別仮定と観測分布がプロファイルより優先し、利用可能な現行のルール値にもプロファイルは上書きしません。

結果の `profile` は選択名、`assumptions_used` は実際に参照した仮定 ID、`assumption_values` はその値です。
`profile_assumptions_used` にはそのうちプロファイルから取得した項目のみを表示します。
使用判定には、評価した候補・列挙した確率分岐も含みます。選ばれた経路だけの一覧ではありません。

管理深さは購入・配置・売却・合成・移動・土地購入・更新等の通常操作だけを数え、`SELECT_STAND` は消費しません。
`--node-budget` に達した探索は `budget-exhausted`、完了済み初手候補がある場合は `bounded-search` として返します。
未完了の候補は返さず、`search_node_budget` を `missing_rule_ids` に入れません。
ロールアウトの `--max-rolls N` は**各初手・各試行の全体で最大 N ロール**です。初手のロールも1回、管理行動は0回と数えます。
未終端の軌跡は採点しません。非ロール行動が連続1000手を超える場合にも安全上限で停止します。

長期・全パックではショップ `N^3` や屋台組合せの列挙が大きくなります。ロールアウトも現在は完全な遷移分布を生成してからサンプリングするため、このコストが残ります。
探索ノード予算はイベント分岐の生成メモリ上限ではありません。
屋台の greedy continuation は今回見送り、既定方策「ロール／先頭屋台」の limitation を維持しています。MCTS ではありません。

## 観測データ

```bash
python -m astral_town calibrate --observations examples/observations.json --output /tmp/estimates.json
python -m astral_town import-estimate --scenario examples/artificial.json --estimate /tmp/estimates.json --report-index 0 --output /tmp/empirical-scenario.json
python -m astral_town solve --scenario /tmp/empirical-scenario.json --horizon 1
```

JSON は `observations` 配列、CSV は `rule_id,context,value` 列です。
CSV の `context` と `value` は JSON 文字列です。文脈には `stage_index`、`selected_packs`、`difficulty_id` を指定できます。
観測例は人工データです。集計は標本数、経験頻度、標準誤差、95%区間を出力します。
未観測の結果の確率は推定しません。経験分布の利用は明示した仮定となり、
`verified_current` を上書きしたり、別ステージのデータを無断適用したりしません。

## 実装状況

Phase 0 から順に、モデル、イベント、各パック、屋台、採点、確率 API、管理探索、Expectimax、
ロールアウト、未知ルール診断、PySide6 GUI、観測集計、計測に基づくキャッシュを追加しています。
検証した範囲と残る制限は `TARGETS.md` と `docs/VALIDATION.md` に記載しています。

**現行ゲーム全体の完成済みオプティマイザとはまだしていません。**
現行盤面、各ステージのノルマ、抽選、同時処理順序、採点などの未確定項目が残ります。
サンプルの成功は、それらをゲーム内で検証したことを意味しません。
将来の仮定として任意の文字列を指定しても、未対応の動作は実装済みの動作へ読み替えずエラーにします。
